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

"""Outcome tests for storing, moving, and caching collection items."""

import builtins
import errno
import http.client
import io
import logging
import os
import pathlib
import pickle
import signal
import socket
import subprocess
import sys
import threading
import time
import xml.etree.ElementTree as ET
from types import SimpleNamespace
from typing import List, Optional

import pytest

import radicale
from radicale import config
from radicale import item as radicale_item
from radicale import log, pathutils, storage, xmlutils
from radicale.log import logger
from radicale.storage import multifilesystem, multifilesystem_nolock
from radicale.storage.multifilesystem import base as storage_base
from radicale.tests.helpers import get_file_content

EVENT_ICS = get_file_content("event1.ics")
CONTACT_VCF = get_file_content("contact1.vcf")
# Unsupported protocol version. CPython and PyPy both raise ValueError,
# which these loaders already treat as a damaged file. An unknown opcode
# is UnpicklingError on CPython and KeyError on PyPy.
_DAMAGED_PICKLE = b"\x80\xff"


def _suite_log_level():
    """Level the suite asked for. A previous module may have left ERROR."""
    name = os.environ.get("PYTEST_RADICALE_LOGLEVEL", "debug")
    return getattr(logging, name.upper())


@pytest.fixture(autouse=True)
def _restore_process_state():
    saved_tokens = dict(log.LOG_CONDITION_TOKEN)
    saved_schema = set(config.DEFAULT_CONFIG_SCHEMA)
    saved = {
        "disabled": log.logger_display_backtrace_disabled,
        "enabled": log.logger_display_backtrace_enabled,
        "filters": list(logger.filters),
        "app": radicale._application_instance,
        "app_path": radicale._application_config_path,
    }
    logging.disable(logging.NOTSET)
    logger.setLevel(_suite_log_level())
    yield
    logging.disable(logging.NOTSET)
    logger.setLevel(_suite_log_level())
    log.logger_display_backtrace_disabled = saved["disabled"]
    log.logger_display_backtrace_enabled = saved["enabled"]
    for filt in list(logger.filters):
        if filt not in saved["filters"]:
            logger.removeFilter(filt)
    radicale._application_instance = saved["app"]
    radicale._application_config_path = saved["app_path"]
    for key in list(config.DEFAULT_CONFIG_SCHEMA):
        if key not in saved_schema:
            del config.DEFAULT_CONFIG_SCHEMA[key]
    log.LOG_CONDITION_TOKEN.clear()
    log.LOG_CONDITION_TOKEN.update(saved_tokens)


def _silence_traces(monkeypatch):
    """Return messages ``logger.trace`` would emit while debug is disabled."""
    calls: List[str] = []
    logger.setLevel(logging.ERROR)

    def trace(msg, *args, **kwargs):
        calls.append(msg % args if args else msg)

    monkeypatch.setattr(logger, "trace", trace)
    return calls


def _configuration(folder, updates=None):
    configuration = config.load()
    configuration.update({
        "storage": {"filesystem_folder": str(folder), "filesystem_fsync": False},
        "auth": {"delay": "0.001"},
    }, "test", privileged=True)
    if updates:
        configuration.update(updates, "test", privileged=True)
    return configuration


def _storage(folder, updates=None):
    return storage.load(_configuration(folder, updates))


def _event(uid="event1", summary="Event", with_tz=True, tzid=True):
    tz = ""
    if with_tz:
        tzid_line = "TZID:Europe/Paris\r\n" if tzid else ""
        tz = (
            "BEGIN:VTIMEZONE\r\n%sBEGIN:STANDARD\r\n"
            "DTSTART:19701101T020000\r\nTZOFFSETFROM:+0200\r\n"
            "TZOFFSETTO:+0100\r\nTZNAME:CET\r\nEND:STANDARD\r\n"
            "END:VTIMEZONE\r\n" % tzid_line)
    text = (
        "BEGIN:VCALENDAR\r\nVERSION:2.0\r\n%s"
        "BEGIN:VEVENT\r\nUID:%s\r\nSUMMARY:%s\r\n"
        "DTSTART:20130901T160000Z\r\nDTEND:20130901T170000Z\r\n"
        "END:VEVENT\r\nEND:VCALENDAR\r\n" % (tz, uid, summary))
    return radicale_item.Item(collection_path="", text=text)


def _contact(uid="contact1", bday=None):
    extra = ("BDAY:%s\r\n" % bday) if bday else ""
    text = (
        "BEGIN:VCARD\r\nVERSION:3.0\r\nUID:%s\r\nFN:Contact\r\n%s"
        "END:VCARD\r\n" % (uid, extra))
    return radicale_item.Item(collection_path="", text=text)


def _free_port():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]
    finally:
        sock.close()


def _http_get(port, path="/", timeout=5):
    last: Optional[BaseException] = None
    for _ in range(50):
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
        try:
            conn.request("GET", path)
            resp = conn.getresponse()
            return resp.status, resp.read()
        except (ConnectionRefusedError, ConnectionResetError, socket.timeout, OSError) as exc:
            last = exc
            time.sleep(0.05)
        finally:
            conn.close()
    raise AssertionError("server did not answer: %s" % last)


class _CollectionPath:
    def __init__(self, path):
        self.path = path


# --- types, web, group, rights ----------------------------------------------


# --- xml, http ----------------------------------------------------------------


