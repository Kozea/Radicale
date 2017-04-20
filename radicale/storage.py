# This file is part of Radicale Server - Calendar Server
# Copyright © 2014 Jean-Marc Martins
# Copyright © 2012-2017 Guillaume Ayoub
#
# This library is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Radicale.  If not, see <http://www.gnu.org/licenses/>.

"""
Storage backends.

This module loads the storage backend, according to the storage configuration.

Default storage uses one folder per collection and one file per collection
entry.

"""

import binascii
import contextlib
import datetime
import errno
import json
import os
import pickle
import posixpath
import shlex
import stat
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from hashlib import md5
from importlib import import_module
from itertools import chain, groupby
from random import getrandbits
from tempfile import NamedTemporaryFile, TemporaryDirectory

import vobject

if os.name == "nt":
    import ctypes
    import ctypes.wintypes
    import msvcrt

    LOCKFILE_EXCLUSIVE_LOCK = 2
    if ctypes.sizeof(ctypes.c_void_p) == 4:
        ULONG_PTR = ctypes.c_uint32
    else:
        ULONG_PTR = ctypes.c_uint64

    class Overlapped(ctypes.Structure):
        _fields_ = [
            ("internal", ULONG_PTR),
            ("internal_high", ULONG_PTR),
            ("offset", ctypes.wintypes.DWORD),
            ("offset_high", ctypes.wintypes.DWORD),
            ("h_event", ctypes.wintypes.HANDLE)]

    lock_file_ex = ctypes.windll.kernel32.LockFileEx
    lock_file_ex.argtypes = [
        ctypes.wintypes.HANDLE,
        ctypes.wintypes.DWORD,
        ctypes.wintypes.DWORD,
        ctypes.wintypes.DWORD,
        ctypes.wintypes.DWORD,
        ctypes.POINTER(Overlapped)]
    lock_file_ex.restype = ctypes.wintypes.BOOL
    unlock_file_ex = ctypes.windll.kernel32.UnlockFileEx
    unlock_file_ex.argtypes = [
        ctypes.wintypes.HANDLE,
        ctypes.wintypes.DWORD,
        ctypes.wintypes.DWORD,
        ctypes.wintypes.DWORD,
        ctypes.POINTER(Overlapped)]
    unlock_file_ex.restype = ctypes.wintypes.BOOL
elif os.name == "posix":
    import fcntl


def load(configuration, logger):
    """Load the storage manager chosen in configuration."""
    storage_type = configuration.get("storage", "type")
    if storage_type == "multifilesystem":
        collection_class = Collection
    else:
        try:
            collection_class = import_module(storage_type).Collection
        except ImportError as e:
            raise RuntimeError("Storage module %r not found" %
                               storage_type) from e
    logger.info("Storage type is %r", storage_type)

    class CollectionCopy(collection_class):
        """Collection copy, avoids overriding the original class attributes."""
    CollectionCopy.configuration = configuration
    CollectionCopy.logger = logger
    return CollectionCopy


def scandir(path, only_dirs=False, only_files=False):
    """Iterator for directory elements. (For compatibility with Python < 3.5)

    ``only_dirs`` only return directories

    ``only_files`` only return files

    """
    if sys.version_info >= (3, 5):
        for entry in os.scandir(path):
            if ((not only_files or entry.is_file()) and
                    (not only_dirs or entry.is_dir())):
                yield entry.name
    else:
        for name in os.listdir(path):
            p = os.path.join(path, name)
            if ((not only_files or os.path.isfile(p)) and
                    (not only_dirs or os.path.isdir(p))):
                yield name


def get_etag(text):
    """Etag from collection or item.

    Encoded as quoted-string (see RFC 2616).

    """
    etag = md5()
    etag.update(text.encode("utf-8"))
    return '"%s"' % etag.hexdigest()


def get_uid(item):
    """UID value of an item if defined."""
    return hasattr(item, "uid") and item.uid.value


def sanitize_path(path):
    """Make path absolute with leading slash to prevent access to other data.

    Preserve a potential trailing slash.

    """
    trailing_slash = "/" if path.endswith("/") else ""
    path = posixpath.normpath(path)
    new_path = "/"
    for part in path.split("/"):
        if not is_safe_path_component(part):
            continue
        new_path = posixpath.join(new_path, part)
    trailing_slash = "" if new_path.endswith("/") else trailing_slash
    return new_path + trailing_slash


def is_safe_path_component(path):
    """Check if path is a single component of a path.

    Check that the path is safe to join too.

    """
    return path and "/" not in path and path not in (".", "..")


