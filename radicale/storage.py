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
import json
import os
import pickle
import posixpath
import shlex
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from hashlib import md5
from importlib import import_module
from itertools import chain, groupby
from math import log
from random import getrandbits
from tempfile import NamedTemporaryFile, TemporaryDirectory

import vobject

if sys.version_info >= (3, 5):
    # HACK: Avoid import cycle for Python < 3.5
    from . import xmlutils

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

INTERNAL_TYPES = ("multifilesystem",)


def load(configuration, logger):
    """Load the storage manager chosen in configuration."""
    if sys.version_info < (3, 5):
        # HACK: Avoid import cycle for Python < 3.5
        global xmlutils
        from . import xmlutils
    storage_type = configuration.get("storage", "type")
    if storage_type == "multifilesystem":
        collection_class = Collection
    else:
        try:
            collection_class = import_module(storage_type).Collection
        except Exception as e:
            raise RuntimeError("Failed to load storage module %r: %s" %
                               (storage_type, e)) from e
    logger.info("Storage type is %r", storage_type)

    class CollectionCopy(collection_class):
        """Collection copy, avoids overriding the original class attributes."""
    CollectionCopy.configuration = configuration
    CollectionCopy.logger = logger
    return CollectionCopy


def check_and_sanitize_item(vobject_item, is_collection=False, uid=None,
                            tag=None):
    """Check vobject items for common errors and add missing UIDs.

    ``multiple`` indicates that the vobject_item contains unrelated components.

    If ``uid`` is not set, the UID is generated randomly.

    """
    if tag and tag not in ("VCALENDAR", "VADDRESSBOOK"):
        raise ValueError("Unsupported collection tag: %r" % tag)
    if vobject_item.name == "VCALENDAR" and tag == "VCALENDAR":
        component_name = None
        object_uid = None
        object_uid_set = False
        for component in vobject_item.components():
            # https://tools.ietf.org/html/rfc4791#section-4.1
            if component.name == "VTIMEZONE":
                continue
            if component_name is None or is_collection:
                component_name = component.name
            elif component_name != component.name:
                raise ValueError("Muliple component types in object: %r, %r" %
                                 (component_name, component.name))
            if component_name not in ("VTODO", "VEVENT", "VJOURNAL"):
                continue
            component_uid = get_uid(component)
            if not object_uid_set or is_collection:
                object_uid_set = True
                object_uid = component_uid
                if component_uid is None:
                    component.add("UID").value = uid or random_uuid4()
                elif not component_uid:
                    component.uid.value = uid or random_uuid4()
            elif not object_uid or not component_uid:
                raise ValueError("Multiple %s components without UID in "
                                 "object" % component_name)
            elif object_uid != component_uid:
                raise ValueError(
                    "Muliple %s components with different UIDs in object: "
                    "%r, %r" % (component_name, object_uid, component_uid))
            # vobject interprets recurrence rules on demand
            try:
                component.rruleset
            except Exception as e:
                raise ValueError("invalid recurrence rules in %s" %
                                 component.name) from e
    elif vobject_item.name == "VCARD" and tag == "VADDRESSBOOK":
        # https://tools.ietf.org/html/rfc6352#section-5.1
        object_uid = get_uid(vobject_item)
        if object_uid is None:
            vobject_item.add("UID").value = uid or random_uuid4()
        elif not object_uid:
            vobject_item.uid.value = uid or random_uuid4()
    elif vobject_item.name == "VLIST" and tag == "VADDRESSBOOK":
        # Custom format used by SOGo Connector to store lists of contacts
        pass
    else:
        raise ValueError("Item type %r not supported in %s collection" %
                         (vobject_item.name, repr(tag) if tag else "generic"))


def check_and_sanitize_props(props):
    """Check collection properties for common errors."""
    tag = props.get("tag")
    if tag and tag not in ("VCALENDAR", "VADDRESSBOOK"):
        raise ValueError("Unsupported collection tag: %r" % tag)


def random_uuid4():
    """Generate a pseudo-random UUID"""
    r = "%016x" % getrandbits(128)
    return "%s-%s-%s-%s-%s" % (r[:8], r[8:12], r[12:16], r[16:20], r[20:])


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


def get_uid(vobject_component):
    """UID value of an item if defined."""
    return ((hasattr(vobject_component, "uid") or None) and
            vobject_component.uid.value)


def get_uid_from_object(vobject_item):
    """UID value of an calendar/addressbook object."""
    if vobject_item.name == "VCALENDAR":
        if hasattr(vobject_item, "vevent"):
            return get_uid(vobject_item.vevent)
        if hasattr(vobject_item, "vjournal"):
            return get_uid(vobject_item.vjournal)
        if hasattr(vobject_item, "vtodo"):
            return get_uid(vobject_item.vtodo)
    elif vobject_item.name == "VCARD":
        return get_uid(vobject_item)
    return None


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


