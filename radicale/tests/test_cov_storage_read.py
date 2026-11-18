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

"""Outcome tests for reading multifilesystem collections."""

import builtins
import errno
import http.client
import logging
import os
import signal
import socket
import stat
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
from radicale import log, storage, xmlutils
from radicale.log import logger
from radicale.storage import multifilesystem
from radicale.tests.helpers import get_file_content

EVENT_ICS = get_file_content("event1.ics")
CONTACT_VCF = get_file_content("contact1.vcf")


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


def test_component_errors_and_collection_reads_without_debug(tmp_path, monkeypatch):
    exists = storage.ComponentExistsError("user/cal")
    missing = storage.ComponentNotFoundError("user/cal")
    assert str(exists) == "Component already exists: 'user/cal'"
    assert str(missing) == "Component doesn't exist: 'user/cal'"
    assert isinstance(exists, ValueError) and isinstance(missing, ValueError)

    storage_ = _storage(tmp_path)
    _calendar(storage_, items=[_event(), _event(uid="other", summary="Other")])
    collection = next(item for item in storage_.discover("/user/cal/")
                      if isinstance(item, storage.BaseCollection))
    calls = _silence_traces(monkeypatch)
    etag = collection.etag
    assert etag.startswith('"') and etag.endswith('"') and len(etag) > 2
    token, changes = collection.sync()
    assert token.startswith("http://radicale.org/ns/sync/")
    assert set(changes) == {"event1.ics", "other.ics"}
    same, quiet = collection.sync(token)
    assert same == token and list(quiet) == []
    with pytest.raises(ValueError, match="Token not found"):
        collection.sync("http://radicale.org/ns/sync/" + ("ab" * 32))
    with pytest.raises(ValueError, match="Sync token are not supported"):
        storage.BaseCollection.sync(collection, token)
    assert collection.has_uid("event1") is True
    assert collection.has_uid("missing") is False
    assert not any(msg.startswith("storage/") for msg in calls)

    calls = _capture_traces(monkeypatch)
    assert collection.has_uid("event1") is True
    # event1.ics is the derived name, so the fast path does not scan.
    assert "storage/has_uid" not in calls

    bare = _calendar(storage_, href="/user/empty/", props={"tag": ""})[0]
    assert list(bare.get_filtered(
        _time_filters("20130901T000000Z", "20130902T000000Z"))) == []

    inside = list(collection.get_filtered(
        _time_filters("20130901T000000Z", "20130902T000000Z")))
    outside = list(collection.get_filtered(
        _time_filters("20130801T000000Z", "20130901T150000Z")))
    touching = list(collection.get_filtered(
        _time_filters("20130801T000000Z", "20130901T160000Z")))
    assert {item.uid for item, _matched in inside} == {"event1", "other"}
    assert outside == []
    assert touching == []
    calls = _silence_traces(monkeypatch)
    again = list(collection.get_filtered(
        _time_filters("20130901T000000Z", "20130902T000000Z")))
    assert len(again) == 2
    assert not any("get_filtered" in msg for msg in calls)
    calls = _capture_traces(monkeypatch)
    traced = list(collection.get_filtered(
        _time_filters("20130901T000000Z", "20130902T000000Z")))
    assert {item.uid for item, _matched in traced} == {"event1", "other"}
    assert any(msg.startswith("storage/get_filtered") for msg in calls)


