# This file is part of Radicale - CalDAV and CardDAV server
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

import errno
import os
import posixpath
import sys
import threading
from tempfile import TemporaryDirectory
from typing import Iterator, Type, Union

from radicale import storage, types

if sys.platform == "win32":
    import ctypes
    import ctypes.wintypes
    import msvcrt

    LOCKFILE_EXCLUSIVE_LOCK: int = 2
    ULONG_PTR: Union[Type[ctypes.c_uint32], Type[ctypes.c_uint64]]
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

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    lock_file_ex = kernel32.LockFileEx
    lock_file_ex.argtypes = [
        ctypes.wintypes.HANDLE,
        ctypes.wintypes.DWORD,
        ctypes.wintypes.DWORD,
        ctypes.wintypes.DWORD,
        ctypes.wintypes.DWORD,
        ctypes.POINTER(Overlapped)]
    lock_file_ex.restype = ctypes.wintypes.BOOL
    unlock_file_ex = kernel32.UnlockFileEx
    unlock_file_ex.argtypes = [
        ctypes.wintypes.HANDLE,
        ctypes.wintypes.DWORD,
        ctypes.wintypes.DWORD,
        ctypes.wintypes.DWORD,
        ctypes.POINTER(Overlapped)]
    unlock_file_ex.restype = ctypes.wintypes.BOOL
else:
    import fcntl

if sys.platform == "linux":
    import ctypes

    RENAME_EXCHANGE: int = 2
    renameat2 = None
    try:
        renameat2 = ctypes.CDLL(None, use_errno=True).renameat2
    except AttributeError:
        pass
    else:
        renameat2.argtypes = [
            ctypes.c_int, ctypes.c_char_p,
            ctypes.c_int, ctypes.c_char_p,
            ctypes.c_uint]
        renameat2.restype = ctypes.c_int

if sys.platform == "darwin":
    # Definition missing in PyPy
    F_FULLFSYNC: int = getattr(fcntl, "F_FULLFSYNC", 51)


class RwLock:
    """A readers-Writer lock that locks a file."""

    _path: str
    _readers: int
    _writer: bool
    _lock: threading.Lock

    def __init__(self, path: str) -> None:
        self._path = path
        self._readers = 0
        self._writer = False
        self._lock = threading.Lock()

    @property
    def locked(self) -> str:
        with self._lock:
            if self._readers > 0:
                return "r"
            if self._writer:
                return "w"
            return ""

    @types.contextmanager
    def acquire(self, mode: str) -> Iterator[None]:
        if mode not in "rw":
            raise ValueError("Invalid mode: %r" % mode)
        with open(self._path, "w+") as lock_file:
            if sys.platform == "win32":
                handle = msvcrt.get_osfhandle(lock_file.fileno())
                flags = LOCKFILE_EXCLUSIVE_LOCK if mode == "w" else 0
                overlapped = Overlapped()
                try:
                    if not lock_file_ex(handle, flags, 0, 1, 0, overlapped):
                        raise ctypes.WinError()
                except OSError as e:
                    raise RuntimeError("Locking the storage failed: %s" % e
                                       ) from e
            else:
                _cmd = fcntl.LOCK_EX if mode == "w" else fcntl.LOCK_SH
                try:
                    fcntl.flock(lock_file.fileno(), _cmd)
                except OSError as e:
                    raise RuntimeError("Locking the storage failed: %s" % e
                                       ) from e
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


def rename_exchange(src: str, dst: str) -> None:
    """Exchange the files or directories `src` and `dst`.

    Both `src` and `dst` must exist but may be of different types.

    On Linux with renameat2 the operation is atomic.
    On other platforms it's not atomic.

    """
    src_dir, src_base = os.path.split(src)
    dst_dir, dst_base = os.path.split(dst)
    src_dir = src_dir or os.curdir
    dst_dir = dst_dir or os.curdir
    if not src_base or not dst_base:
        raise ValueError("Invalid arguments: %r -> %r" % (src, dst))
    if sys.platform == "linux" and renameat2:
        src_base_bytes = os.fsencode(src_base)
        dst_base_bytes = os.fsencode(dst_base)
        src_dir_fd = os.open(src_dir, 0)
        try:
            dst_dir_fd = os.open(dst_dir, 0)
            try:
                if renameat2(src_dir_fd, src_base_bytes,
                             dst_dir_fd, dst_base_bytes,
                             RENAME_EXCHANGE) == 0:
                    return
                errno_ = ctypes.get_errno()
                # Fallback if RENAME_EXCHANGE not supported by filesystem
                if errno_ != errno.EINVAL:
                    raise OSError(errno_, os.strerror(errno_))
            finally:
                os.close(dst_dir_fd)
        finally:
            os.close(src_dir_fd)
    with TemporaryDirectory(prefix=".Radicale.tmp-", dir=src_dir
                            ) as tmp_dir:
        os.rename(dst, os.path.join(tmp_dir, "interim"))
        os.rename(src, dst)
        os.rename(os.path.join(tmp_dir, "interim"), src)


def fsync(fd: int) -> None:
    if sys.platform == "darwin":
        try:
            fcntl.fcntl(fd, F_FULLFSYNC)
            return
        except OSError as e:
            # Fallback if F_FULLFSYNC not supported by filesystem
            if e.errno != errno.EINVAL:
                raise
    os.fsync(fd)


def strip_path(path: str) -> str:
    assert sanitize_path(path) == path
    return path.strip("/")


def unstrip_path(stripped_path: str, trailing_slash: bool = False) -> str:
    assert strip_path(sanitize_path(stripped_path)) == stripped_path
    assert stripped_path or trailing_slash
    path = "/%s" % stripped_path
    if trailing_slash and not path.endswith("/"):
        path += "/"
    return path


def sanitize_path(path: str) -> str:
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


def is_safe_path_component(path: str) -> bool:
    """Check if path is a single component of a path.

    Check that the path is safe to join too.

    """
    return bool(path) and "/" not in path and path not in (".", "..")


def is_safe_filesystem_path_component(path: str) -> bool:
    """Check if path is a single component of a local and posix filesystem
       path.

    Check that the path is safe to join too.

    """
    return (
        bool(path) and not os.path.splitdrive(path)[0] and
        (sys.platform != "win32" or ":" not in path) and  # Block NTFS-ADS
        not os.path.split(path)[0] and path not in (os.curdir, os.pardir) and
        not path.startswith(".") and not path.endswith("~") and
        is_safe_path_component(path))


def path_to_filesystem(root: str, sane_path: str) -> str:
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
                part not in (e.name for e in os.scandir(safe_path_parent))):
            raise CollidingPathError(part)
    return safe_path


class UnsafePathError(ValueError):

    def __init__(self, path: str) -> None:
        super().__init__("Can't translate name safely to filesystem: %r" %
                         path)


class CollidingPathError(ValueError):

    def __init__(self, path: str) -> None:
        super().__init__("File name collision: %r" % path)


def name_from_path(path: str, collection: "storage.BaseCollection") -> str:
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
