# This file is part of Radicale Server - Calendar Server
# Copyright © 2014 Jean-Marc Martins
# Copyright © 2012-2016 Guillaume Ayoub
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

import json
import os
import posixpath
import shutil
import stat
import threading
import time
from contextlib import contextmanager
from hashlib import md5
from importlib import import_module
from uuid import uuid4

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
        _fields_ = [("internal", ULONG_PTR),
                    ("internal_high", ULONG_PTR),
                    ("offset", ctypes.wintypes.DWORD),
                    ("offset_high", ctypes.wintypes.DWORD),
                    ("h_event", ctypes.wintypes.HANDLE)]

    lock_file_ex = ctypes.windll.kernel32.LockFileEx
    lock_file_ex.argtypes = [ctypes.wintypes.HANDLE,
                             ctypes.wintypes.DWORD,
                             ctypes.wintypes.DWORD,
                             ctypes.wintypes.DWORD,
                             ctypes.wintypes.DWORD,
                             ctypes.POINTER(Overlapped)]
    lock_file_ex.restype = ctypes.wintypes.BOOL
elif os.name == "posix":
    import fcntl


def load(configuration, logger):
    """Load the storage manager chosen in configuration."""
    storage_type = configuration.get("storage", "type")
    if storage_type == "multifilesystem":
        collection_class = Collection
    else:
        collection_class = import_module(storage_type).Collection

    class CollectionCopy(collection_class):
        """Collection copy, avoids overriding the original class attributes."""
    CollectionCopy.configuration = configuration
    CollectionCopy.logger = logger
    return CollectionCopy


MIMETYPES = {"VADDRESSBOOK": "text/vcard", "VCALENDAR": "text/calendar"}


def get_etag(text):
    """Etag from collection or item."""
    etag = md5()
    etag.update(text.encode("utf-8"))
    return '"%s"' % etag.hexdigest()


def sanitize_path(path):
    """Make path absolute with leading slash to prevent access to other data.

    Preserve a potential trailing slash.

    """
    trailing_slash = "/" if path.endswith("/") else ""
    path = posixpath.normpath(path)
    new_path = "/"
    for part in path.split("/"):
        if not part or part in (".", ".."):
            continue
        new_path = posixpath.join(new_path, part)
    trailing_slash = "" if new_path.endswith("/") else trailing_slash
    return new_path + trailing_slash


def is_safe_filesystem_path_component(path):
    """Check if path is a single component of a filesystem path.

    Check that the path is safe to join too.

    """
    return (
        path and not os.path.splitdrive(path)[0] and
        not os.path.split(path)[0] and path not in (os.curdir, os.pardir))


def path_to_filesystem(root, *paths):
    """Convert path to a local filesystem path relative to base_folder.

    Conversion is done in a secure manner, or raises ``ValueError``.

    """
    root = sanitize_path(root)
    paths = [sanitize_path(path).strip("/") for path in paths]
    safe_path = root
    for path in paths:
        if not path:
            continue
        for part in path.split("/"):
            if not is_safe_filesystem_path_component(part):
                raise ValueError("Unsafe path")
            safe_path = os.path.join(safe_path, part)
    return safe_path


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
    def discover(cls, path, depth="1"):
        """Discover a list of collections under the given ``path``.

        If ``depth`` is "0", only the actual object under ``path`` is
        returned.

        If ``depth`` is anything but "0", it is considered as "1" and direct
        children are included in the result. If ``include_container`` is
        ``True`` (the default), the containing object is included in the
        result.

        The ``path`` is relative.

        """
        raise NotImplementedError

    @property
    def etag(self):
        return get_etag(self.serialize())

    @classmethod
    def create_collection(cls, href, collection=None, tag=None):
        """Create a collection.

        ``collection`` is a list of vobject components.

        ``tag`` is the type of collection (VCALENDAR or VADDRESSBOOK). If
        ``tag`` is not given, it is guessed from the collection.

        """
        raise NotImplementedError

    def list(self):
        """List collection items."""
        raise NotImplementedError

    def get(self, href):
        """Fetch a single item."""
        raise NotImplementedError

    def get_multi(self, hrefs):
        """Fetch multiple items. Duplicate hrefs must be ignored.

        Functionally similar to ``get``, but might bring performance benefits
        on some storages when used cleverly.

        """
        for href in set(hrefs):
            yield self.get(href)

    def has(self, href):
        """Check if an item exists by its href.

        Functionally similar to ``get``, but might bring performance benefits
        on some storages when used cleverly.

        """
        return self.get(href) is not None

    def upload(self, href, vobject_item):
        """Upload a new item."""
        raise NotImplementedError

    def update(self, href, vobject_item, etag=None):
        """Update an item.

        Functionally similar to ``delete`` plus ``upload``, but might bring
        performance benefits on some storages when used cleverly.

        """
        self.delete(href, etag)
        self.upload(href, vobject_item)

    def delete(self, href=None, etag=None):
        """Delete an item.

        When ``href`` is ``None``, delete the collection.

        """
        raise NotImplementedError

    @contextmanager
    def at_once(self):
        """Set a context manager buffering the reads and writes."""
        # TODO: use in code
        yield

    def get_meta(self, key):
        """Get metadata value for collection."""
        raise NotImplementedError

    def set_meta(self, key, value):
        """Set metadata value for collection."""
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
    def acquire_lock(cls, mode):
        """Set a context manager to lock the whole storage.

        ``mode`` must either be "r" for shared access or "w" for exclusive
        access.

        """
        raise NotImplementedError


