# This file is part of Radicale Server - Calendar Server
# Copyright © 2014 Jean-Marc Martins
# Copyright © 2012-2017 Guillaume Ayoub
# Copyright © 2017-2018 Unrud <unrud@outlook.com>
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
Helper functions for working with the file system.

"""

import contextlib
import os
import posixpath
import threading

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


class RwLock:
    """A readers-Writer lock that locks a file."""

    def __init__(self, path):
        self._path = path
        self._readers = 0
        self._writer = False
        self._lock = threading.Lock()

    @property
    def locked(self):
        with self._lock:
            if self._readers > 0:
                return "r"
            if self._writer:
                return "w"
            return ""

    @contextlib.contextmanager
    def acquire(self, mode):
        if mode not in "rw":
            raise ValueError("Invalid mode: %r" % mode)
        with open(self._path, "w+") as lock_file:
            if os.name == "nt":
                handle = msvcrt.get_osfhandle(lock_file.fileno())
                flags = LOCKFILE_EXCLUSIVE_LOCK if mode == "w" else 0
                overlapped = Overlapped()
                if not lock_file_ex(handle, flags, 0, 1, 0, overlapped):
                    raise RuntimeError("Locking the storage failed: %s" %
                                       ctypes.FormatError())
            elif os.name == "posix":
                _cmd = fcntl.LOCK_EX if mode == "w" else fcntl.LOCK_SH
                try:
                    fcntl.flock(lock_file.fileno(), _cmd)
                except OSError as e:
                    raise RuntimeError("Locking the storage failed: %s" %
                                       e) from e
            else:
                raise RuntimeError("Locking the storage failed: "
                                   "Unsupported operating system")
            with self._lock:
                if self._writer or mode == "w" and self._readers != 0:
                    raise RuntimeError("Locking the storage failed: "
                                       "Guarantees failed")
                if mode == "r":
                    self._readers += 1
                else:
                    self._writer = True
            try:
                yield
            finally:
                with self._lock:
                    if mode == "r":
                        self._readers -= 1
                    self._writer = False


def fsync(fd):
    if os.name == "posix" and hasattr(fcntl, "F_FULLFSYNC"):
        fcntl.fcntl(fd, fcntl.F_FULLFSYNC)
    else:
        os.fsync(fd)


def strip_path(path):
    assert sanitize_path(path) == path
    return path.strip("/")


def unstrip_path(stripped_path, trailing_slash=False):
    assert strip_path(sanitize_path(stripped_path)) == stripped_path
    assert stripped_path or trailing_slash
    path = "/%s" % stripped_path
    if trailing_slash and not path.endswith("/"):
        path += "/"
    return path


def sanitize_path(path):
    """Make path absolute with leading slash to prevent access to other data.

    Preserve potential trailing slash.

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


def path_to_filesystem(root, sane_path):
    """Convert `sane_path` to a local filesystem path relative to `root`.

    `root` must be a secure filesystem path, it will be prepend to the path.

    `sane_path` must be a sanitized path without leading or trailing ``/``.

    Conversion of `sane_path` is done in a secure manner,
    or raises ``ValueError``.

    """
    assert sane_path == strip_path(sanitize_path(sane_path))
    safe_path = root
    parts = sane_path.split("/") if sane_path else []
    for part in parts:
        if not is_safe_filesystem_path_component(part):
            raise UnsafePathError(part)
        safe_path_parent = safe_path
        safe_path = os.path.join(safe_path, part)
        # Check for conflicting files (e.g. case-insensitive file systems
        # or short names on Windows file systems)
        if (os.path.lexists(safe_path) and
                part not in (e.name for e in
                             os.scandir(safe_path_parent))):
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


def name_from_path(path, collection):
    """Return Radicale item name from ``path``."""
    assert sanitize_path(path) == path
    start = unstrip_path(collection.path, True)
    if not (path + "/").startswith(start):
        raise ValueError("%r doesn't start with %r" % (path, start))
    name = path[len(start):]
    if name and not is_safe_path_component(name):
        raise ValueError("%r is not a component in collection %r" %
                         (name, collection.path))
    return name