def test_has_uid_fast_path_boundaries(tmp_path, monkeypatch):
    """Derived names answer directly. Unsafe, foreign, and broken names scan."""
    storage_ = _storage(tmp_path)
    collection = _calendar(storage_, items=[
        _event(uid="event1"),
        _event(uid=".dot", summary="Dotted"),
    ])[0]
    dot_href = radicale_item.get_etag(".dot").strip('"') + ".ics"
    names = set(os.listdir(collection._filesystem_path))
    assert "event1.ics" in names
    assert ".dot.ics" not in names
    assert dot_href in names

    calls = _capture_traces(monkeypatch)
    assert collection.has_uid("event1") is True
    assert "storage/has_uid" not in calls

    calls = _capture_traces(monkeypatch)
    assert collection.has_uid(".dot") is True
    assert "storage/has_uid" not in calls

    calls = _capture_traces(monkeypatch)
    assert collection.has_uid("missing") is False
    assert "storage/has_uid" in calls

    foreign = os.path.join(collection._filesystem_path, "wanted.ics")
    with open(foreign, "w", encoding="utf-8", newline="") as handle:
        handle.write(_event(uid="other", summary="Other").serialize())
    calls = _capture_traces(monkeypatch)
    assert collection.has_uid("wanted") is False
    assert "storage/has_uid" in calls
    assert collection.has_uid("other") is True

    broken = os.path.join(collection._filesystem_path, "broken.ics")
    with open(broken, "w", encoding="utf-8") as handle:
        handle.write("not a calendar\n")
    assert collection.has_uid("broken") is False


def test_serialize_description_timezones_and_addressbook_conversion(tmp_path, monkeypatch):
    storage_ = _storage(tmp_path)
    _calendar(storage_, items=[
        _event(summary="One"),
        _event(uid="two", summary="Two"),
        _event(uid="bare", summary="Bare"),
        _event(uid="bare2", summary="Bare2"),
    ], props={
        "tag": "VCALENDAR",
        "D:displayname": "Team",
        "C:calendar-description": "Team calendar",
    })
    collection = next(item for item in storage_.discover("/user/cal/")
                      if isinstance(item, storage.BaseCollection))
    real_serialize = radicale_item.Item.serialize

    def serialize_without_tzid(self):
        text = real_serialize(self)
        if self.uid in ("bare", "bare2"):
            extra = (
                "BEGIN:VTIMEZONE\r\nBEGIN:STANDARD\r\n"
                "DTSTART:19701101T020000\r\nTZOFFSETFROM:+0200\r\n"
                "TZOFFSETTO:+0100\r\nEND:STANDARD\r\nEND:VTIMEZONE\r\n")
            text = text.replace("END:VCALENDAR\r\n", extra + "END:VCALENDAR\r\n", 1)
        return text

    monkeypatch.setattr(radicale_item.Item, "serialize", serialize_without_tzid)
    calls = _silence_traces(monkeypatch)
    text = collection.serialize()
    assert "Team calendar" in text
    assert "X-WR-CALDESC" in text
    assert text.count("TZID:Europe/Paris") == 1
    assert text.count("BEGIN:VTIMEZONE") == 3
    assert "SUMMARY:Bare" in text
    assert "SUMMARY:Bare2" in text
    assert not any(msg == "storage/serialize" for msg in calls)
    assert collection.serialize() == "" or collection.tag == "VCALENDAR"

    other = _calendar(storage_, href="/user/notes/", props={"tag": "VSUBSCRIBED"})[0]
    assert other.serialize() == ""

    _calendar(storage_, href="/user/book/", items=[
        _contact(uid="bday", bday="19900102"),
        _contact(uid="nobirth"),
    ], props={"tag": "VADDRESSBOOK"})
    book = next(item for item in storage_.discover("/user/book/")
                if isinstance(item, storage.BaseCollection))
    calls = _silence_traces(monkeypatch)
    converted = book.serialize(vcf_to_ics=True)
    plain = book.serialize(vcf_to_ics=False)
    assert "1990" in converted
    assert "nobirth" not in converted
    assert "BEGIN:VCARD" in plain and "nobirth" in plain
    assert not any("convert VCF" in msg for msg in calls)
    calls = _capture_traces(monkeypatch)
    traced = book.serialize(vcf_to_ics=True)
    assert "1990" in traced
    assert any("convert VCF to ICS" in msg for msg in calls)


def test_last_modified_without_props_and_mtime_resolution(tmp_path, monkeypatch, caplog):
    caplog.set_level(logging.DEBUG)
    storage_ = _storage(tmp_path)
    collection = _calendar(storage_, href="/user/empty/", props=None)[0]
    os.remove(collection._props_path)
    assert not os.path.exists(collection._props_path)
    stamp = collection.last_modified
    assert stamp.endswith("GMT")
    assert ":" in stamp