def is_safe_filesystem_path_component(path):
    """Check if path is a single component of a local and posix filesystem
       path.

    Check that the path is safe to join too.

    """
    return (
        path and not os.path.splitdrive(path)[0] and
        not os.path.split(path)[0] and path not in (os.curdir, os.pardir) and
        not path.startswith(".") and not path.endswith("~") and
        is_safe_path_component(path))


def path_to_filesystem(root, *paths):
    """Convert path to a local filesystem path relative to base_folder.

    `root` must be a secure filesystem path, it will be prepend to the path.

    Conversion of `paths` is done in a secure manner, or raises ``ValueError``.

    """
    paths = [sanitize_path(path).strip("/") for path in paths]
    safe_path = root
    for path in paths:
        if not path:
            continue
        for part in path.split("/"):
            if not is_safe_filesystem_path_component(part):
                raise UnsafePathError(part)
            safe_path_parent = safe_path
            safe_path = os.path.join(safe_path, part)
            # Check for conflicting files (e.g. case-insensitive file systems
            # or short names on Windows file systems)
            if (os.path.lexists(safe_path) and
                    part not in scandir(safe_path_parent)):
                raise CollidingPathError(part)
    return safe_path


class UnsafePathError(ValueError):
    def __init__(self, path):
        message = "Can't translate name safely to filesystem: %r" % path
        super().__init__(message)


class CollidingPathError(ValueError):
    def __init__(self, path):
        message = "File name collision: %r" % path
        super().__init__(message)


class ComponentExistsError(ValueError):
    def __init__(self, path):
        message = "Component already exists: %r" % path
        super().__init__(message)


class ComponentNotFoundError(ValueError):
    def __init__(self, path):
        message = "Component doesn't exist: %r" % path
        super().__init__(message)


class Item:
    def __init__(self, collection, item, href, last_modified=None):
        self.collection = collection
        self.item = item
        self.href = href
        self.last_modified = last_modified

    def __getattr__(self, attr):
        return getattr(self.item, attr)

    @property
    def etag(self):
        """Encoded as quoted-string (see RFC 2616)."""
        return get_etag(self.serialize())


class BaseCollection:

    # Overriden on copy by the "load" function
    configuration = None
    logger = None

    def __init__(self, path, principal=False):
        """Initialize the collection.

        ``path`` must be the normalized relative path of the collection, using
        the slash as the folder delimiter, with no leading nor trailing slash.

        """
        raise NotImplementedError

    @classmethod
    def discover(cls, path, depth="0"):
        """Discover a list of collections under the given ``path``.

        If ``depth`` is "0", only the actual object under ``path`` is
        returned.

        If ``depth`` is anything but "0", it is considered as "1" and direct
        children are included in the result.

        The ``path`` is relative.

        The root collection "/" must always exist.

        """
        raise NotImplementedError

    @classmethod
    def move(cls, item, to_collection, to_href):
        """Move an object.

        ``item`` is the item to move.

        ``to_collection`` is the target collection.

        ``to_href`` is the target name in ``to_collection``. An item with the
        same name might already exist.

        """
        if item.collection.path == to_collection.path and item.href == to_href:
            return
        to_collection.upload(to_href, item.item)
        item.collection.delete(item.href)

    @property
    def etag(self):
        """Encoded as quoted-string (see RFC 2616)."""
        return get_etag(self.serialize())

    @classmethod
    def create_collection(cls, href, collection=None, props=None):
        """Create a collection.

        If the collection already exists and neither ``collection`` nor
        ``props`` are set, this method shouldn't do anything. Otherwise the
        existing collection must be replaced.

        ``collection`` is a list of vobject components.

        ``props`` are metadata values for the collection.

        ``props["tag"]`` is the type of collection (VCALENDAR or
        VADDRESSBOOK). If the key ``tag`` is missing, it is guessed from the
        collection.

        """
        raise NotImplementedError

    def sync(self, old_token=None):
        """Get the current sync token and changed items for synchronization.

        ``old_token`` an old sync token which is used as the base of the
        delta update. If sync token is missing, all items are returned.
        ValueError is raised for invalid or old tokens.

        WARNING: This simple default implementation treats all sync-token as
                 invalid. It adheres to the specification but some clients
                 (e.g. InfCloud) don't like it. Subclasses should provide a
                 more sophisticated implementation.

        """
        token = "http://radicale.org/ns/sync/%s" % self.etag.strip("\"")
        if old_token:
            raise ValueError("Sync token are not supported")
        return token, self.list()

    def list(self):
        """List collection items."""
        raise NotImplementedError

    def get(self, href):
        """Fetch a single item."""
        raise NotImplementedError

    def get_multi(self, hrefs):
        """Fetch multiple items.

        Functionally similar to ``get``, but might bring performance benefits
        on some storages when used cleverly. It's not required to return the
        requested items in the correct order. Duplicated hrefs can be ignored.

        Returns tuples with the href and the item or None if the item doesn't
        exist.

        """
        return map(lambda href: (href, self.get(href)), hrefs)

    def get_all(self):
        """Fetch all items.

        Functionally similar to ``get``, but might bring performance benefits
        on some storages when used cleverly.

        """
        return map(self.get, self.list())

    def pre_filtered_list(self, filters):
        """List collection items with optional pre filtering.

        This could largely improve performance of reports depending on
        the filters and this implementation.
        This returns all event by default
        """
        return self.get_all()

    def has(self, href):
        """Check if an item exists by its href.

        Functionally similar to ``get``, but might bring performance benefits
        on some storages when used cleverly.

        """
        return self.get(href) is not None

    def upload(self, href, vobject_item):
        """Upload a new or replace an existing item."""
        raise NotImplementedError

    def delete(self, href=None):
        """Delete an item.

        When ``href`` is ``None``, delete the collection.

        """
        raise NotImplementedError

    def get_meta(self, key):
        """Get metadata value for collection."""
        raise NotImplementedError

    def set_meta(self, props):
        """Set metadata values for collection."""
        raise NotImplementedError

    @property
    def last_modified(self):
        """Get the HTTP-datetime of when the collection was modified."""
        raise NotImplementedError

    def serialize(self):
        """Get the unicode string representing the whole collection."""
        raise NotImplementedError

    @classmethod
    @contextmanager
    def acquire_lock(cls, mode, user=None):
        """Set a context manager to lock the whole storage.

        ``mode`` must either be "r" for shared access or "w" for exclusive
        access.

        ``user`` is the name of the logged in user or empty.

        """
        raise NotImplementedError


