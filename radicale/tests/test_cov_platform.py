# This file is part of Radicale - CalDAV and CardDAV server
# Copyright © 2026-2026 oliviasculley <olivia@sculley.dev>
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

"""Outcome tests for platform-specific imports and small support branches.

These paths are real code, but this host is 64-bit Linux on Python 3.14, so
the Windows, macOS, and pre-3.13 branches do not run unless the process looks
like that platform for one reload.
"""

import contextlib
import ctypes
import ctypes.wintypes
import errno
import importlib
import importlib.abc
import io
import json
import logging
import os
import pathlib
import signal
import sys
import types
from typing import Any, Callable, List, Optional, Union

import pytest

import radicale.__main__ as main
from radicale import VERSION, config, httputils, log, pathutils
from radicale import types as radicale_types
from radicale import utils, xmlutils
from radicale.log import logger


class _WinFunc:
    """Stand-in for a ``ctypes`` function loaded from ``kernel32``."""

    def __init__(self, fn: Callable[..., int]) -> None:
        self._fn = fn
        self.argtypes: Optional[list] = None
        self.restype: Any = None
        self.calls: List[tuple] = []

    def __call__(self, *args: Any) -> int:
        self.calls.append(args)
        return self._fn(*args)


class _WinDLL:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.LockFileEx = _WinFunc(lambda *_args: 0 if _WinDLL.fail else 1)
        self.UnlockFileEx = _WinFunc(lambda *_args: 1)

    fail = False


def _win_error(code: int = 0, descr: str = "win error") -> OSError:
    return OSError(code, descr)


@contextlib.contextmanager
def _windows_pathutils(pointer_bytes: int):
    """Reload ``pathutils`` as Windows and restore the Linux module."""
    real_sizeof = ctypes.sizeof

    def sizeof(obj: Any) -> int:
        if obj is ctypes.c_void_p:
            return pointer_bytes
        return real_sizeof(obj)

    msvcrt = types.ModuleType("msvcrt")
    msvcrt.get_osfhandle = lambda fd: fd  # type: ignore[attr-defined]
    saved_platform = sys.platform
    saved_msvcrt = sys.modules.get("msvcrt")
    saved_handle = ctypes.wintypes.HANDLE
    had_windll = hasattr(ctypes, "WinDLL")
    had_winerror = hasattr(ctypes, "WinError")
    saved_windll = getattr(ctypes, "WinDLL", None)
    saved_winerror = getattr(ctypes, "WinError", None)
    sys.modules["msvcrt"] = msvcrt
    sys.platform = "win32"
    ctypes.sizeof = sizeof  # type: ignore[assignment]
    ctypes.WinDLL = _WinDLL  # type: ignore[attr-defined]
    ctypes.WinError = _win_error  # type: ignore[attr-defined]
    # A 32-bit overlapped record uses a 32-bit handle. The host pointer type
    # stays 64-bit, so the structure would otherwise mix the two widths.
    if pointer_bytes == 4:
        ctypes.wintypes.HANDLE = ctypes.c_uint32  # type: ignore[misc, assignment]
    _WinDLL.fail = False
    try:
        importlib.reload(pathutils)
        yield pathutils
    finally:
        sys.platform = saved_platform
        ctypes.sizeof = real_sizeof  # type: ignore[assignment]
        ctypes.wintypes.HANDLE = saved_handle
        if had_windll:
            ctypes.WinDLL = saved_windll  # type: ignore[attr-defined]
        else:
            del ctypes.WinDLL  # type: ignore[attr-defined]
        if had_winerror:
            ctypes.WinError = saved_winerror  # type: ignore[attr-defined]
        else:
            del ctypes.WinError  # type: ignore[attr-defined]
        if saved_msvcrt is None:
            sys.modules.pop("msvcrt", None)
        else:
            sys.modules["msvcrt"] = saved_msvcrt
        importlib.reload(pathutils)