@pytest.mark.parametrize(("delta", "phrase", "kind"), [
    (999999999999, "result: 1 ns", "info"),
    (999999999998, "result: 2 ns", "info"),
    (999999999996, "result: 5 ns", "info"),
    (999999999990, "result: 10 ns", "info"),
    (999999999000, "result: 1 us", "info"),
    (999999000000, "result: 1 ms", "info"),
    (999000000000, "result: 1 s", "very"),
    (999900000000, "result: 100 ms", "very"),
    (999990000000, "result: 10 ms", "risky"),
])
def test_storage_reports_mtime_precision(tmp_path, monkeypatch, caplog, delta, phrase, kind):
    caplog.set_level(logging.DEBUG)
    _patch_mtime_delta(monkeypatch, delta)
    _storage(tmp_path / ("d%d" % delta))
    assert "test get: %d ns" % delta in caplog.text
    assert phrase in caplog.text
    if kind == "very":
        assert "VERY RISKY" in caplog.text
        assert "may be an option" not in caplog.text
    elif kind == "risky":
        assert "RISKY ON PRODUCTION SYSTEMS" in caplog.text
        assert "VERY RISKY" not in caplog.text
    else:
        assert "RISKY" not in caplog.text
        assert "may be an option" in caplog.text


def test_mtime_probe_permission_utime_and_io_errors(tmp_path, monkeypatch, caplog):
    caplog.set_level(logging.DEBUG)
    real_open = builtins.open

    def deny_open(path, *args, **kwargs):
        if str(path).endswith(".Radicale.mtime_test"):
            raise PermissionError(13, "denied", str(path))
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", deny_open)
    with pytest.raises(PermissionError):
        _storage(tmp_path / "denied")
    assert "cannot write file" in caplog.text
    assert "Permission denied while accessing storage" in caplog.text

    caplog.clear()

    def io_open(path, *args, **kwargs):
        if str(path).endswith(".Radicale.mtime_test"):
            raise OSError(errno.EIO, "io", str(path))
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", io_open)
    created = _storage(tmp_path / "io")
    assert os.path.isdir(created._filesystem_folder)
    assert "cannot write file" in caplog.text
    assert "not successful" in caplog.text
    assert "Permission denied while accessing storage" not in caplog.text

    caplog.clear()
    monkeypatch.setattr(builtins, "open", real_open)

    def deny_utime(path, *args, **kwargs):
        if str(path).endswith(".Radicale.mtime_test"):
            raise OSError(errno.EPERM, "utime", str(path))
        return os.utime(path, *args, **kwargs)

    monkeypatch.setattr(multifilesystem.os, "utime", deny_utime)
    created = _storage(tmp_path / "utime")
    probe = os.path.join(created._get_collection_root_folder(), ".Radicale.mtime_test")
    assert not os.path.exists(probe)
    assert "cannot set utime" in caplog.text
    assert "not successful" in caplog.text


def test_discover_unsafe_paths_groups_and_skipped_names(tmp_path, monkeypatch, caplog):
    caplog.set_level(logging.DEBUG)
    storage_ = _storage(tmp_path)
    collection = _calendar(storage_, items=[_event(), _event(uid="other", summary="Other")])[0]
    assert list(storage_.discover("/foo~/")) == []
    assert "Unsafe path" in caplog.text
    os.makedirs(os.path.join(collection._filesystem_path, "bad~"))
    os.makedirs(os.path.join(collection._filesystem_path, ".Radicale.tmp-skip"))
    listed = list(storage_.discover("/user/cal/", "1"))
    assert any(getattr(item, "uid", None) == "event1" for item in listed)
    assert "Skipping collection 'bad~'" in caplog.text
    assert ".Radicale.tmp-skip" not in caplog.text

    original = multifilesystem.Collection._get

    def nothing(self, href, verify_href=True):
        return None

    multifilesystem.Collection._get = nothing
    try:
        assert list(storage_.discover("/user/cal/event1.ics")) == []
        found = list(storage_.discover("/user/cal/", "1"))
    finally:
        multifilesystem.Collection._get = original
    assert all(item is not None for item in found)
    assert not any(getattr(item, "href", None) == "event1.ics" for item in found)

    storage_._group_collections_folder = ""
    calls = _silence_traces(monkeypatch)
    assert not any(isinstance(item, storage.BaseCollection) and item.path.startswith("GROUPS")
                   for item in storage_.discover("/", "1", user_groups={"staff"}))
    assert calls == []

    storage_._group_collections_folder = "ABSENT"
    calls = _silence_traces(monkeypatch)
    list(storage_.discover("/", "1", user_groups={"staff"}))
    assert calls == []