def _propupdate(*children):
    root = ET.Element(xmlutils.make_clark("D:propertyupdate"))
    for child in children:
        root.append(child)
    return root


def _set_or_remove(kind, prop):
    element = ET.Element(xmlutils.make_clark("D:" + kind))
    holder = ET.SubElement(element, xmlutils.make_clark("D:prop"))
    holder.append(prop)
    return element


class _Node:
    def __init__(self, name, data=b"", children=None, directory=False):
        self.name = name
        self._data = data
        self._children = children or {}
        self._directory = directory

    def is_dir(self):
        return self._directory

    def is_file(self):
        return not self._directory

    def iterdir(self):
        return list(self._children.values())

    def joinpath(self, part):
        return self._children[part]

    def read_bytes(self):
        return self._data


# --- pathutils, utils ---------------------------------------------------------


# --- log, config, package init, main -----------------------------------------


def _run_cli(args):
    from radicale import __main__ as main
    saved = {number: signal.getsignal(number) for number in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP, signal.SIGQUIT)}
    saved_argv = sys.argv
    sys.argv = ["radicale", *args]
    try:
        try:
            main.run()
        except SystemExit as exc:
            return 0 if exc.code is None else exc.code
        return 0
    finally:
        sys.argv = saved_argv
        for number, handler in saved.items():
            signal.signal(number, handler)


# --- storage ----------------------------------------------------------------


def _capture_traces(monkeypatch):
    calls: List[str] = []
    logger.setLevel(logging.DEBUG)

    def trace(msg, *args, **kwargs):
        try:
            calls.append(msg % args if args else msg)
        except Exception:
            calls.append(str(msg))

    monkeypatch.setattr(logger, "trace", trace)
    return calls


def _record_debug(monkeypatch):
    calls: List[str] = []

    def debug(msg, *args, **kwargs):
        try:
            calls.append(msg % args if args else str(msg))
        except Exception:
            calls.append(str(msg))

    monkeypatch.setattr(logger, "debug", debug)
    return calls


def _time_filters(start, end):
    filt = ET.Element(xmlutils.make_clark("C:filter"))
    comp = ET.SubElement(filt, xmlutils.make_clark("C:comp-filter"))
    comp.set("name", "VCALENDAR")
    rng = ET.SubElement(comp, xmlutils.make_clark("C:time-range"))
    rng.set("start", start)
    rng.set("end", end)
    return [filt]


def _patch_mtime_delta(monkeypatch, delta):
    real_stat = multifilesystem.os.stat
    state = {"n": 0, "base": 0}

    def fake_stat(path, *args, **kwargs):
        result = real_stat(path, *args, **kwargs)
        if not str(path).endswith(".Radicale.mtime_test"):
            return result
        state["n"] += 1
        if state["n"] == 1:
            state["base"] = result.st_mtime_ns
            return result
        return SimpleNamespace(st_mtime_ns=state["base"] + delta)

    monkeypatch.setattr(multifilesystem.os, "stat", fake_stat)


def _calendar(storage_, href="/user/cal/", items=None, props=None):
    if props is None:
        props = {"tag": "VCALENDAR"}
    with storage_.acquire_lock("w"):
        return storage_.create_collection(href, items=items, props=props)