def test_missing_filesystem_component_is_not_created(tmp_path):
    """A name that is not on disk is joined and left uncreated.

    An existing parent with a missing child is the same class of path: the
    collision scan does not treat absence as a collision. Marking the path
    collision-free skips that scan and still creates nothing.
    """
    parent = tmp_path / "parent"
    parent.mkdir()
    missing = pathutils.path_to_filesystem(str(tmp_path), "parent/child")
    assert missing == os.path.join(str(tmp_path), "parent", "child")
    assert os.path.isdir(parent)
    assert not os.path.exists(missing)

    skipped = pathutils.path_to_filesystem(
        str(tmp_path), "parent/other", path_is_collision_free=True)
    assert skipped == os.path.join(str(tmp_path), "parent", "other")
    assert not os.path.exists(skipped)


def test_windows_file_lock_reports_shared_exclusive_and_failure(tmp_path):
    """Windows locks use shared flags for readers and exclusive flags for writers.

    A lock that the system refuses becomes the same storage-lock error the
    caller sees on other platforms. A 32-bit pointer width selects the
    32-bit overlapped field; this host's width selects the 64-bit field.
    """
    lock_path = tmp_path / "storage.lock"
    lock_path.write_text("")

    with _windows_pathutils(8) as win_pathutils:
        assert win_pathutils.ULONG_PTR is ctypes.c_uint64
        lock = win_pathutils.RwLock(str(lock_path))
        kernel_lock = win_pathutils.lock_file_ex
        with lock.acquire("r"):
            assert lock.locked == "r"
        assert kernel_lock.calls[-1][1] == 0
        assert lock.locked == ""

        with lock.acquire("w"):
            assert lock.locked == "w"
        assert kernel_lock.calls[-1][1] == win_pathutils.LOCKFILE_EXCLUSIVE_LOCK
        assert lock.locked == ""

        _WinDLL.fail = True
        with pytest.raises(RuntimeError, match="Locking the storage failed"):
            with lock.acquire("w"):
                pass
        assert lock.locked == ""

    with _windows_pathutils(4) as win32_pathutils:
        assert win32_pathutils.ULONG_PTR is ctypes.c_uint32
        narrow = win32_pathutils.RwLock(str(lock_path))
        with narrow.acquire("r"):
            assert narrow.locked == "r"
        assert narrow.locked == ""

    # The Linux module is back: a shared lock still reports a reader.
    restored = pathutils.RwLock(str(lock_path))
    with restored.acquire("r"):
        assert restored.locked == "r"