def left_encode_int(v):
    length = int(log(v, 256)) + 1 if v != 0 else 1
    return bytes((length,)) + v.to_bytes(length, 'little')


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
    def __init__(self, collection, item=None, href=None, last_modified=None,
                 text=None, etag=None, uid=None, name=None,
                 component_name=None):
        """Initialize an item.

        ``collection`` the parent collection.

        ``href`` the href of the item.

        ``last_modified`` the HTTP-datetime of when the item was modified.

        ``text`` the text representation of the item (optional if ``item`` is
        set).

        ``item`` the vobject item (optional if ``text`` is set).

        ``etag`` the etag of the item (optional). See ``get_etag``.

        ``uid`` the UID of the object (optional). See ``get_uid_from_object``.

        """
        if text is None and item is None:
            raise ValueError("at least one of 'text' or 'item' must be set")
        self.collection = collection
        self.href = href
        self.last_modified = last_modified
        self._text = text
        self._item = item
        self._etag = etag
        self._uid = uid
        self._name = name
        self._component_name = component_name

    def __getattr__(self, attr):
        return getattr(self.item, attr)

    def serialize(self):
        if self._text is None:
            try:
                self._text = self.item.serialize()
            except Exception as e:
                raise RuntimeError("Failed to serialize item %r from %r: %s" %
                                   (self.href, self.collection.path, e)) from e
        return self._text

    @property
    def item(self):
        if self._item is None:
            try:
                self._item = vobject.readOne(self._text)
            except Exception as e:
                raise RuntimeError("Failed to parse item %r from %r: %s" %
                                   (self.href, self.collection.path, e)) from e
        return self._item

    @property
    def etag(self):
        """Encoded as quoted-string (see RFC 2616)."""
        if self._etag is None:
            self._etag = get_etag(self.serialize())
        return self._etag

    @property
    def uid(self):
        if self._uid is None:
            self._uid = get_uid_from_object(self.item)
        return self._uid

    @property
    def name(self):
        if self._name is not None:
            return self._name
        return self.item.name

    @property
    def component_name(self):
        if self._component_name is not None:
            return self._component_name
        return xmlutils.find_tag(self.item)