class Collection(BaseCollection):
    """Collection stored in several files per calendar."""

    def __init__(self, path, principal=False):
        folder = os.path.expanduser(
            self.configuration.get("storage", "filesystem_folder"))
        # path should already be sanitized
        self.path = sanitize_path(path).strip("/")
        self.storage_encoding = self.configuration.get("encoding", "stock")
        self._filesystem_path = path_to_filesystem(folder, self.path)
        split_path = self.path.split("/")
        if len(split_path) > 1:
            # URL with at least one folder
            self.owner = split_path[0]
        else:
            self.owner = None
        self.is_principal = principal

    @classmethod
    def discover(cls, path, depth="1"):
        # path == None means wrong URL
        if path is None:
            return

        # path should already be sanitized
        sane_path = sanitize_path(path).strip("/")
        attributes = sane_path.split("/")
        if not attributes:
            return

        # Try to guess if the path leads to a collection or an item
        folder = os.path.expanduser(
            cls.configuration.get("storage", "filesystem_folder"))
        if not os.path.isdir(path_to_filesystem(folder, sane_path)):
            # path is not a collection
            if os.path.isfile(path_to_filesystem(folder, sane_path)):
                # path is an item
                attributes.pop()
            elif os.path.isdir(path_to_filesystem(folder, *attributes[:-1])):
                # path parent is a collection
                attributes.pop()
            # TODO: else: return?

        path = "/".join(attributes)

        principal = len(attributes) <= 1
        collection = cls(path, principal)
        yield collection
        if depth != "0":
            # TODO: fix this
            items = list(collection.list())
            if items:
                for item in items:
                    yield collection.get(item[0])
            _, directories, _ = next(os.walk(collection._filesystem_path))
            for sub_path in directories:
                full_path = os.path.join(collection._filesystem_path, sub_path)
                if os.path.exists(path_to_filesystem(full_path)):
                    yield cls(posixpath.join(path, sub_path))

    @classmethod
    def create_collection(cls, href, collection=None, tag=None):
        folder = os.path.expanduser(
            cls.configuration.get("storage", "filesystem_folder"))
        path = path_to_filesystem(folder, href)
        if not os.path.exists(path):
            os.makedirs(path)
        if not tag and collection:
            tag = collection[0].name
        self = cls(href)
        if tag == "VCALENDAR":
            self.set_meta("tag", "VCALENDAR")
            if collection:
                collection, = collection
                for content in ("vevent", "vtodo", "vjournal"):
                    if content in collection.contents:
                        for item in getattr(collection, "%s_list" % content):
                            new_collection = vobject.iCalendar()
                            new_collection.add(item)
                            self.upload(uuid4().hex, new_collection)
        elif tag == "VCARD":
            self.set_meta("tag", "VADDRESSBOOK")
            if collection:
                for card in collection:
                    self.upload(uuid4().hex, card)
        return self

    def list(self):
        try:
            hrefs = os.listdir(self._filesystem_path)
        except IOError:
            return

        for href in hrefs:
            path = os.path.join(self._filesystem_path, href)
            if not href.endswith(".props") and os.path.isfile(path):
                with open(path, encoding=self.storage_encoding) as fd:
                    yield href, get_etag(fd.read())

    def get(self, href):
        if not href:
            return
        href = href.strip("{}").replace("/", "_")
        if is_safe_filesystem_path_component(href):
            path = os.path.join(self._filesystem_path, href)
            if os.path.isfile(path):
                with open(path, encoding=self.storage_encoding) as fd:
                    text = fd.read()
                last_modified = time.strftime(
                    "%a, %d %b %Y %H:%M:%S GMT",
                    time.gmtime(os.path.getmtime(path)))
                return Item(self, vobject.readOne(text), href, last_modified)
        else:
            self.logger.debug(
                "Can't tranlate name safely to filesystem, "
                "skipping component: %s", href)

    def has(self, href):
        return self.get(href) is not None

    def upload(self, href, vobject_item):
        # TODO: use returned object in code
        if is_safe_filesystem_path_component(href):
            path = path_to_filesystem(self._filesystem_path, href)
            if not os.path.exists(path):
                item = Item(self, vobject_item, href)
                with open(path, "w", encoding=self.storage_encoding) as fd:
                    fd.write(item.serialize())
                return item
        else:
            self.logger.debug(
                "Can't tranlate name safely to filesystem, "
                "skipping component: %s", href)

    def update(self, href, vobject_item, etag=None):
        # TODO: use etag in code and test it here
        # TODO: use returned object in code
        if is_safe_filesystem_path_component(href):
            path = path_to_filesystem(self._filesystem_path, href)
            if os.path.exists(path):
                with open(path, encoding=self.storage_encoding) as fd:
                    text = fd.read()
                if not etag or etag == get_etag(text):
                    item = Item(self, vobject_item, href)
                    with open(path, "w", encoding=self.storage_encoding) as fd:
                        fd.write(item.serialize())
                    return item
        else:
            self.logger.debug(
                "Can't tranlate name safely to filesystem, "
                "skipping component: %s", href)

    def delete(self, href=None, etag=None):
        # TODO: use etag in code and test it here
        # TODO: use returned object in code
        if href is None:
            # Delete the collection
            if os.path.isdir(self._filesystem_path):
                shutil.rmtree(self._filesystem_path)
            props_path = self._filesystem_path + ".props"
            if os.path.isfile(props_path):
                os.remove(props_path)
            return
        elif is_safe_filesystem_path_component(href):
            # Delete an item
            path = path_to_filesystem(self._filesystem_path, href)
            if os.path.isfile(path):
                with open(path, encoding=self.storage_encoding) as fd:
                    text = fd.read()
                if not etag or etag == get_etag(text):
                    os.remove(path)
                    return
        else:
            self.logger.debug(
                "Can't tranlate name safely to filesystem, "
                "skipping component: %s", href)

    @contextmanager
    def at_once(self):
        # TODO: use a file locker
        yield

    def get_meta(self, key):
        props_path = self._filesystem_path + ".props"
        if os.path.exists(props_path):
            with open(props_path, encoding=self.storage_encoding) as prop:
                return json.load(prop).get(key)

    def set_meta(self, key, value):
        props_path = self._filesystem_path + ".props"
        properties = {}
        if os.path.exists(props_path):
            with open(props_path, encoding=self.storage_encoding) as prop:
                properties.update(json.load(prop))

        if value:
            properties[key] = value
        else:
            properties.pop(key, None)

        with open(props_path, "w+", encoding=self.storage_encoding) as prop:
            json.dump(properties, prop)

    @property
    def last_modified(self):
        last = max([os.path.getmtime(self._filesystem_path)] + [
            os.path.getmtime(os.path.join(self._filesystem_path, filename))
            for filename in os.listdir(self._filesystem_path)] or [0])
        return time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime(last))

    def serialize(self):
        items = []
        for href in os.listdir(self._filesystem_path):
            path = os.path.join(self._filesystem_path, href)
            if os.path.isfile(path) and not path.endswith(".props"):
                with open(path, encoding=self.storage_encoding) as fd:
                    items.append(vobject.readOne(fd.read()))
        if self.get_meta("tag") == "VCALENDAR":
            collection = vobject.iCalendar()
            for item in items:
                for content in ("vevent", "vtodo", "vjournal"):
                    if content in item.contents:
                        collection.add(getattr(item, content))
                        break
            return collection.serialize()
        elif self.get_meta("tag") == "VADDRESSBOOK":
            return "".join([item.serialize() for item in items])
        return ""

    _lock = threading.Lock()

    @classmethod
    @contextmanager
    def acquire_lock(cls, mode):
        class Lock:
            def __init__(self, release_method):
                self._release_method = release_method

            def release(self):
                self._release_method()

        if mode not in ("r", "w"):
            raise ValueError("Invalid lock mode: %s" % mode)
        folder = os.path.expanduser(
            cls.configuration.get("storage", "filesystem_folder"))
        if not os.path.exists(folder):
            os.makedirs(folder, exist_ok=True)
        lock_path = os.path.join(folder, "Radicale.lock")
        lock_file = open(lock_path, "w+")
        # set access rights to a necessary minimum to prevent locking by
        # arbitrary users
        try:
            os.chmod(lock_path, stat.S_IWUSR | stat.S_IRUSR)
        except OSError:
            cls.logger.debug("Failed to set permissions on lock file")
        locked = False
        if os.name == "nt":
            handle = msvcrt.get_osfhandle(lock_file.fileno())
            flags = LOCKFILE_EXCLUSIVE_LOCK if mode == "w" else 0
            overlapped = Overlapped()
            if lock_file_ex(handle, flags, 0, 1, 0, overlapped):
                locked = True
        elif os.name == "posix":
            operation = fcntl.LOCK_EX if mode == "w" else fcntl.LOCK_SH
            # According to documentation flock() is emulated with fcntl() on
            # some platforms. fcntl() locks are not associated with an open
            # file descriptor. The same file can be locked multiple times
            # within the same process and if any fd of the file is closed,
            # all locks are released.
            # flock() does not work on NFS shares.
            try:
                fcntl.flock(lock_file.fileno(), operation)
            except OSError:
                pass
            else:
                locked = True
        if locked:
            lock = Lock(lock_file.close)
        else:
            cls.logger.debug("Locking not supported")
            lock_file.close()
            # Fallback to primitive lock which only works within one process
            # and doesn't distinguish between shared and exclusive access.
            # TODO: use readers–writer lock
            cls._lock.acquire()
            lock = Lock(cls._lock.release)
        yield
        lock.release()