def test_get_boundaries_cache_reload_and_size(tmp_path, monkeypatch, caplog):
    caplog.set_level(logging.DEBUG)
    from radicale.storage.multifilesystem import get as storage_get
    storage_ = _storage(tmp_path)
    collection = _calendar(storage_, items=[_event()])[0]
    os.makedirs(os.path.join(collection._filesystem_path, "subdir"))
    skipped = os.path.join(collection._filesystem_path, "bad~")
    with open(skipped, "w", encoding="utf-8") as handle:
        handle.write("skip")
    hidden = os.path.join(collection._filesystem_path, ".Radicale.hidden")
    with open(hidden, "w", encoding="utf-8") as handle:
        handle.write("hidden")
    assert "bad~" not in list(collection._list())
    assert ".Radicale.hidden" not in list(collection._list())
    assert "Skipping item 'bad~'" in caplog.text

    storage_._use_mtime_and_size_for_item_cache = True
    assert collection._get("missing.ics") is None
    assert collection._get("subdir") is None
    item_path = os.path.join(collection._filesystem_path, "event1.ics")
    os.chmod(item_path, 0)
    try:
        if os.access(item_path, os.R_OK):
            assert collection._get("event1.ics").uid == "event1"
            monkeypatch.setattr(storage_get.sys, "platform", "win32")
            assert collection._get("event1.ics").uid == "event1"
        else:
            with pytest.raises(PermissionError):
                collection._get("event1.ics")
            monkeypatch.setattr(storage_get.sys, "platform", "win32")
            with pytest.raises(PermissionError):
                collection._get("event1.ics")
    finally:
        os.chmod(item_path, 0o644)

    real_isfile = storage_get.os.path.isfile

    def isfile(path):
        if str(path).endswith("subdir"):
            raise PermissionError(path)
        return real_isfile(path)

    monkeypatch.setattr(storage_get.os.path, "isfile", isfile)
    monkeypatch.setattr(storage_get.sys, "platform", "win32")
    assert collection._get("subdir") is None
    monkeypatch.setattr(storage_get.sys, "platform", "linux")
    with pytest.raises(PermissionError):
        collection._get("subdir")
    monkeypatch.undo()

    storage_._use_mtime_and_size_for_item_cache = False
    storage_._debug_cache_actions = True
    calls = _record_debug(monkeypatch)
    loaded = collection._get("event1.ics")
    assert loaded is not None and loaded.uid == "event1"
    assert any("early read" in msg for msg in calls)
    calls = _record_debug(monkeypatch)
    again = collection._get("event1.ics")
    assert again.uid == "event1"
    assert any("Item cache hit" in msg for msg in calls)

    cache_folder = storage_._get_collection_cache_subfolder(
        collection._filesystem_path, ".Radicale.cache", "item")
    cache_file = os.path.join(cache_folder, "event1.ics")
    os.remove(cache_file)
    counts = {"n": 0}
    real_load = collection._load_item_cache

    def counting(href, cache_hash):
        counts["n"] += 1
        return real_load(href, cache_hash)

    collection._load_item_cache = counting
    with storage_.acquire_lock("r"):
        assert collection._get("event1.ics").uid == "event1"
    assert counts["n"] == 2
    os.remove(cache_file)
    counts["n"] = 0
    with storage_.acquire_lock("w"):
        assert collection._get("event1.ics").uid == "event1"
    assert counts["n"] == 1

    storage_._use_mtime_and_size_for_item_cache = True
    os.remove(cache_file)
    calls = _record_debug(monkeypatch)
    assert collection._get("event1.ics").uid == "event1"
    assert any("late read" in msg for msg in calls)
    assert any("mtime and size" in msg for msg in calls)

    size = os.path.getsize(item_path)
    storage_._max_resource_size = size
    multi = dict(collection.get_multi(["event1.ics", "foo~"]))
    assert multi["event1.ics"].uid == "event1"
    assert multi["foo~"] is None
    storage_._max_resource_size = size - 1
    assert dict(collection.get_multi(["event1.ics"])) == {}
    assert list(collection.get_all()) == []
    assert "file skipped because size exceeds" in caplog.text
    storage_._max_resource_size = size
    broken = os.path.join(collection._filesystem_path, "broken.ics")
    with open(broken, "w", encoding="utf-8") as handle:
        handle.write("not a calendar")
    collection._skip_broken_item = True
    hrefs = {item.href for item in collection.get_all()}
    assert hrefs == {"event1.ics"}
    assert "broken.ics" not in dict(collection.get_multi(["broken.ics", "event1.ics"]))


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