def test_win32_skips_umask_and_case_insensitive_group_folder(tmp_path, monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    monkeypatch.setattr(multifilesystem.sys, "platform", "win32")
    created = _storage(tmp_path / "win", {"storage": {"folder_umask": "zz"}})
    assert os.path.isdir(created._filesystem_folder)
    assert "folder umask defined but invalid" not in caplog.text

    caplog.clear()
    monkeypatch.undo()
    monkeypatch.setattr(
        multifilesystem.pathutils, "path_is_collision_free_case_sensitive",
        lambda _path: False)
    disabled = _storage(tmp_path / "groups", {"group": {"group_collections_folder": "Groups"}})
    assert disabled._group_collections_folder == ""
    assert "Group collections folder disabled" in caplog.text

    caplog.clear()
    kept = _storage(tmp_path / "empty-group", {"group": {"group_collections_folder": ""}})
    assert kept._group_collections_folder == ""
    assert "Group collections folder disabled" not in caplog.text


def test_cache_folders_fsync_and_makedirs_failures(tmp_path, monkeypatch, caplog):
    caplog.set_level(logging.ERROR)
    cache_root = tmp_path / "cache"
    storage_ = _storage(tmp_path / "store", {"storage": {
        "filesystem_cache_folder": str(cache_root),
        "use_cache_subfolder_for_item": "True",
        "use_cache_subfolder_for_history": "True",
        "use_cache_subfolder_for_synctoken": "True",
    }})
    _calendar(storage_, items=[_event()])
    collection = next(item for item in storage_.discover("/user/cal/")
                      if isinstance(item, storage.BaseCollection))
    with storage_.acquire_lock("w"):
        token, changes = collection.sync()
    assert token.startswith("http://radicale.org/ns/sync/")
    assert changes
    names = [path.name for path in cache_root.rglob("*") if path.is_file()]
    assert "event1.ics" in names
    assert any(len(name) == 64 for name in names)
    assert (cache_root / "collection-cache").is_dir()
    assert not (pathlib.Path(collection._filesystem_path) / ".Radicale.cache").exists()

    storage_._filesystem_fsync = True

    def fail_fsync(_fd):
        raise OSError(errno.EIO, "fsync")

    monkeypatch.setattr(storage_base.pathutils, "fsync", fail_fsync)
    handle = io.BytesIO()
    handle.name = "item.ics"
    with pytest.raises(RuntimeError, match="Fsync'ing file"):
        storage_._fsync(handle)

    def opened(*_args, **_kwargs):
        raise AssertionError("directory was opened")

    # Directory fsync is POSIX-only. Windows returns before os.open.
    if sys.platform == "win32":
        monkeypatch.setattr(storage_base.os, "open", opened)
        storage_._sync_directory(str(tmp_path))
    else:
        with pytest.raises(RuntimeError, match="Fsync'ing directory"):
            storage_._sync_directory(str(tmp_path))
        monkeypatch.setattr(storage_base.sys, "platform", "win32")
        monkeypatch.setattr(storage_base.os, "open", opened)
        storage_._sync_directory(str(tmp_path))

    monkeypatch.undo()
    storage_._filesystem_fsync = False

    def deny_makedirs(path, exist_ok=False):
        raise PermissionError(13, "denied", path)

    monkeypatch.setattr(storage_base.os, "makedirs", deny_makedirs)
    with pytest.raises(PermissionError):
        storage_._makedirs_synced(str(tmp_path / "nope" / "deeper"))
    assert "Cannot create storage path" in caplog.text

    def boom_makedirs(path, exist_ok=False):
        raise RuntimeError("boom-makedirs")

    monkeypatch.setattr(storage_base.os, "makedirs", boom_makedirs)
    with pytest.raises(RuntimeError, match="boom-makedirs"):
        storage_._makedirs_synced(str(tmp_path / "other" / "deeper"))

    monkeypatch.undo()
    monkeypatch.setattr(storage_base.os.path, "isdir", lambda _path: False)
    monkeypatch.setattr(storage_base.os.path, "dirname", lambda path: path)
    made = []

    def once(path, exist_ok=False):
        made.append(path)

    monkeypatch.setattr(storage_base.os, "makedirs", once)
    target = str(tmp_path / "same")
    storage_._makedirs_synced(target)
    assert made == [target]


def test_item_cache_expiry_hash_and_corrupt_entries(tmp_path, monkeypatch, caplog):
    caplog.set_level(logging.DEBUG)
    storage_ = _storage(tmp_path)
    collection = _calendar(storage_)[0]
    folder = tmp_path / "entries"
    folder.mkdir()
    fresh = folder / "fresh"
    stale = folder / "stale"
    ghost = folder / "ghost"
    locked = folder / "locked"
    for path in (fresh, stale, ghost, locked):
        path.write_text("x", encoding="utf-8")
    old = time.time() - 100
    os.utime(stale, (old, old))
    os.utime(locked, (old, old))
    real_getmtime = storage_base.os.path.getmtime

    def getmtime(path):
        if str(path).endswith("ghost"):
            raise FileNotFoundError(path)
        return real_getmtime(path)

    monkeypatch.setattr(os.path, "getmtime", getmtime)
    # CollectionPartCache uses os.path.getmtime from its own module global.
    from radicale.storage.multifilesystem import cache as storage_cache
    monkeypatch.setattr(storage_cache.os.path, "getmtime", getmtime)
    real_remove = storage_cache.os.remove

    def remove(path):
        if str(path).endswith("locked"):
            raise PermissionError(path)
        return real_remove(path)

    monkeypatch.setattr(storage_cache.os, "remove", remove)
    collection._clean_cache(str(folder), ["ghost", "fresh", "stale", "locked"], max_age=10)
    assert ghost.exists() and fresh.exists() and locked.exists()
    assert not stale.exists()

    item = _event()
    storage_._use_mtime_and_size_for_item_cache = True
    with pytest.raises(RuntimeError, match="use_mtime_and_size_for_item_cache"):
        collection._store_item_cache("event1.ics", item, "")
    storage_._use_mtime_and_size_for_item_cache = False
    stored = collection._store_item_cache("event1.ics", item, "")
    assert stored.uid == "event1"
    cache_hash = collection._item_cache_hash(item.serialize().encode())
    storage_._debug_cache_actions = True
    logger.setLevel(logging.DEBUG)
    loaded = collection._load_item_cache("event1.ics", cache_hash)
    assert loaded is not None and loaded.uid == "event1"
    assert "Item cache match" in caplog.text
    assert collection._load_item_cache("event1.ics", "0" * 64) is None
    assert "Item cache no match" in caplog.text
    assert collection._load_item_cache("missing.ics", cache_hash) is None
    assert "Item cache not found" in caplog.text

    cache_folder = storage_._get_collection_cache_subfolder(
        collection._filesystem_path, ".Radicale.cache", "item")
    empty_hash = os.path.join(cache_folder, "empty.ics")
    with open(empty_hash, "wb") as handle:
        pickle.dump(("", "u", "e", "text", "name", "VEVENT", 1, 2), handle)
    assert collection._load_item_cache("empty.ics", "") is None
    corrupt = os.path.join(cache_folder, "corrupt.ics")
    with open(corrupt, "wb") as handle:
        handle.write(_DAMAGED_PICKLE)
    assert collection._load_item_cache("corrupt.ics", cache_hash) is None
    assert "Failed to load item cache entry" in caplog.text

    storage_._debug_cache_actions = False
    calls = _record_debug(monkeypatch)
    assert collection._load_item_cache("event1.ics", "f" * 64) is None
    assert not any("no match" in msg for msg in calls)


def test_create_collection_skips_unreadable_items_and_other_tags(tmp_path):
    storage_ = _storage(tmp_path)
    _calendar(storage_, items=[_event(summary="Old")])
    original = multifilesystem.Collection._get

    def none_or_real(self, href, verify_href=True):
        if ".Radicale.tmp-" in self._filesystem_path:
            return original(self, href, verify_href)
        return None

    multifilesystem.Collection._get = none_or_real
    try:
        _collection, replaced, _new = _calendar(
            storage_, items=[_event(summary="New")])
    finally:
        multifilesystem.Collection._get = original
    assert replaced == {}
    found = list(storage_.discover("/user/cal/", "1"))
    assert any(getattr(item, "uid", None) == "event1" for item in found)

    def explode(self, href, verify_href=True):
        if ".Radicale.tmp-" in self._filesystem_path:
            return original(self, href, verify_href)
        raise ValueError("unreadable")

    multifilesystem.Collection._get = explode
    try:
        _calendar(storage_, items=[_event(summary="Newer")])
    finally:
        multifilesystem.Collection._get = original
    text = pathlib.Path(next(
        item._filesystem_path for item in storage_.discover("/user/cal/")
        if isinstance(item, storage.BaseCollection)))
    assert "Newer" in (text / "event1.ics").read_text(encoding="utf-8")

    subscribed, _replaced, new_hrefs = _calendar(
        storage_, href="/user/sub/", items=[_event()], props={"tag": "VSUBSCRIBED"})
    assert new_hrefs == []
    assert list(subscribed._list()) == []


def test_delete_unsafe_missing_and_absent_cache(tmp_path):
    storage_ = _storage(tmp_path)
    collection = _calendar(storage_, items=[_event()])[0]
    with storage_.acquire_lock("w"):
        with pytest.raises(pathutils.UnsafePathError):
            collection.delete("foo~")
        with pytest.raises(storage.ComponentNotFoundError, match="missing.ics"):
            collection.delete("missing.ics")
        cache_folder = storage_._get_collection_cache_subfolder(
            collection._filesystem_path, ".Radicale.cache", "item")
        cache_file = os.path.join(cache_folder, "event1.ics")
        if os.path.isfile(cache_file):
            os.remove(cache_file)
        collection.delete("event1.ics")
    assert collection._get("event1.ics") is None
    assert not os.path.exists(os.path.join(collection._filesystem_path, "event1.ics"))


def test_history_corrupt_entry_and_unsafe_deleted_name(tmp_path, caplog):
    caplog.set_level(logging.WARNING)
    storage_ = _storage(tmp_path)
    collection = _calendar(storage_, items=[_event()])[0]
    with storage_.acquire_lock("w"):
        collection.sync()
        collection.delete("event1.ics")
    history_folder = storage_._get_collection_cache_subfolder(
        collection._filesystem_path, ".Radicale.cache", "history")
    with open(os.path.join(history_folder, "bad~"), "wb") as handle:
        handle.write(b"x")
    hrefs = list(collection._get_deleted_history_hrefs())
    assert "event1.ics" in hrefs
    assert "bad~" not in hrefs
    corrupt = os.path.join(history_folder, "event1.ics")
    with open(corrupt, "wb") as handle:
        handle.write(_DAMAGED_PICKLE)
    with storage_.acquire_lock("w"):
        token, changes = collection.sync()
    assert token.startswith("http://radicale.org/ns/sync/")
    assert "event1.ics" in changes
    assert "Failed to load history cache entry" in caplog.text


def test_storage_hook_placeholders_failures_and_platform_flags(tmp_path, monkeypatch, caplog):
    caplog.set_level(logging.DEBUG)
    logger.setLevel(logging.DEBUG)
    from radicale.storage.multifilesystem import lock as storage_lock
    marker = tmp_path / "hook.txt"
    # The hook runs with shell=True. cmd.exe separates commands with "&".
    if sys.platform == "win32":
        hook = "echo hook-out& echo hook-out> %s& echo hook-err>&2" % marker
        failing_hook = "echo ran& exit 3"
    else:
        hook = "echo hook-out; echo hook-out > %s; echo hook-err >&2" % marker
        failing_hook = "echo ran; exit 3"
    storage_ = _storage(tmp_path / "ok", {"storage": {"hook": hook}})
    _calendar(storage_, items=[_event()])
    assert marker.read_text(encoding="utf-8").strip() == "hook-out"
    assert "Captured stdout from storage hook" in caplog.text
    assert "hook-out" in caplog.text
    assert "Captured stderr from storage hook" in caplog.text
    assert "hook-err" in caplog.text

    caplog.clear()
    failing = _storage(tmp_path / "fail", {"storage": {"hook": failing_hook}})
    _calendar(failing, href="/user/cal/", items=[_event()])
    assert "exit status 3" in caplog.text
    assert any(getattr(item, "uid", None) == "event1" for item in failing.discover("/user/cal/", "1"))

    caplog.clear()
    unknown = _storage(tmp_path / "bad", {"storage": {"hook": "echo %(nope)s"}})
    _calendar(unknown, href="/user/cal/", items=[_event()])
    assert "not supported placeholder" in caplog.text

    caplog.clear()

    def popen_boom(*_args, **_kwargs):
        raise OSError("popen-boom")

    monkeypatch.setattr(storage_lock.subprocess, "Popen", popen_boom)
    popped = _storage(tmp_path / "popen", {"storage": {"hook": "echo hi"}})
    _calendar(popped, href="/user/cal/", items=[_event()])
    assert "not successful on 'Popen'" in caplog.text
    monkeypatch.undo()

    class _Boom(BaseException):
        pass

    class _FakePopen:
        def __init__(self, *args, **kwargs):
            self.pid = 1 << 22
            self.args = args[0] if args else ""
            self.returncode = 0

        def communicate(self):
            raise _Boom("hook-interrupted")

        def kill(self):
            self.killed = True

        def wait(self):
            return 0

    monkeypatch.setattr(storage_lock.subprocess, "Popen", _FakePopen)
    interrupted = _storage(tmp_path / "comm", {"storage": {"hook": "echo hi"}})
    _calendar(interrupted, href="/user/cal/", items=[_event()])
    assert "not successful on 'communicate'" in caplog.text
    monkeypatch.undo()

    seen = {}
    real_popen = subprocess.Popen

    def recording_popen(command, **kwargs):
        seen["creationflags"] = kwargs.get("creationflags")
        return real_popen(command, **kwargs)

    monkeypatch.setattr(storage_lock, "sys", SimpleNamespace(
        platform="win32", version_info=sys.version_info))
    monkeypatch.setattr(storage_lock.subprocess, "CREATE_NEW_PROCESS_GROUP", 0, raising=False)
    monkeypatch.setattr(storage_lock.subprocess, "Popen", recording_popen)

    def killpg(*_args, **_kwargs):
        raise AssertionError("killpg called")

    monkeypatch.setattr(storage_lock.os, "killpg", killpg, raising=False)
    win_marker = tmp_path / "win.txt"
    windows = _storage(tmp_path / "win", {"storage": {"hook": "echo win-hook > %s" % win_marker}})
    _calendar(windows, href="/user/cal/", items=[_event()])
    assert seen["creationflags"] == 0
    assert win_marker.read_text(encoding="utf-8").strip() == "win-hook"
    monkeypatch.undo()

    group_marker = tmp_path / "pgrp"
    monkeypatch.setattr(storage_lock.sys, "version_info", (3, 9, 0))

    def setpgrp():
        group_marker.write_text("yes", encoding="utf-8")

    monkeypatch.setattr(storage_lock.os, "setpgrp", setpgrp, raising=False)
    old = _storage(tmp_path / "py39", {"storage": {"hook": "echo old-python"}})
    _calendar(old, href="/user/cal/", items=[_event()])
    # win32 selects creationflags before the Python 3.9 preexec_fn branch.
    if sys.platform == "win32":
        assert not group_marker.exists()
    else:
        assert group_marker.read_text(encoding="utf-8") == "yes"


def test_meta_cache_lock_invalid_json_and_write_failure(tmp_path, caplog):
    storage_ = _storage(tmp_path)
    collection = _calendar(storage_, props={"tag": "VCALENDAR", "D:displayname": "First"})[0]
    with open(collection._props_path, encoding="utf-8") as handle:
        assert "First" in handle.read()
    with open(collection._props_path, "w", encoding="utf-8") as handle:
        handle.write("{")
    with pytest.raises(RuntimeError, match="Failed to load properties of collection"):
        collection.get_meta()
    os.remove(collection._props_path)
    os.mkdir(collection._props_path)
    with pytest.raises(ValueError, match="Failed to write meta data"):
        collection.set_meta({"tag": "VCALENDAR"})


def test_move_unsafe_replace_and_cache_failures(tmp_path, monkeypatch, caplog):
    caplog.set_level(logging.ERROR)
    from radicale.storage.multifilesystem import move as storage_move
    storage_ = _storage(tmp_path)
    collection = _calendar(storage_, items=[_event()])[0]
    other = _calendar(storage_, href="/user/other/")[0]
    uploaded = next(item for item in storage_.discover("/user/cal/", "1")
                    if getattr(item, "uid", None) == "event1")
    with storage_.acquire_lock("w"):
        with pytest.raises(pathutils.UnsafePathError):
            storage_.move(uploaded, other, "foo~")
        real_replace = storage_move.os.replace

        def fail_replace(src, dst):
            raise OSError(errno.EIO, "replace")

        monkeypatch.setattr(storage_move.os, "replace", fail_replace)
        with pytest.raises(ValueError, match="Failed to move file"):
            storage_.move(uploaded, other, "moved.ics")
        assert os.path.isfile(os.path.join(collection._filesystem_path, "event1.ics"))
        monkeypatch.setattr(storage_move.os, "replace", real_replace)

        cache_folder = storage_._get_collection_cache_subfolder(
            collection._filesystem_path, ".Radicale.cache", "item")
        cache_file = os.path.join(cache_folder, uploaded.href)
        if os.path.isfile(cache_file):
            os.remove(cache_file)
        storage_.move(uploaded, other, "moved.ics")
    moved_path = os.path.join(other._filesystem_path, "moved.ics")
    assert os.path.isfile(moved_path)
    assert "SUMMARY:Event" in pathlib.Path(moved_path).read_text(encoding="utf-8")
    assert not os.path.exists(os.path.join(collection._filesystem_path, "event1.ics"))

    again = next(item for item in storage_.discover("/user/other/", "1")
                 if getattr(item, "href", None) == "moved.ics")
    cache_folder = storage_._get_collection_cache_subfolder(
        other._filesystem_path, ".Radicale.cache", "item")
    cache_file = os.path.join(cache_folder, "moved.ics")
    if os.path.lexists(cache_file):
        os.remove(cache_file)
    os.makedirs(cache_file)

    def fail_cache(src, dst):
        normalized = str(src).replace("\\", "/")
        if "/.Radicale.cache/item/" in normalized:
            raise OSError(errno.EIO, "cache")
        return real_replace(src, dst)

    monkeypatch.setattr(storage_move.os, "replace", fail_cache)
    with storage_.acquire_lock("w"):
        storage_.move(again, collection, "event1.ics")
    assert os.path.isfile(os.path.join(collection._filesystem_path, "event1.ics"))
    assert "Failed to move cache file" in caplog.text


def test_sync_token_shapes_damage_permission_and_deletions(tmp_path, caplog):
    caplog.set_level(logging.WARNING)
    storage_ = _storage(tmp_path)
    collection = _calendar(storage_, items=[_event()])[0]
    with storage_.acquire_lock("w"):
        with pytest.raises(ValueError, match="Malformed token: 'nope'"):
            collection.sync("nope")
        prefix = "http://radicale.org/ns/sync/"
        with pytest.raises(ValueError, match="Malformed token"):
            collection.sync(prefix + ("g" * 64))
        with pytest.raises(ValueError, match="Malformed token"):
            collection.sync(prefix + "ab")
        token, changes = collection.sync()
        assert token.startswith(prefix)
        assert "event1.ics" in changes
        same, unchanged = collection.sync(token)
        assert same == token and unchanged == ()
        collection.upload("other.ics", _event(uid="other", summary="Other"))
    with storage_.acquire_lock("w"):
        collection.upload("later.ics", _event(uid="later", summary="Later"))
        token_folder = storage_._get_collection_cache_subfolder(
            collection._filesystem_path, ".Radicale.cache", "sync-token")
        token_name = token.rsplit("/", 1)[-1]
        token_path = os.path.join(token_folder, token_name)
        with open(token_path, "rb") as handle:
            state = pickle.load(handle)
        state["ghost.ics"] = "dead"
        with open(token_path, "wb") as handle:
            pickle.dump(state, handle)
        _token2, changed = collection.sync(token)
        assert "ghost.ics" in changed
        assert "other.ics" in changed
        assert "later.ics" in changed
        assert "event1.ics" not in changed
        with open(token_path, "wb") as handle:
            handle.write(_DAMAGED_PICKLE)
        with pytest.raises(ValueError, match="Token not found"):
            collection.sync(token)
        assert not os.path.exists(token_path)
        assert "Failed to load stored sync token" in caplog.text

        os.chmod(token_folder, 0o555)
        try:
            collection.upload("third.ics", _event(uid="third", summary="Third"))
            new_token, new_changes = collection.sync()
        finally:
            os.chmod(token_folder, 0o755)
        assert new_token.startswith(prefix)
        assert "third.ics" in new_changes


def test_upload_nonce_names_errno_and_cache_logs(tmp_path, monkeypatch, caplog):
    caplog.set_level(logging.DEBUG)
    from radicale.storage.multifilesystem import upload as storage_upload
    storage_ = _storage(tmp_path)
    storage_._debug_cache_actions = True
    logger.setLevel(logging.DEBUG)
    collection = _calendar(storage_)[0]
    preexisting = os.path.join(collection._filesystem_path, "event1.ics")
    with open(preexisting, "w", encoding="utf-8") as handle:
        handle.write("OLD")
    with storage_.acquire_lock("w"):
        collection._upload_all_nonatomic([_event()], ".ics")
    assert pathlib.Path(preexisting).read_text(encoding="utf-8") == "OLD"
    stored = [path for path in pathlib.Path(collection._filesystem_path).iterdir()
              if path.name != "event1.ics" and path.suffix == ".ics"]
    assert stored and "BEGIN:VCALENDAR" in stored[0].read_text(encoding="utf-8")
    assert "with hash" in caplog.text

    state = {"n": 0}
    real_open = builtins.open

    def flaky_open(path, mode="r", *args, **kwargs):
        name = str(path)
        if name.endswith(".ics") and "w" in str(mode) and ".Radicale.cache" not in name:
            state["n"] += 1
            if state["n"] == 1:
                # Linux retries EINVAL. Windows retries ERROR_INVALID_NAME (123).
                bad = 123 if sys.platform == "win32" else errno.EINVAL
                raise OSError(bad, "bad name")
        return real_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(storage_upload, "open", flaky_open, raising=False)
    fresh = _calendar(storage_, href="/user/fresh/")[0]
    with storage_.acquire_lock("w"):
        fresh._upload_all_nonatomic([_event(uid="flaky")], ".ics")
    assert any("flaky" in path.read_text(encoding="utf-8")
               for path in pathlib.Path(fresh._filesystem_path).glob("*.ics"))

    def eio_open(path, mode="r", *args, **kwargs):
        if str(path).endswith(".ics") and "w" in str(mode) and ".Radicale.cache" not in str(path):
            raise OSError(errno.EIO, "io")
        return real_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(storage_upload, "open", eio_open, raising=False)
    with storage_.acquire_lock("w"):
        with pytest.raises(OSError) as exc_info:
            fresh._upload_all_nonatomic([_event(uid="io")], ".ics")
    assert exc_info.value.errno == errno.EIO

    def inval_open(path, mode="r", *args, **kwargs):
        if str(path).endswith(".ics") and "w" in str(mode) and ".Radicale.cache" not in str(path):
            raise OSError(errno.EINVAL, "bad name")
        return real_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(storage_upload, "open", inval_open, raising=False)
    with storage_.acquire_lock("w"):
        if sys.platform == "win32":
            with pytest.raises(OSError) as exc_info:
                fresh._upload_all_nonatomic([_event(uid="none")], ".ics")
            assert exc_info.value.errno == errno.EINVAL
        else:
            with pytest.raises(RuntimeError, match="No href found"):
                fresh._upload_all_nonatomic([_event(uid="none")], ".ics")

    state["n"] = 0
    monkeypatch.setattr(storage_upload, "sys", SimpleNamespace(platform="win32"))

    def win_open(path, mode="r", *args, **kwargs):
        name = str(path)
        if name.endswith(".ics") and "w" in str(mode) and ".Radicale.cache" not in name:
            state["n"] += 1
            if state["n"] == 1:
                raise OSError(123, "bad win name")
        return real_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(storage_upload, "open", win_open, raising=False)
    with storage_.acquire_lock("w"):
        fresh._upload_all_nonatomic([_event(uid="winname")], ".ics")
    assert any("winname" in path.read_text(encoding="utf-8")
               for path in pathlib.Path(fresh._filesystem_path).glob("*.ics"))

    def win_other(path, mode="r", *args, **kwargs):
        if str(path).endswith(".ics") and "w" in str(mode) and ".Radicale.cache" not in str(path):
            raise OSError(errno.EINVAL, "not the windows code")
        return real_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(storage_upload, "open", win_other, raising=False)
    with storage_.acquire_lock("w"):
        with pytest.raises(OSError) as exc_info:
            fresh._upload_all_nonatomic([_event(uid="winother")], ".ics")
    assert exc_info.value.errno == errno.EINVAL

    def win_exhausted(path, mode="r", *args, **kwargs):
        if str(path).endswith(".ics") and "w" in str(mode) and ".Radicale.cache" not in str(path):
            raise OSError(123, "bad win name")
        return real_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(storage_upload, "open", win_exhausted, raising=False)
    with storage_.acquire_lock("w"):
        with pytest.raises(RuntimeError, match="No href found"):
            fresh._upload_all_nonatomic([_event(uid="winnone")], ".ics")
    monkeypatch.undo()

    mtime_storage = _storage(tmp_path / "mtime", {"storage": {
        "use_mtime_and_size_for_item_cache": "True"}})
    mtime_storage._debug_cache_actions = True
    caplog.clear()
    _calendar(mtime_storage, href="/user/cal/", items=[_event()])
    assert "with mtime and size" in caplog.text


def test_verify_collection_item_and_uid_failures(tmp_path, monkeypatch, caplog):
    caplog.set_level(logging.ERROR)
    storage_ = _storage(tmp_path)
    collection = _calendar(storage_, items=[_event()])[0]

    def boom_sync(self, old_token=""):
        raise ValueError("sync-boom")

    monkeypatch.setattr(multifilesystem.Collection, "sync", boom_sync)
    storage_.verify()
    monkeypatch.undo()

    props = collection._props_path
    with open(props, "w", encoding="utf-8") as handle:
        handle.write("{")
    assert storage_.verify() is False
    assert "Invalid collection" in caplog.text
    with open(props, "w", encoding="utf-8") as handle:
        handle.write('{"tag": "VCALENDAR"}')

    source = os.path.join(collection._filesystem_path, "event1.ics")
    duplicate = os.path.join(collection._filesystem_path, "copy.ics")
    pathlib.Path(duplicate).write_text(pathlib.Path(source).read_text(encoding="utf-8"), encoding="utf-8")
    caplog.clear()
    storage_.verify()
    assert "UID conflict" in caplog.text
    os.remove(duplicate)

    os.makedirs(os.path.join(collection._filesystem_path, "child"))
    caplog.clear()
    storage_.verify()
    assert "must not have child collections" in caplog.text


def test_nolock_waits_and_write_lock_skips_cache_lock(tmp_path):
    lock = multifilesystem_nolock.RwLock()
    with pytest.raises(ValueError, match="Invalid mode: 'x'"):
        with lock.acquire("x"):
            pass
    writer_entered = threading.Event()

    def writer():
        with lock.acquire("w"):
            writer_entered.set()

    with lock.acquire("r"):
        with lock.acquire("r"):
            pass
        thread = threading.Thread(target=writer)
        thread.start()
        time.sleep(0.2)
        assert not writer_entered.is_set()
    thread.join(2)
    assert writer_entered.is_set()

    key_lock = multifilesystem_nolock.LockDict()
    entered = {name: threading.Event() for name in ("a", "b", "c")}
    release = {name: threading.Event() for name in ("a", "b", "c")}

    def holder(name):
        with key_lock.acquire("k"):
            entered[name].set()
            assert release[name].wait(3)

    threads = [threading.Thread(target=holder, args=(name,)) for name in ("a", "b", "c")]
    threads[0].start()
    assert entered["a"].wait(2)
    threads[1].start()
    threads[2].start()
    time.sleep(0.2)
    assert not entered["b"].is_set()
    release["a"].set()
    assert entered["b"].wait(2)
    time.sleep(0.2)
    assert not entered["c"].is_set()
    release["b"].set()
    assert entered["c"].wait(2)
    release["c"].set()
    for thread in threads:
        thread.join(2)
    assert "k" not in key_lock._dict

    storage_ = _storage(tmp_path, {"storage": {"type": "multifilesystem_nolock"}})
    with storage_.acquire_lock("w"):
        collection = storage_.create_collection(
            "/user/cal/", props={"tag": "VCALENDAR"})[0]
        other_entered = threading.Event()

        def other():
            with collection._acquire_cache_lock("item"):
                other_entered.set()

        worker = threading.Thread(target=other)
        with collection._acquire_cache_lock("item"):
            worker.start()
            assert other_entered.wait(1)
        worker.join(2)

    made = []

    def boom(*_args, **_kwargs):
        made.append("lock")
        raise AssertionError("cache lock")

    from radicale.storage.multifilesystem import lock as storage_lock

    # The nolock collection overrides _acquire_cache_lock; the filesystem one
    # is what still consults the storage lock mode.
    filesystem = _storage(tmp_path / "fs")
    filesystem_collection = _calendar(filesystem)[0]
    with filesystem.acquire_lock("w"):
        original = storage_lock.pathutils.RwLock
        storage_lock.pathutils.RwLock = boom
        try:
            with filesystem_collection._acquire_cache_lock("item"):
                pass
        finally:
            storage_lock.pathutils.RwLock = original
    assert made == []


# --- server and server_cheroot ----------------------------------------------


def _bind_server(folder, port, **options):
    server_options = {"hosts": "127.0.0.1:%d" % port}
    server_options.update(options)
    return _configuration(folder, {"server": server_options})


def _thread_result(target):
    holder = {}

    def run():
        try:
            target()
        except BaseException as exc:  # noqa: BLE001 - the server thread must report
            holder["exc"] = exc

    thread = threading.Thread(target=run)
    thread.start()
    return thread, holder


class _ShiftingMatch:
    """Equal to ``included`` on the outer network check, then to nothing.

    ``log_conditional`` tests membership three times. The first two lists are
    the plain comparisons; the third selects included vs excluded. Returning
    true only for that outer ``included`` makes the excluded arm false.
    """

    def __init__(self):
        self.hits = 0

    def __eq__(self, other):
        self.hits += 1
        return self.hits == 6 and other == "included"

    def __hash__(self):
        return 0


def _capture_traces_direct():
    calls: List[str] = []

    def trace(msg, *args, **kwargs):
        try:
            calls.append(msg % args if args else msg)
        except Exception:
            calls.append(str(msg))

    logger.trace = trace
    return calls


def test_upload_logs_mtime_or_hash_and_batch_can_stay_quiet(tmp_path, monkeypatch):
    storage_ = _storage(tmp_path)
    storage_._debug_cache_actions = True
    storage_._use_mtime_and_size_for_item_cache = True
    collection = _calendar(storage_)[0]
    calls = _record_debug(monkeypatch)
    with storage_.acquire_lock("w"):
        uploaded, old = collection.upload("new.ics", _event(uid="new", summary="New"))
    assert old is None and uploaded.uid == "new"
    assert "SUMMARY:New" in pathlib.Path(
        os.path.join(collection._filesystem_path, "new.ics")).read_text(encoding="utf-8")
    assert any("Item cache store" in msg and "with mtime and size" in msg for msg in calls)

    storage_._use_mtime_and_size_for_item_cache = False
    calls = _record_debug(monkeypatch)
    with storage_.acquire_lock("w"):
        uploaded, old = collection.upload("hash.ics", _event(uid="hashitem", summary="Hash"))
    assert old is None and uploaded.uid == "hashitem"
    assert "SUMMARY:Hash" in pathlib.Path(
        os.path.join(collection._filesystem_path, "hash.ics")).read_text(encoding="utf-8")
    assert any("Item cache store" in msg and "with hash" in msg for msg in calls)

    storage_._debug_cache_actions = False
    storage_._use_mtime_and_size_for_item_cache = True
    quiet = _calendar(storage_, href="/user/quiet/")[0]
    calls = _record_debug(monkeypatch)
    with storage_.acquire_lock("w"):
        quiet._upload_all_nonatomic([_event(uid="quiet")], ".ics")
    stored = list(pathlib.Path(quiet._filesystem_path).glob("*.ics"))
    assert len(stored) == 1
    assert "quiet" in stored[0].read_text(encoding="utf-8")
    assert any("quiet" in msg for msg in calls)
    assert not any("with mtime and size" in msg for msg in calls)
    cache_folder = storage_._get_collection_cache_subfolder(
        quiet._filesystem_path, ".Radicale.cache", "item")
    assert list(pathlib.Path(cache_folder).iterdir())

    storage_._debug_cache_actions = True
    loud = _calendar(storage_, href="/user/loud/")[0]
    calls = _record_debug(monkeypatch)
    with storage_.acquire_lock("w"):
        loud._upload_all_nonatomic([_event(uid="loud")], ".ics")
    assert any("with mtime and size" in msg for msg in calls)
    assert any("loud" in path.read_text(encoding="utf-8")
               for path in pathlib.Path(loud._filesystem_path).glob("*.ics"))