class Collection(BaseCollection):
    """Collection stored in several files per calendar."""

    def __init__(self, path, principal=False, folder=None):
        if not folder:
            folder = self._get_collection_root_folder()
        # Path should already be sanitized
        self.path = sanitize_path(path).strip("/")
        self.encoding = self.configuration.get("encoding", "stock")
        self._filesystem_path = path_to_filesystem(folder, self.path)
        self._props_path = os.path.join(
            self._filesystem_path, ".Radicale.props")
        split_path = self.path.split("/")
        self.owner = split_path[0] if len(split_path) > 1 else None
        self.is_principal = principal
        self._meta = None
        self._etag = None

    @classmethod
    def _get_collection_root_folder(cls):
        filesystem_folder = os.path.expanduser(
            cls.configuration.get("storage", "filesystem_folder"))
        return os.path.join(filesystem_folder, "collection-root")

    @contextmanager
    def _atomic_write(self, path, mode="w", newline=None):
        directory = os.path.dirname(path)
        tmp = NamedTemporaryFile(
            mode=mode, dir=directory, delete=False, prefix=".Radicale.tmp-",
            newline=newline, encoding=None if "b" in mode else self.encoding)
        try:
            yield tmp
            self._fsync(tmp.fileno())
            tmp.close()
            os.replace(tmp.name, path)
        except:
            tmp.close()
            os.remove(tmp.name)
            raise
        self._sync_directory(directory)

    @staticmethod
    def _find_available_file_name(exists_fn):
        # Prevent infinite loop
        for _ in range(10000):
            file_name = hex(getrandbits(32))[2:]
            if not exists_fn(file_name):
                return file_name
        raise FileExistsError(errno.EEXIST, "No usable file name found")

    @classmethod
    def _fsync(cls, fd):
        if cls.configuration.getboolean("storage", "filesystem_fsync"):
            if os.name == "posix" and hasattr(fcntl, "F_FULLFSYNC"):
                fcntl.fcntl(fd, fcntl.F_FULLFSYNC)
            else:
                os.fsync(fd)

    @classmethod
    def _sync_directory(cls, path):
        """Sync directory to disk.

        This only works on POSIX and does nothing on other systems.

        """
        if not cls.configuration.getboolean("storage", "filesystem_fsync"):
            return
        if os.name == "posix":
            fd = os.open(path, 0)
            try:
                cls._fsync(fd)
            finally:
                os.close(fd)

    @classmethod
    def _makedirs_synced(cls, filesystem_path):
        """Recursively create a directory and its parents in a sync'ed way.

        This method acts silently when the folder already exists.

        """
        if os.path.isdir(filesystem_path):
            return
        parent_filesystem_path = os.path.dirname(filesystem_path)
        # Prevent infinite loop
        if filesystem_path != parent_filesystem_path:
            # Create parent dirs recursively
            cls._makedirs_synced(parent_filesystem_path)
        # Possible race!
        os.makedirs(filesystem_path, exist_ok=True)
        cls._sync_directory(parent_filesystem_path)

    @classmethod
    def discover(cls, path, depth="0"):
        # Path should already be sanitized
        sane_path = sanitize_path(path).strip("/")
        attributes = sane_path.split("/")
        if not attributes[0]:
            attributes.pop()

        folder = cls._get_collection_root_folder()
        # Create the root collection
        cls._makedirs_synced(folder)
        try:
            filesystem_path = path_to_filesystem(folder, sane_path)
        except ValueError as e:
            # Path is unsafe
            cls.logger.debug("Collection with unsafe path %r requested: %s",
                             sane_path, e, exc_info=True)
            return

        # Check if the path exists and if it leads to a collection or an item
        if not os.path.isdir(filesystem_path):
            if attributes and os.path.isfile(filesystem_path):
                href = attributes.pop()
            else:
                return
        else:
            href = None

        path = "/".join(attributes)
        principal = len(attributes) == 1
        collection = cls(path, principal)

        if href:
            yield collection.get(href)
            return

        yield collection

        if depth == "0":
            return

        for item in collection.list():
            yield collection.get(item)

        for href in scandir(filesystem_path, only_dirs=True):
            if not is_safe_filesystem_path_component(href):
                if not href.startswith(".Radicale"):
                    cls.logger.debug("Skipping collection %r in %r", href,
                                     path)
                continue
            child_filesystem_path = path_to_filesystem(filesystem_path, href)
            if os.path.isdir(child_filesystem_path):
                child_path = posixpath.join(path, href)
                child_principal = len(attributes) == 0
                yield cls(child_path, child_principal)

    @classmethod
    def create_collection(cls, href, collection=None, props=None):
        folder = cls._get_collection_root_folder()

        # Path should already be sanitized
        sane_path = sanitize_path(href).strip("/")
        attributes = sane_path.split("/")
        if not attributes[0]:
            attributes.pop()
        principal = len(attributes) == 1
        filesystem_path = path_to_filesystem(folder, sane_path)

        if not props:
            props = {}
        if not props.get("tag") and collection:
            props["tag"] = collection[0].name
        if not props:
            cls._makedirs_synced(filesystem_path)
            return cls(sane_path, principal=principal)

        parent_dir = os.path.dirname(filesystem_path)
        cls._makedirs_synced(parent_dir)

        # Create a temporary directory with an unsafe name
        with TemporaryDirectory(
                prefix=".Radicale.tmp-", dir=parent_dir) as tmp_dir:
            # The temporary directory itself can't be renamed
            tmp_filesystem_path = os.path.join(tmp_dir, "collection")
            os.makedirs(tmp_filesystem_path)
            self = cls("/", principal=principal, folder=tmp_filesystem_path)
            self.set_meta(props)

            if collection:
                if props.get("tag") == "VCALENDAR":
                    collection, = collection
                    items = []
                    for content in ("vevent", "vtodo", "vjournal"):
                        items.extend(
                            getattr(collection, "%s_list" % content, []))
                    items_by_uid = groupby(sorted(items, key=get_uid), get_uid)
                    vobject_items = {}
                    for uid, items in items_by_uid:
                        new_collection = vobject.iCalendar()
                        for item in items:
                            new_collection.add(item)
                        href = self._find_available_file_name(
                            vobject_items.get)
                        vobject_items[href] = new_collection
                    self.upload_all_nonatomic(vobject_items)
                elif props.get("tag") == "VCARD":
                    vobject_items = {}
                    for card in collection:
                        href = self._find_available_file_name(
                            vobject_items.get)
                        vobject_items[href] = card
                    self.upload_all_nonatomic(vobject_items)

            # This operation is not atomic on the filesystem level but it's
            # very unlikely that one rename operations succeeds while the
            # other fails or that only one gets written to disk.
            if os.path.exists(filesystem_path):
                os.rename(filesystem_path, os.path.join(tmp_dir, "delete"))
            os.rename(tmp_filesystem_path, filesystem_path)
            cls._sync_directory(parent_dir)

        return cls(sane_path, principal=principal)

    def upload_all_nonatomic(self, vobject_items):
        """Upload a new set of items.

        This takes a mapping of href and vobject items and
        uploads them nonatomic and without existence checks.

        """
        with contextlib.ExitStack() as stack:
            fs = []
            for href, item in vobject_items.items():
                if not is_safe_filesystem_path_component(href):
                    raise UnsafePathError(href)
                path = path_to_filesystem(self._filesystem_path, href)
                fs.append(stack.enter_context(
                    open(path, "w", encoding=self.encoding, newline="")))
                fs[-1].write(item.serialize())
            # sync everything at once because it's slightly faster.
            for f in fs:
                self._fsync(f.fileno())
        self._sync_directory(self._filesystem_path)

    @classmethod
    def move(cls, item, to_collection, to_href):
        if not is_safe_filesystem_path_component(to_href):
            raise UnsafePathError(to_href)
        os.replace(
            path_to_filesystem(item.collection._filesystem_path, item.href),
            path_to_filesystem(to_collection._filesystem_path, to_href))
        cls._sync_directory(to_collection._filesystem_path)
        if item.collection._filesystem_path != to_collection._filesystem_path:
            cls._sync_directory(item.collection._filesystem_path)
        # Track the change
        to_collection._update_history_etag(to_href, item)
        item.collection._update_history_etag(item.href, None)
        to_collection._clean_history_cache()
        if item.collection._filesystem_path != to_collection._filesystem_path:
            item.collection._clean_history_cache()

    @classmethod
    def _clean_cache(cls, folder, names, max_age=None):
        """Delete all ``names`` in ``folder`` that are older than ``max_age``.
        """
        age_limit = time.time() - max_age if max_age is not None else None
        modified = False
        for name in names:
            if not is_safe_filesystem_path_component(name):
                continue
            if age_limit is not None:
                try:
                    # Race: Another process might have deleted the file.
                    mtime = os.path.getmtime(os.path.join(folder, name))
                except FileNotFoundError:
                    continue
                if mtime > age_limit:
                    continue
            cls.logger.debug("Found expired item in cache: %r", name)
            # Race: Another process might have deleted or locked the
            # file.
            try:
                os.remove(os.path.join(folder, name))
            except (FileNotFoundError, PermissionError):
                continue
            modified = True
        if modified:
            cls._sync_directory(folder)

    def _update_history_etag(self, href, item):
        """Updates and retrieves the history etag from the history cache.

        The history cache contains a file for each current and deleted item
        of the collection. These files contain the etag of the item (empty
        string for deleted items) and a history etag, which is a hash over
        the previous history etag and the etag separated by "/".
        """
        history_folder = os.path.join(self._filesystem_path,
                                      ".Radicale.cache", "history")
        try:
            with open(os.path.join(history_folder, href), "rb") as f:
                cache_etag, history_etag = pickle.load(f)
        except (FileNotFoundError, pickle.UnpicklingError, ValueError) as e:
            if isinstance(e, (pickle.UnpicklingError, ValueError)):
                self.logger.warning(
                    "Failed to load history cache entry %r in %r: %s",
                    href, self.path, e, exc_info=True)
                # Delete the damaged file
                try:
                    os.remove(os.path.join(history_folder, href))
                except (FileNotFoundError, PermissionError):
                    pass
            cache_etag = ""
            # Initialize with random data to prevent collisions with cleaned
            # expired items.
            history_etag = binascii.hexlify(os.urandom(16)).decode("ascii")
        etag = item.etag if item else ""
        if etag != cache_etag:
            self._makedirs_synced(history_folder)
            history_etag = get_etag(history_etag + "/" + etag).strip("\"")
            try:
                # Race: Other processes might have created and locked the file.
                with self._atomic_write(os.path.join(history_folder, href),
                                        "wb") as f:
                    pickle.dump([etag, history_etag], f)
            except PermissionError:
                pass
        return history_etag

    def _get_deleted_history_hrefs(self):
        """Returns the hrefs of all deleted items that are still in the
        history cache."""
        history_folder = os.path.join(self._filesystem_path,
                                      ".Radicale.cache", "history")
        try:
            for href in os.listdir(history_folder):
                if not is_safe_filesystem_path_component(href):
                    continue
                if os.path.isfile(os.path.join(self._filesystem_path, href)):
                    continue
                yield href
        except FileNotFoundError:
            pass

    def _clean_history_cache(self):
        # Delete all expired cache entries of deleted items.
        history_folder = os.path.join(self._filesystem_path,
                                      ".Radicale.cache", "history")
        self._clean_cache(history_folder, self._get_deleted_history_hrefs(),
                          max_age=self.configuration.getint(
                              "storage", "max_sync_token_age"))

    def sync(self, old_token=None):
        # The sync token has the form http://radicale.org/ns/sync/TOKEN_NAME
        # where TOKEN_NAME is the md5 hash of all history etags of present and
        # past items of the collection.
        def check_token_name(token_name):
            if len(token_name) != 32:
                return False
            for c in token_name:
                if c not in "0123456789abcdef":
                    return False
            return True

        old_token_name = None
        if old_token:
            # Extract the token name from the sync token
            if not old_token.startswith("http://radicale.org/ns/sync/"):
                raise ValueError("Malformed token: %s" % old_token)
            old_token_name = old_token[len("http://radicale.org/ns/sync/"):]
            if not check_token_name(old_token_name):
                raise ValueError("Malformed token: %s" % old_token)
        # Get the current state and sync-token of the collection.
        state = {}
        token_name_hash = md5()
        # Find the history of all existing and deleted items
        for href, item in chain(
                ((item.href, item) for item in self.pre_filtered_list(())),
                ((href, None) for href in self._get_deleted_history_hrefs())):
            history_etag = self._update_history_etag(href, item)
            state[href] = history_etag
            token_name_hash.update((href + "/" + history_etag).encode("utf-8"))
        token_name = token_name_hash.hexdigest()
        token = "http://radicale.org/ns/sync/%s" % token_name
        if token_name == old_token_name:
            # Nothing changed
            return token, ()
        token_folder = os.path.join(self._filesystem_path,
                                    ".Radicale.cache", "sync-token")
        token_path = os.path.join(token_folder, token_name)
        old_state = {}
        if old_token_name:
            # load the old token state
            old_token_path = os.path.join(token_folder, old_token_name)
            try:
                # Race: Another process might have deleted the file.
                with open(old_token_path, "rb") as f:
                    old_state = pickle.load(f)
            except (FileNotFoundError, pickle.UnpicklingError,
                    ValueError) as e:
                if isinstance(e, (pickle.UnpicklingError, ValueError)):
                    self.logger.warning(
                        "Failed to load stored sync token %r in %r: %s",
                        old_token_name, self.path, e, exc_info=True)
                    # Delete the damaged file
                    try:
                        os.remove(old_token_path)
                    except (FileNotFoundError, PermissionError):
                        pass
                raise ValueError("Token not found: %s" % old_token)
        # write the new token state or update the modification time of
        # existing token state
        if not os.path.exists(token_path):
            self._makedirs_synced(token_folder)
            try:
                # Race: Other processes might have created and locked the file.
                with self._atomic_write(token_path, "wb") as f:
                    pickle.dump(state, f)
            except PermissionError:
                pass
            else:
                # clean up old sync tokens and item cache
                self._clean_cache(token_folder, os.listdir(token_folder),
                                  max_age=self.configuration.getint(
                                      "storage", "max_sync_token_age"))
                self._clean_history_cache()
        else:
            # Try to update the modification time
            try:
                # Race: Another process might have deleted the file.
                os.utime(token_path)
            except FileNotFoundError:
                pass
        changes = []
        # Find all new, changed and deleted (that are still in the item cache)
        # items
        for href, history_etag in state.items():
            if history_etag != old_state.get(href):
                changes.append(href)
        # Find all deleted items that are no longer in the item cache
        for href, history_etag in old_state.items():
            if href not in state:
                changes.append(href)
        return token, changes

    @classmethod
    def _clean_cache(cls, folder, names, max_age=None):
        # Delete all ``names`` in ``folder`` that are older than ``max_age``.
        age_limit = time.time() - max_age if max_age is not None else None
        modified = False
        for name in names:
            if not is_safe_filesystem_path_component(name):
                continue
            if age_limit is not None:
                try:
                    # Race: Another process might have deleted the file.
                    mtime = os.path.getmtime(os.path.join(folder, name))
                except FileNotFoundError:
                    continue
                if mtime > age_limit:
                    continue
            cls.logger.debug("Found expired item in cache: %s", name)
            # Race: Another process might have deleted or locked the
            # file.
            try:
                os.remove(os.path.join(folder, name))
            except (FileNotFoundError, PermissionError):
                continue
            modified = True
        if modified:
            cls._sync_directory(folder)

    def list(self):
        for href in scandir(self._filesystem_path, only_files=True):
            if not is_safe_filesystem_path_component(href):
                if not href.startswith(".Radicale"):
                    self.logger.debug(
                        "Skipping item %r in %r", href, self.path)
                continue
            yield href

    def get(self, href, verify_href=True):
        if verify_href:
            try:
                if not is_safe_filesystem_path_component(href):
                    raise UnsafePathError(href)
                path = path_to_filesystem(self._filesystem_path, href)
            except ValueError as e:
                self.logger.debug(
                    "Can't translate name %r safely to filesystem in %r: %s",
                    href, self.path, e, exc_info=True)
                return None
        else:
            path = os.path.join(self._filesystem_path, href)
        try:
            with open(path, encoding=self.encoding, newline="") as f:
                text = f.read()
        except (FileNotFoundError, IsADirectoryError):
            return None
        last_modified = time.strftime(
            "%a, %d %b %Y %H:%M:%S GMT",
            time.gmtime(os.path.getmtime(path)))
        try:
            item = vobject.readOne(text)
        except Exception as e:
            raise RuntimeError("Failed to parse item %r in %r" %
                               (href, self.path)) from e
        return Item(self, item, href, last_modified)

    def get_multi(self, hrefs):
        # It's faster to check for file name collissions here, because
        # we only need to call os.listdir once.
        files = None
        for href in hrefs:
            if files is None:
                # Only list dir when hrefs is not empty
                files = os.listdir(self._filesystem_path)
            path = os.path.join(self._filesystem_path, href)
            if (not is_safe_filesystem_path_component(href) or
                    href not in files and os.path.lexists(path)):
                self.logger.debug(
                    "Can't translate name safely to filesystem: %s", href)
                yield (href, None)
            else:
                yield (href, self.get(href, verify_href=False))

    def get_all(self):
        # We don't need to check for collissions, because the the file names
        # are from os.listdir.
        return map(lambda x: self.get(x, verify_href=False), self.list())

    def upload(self, href, vobject_item):
        if not is_safe_filesystem_path_component(href):
            raise UnsafePathError(href)
        path = path_to_filesystem(self._filesystem_path, href)
        item = Item(self, vobject_item, href)
        with self._atomic_write(path, newline="") as fd:
            fd.write(item.serialize())
        # Track the change
        self._update_history_etag(href, item)
        self._clean_history_cache()
        return item

    def delete(self, href=None):
        if href is None:
            # Delete the collection
            parent_dir = os.path.dirname(self._filesystem_path)
            try:
                os.rmdir(self._filesystem_path)
            except OSError:
                with TemporaryDirectory(
                        prefix=".Radicale.tmp-", dir=parent_dir) as tmp:
                    os.rename(self._filesystem_path, os.path.join(
                        tmp, os.path.basename(self._filesystem_path)))
                    self._sync_directory(parent_dir)
            else:
                self._sync_directory(parent_dir)
        else:
            # Delete an item
            if not is_safe_filesystem_path_component(href):
                raise UnsafePathError(href)
            path = path_to_filesystem(self._filesystem_path, href)
            if not os.path.isfile(path):
                raise ComponentNotFoundError(href)
            os.remove(path)
            self._sync_directory(os.path.dirname(path))
            # Track the change
            self._update_history_etag(href, None)
            self._clean_history_cache()

    def get_meta(self, key=None):
        # reuse cached value if the storage is read-only
        if self._writer or self._meta is None:
            try:
                with open(self._props_path, encoding=self.encoding) as f:
                    self._meta = json.load(f)
            except FileNotFoundError:
                self._meta = {}
            except ValueError as e:
                raise RuntimeError("Failed to load properties of collect"
                                   "ion %r: %s" % (self.path, e)) from e
        return self._meta.get(key) if key else self._meta

    def set_meta(self, props):
        new_props = self.get_meta()
        new_props.update(props)
        for key in tuple(new_props.keys()):
            if not new_props[key]:
                del new_props[key]
        with self._atomic_write(self._props_path, "w") as f:
            json.dump(new_props, f)

    @property
    def last_modified(self):
        relevant_files = chain(
            (self._filesystem_path,),
            (self._props_path,) if os.path.exists(self._props_path) else (),
            map(lambda x: os.path.join(self._filesystem_path, x), self.list()))
        last = max(map(os.path.getmtime, relevant_files))
        return time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime(last))

    def serialize(self):
        items = []
        time_begin = datetime.datetime.now()
        for href in self.list():
            items.append(self.get(href).item)
        time_end = datetime.datetime.now()
        self.logger.info(
            "Read %d items in %.3f seconds from %r", len(items),
            (time_end - time_begin).total_seconds(), self.path)
        if self.get_meta("tag") == "VCALENDAR":
            collection = vobject.iCalendar()
            for item in items:
                for content in ("vevent", "vtodo", "vjournal"):
                    if content in item.contents:
                        for item_part in getattr(item, "%s_list" % content):
                            collection.add(item_part)
                        break
            return collection.serialize()
        elif self.get_meta("tag") == "VADDRESSBOOK":
            return "".join([item.serialize() for item in items])
        return ""

    @property
    def etag(self):
        # reuse cached value if the storage is read-only
        if self._writer or self._etag is None:
            etag = md5()
            for item in self.get_all():
                etag.update((item.href + "/" + item.etag).encode("utf-8"))
            self._etag = '"%s"' % etag.hexdigest()
        return self._etag

    _lock = threading.Lock()
    _waiters = []
    _lock_file = None
    _lock_file_locked = False
    _readers = 0
    _writer = False

    @classmethod
    @contextmanager
    def acquire_lock(cls, mode, user=None):
        def condition():
            if mode == "r":
                return not cls._writer
            else:
                return not cls._writer and cls._readers == 0

        file_locking = cls.configuration.getboolean("storage",
                                                    "filesystem_locking")
        folder = os.path.expanduser(cls.configuration.get(
            "storage", "filesystem_folder"))
        # Use a primitive lock which only works within one process as a
        # precondition for inter-process file-based locking
        with cls._lock:
            if cls._waiters or not condition():
                # Use FIFO for access requests
                waiter = threading.Condition(lock=cls._lock)
                cls._waiters.append(waiter)
                while True:
                    waiter.wait()
                    if condition():
                        break
                cls._waiters.pop(0)
            if mode == "r":
                cls._readers += 1
                # Notify additional potential readers
                if cls._waiters:
                    cls._waiters[0].notify()
            else:
                cls._writer = True
            if not cls._lock_file:
                cls._makedirs_synced(folder)
                lock_path = os.path.join(folder, ".Radicale.lock")
                cls._lock_file = open(lock_path, "w+")
                # Set access rights to a necessary minimum to prevent locking
                # by arbitrary users
                try:
                    os.chmod(lock_path, stat.S_IWUSR | stat.S_IRUSR)
                except OSError as e:
                    cls.logger.info("Failed to set permissions on lock file:"
                                    " %s", e, exc_info=True)
            if file_locking and not cls._lock_file_locked:
                if os.name == "nt":
                    handle = msvcrt.get_osfhandle(cls._lock_file.fileno())
                    flags = LOCKFILE_EXCLUSIVE_LOCK if mode == "w" else 0
                    overlapped = Overlapped()
                    if not lock_file_ex(handle, flags, 0, 1, 0, overlapped):
                        raise RuntimeError("Locking the storage failed: %s" %
                                           ctypes.FormatError())
                elif os.name == "posix":
                    _cmd = fcntl.LOCK_EX if mode == "w" else fcntl.LOCK_SH
                    try:
                        fcntl.flock(cls._lock_file.fileno(), _cmd)
                    except OSError as e:
                        raise RuntimeError("Locking the storage failed: %s" %
                                           e) from e
                else:
                    raise RuntimeError("Locking the storage failed: "
                                       "Unsupported operating system")
                cls._lock_file_locked = True
        try:
            yield
            # execute hook
            hook = cls.configuration.get("storage", "hook")
            if mode == "w" and hook:
                cls.logger.debug("Running hook")
                subprocess.check_call(
                    hook % {"user": shlex.quote(user or "Anonymous")},
                    shell=True, cwd=folder)
        finally:
            with cls._lock:
                if mode == "r":
                    cls._readers -= 1
                else:
                    cls._writer = False
                if file_locking and cls._readers == 0:
                    if os.name == "nt":
                        handle = msvcrt.get_osfhandle(cls._lock_file.fileno())
                        overlapped = Overlapped()
                        if not unlock_file_ex(handle, 0, 1, 0, overlapped):
                            raise RuntimeError("Unlocking the storage failed: "
                                               "%s" % ctypes.FormatError())
                    elif os.name == "posix":
                        try:
                            fcntl.flock(cls._lock_file.fileno(), fcntl.LOCK_UN)
                        except OSError as e:
                            raise RuntimeError("Unlocking the storage failed: "
                                               "%s" % e) from e
                    else:
                        raise RuntimeError("Unlocking the storage failed: "
                                           "Unsupported operating system")
                    cls._lock_file_locked = False
                if cls._waiters:
                    cls._waiters[0].notify()
                if (cls.configuration.getboolean(
                        "storage", "filesystem_close_lock_file") and
                        cls._readers == 0 and not cls._waiters):
                    cls._lock_file.close()
                    cls._lock_file = None