def test_get_filtered_skip_is_quiet_when_debug_is_off(tmp_path, monkeypatch):
    storage_ = _storage(tmp_path)
    collection = _calendar(storage_, items=[_event(), _event(uid="other")])[0]
    calls = _silence_traces(monkeypatch)
    skipped = list(collection.get_filtered(
        _time_filters("20130801T000000Z", "20130901T150000Z")))
    touching = list(collection.get_filtered(
        _time_filters("20130801T000000Z", "20130901T160000Z")))
    kept = list(collection.get_filtered(
        _time_filters("20130901T160000Z", "20130901T170000Z")))
    assert skipped == []
    assert touching == []
    assert {item.uid for item, _matched in kept} == {"event1", "other"}
    assert calls == []


def test_get_fifo_reload_hit_and_missing_href(tmp_path, monkeypatch):
    storage_ = _storage(tmp_path)
    collection = _calendar(storage_, items=[_event()])[0]
    storage_._use_mtime_and_size_for_item_cache = True
    if hasattr(os, "mkfifo"):
        pipe = os.path.join(collection._filesystem_path, "pipe.ics")
        os.mkfifo(pipe)
        os.chmod(pipe, 0)
        try:
            if os.access(pipe, os.R_OK):
                # Root ignores mode 000. Opening the fifo would block with no writer.
                assert stat.S_ISFIFO(os.stat(pipe).st_mode)
            else:
                with pytest.raises(PermissionError):
                    collection._get("pipe.ics")
        finally:
            try:
                os.chmod(pipe, 0o644)
            except OSError:
                pass
            os.remove(pipe)

    storage_._use_mtime_and_size_for_item_cache = False
    assert collection._get("event1.ics").uid == "event1"
    state = {"n": 0}
    real_load = collection._load_item_cache

    def load(href, cache_hash):
        state["n"] += 1
        if state["n"] == 1:
            return None
        return real_load(href, cache_hash)

    def store(*_args, **_kwargs):
        raise AssertionError("cache store ran after a reload hit")

    collection._load_item_cache = load
    collection._store_item_cache = store
    with storage_.acquire_lock("r"):
        found = collection._get("event1.ics")
    assert found.uid == "event1"
    assert state["n"] == 2

    calls = _silence_traces(monkeypatch)
    multi = dict(collection.get_multi(["event1.ics", "missing.ics"]))
    assert multi["event1.ics"].uid == "event1"
    assert multi["missing.ics"] is None
    assert calls == []

    collection._list = lambda: ["missing.ics", "event1.ics"]
    assert [item.href for item in collection.get_all()] == ["event1.ics"]
    collection._list = lambda: []
    assert list(collection.get_all()) == []