class BaseCollection:

    # Overriden on copy by the "load" function
    configuration = None
    logger = None

    # Properties of instance
    """The sanitized path of the collection without leading or trailing ``/``.
    """
    path = ""

    @property
    def owner(self):
        """The owner of the collection."""
        return self.path.split("/", maxsplit=1)[0]

    @property
    def is_principal(self):
        """Collection is a principal."""
        return bool(self.path) and "/" not in self.path

    @owner.setter
    def owner(self, value):
        # DEPRECATED: Included for compatibility reasons
        pass

    @is_principal.setter
    def is_principal(self, value):
        # DEPRECATED: Included for compatibility reasons
        pass

    @classmethod
    def discover(cls, path, depth="0"):
        """Discover a list of collections under the given ``path``.

        ``path`` is sanitized.

        If ``depth`` is "0", only the actual object under ``path`` is
        returned.

        If ``depth`` is anything but "0", it is considered as "1" and direct
        children are included in the result.

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
        etag = md5()
        for item in self.get_all():
            etag.update((item.href + "/" + item.etag).encode("utf-8"))
        etag.update(json.dumps(self.get_meta(), sort_keys=True).encode())
        return '"%s"' % etag.hexdigest()

    @classmethod
    def create_collection(cls, href, collection=None, props=None):
        """Create a collection.

        ``href`` is the sanitized path.

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
        """Fetch multiple items. Duplicate hrefs must be ignored.

        DEPRECATED: use ``get_multi2`` instead

        """
        return (self.get(href) for href in set(hrefs))

    def get_multi2(self, hrefs):
        """Fetch multiple items.

        Functionally similar to ``get``, but might bring performance benefits
        on some storages when used cleverly. It's not required to return the
        requested items in the correct order. Duplicated hrefs can be ignored.

        Returns tuples with the href and the item or None if the item doesn't
        exist.

        """
        return ((href, self.get(href)) for href in hrefs)

    def get_all(self):
        """Fetch all items.

        Functionally similar to ``get``, but might bring performance benefits
        on some storages when used cleverly.

        """
        return map(self.get, self.list())

    def get_all_filtered(self, filters):
        """Fetch all items with optional filtering.

        This can largely improve performance of reports depending on
        the filters and this implementation.

        Returns tuples in the form ``(item, filters_matched)``.
        ``filters_matched`` is a bool that indicates if ``filters`` are fully
        matched.

        This returns all events by default
        """
        return ((item, False) for item in self.get_all())

    def pre_filtered_list(self, filters):
        """List collection items with optional pre filtering.

        DEPRECATED: use ``get_all_filtered`` instead

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

    def get_meta(self, key=None):
        """Get metadata value for collection.

        Return the value of the property ``key``. If ``key`` is ``None`` return
        a dict with all properties

        """
        raise NotImplementedError

    def set_meta(self, props):
        """Set metadata values for collection.

        ``props`` a dict with updates for properties. If a value is empty, the
        property must be deleted.

        DEPRECATED: use ``set_meta_all`` instead

        """
        raise NotImplementedError

    def set_meta_all(self, props):
        """Set metadata values for collection.

        ``props`` a dict with values for properties.

        """
        delta_props = self.get_meta()
        for key in delta_props.keys():
            if key not in props:
                delta_props[key] = None
        delta_props.update(props)
        self.set_meta(self, delta_props)

    @property
    def last_modified(self):
        """Get the HTTP-datetime of when the collection was modified."""
        raise NotImplementedError

    def serialize(self):
        """Get the unicode string representing the whole collection."""
        if self.get_meta("tag") == "VCALENDAR":
            in_vcalendar = False
            vtimezones = ""
            included_tzids = set()
            vtimezone = []
            tzid = None
            components = ""
            # Concatenate all child elements of VCALENDAR from all items
            # together, while preventing duplicated VTIMEZONE entries.
            # VTIMEZONEs are only distinguished by their TZID, if different
            # timezones share the same TZID this produces errornous ouput.
            # VObject fails at this too.
            for item in self.get_all():
                depth = 0
                for line in item.serialize().split("\r\n"):
                    if line.startswith("BEGIN:"):
                        depth += 1
                    if depth == 1 and line == "BEGIN:VCALENDAR":
                        in_vcalendar = True
                    elif in_vcalendar:
                        if depth == 1 and line.startswith("END:"):
                            in_vcalendar = False
                        if depth == 2 and line == "BEGIN:VTIMEZONE":
                            vtimezone.append(line + "\r\n")
                        elif vtimezone:
                            vtimezone.append(line + "\r\n")
                            if depth == 2 and line.startswith("TZID:"):
                                tzid = line[len("TZID:"):]
                            elif depth == 2 and line.startswith("END:"):
                                if tzid is None or tzid not in included_tzids:
                                    vtimezones += "".join(vtimezone)
                                    included_tzids.add(tzid)
                                vtimezone.clear()
                                tzid = None
                        elif depth >= 2:
                            components += line + "\r\n"
                    if line.startswith("END:"):
                        depth -= 1
            template = vobject.iCalendar()
            displayname = self.get_meta("D:displayname")
            if displayname:
                template.add("X-WR-CALNAME")
                template.x_wr_calname.value_param = "TEXT"
                template.x_wr_calname.value = displayname
            description = self.get_meta("C:calendar-description")
            if description:
                template.add("X-WR-CALDESC")
                template.x_wr_caldesc.value_param = "TEXT"
                template.x_wr_caldesc.value = description
            template = template.serialize()
            template_insert_pos = template.find("\r\nEND:VCALENDAR\r\n") + 2
            assert template_insert_pos != -1
            return (template[:template_insert_pos] +
                    vtimezones + components +
                    template[template_insert_pos:])
        elif self.get_meta("tag") == "VADDRESSBOOK":
            return "".join((item.serialize() for item in self.get_all()))
        return ""

    @classmethod
    @contextmanager
    def acquire_lock(cls, mode, user=None):
        """Set a context manager to lock the whole storage.

        ``mode`` must either be "r" for shared access or "w" for exclusive
        access.

        ``user`` is the name of the logged in user or empty.

        """
        raise NotImplementedError

    @classmethod
    def verify(cls):
        """Check the storage for errors."""
        return True


ITEM_CACHE_VERSION = 1


class Collection(BaseCollection):
    """Collection stored in several files per calendar."""

    def __init__(self, path, principal=None, folder=None,
                 filesystem_path=None):
        # DEPRECATED: Remove principal and folder attributes
        if folder is None:
            folder = self._get_collection_root_folder()
        # Path should already be sanitized
        self.path = sanitize_path(path).strip("/")
        self._encoding = self.configuration.get("encoding", "stock")
        # DEPRECATED: Use ``self._encoding`` instead
        self.encoding = self._encoding
        if filesystem_path is None:
            filesystem_path = path_to_filesystem(folder, self.path)
        self._filesystem_path = filesystem_path
        self._props_path = os.path.join(
            self._filesystem_path, ".Radicale.props")
        self._meta_cache = None
        self._etag_cache = None
        self._item_cache_cleaned = False

    @classmethod
    def _get_collection_root_folder(cls):
        filesystem_folder = os.path.expanduser(
            cls.configuration.get("storage", "filesystem_folder"))
        return os.path.join(filesystem_folder, "collection-root")

    @contextmanager
    def _atomic_write(self, path, mode="w", newline=None, sync_directory=True):
        directory = os.path.dirname(path)
        tmp = NamedTemporaryFile(
            mode=mode, dir=directory, delete=False, prefix=".Radicale.tmp-",
            newline=newline, encoding=None if "b" in mode else self._encoding)
        try:
            yield tmp
            try:
                self._fsync(tmp.fileno())
            except OSError as e:
                raise RuntimeError("Fsync'ing file %r failed: %s" %
                                   (path, e)) from e
            tmp.close()
            os.replace(tmp.name, path)
        except:
            tmp.close()
            os.remove(tmp.name)
            raise
        if sync_directory:
            self._sync_directory(directory)

    @staticmethod
    def _find_available_file_name(exists_fn, suffix=""):
        # Prevent infinite loop
        for _ in range(1000):
            file_name = random_uuid4() + suffix
            if not exists_fn(file_name):
                return file_name
        # something is wrong with the PRNG
        raise RuntimeError("No unique random sequence found")

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
            try:
                fd = os.open(path, 0)
                try:
                    cls._fsync(fd)
                finally:
                    os.close(fd)
            except OSError as e:
                raise RuntimeError("Fsync'ing directory %r failed: %s" %
                                   (path, e)) from e

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
    def discover(cls, path, depth="0", child_context_manager=(
                 lambda path, href=None: contextlib.ExitStack())):
        # Path should already be sanitized
        sane_path = sanitize_path(path).strip("/")
        attributes = sane_path.split("/") if sane_path else []

        folder = cls._get_collection_root_folder()
        # Create the root collection
        cls._makedirs_synced(folder)
        try:
            filesystem_path = path_to_filesystem(folder, sane_path)
        except ValueError as e:
            # Path is unsafe
            cls.logger.debug("Unsafe path %r requested from storage: %s",
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

        sane_path = "/".join(attributes)
        collection = cls(sane_path)

        if href:
            yield collection.get(href)
            return

        yield collection

        if depth == "0":
            return

        for href in collection.list():
            with child_context_manager(sane_path, href):
                yield collection.get(href)

        for href in scandir(filesystem_path, only_dirs=True):
            if not is_safe_filesystem_path_component(href):
                if not href.startswith(".Radicale"):
                    cls.logger.debug("Skipping collection %r in %r", href,
                                     sane_path)
                continue
            child_path = posixpath.join(sane_path, href)
            with child_context_manager(child_path):
                yield cls(child_path)

    @classmethod
    def verify(cls):
        item_errors = collection_errors = 0

        @contextlib.contextmanager
        def exception_cm(path, href=None):
            nonlocal item_errors, collection_errors
            try:
                yield
            except Exception as e:
                if href:
                    item_errors += 1
                    name = "item %r in %r" % (href, path.strip("/"))
                else:
                    collection_errors += 1
                    name = "collection %r" % path.strip("/")
                cls.logger.error("Invalid %s: %s", name, e, exc_info=True)

        remaining_paths = [""]
        while remaining_paths:
            path = remaining_paths.pop(0)
            cls.logger.debug("Verifying collection %r", path)
            with exception_cm(path):
                saved_item_errors = item_errors
                collection = None
                for item in cls.discover(path, "1", exception_cm):
                    if not collection:
                        collection = item
                        collection.get_meta()
                        continue
                    if isinstance(item, BaseCollection):
                        remaining_paths.append(item.path)
                    else:
                        cls.logger.debug("Verified item %r in %r",
                                         item.href, path)
                if item_errors == saved_item_errors:
                    collection.sync()
        return item_errors == 0 and collection_errors == 0

    @classmethod
    def create_collection(cls, href, collection=None, props=None):
        folder = cls._get_collection_root_folder()

        # Path should already be sanitized
        sane_path = sanitize_path(href).strip("/")
        filesystem_path = path_to_filesystem(folder, sane_path)

        if not props:
            cls._makedirs_synced(filesystem_path)
            return cls(sane_path)

        parent_dir = os.path.dirname(filesystem_path)
        cls._makedirs_synced(parent_dir)

        # Create a temporary directory with an unsafe name
        with TemporaryDirectory(
                prefix=".Radicale.tmp-", dir=parent_dir) as tmp_dir:
            # The temporary directory itself can't be renamed
            tmp_filesystem_path = os.path.join(tmp_dir, "collection")
            os.makedirs(tmp_filesystem_path)
            self = cls(sane_path, filesystem_path=tmp_filesystem_path)
            self.set_meta_all(props)

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
                        # href must comply to is_safe_filesystem_path_component
                        # and no file name collisions must exist between hrefs
                        href = self._find_available_file_name(
                            vobject_items.get, suffix=".ics")
                        vobject_items[href] = new_collection
                    self._upload_all_nonatomic(vobject_items)
                elif props.get("tag") == "VADDRESSBOOK":
                    vobject_items = {}
                    for card in collection:
                        # href must comply to is_safe_filesystem_path_component
                        # and no file name collisions must exist between hrefs
                        href = self._find_available_file_name(
                            vobject_items.get, suffix=".vcf")
                        vobject_items[href] = card
                    self._upload_all_nonatomic(vobject_items)

            # This operation is not atomic on the filesystem level but it's
            # very unlikely that one rename operations succeeds while the
            # other fails or that only one gets written to disk.
            if os.path.exists(filesystem_path):
                os.rename(filesystem_path, os.path.join(tmp_dir, "delete"))
            os.rename(tmp_filesystem_path, filesystem_path)
            cls._sync_directory(parent_dir)

        return cls(sane_path)

    def upload_all_nonatomic(self, vobject_items):
        """DEPRECATED: Use ``_upload_all_nonatomic``"""
        return self._upload_all_nonatomic(vobject_items)

    def _upload_all_nonatomic(self, vobject_items):
        """Upload a new set of items.

        This takes a mapping of href and vobject items and
        uploads them nonatomic and without existence checks.

        """
        cache_folder = os.path.join(self._filesystem_path,
                                    ".Radicale.cache", "item")
        self._makedirs_synced(cache_folder)
        for href, vobject_item in vobject_items.items():
            if not is_safe_filesystem_path_component(href):
                raise UnsafePathError(href)
            try:
                cache_content = self._item_cache_content(href, vobject_item)
                _, _, _, text, _, _, _, _ = cache_content
            except Exception as e:
                raise ValueError(
                    "Failed to store item %r in temporary collection %r: %s" %
                    (href, self.path, e)) from e
            with self._atomic_write(os.path.join(cache_folder, href), "wb",
                                    sync_directory=False) as f:
                pickle.dump(cache_content, f)
            path = path_to_filesystem(self._filesystem_path, href)
            with self._atomic_write(
                    path, newline="", sync_directory=False) as f:
                f.write(text)
        self._sync_directory(cache_folder)
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
        # Move the item cache entry
        cache_folder = os.path.join(item.collection._filesystem_path,
                                    ".Radicale.cache", "item")
        to_cache_folder = os.path.join(to_collection._filesystem_path,
                                       ".Radicale.cache", "item")
        cls._makedirs_synced(to_cache_folder)
        try:
            os.replace(os.path.join(cache_folder, item.href),
                       os.path.join(to_cache_folder, to_href))
        except FileNotFoundError:
            pass
        else:
            cls._makedirs_synced(to_cache_folder)
            if cache_folder != to_cache_folder:
                cls._makedirs_synced(cache_folder)
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
            for href in scandir(history_folder):
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
                raise ValueError("Malformed token: %r" % old_token)
            old_token_name = old_token[len("http://radicale.org/ns/sync/"):]
            if not check_token_name(old_token_name):
                raise ValueError("Malformed token: %r" % old_token)
        # Get the current state and sync-token of the collection.
        state = {}
        token_name_hash = md5()
        # Find the history of all existing and deleted items
        for href, item in chain(
                ((item.href, item) for item in self.get_all()),
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
                raise ValueError("Token not found: %r" % old_token)
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

    def list(self):
        for href in scandir(self._filesystem_path, only_files=True):
            if not is_safe_filesystem_path_component(href):
                if not href.startswith(".Radicale"):
                    self.logger.debug(
                        "Skipping item %r in %r", href, self.path)
                continue
            yield href

    def get(self, href, verify_href=True):
        item, metadata = self._get_with_metadata(href, verify_href=verify_href)
        return item

    def _item_cache_hash(self, raw_text):
        _hash = md5()
        _hash.update(left_encode_int(ITEM_CACHE_VERSION))
        _hash.update(raw_text)
        return _hash.hexdigest()

    def _item_cache_content(self, href, vobject_item, cache_hash=None):
        text = vobject_item.serialize()
        if cache_hash is None:
            cache_hash = self._item_cache_hash(text.encode(self._encoding))
        etag = get_etag(text)
        uid = get_uid_from_object(vobject_item)
        name = vobject_item.name
        tag, start, end = xmlutils.find_tag_and_time_range(vobject_item)
        return cache_hash, uid, etag, text, name, tag, start, end

    def _store_item_cache(self, href, vobject_item, cache_hash=None):
        cache_folder = os.path.join(self._filesystem_path, ".Radicale.cache",
                                    "item")
        content = self._item_cache_content(href, vobject_item, cache_hash)
        self._makedirs_synced(cache_folder)
        try:
            # Race: Other processes might have created and locked the
            # file.
            with self._atomic_write(os.path.join(cache_folder, href),
                                    "wb") as f:
                pickle.dump(content, f)
        except PermissionError:
            pass
        return content

    _cache_locks = {}
    _cache_locks_lock = threading.Lock()

    @contextmanager
    def _acquire_cache_lock(self, ns=""):
        with contextlib.ExitStack() as lock_stack:
            with contextlib.ExitStack() as locks_lock_stack:
                locks_lock_stack.enter_context(self._cache_locks_lock)
                lock_id = ns + "/" + self.path
                lock = self._cache_locks.get(lock_id)
                if not lock:
                    cache_folder = os.path.join(self._filesystem_path,
                                                ".Radicale.cache")
                    self._makedirs_synced(cache_folder)
                    lock_path = None
                    if self.configuration.getboolean(
                            "storage", "filesystem_locking"):
                        lock_path = os.path.join(
                            cache_folder,
                            ".Radicale.lock" + (".%s" % ns if ns else ""))
                    lock = FileBackedRwLock(lock_path)
                    self._cache_locks[lock_id] = lock
                lock_stack.enter_context(lock.acquire_lock(
                    "w", lambda: locks_lock_stack.pop_all().close()))
            try:
                yield
            finally:
                with self._cache_locks_lock:
                    lock_stack.pop_all().close()
                    if not lock.in_use():
                        del self._cache_locks[lock_id]

    def _load_item_cache(self, href, input_hash):
        cache_folder = os.path.join(self._filesystem_path, ".Radicale.cache",
                                    "item")
        cache_hash = uid = etag = text = name = tag = start = end = None
        try:
            with open(os.path.join(cache_folder, href), "rb") as f:
                cache_hash, *content = pickle.load(f)
                if cache_hash == input_hash:
                    uid, etag, text, name, tag, start, end = content
        except FileNotFoundError as e:
            pass
        except (pickle.UnpicklingError, ValueError) as e:
            self.logger.warning(
                "Failed to load item cache entry %r in %r: %s",
                href, self.path, e, exc_info=True)
        return cache_hash, uid, etag, text, name, tag, start, end

    def _clean_item_cache(self):
        cache_folder = os.path.join(self._filesystem_path, ".Radicale.cache",
                                    "item")
        self._clean_cache(cache_folder, (
            href for href in scandir(cache_folder) if not
            os.path.isfile(os.path.join(self._filesystem_path, href))))

    def _get_with_metadata(self, href, verify_href=True):
        """Like ``get`` but additonally returns the following metadata:
        tag, start, end: see ``xmlutils.find_tag_and_time_range``. If
        extraction of the metadata failed, the values are all ``None``."""
        if verify_href:
            try:
                if not is_safe_filesystem_path_component(href):
                    raise UnsafePathError(href)
                path = path_to_filesystem(self._filesystem_path, href)
            except ValueError as e:
                self.logger.debug(
                    "Can't translate name %r safely to filesystem in %r: %s",
                    href, self.path, e, exc_info=True)
                return None, None
        else:
            path = os.path.join(self._filesystem_path, href)
        try:
            with open(path, "rb") as f:
                raw_text = f.read()
        except (FileNotFoundError, IsADirectoryError):
            return None, None
        # The hash of the component in the file system. This is used to check,
        # if the entry in the cache is still valid.
        input_hash = self._item_cache_hash(raw_text)
        cache_hash, uid, etag, text, name, tag, start, end = \
            self._load_item_cache(href, input_hash)
        vobject_item = None
        if input_hash != cache_hash:
            with contextlib.ExitStack() as lock_stack:
                # Lock the item cache to prevent multpile processes from
                # generating the same data in parallel.
                # This improves the performance for multiple requests.
                if self._lock.locked() == "r":
                    lock_stack.enter_context(self._acquire_cache_lock("item"))
                    # Check if another process created the file in the meantime
                    cache_hash, uid, etag, text, name, tag, start, end = \
                        self._load_item_cache(href, input_hash)
                if input_hash != cache_hash:
                    try:
                        vobject_items = tuple(vobject.readComponents(
                            raw_text.decode(self._encoding)))
                        if len(vobject_items) != 1:
                            raise RuntimeError("Content contains %d components"
                                               % len(vobject_items))
                        vobject_item = vobject_items[0]
                        check_and_sanitize_item(vobject_item, uid=uid,
                                                tag=self.get_meta("tag"))
                        cache_hash, uid, etag, text, name, tag, start, end = \
                            self._store_item_cache(
                                href, vobject_item, input_hash)
                    except Exception as e:
                        raise RuntimeError("Failed to load item %r in %r: %s" %
                                           (href, self.path, e)) from e
                    # Clean cache entries once after the data in the file
                    # system was edited externally.
                    if not self._item_cache_cleaned:
                        self._item_cache_cleaned = True
                        self._clean_item_cache()
        last_modified = time.strftime(
            "%a, %d %b %Y %H:%M:%S GMT",
            time.gmtime(os.path.getmtime(path)))
        return Item(
            self, href=href, last_modified=last_modified, etag=etag,
            text=text, item=vobject_item, uid=uid, name=name,
            component_name=tag), (tag, start, end)

    def get_multi2(self, hrefs):
        # It's faster to check for file name collissions here, because
        # we only need to call os.listdir once.
        files = None
        for href in hrefs:
            if files is None:
                # List dir after hrefs returned one item, the iterator may be
                # empty and the for-loop is never executed.
                files = os.listdir(self._filesystem_path)
            path = os.path.join(self._filesystem_path, href)
            if (not is_safe_filesystem_path_component(href) or
                    href not in files and os.path.lexists(path)):
                self.logger.debug(
                    "Can't translate name safely to filesystem: %r", href)
                yield (href, None)
            else:
                yield (href, self.get(href, verify_href=False))

    def get_all(self):
        # We don't need to check for collissions, because the the file names
        # are from os.listdir.
        return (self.get(href, verify_href=False) for href in self.list())

    def get_all_filtered(self, filters):
        tag, start, end, simple = xmlutils.simplify_prefilters(
            filters, collection_tag=self.get_meta("tag"))
        if not tag:
            # no filter
            yield from ((item, simple) for item in self.get_all())
            return
        for item, (itag, istart, iend) in (
                self._get_with_metadata(href, verify_href=False)
                for href in self.list()):
            if tag == itag and istart < end and iend > start:
                yield item, simple and (start <= istart or iend <= end)

    def upload(self, href, vobject_item):
        if not is_safe_filesystem_path_component(href):
            raise UnsafePathError(href)
        try:
            cache_hash, uid, etag, text, name, tag, _, _ = \
                self._store_item_cache(href, vobject_item)
        except Exception as e:
            raise ValueError("Failed to store item %r in collection %r: %s" %
                             (href, self.path, e)) from e
        path = path_to_filesystem(self._filesystem_path, href)
        with self._atomic_write(path, newline="") as fd:
            fd.write(text)
        # Clean the cache after the actual item is stored, or the cache entry
        # will be removed again.
        self._clean_item_cache()
        item = Item(self, href=href, etag=etag, text=text, item=vobject_item,
                    uid=uid, name=name, component_name=tag)
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
        if self._lock.locked() == "w" or self._meta_cache is None:
            try:
                try:
                    with open(self._props_path, encoding=self._encoding) as f:
                        self._meta_cache = json.load(f)
                except FileNotFoundError:
                    self._meta_cache = {}
                check_and_sanitize_props(self._meta_cache)
            except ValueError as e:
                raise RuntimeError("Failed to load properties of collection "
                                   "%r: %s" % (self.path, e)) from e
        return self._meta_cache.get(key) if key else self._meta_cache

    def set_meta_all(self, props):
        with self._atomic_write(self._props_path, "w") as f:
            json.dump(props, f, sort_keys=True)

    @property
    def last_modified(self):
        relevant_files = chain(
            (self._filesystem_path,),
            (self._props_path,) if os.path.exists(self._props_path) else (),
            (os.path.join(self._filesystem_path, h) for h in self.list()))
        last = max(map(os.path.getmtime, relevant_files))
        return time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime(last))

    @property
    def etag(self):
        # reuse cached value if the storage is read-only
        if self._lock.locked() == "w" or self._etag_cache is None:
            self._etag_cache = super().etag
        return self._etag_cache

    _lock = None

    @classmethod
    @contextmanager
    def acquire_lock(cls, mode, user=None):
        folder = os.path.expanduser(cls.configuration.get(
            "storage", "filesystem_folder"))
        if not cls._lock:
            cls._makedirs_synced(folder)
            lock_path = None
            if cls.configuration.getboolean("storage", "filesystem_locking"):
                lock_path = os.path.join(folder, ".Radicale.lock")
            close_lock_file = cls.configuration.getboolean(
                "storage", "filesystem_close_lock_file")
            cls._lock = FileBackedRwLock(lock_path, close_lock_file)
        with cls._lock.acquire_lock(mode):
            yield
            # execute hook
            hook = cls.configuration.get("storage", "hook")
            if mode == "w" and hook:
                cls.logger.debug("Running hook")
                subprocess.check_call(
                    hook % {"user": shlex.quote(user or "Anonymous")},
                    shell=True, cwd=folder)


class FileBackedRwLock:
    """A readers-Writer lock that can additionally lock a file.

    All requests are processed in FIFO order.

    """

    def __init__(self, path=None, close_lock_file=True):
        """Initilize a lock.

        ``path`` the file that is used for locking (optional)

        ``close_lock_file`` close the lock file, when unlocked and no requests
        are pending

        """
        self._path = path
        self._close_lock_file = close_lock_file

        self._lock = threading.Lock()
        self._waiters = []
        self._lock_file = None
        self._lock_file_locked = False
        self._readers = 0
        self._writer = False

    def locked(self):
        if self._writer:
            return "w"
        if self._readers:
            return "r"
        return ""

    def in_use(self):
        with self._lock:
            return self._waiters or self._readers or self._writer

    @contextmanager
    def acquire_lock(self, mode, sync_callback=None):
        def condition():
            if mode == "r":
                return not self._writer
            else:
                return not self._writer and self._readers == 0

        # Use a primitive lock which only works within one process as a
        # precondition for inter-process file-based locking
        with self._lock:
            if sync_callback:
                sync_callback()
            if self._waiters or not condition():
                # Use FIFO for access requests
                waiter = threading.Condition(lock=self._lock)
                self._waiters.append(waiter)
                while True:
                    waiter.wait()
                    if condition():
                        break
                self._waiters.pop(0)
            if mode == "r":
                self._readers += 1
                # Notify additional potential readers
                if self._waiters:
                    self._waiters[0].notify()
            else:
                self._writer = True
            if self._path and not self._lock_file_locked:
                if not self._lock_file:
                    self._lock_file = open(self._path, "w+")
                if os.name == "nt":
                    handle = msvcrt.get_osfhandle(self._lock_file.fileno())
                    flags = LOCKFILE_EXCLUSIVE_LOCK if mode == "w" else 0
                    overlapped = Overlapped()
                    if not lock_file_ex(handle, flags, 0, 1, 0, overlapped):
                        raise RuntimeError("Locking the storage failed "
                                           "(can be disabled in the config): "
                                           "%s" % ctypes.FormatError())
                elif os.name == "posix":
                    _cmd = fcntl.LOCK_EX if mode == "w" else fcntl.LOCK_SH
                    try:
                        fcntl.flock(self._lock_file.fileno(), _cmd)
                    except OSError as e:
                        raise RuntimeError("Locking the storage failed "
                                           "(can be disabled in the config): "
                                           "%s" % e) from e
                else:
                    raise RuntimeError("Locking the storage failed "
                                       "(can be disabled in the config): "
                                       "Unsupported operating system")
                self._lock_file_locked = True
        try:
            yield
        finally:
            with self._lock:
                if mode == "r":
                    self._readers -= 1
                else:
                    self._writer = False
                if self._lock_file_locked and self._readers == 0:
                    if os.name == "nt":
                        handle = msvcrt.get_osfhandle(self._lock_file.fileno())
                        overlapped = Overlapped()
                        if not unlock_file_ex(handle, 0, 1, 0, overlapped):
                            raise RuntimeError("Unlocking the storage failed: "
                                               "%s" % ctypes.FormatError())
                    elif os.name == "posix":
                        try:
                            fcntl.flock(self._lock_file.fileno(),
                                        fcntl.LOCK_UN)
                        except OSError as e:
                            raise RuntimeError("Unlocking the storage failed: "
                                               "%s" % e) from e
                    else:
                        raise RuntimeError("Unlocking the storage failed: "
                                           "Unsupported operating system")
                    if self._close_lock_file and not self._waiters:
                        self._lock_file.close()
                        self._lock_file = None
                    self._lock_file_locked = False
                if self._waiters:
                    self._waiters[0].notify()