def test_darwin_full_fsync_keeps_the_written_bytes(tmp_path):
    """macOS asks for a full fsync and still leaves the written bytes in place.

    This host has no ``F_FULLFSYNC`` command. The fallback is the portable
    fsync, and the file contents are the caller's evidence that it happened.
    """
    target = tmp_path / "item.ics"
    fd = os.open(str(target), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        os.write(fd, b"BEGIN:VCALENDAR")
        saved = sys.platform
        saved_fcntl = sys.modules.get("fcntl")
        sys.platform = "darwin"
        try:
            if saved_fcntl is None:
                # Windows has no fcntl module. A missing full-fsync command
                # is the EINVAL that sends fsync to os.fsync.
                fake = types.ModuleType("fcntl")

                def _no_full(_fd, _cmd):
                    raise OSError(errno.EINVAL, "no fullfsync")

                fake.fcntl = _no_full  # type: ignore[attr-defined]
                sys.modules["fcntl"] = fake
            importlib.reload(pathutils)
            assert pathutils.F_FULLFSYNC == 51
            pathutils.fsync(fd)
        finally:
            sys.platform = saved
            if saved_fcntl is None:
                sys.modules.pop("fcntl", None)
            else:
                sys.modules["fcntl"] = saved_fcntl
            importlib.reload(pathutils)
        os.lseek(fd, 0, os.SEEK_SET)
        assert os.read(fd, 100) == b"BEGIN:VCALENDAR"
    finally:
        os.close(fd)


def test_python38_web_resource_serves_index_and_misses_unknown_names():
    """The pre-3.9 resource loader still serves the shipped web index.

    A name that is not in that directory is a 404 from the same loader.
    """
    web_dir = os.path.join(os.path.dirname(httputils.__file__), "web", "internal_data")
    assert os.path.isfile(os.path.join(web_dir, "index.html"))

    pkg = types.ModuleType("pkg_resources")

    def resource_filename(package: str, resource: str) -> str:
        assert package == "radicale.web"
        assert resource == "internal_data"
        return web_dir

    pkg.resource_filename = resource_filename  # type: ignore[attr-defined]
    saved_version = sys.version_info
    saved_pkg = sys.modules.get("pkg_resources")
    sys.modules["pkg_resources"] = pkg
    try:
        sys.version_info = (3, 8, 20, "final", 0)  # type: ignore[assignment]
        importlib.reload(httputils)
        assert httputils._TRAVERSABLE_LIKE_TYPE is pathlib.Path
        status, headers, body, encoding = httputils.serve_resource(
            "radicale.web", "internal_data", "", "/.web/")
        assert status == 200
        assert encoding is None
        assert dict(headers)["Content-Type"] == "text/html"
        assert b"Radicale Web Interface" in body
        status, _headers, missing, _encoding = httputils.serve_resource(
            "radicale.web", "internal_data", "", "/.web/no-such-file.txt")
        assert status == 404
        assert missing == "The requested resource could not be found."
    finally:
        sys.version_info = saved_version
        if saved_pkg is None:
            sys.modules.pop("pkg_resources", None)
        else:
            sys.modules["pkg_resources"] = saved_pkg
        importlib.reload(httputils)


def test_python312_traversable_alias_still_serves_stylesheet():
    """Python 3.9 through 3.12 name the traversable type from ``importlib.abc``.

    Serving a real stylesheet shows the reloaded helper still reads the
    shipped tree. The alias is the 3.12 union, not the 3.13 one.
    """
    if not hasattr(importlib.abc, "Traversable"):
        # Python 3.13 moved the name. 3.9 and 3.10 have no resources.abc package.
        import importlib.resources.abc as resources_abc
        importlib.abc.Traversable = resources_abc.Traversable  # type: ignore[attr-defined]
        remove_alias = True
    else:
        remove_alias = False
    saved_version = sys.version_info
    try:
        sys.version_info = (3, 12, 0, "final", 0)  # type: ignore[assignment]
        importlib.reload(httputils)
        assert httputils._TRAVERSABLE_LIKE_TYPE == Union[
            importlib.abc.Traversable, pathlib.Path]
        status, headers, body, _encoding = httputils.serve_resource(
            "radicale.web", "internal_data", "", "/.web/css/main.css")
        assert status == 200
        assert dict(headers)["Content-Type"] == "text/css"
        assert b"--body-bg-color" in body
    finally:
        sys.version_info = saved_version
        importlib.reload(httputils)
        if remove_alias:
            del importlib.abc.Traversable  # type: ignore[attr-defined]


def test_windows_identity_string_does_not_use_the_passwd_database(monkeypatch):
    """On Windows the process identity is the login name and not a group list.

    The Unix build imports ``pwd`` and ``grp``. The Windows build does not,
    and the returned string has no ``groups=`` field.
    """
    saved = sys.platform
    try:
        monkeypatch.setattr(sys, "platform", "win32")
        utils.__dict__.pop("pwd", None)
        utils.__dict__.pop("grp", None)
        importlib.reload(utils)
        assert not hasattr(utils, "pwd")
        assert not hasattr(utils, "grp")
        monkeypatch.setattr(utils.os, "getlogin", lambda: "cov-user")
        assert utils.user_groups_as_string() == "user=cov-user"
    finally:
        sys.platform = saved
        importlib.reload(utils)
    identity = utils.user_groups_as_string()
    assert identity.startswith("user=")
    if sys.platform == "win32":
        assert identity == "user=cov-user"
        assert "groups=" not in identity
    else:
        assert "groups=" in identity
        assert "cov-user" not in identity


def test_windows_break_signal_exits_and_hangup_stays_untouched(monkeypatch):
    """``SIGBREAK`` is the Windows shutdown signal and requests process exit.

    ``SIGHUP`` is not in that set. ``--version`` still prints the version and
    exits 0 after the handlers are installed.
    """
    on_windows = sys.platform == "win32"
    if not on_windows:
        # This process has no SIGBREAK. Point that name at a real signal so
        # the Windows handler can be installed here.
        monkeypatch.setattr(signal, "SIGBREAK", signal.SIGUSR1, raising=False)
    monkeypatch.setattr(sys, "platform", "win32")
    watched = [signal.SIGTERM, signal.SIGINT, signal.SIGBREAK]
    if not on_windows:
        watched.append(signal.SIGHUP)
    saved_signals = {number: signal.getsignal(number) for number in watched}
    saved_factory = logging.getLogRecordFactory()
    saved_level = logger.level
    saved_filters = list(logger.filters)
    saved_argv = sys.argv
    stdout = io.StringIO()
    sys.argv = ["radicale", "--version"]
    try:
        with contextlib.redirect_stdout(stdout):
            try:
                main.run()
            except SystemExit as exc:
                code = 0 if exc.code is None else exc.code
            else:
                code = 0
        assert code == 0
        assert VERSION in stdout.getvalue()
        if not on_windows:
            assert signal.getsignal(signal.SIGHUP) is saved_signals[signal.SIGHUP]
        handler = signal.getsignal(signal.SIGBREAK)
        assert callable(handler)
        with pytest.raises(SystemExit) as caught:
            handler(signal.SIGBREAK, None)
        assert caught.value.code == 1
    finally:
        sys.argv = saved_argv
        for number, previous in saved_signals.items():
            signal.signal(number, previous)
        logging.setLogRecordFactory(saved_factory)
        logger.setLevel(saved_level)
        for installed in list(logger.filters):
            logger.removeFilter(installed)
        for installed in saved_filters:
            logger.addFilter(installed)


def test_clark_notation_rejects_an_empty_namespace_or_name():
    """A Clark tag needs both a namespace and a local name.

    A complete tag is returned unchanged. Empty on either side is invalid.
    """
    assert xmlutils.make_clark("{DAV:}href") == "{DAV:}href"
    with pytest.raises(ValueError, match="Invalid XML tag"):
        xmlutils.make_clark("{}href")
    with pytest.raises(ValueError, match="Invalid XML tag"):
        xmlutils.make_clark("{DAV:}")


def test_log_condition_value_before_match_and_unknown_type():
    """The value entry is checked even when it appears before the match entry.

    An IP match that is neither an address operator nor a network operator is
    still rejected for the match name. An unknown token type does not invent
    a value error; a missing match entry is an incomplete condition.
    """
    parsed = config.json_str_condition(json.dumps(
        {"host": {"value": "192.0.2.1", "match": "equal"}}))
    assert parsed["host"] == {"value": "192.0.2.1", "match": "equal"}

    parsed = config.json_str_condition(json.dumps(
        {"host": {"value": "192.0.2.0/24", "match": "included"}}))
    assert parsed["host"]["value"] == "192.0.2.0/24"

    with pytest.raises(ValueError, match="unsupported log match: 'nope'"):
        config.json_str_condition(json.dumps(
            {"host": {"value": "192.0.2.1", "match": "nope"}}))

    log.LOG_CONDITION_TOKEN["weird"] = "other"
    try:
        with pytest.raises(ValueError, match="incomplete condition"):
            config.json_str_condition(json.dumps({"weird": {"value": "kept"}}))
    finally:
        del log.LOG_CONDITION_TOKEN["weird"]


def test_excluded_address_boundary_does_not_require_debug(caplog):
    """An address outside an excluded network passes; one inside does not.

    The network itself is inside the exclusion. Debug being off does not
    change those answers and does not emit the pass trace.
    """
    saved = logger.level
    logger.setLevel(logging.ERROR)
    try:
        caplog.clear()
        outside = log.log_conditional(
            "gate",
            {"host": {"match": "excluded", "value": "192.0.2.0/24"}},
            {"host": "198.51.100.10/32"})
        inside = log.log_conditional(
            "gate",
            {"host": {"match": "excluded", "value": "192.0.2.0/24"}},
            {"host": "192.0.2.10/32"})
        edge = log.log_conditional(
            "gate",
            {"host": {"match": "excl", "value": "192.0.2.0/24"}},
            {"host": "192.0.2.0/24"})
    finally:
        logger.setLevel(saved)
    assert outside is True
    assert inside is False
    assert edge is False
    assert "ip/PASSED" not in caplog.text
    assert "ip/CHECK" not in caplog.text


def test_error_stream_protocol_methods_return_ellipsis():
    """The error-stream protocol methods are callable and return nothing."""
    stream = object()
    assert radicale_types.ErrorStream.flush(stream) is None
    assert radicale_types.ErrorStream.write(stream, "line") is None
