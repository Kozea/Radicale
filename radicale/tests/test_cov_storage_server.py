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

"""Outcome tests for storage, server, and the small library modules."""

import base64
import builtins
import ctypes
import datetime
import errno
import http.client
import importlib
import io
import json
import logging
import os
import pathlib
import pickle
import signal
import socket
import ssl
import subprocess
import sys
import threading
import time
import xml.etree.ElementTree as ET
from collections import OrderedDict
from types import SimpleNamespace
from typing import List, Optional

import pytest

import radicale
from radicale import config, group, httputils
from radicale import item as radicale_item
from radicale import (log, pathutils, rights, server, storage, types, utils,
                      web, xmlutils)
from radicale.log import logger
from radicale.storage import multifilesystem, multifilesystem_nolock
from radicale.storage.multifilesystem import base as storage_base
from radicale.tests.helpers import get_file_content, get_file_path

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


def test_protocol_stream_bodies_return_ellipsis():
    """Protocol method bodies are executable stubs."""
    assert types.InputStream.read.__defaults__ == (Ellipsis,)
    assert types.InputStream.read(object(), 0) is None
    assert types.ErrorStream.flush(object()) is None
    assert types.ErrorStream.write(object(), "x") is None
    assert types.ErrorStream.write(object(), "") is None


def test_base_web_get_is_method_not_allowed():
    application = web.BaseWeb(config.load())
    status, headers, body, _ = application.get({}, "", "/.web/", "", set(), {})
    assert status == 405
    assert "not allowed" in body


def test_group_none_returns_empty_set():
    configuration = config.load()
    configuration.update({"group": {"type": "none"}}, "test")
    plugin = group.load(configuration)
    assert plugin.groups("anyone") == set()
    assert plugin.groups("") == set()


def test_htgroup_reread_swallows_line_without_colon_and_keeps_later_groups(tmp_path, monkeypatch):
    path = tmp_path / "htgroup"
    path.write_text("staff: alice\n", encoding="utf-8")
    configuration = config.load()
    configuration.update({
        "group": {"type": "htgroup", "htgroup_filename": str(path), "htgroup_cache": "False"},
    }, "test")
    plugin = group.load(configuration)
    path.write_text("staff: alice\nbadline\nops: bob\n", encoding="utf-8")
    calls = _silence_traces(monkeypatch)
    assert plugin.groups("bob") == {"ops"}
    assert plugin.groups("alice") == {"staff"}
    assert calls == []


def test_htgroup_cached_bad_file_sets_reminder_clock_without_warning(tmp_path, caplog):
    caplog.set_level(logging.WARNING)
    path = tmp_path / "htgroup"
    path.write_text("staff: alice\n", encoding="utf-8")
    configuration = config.load()
    configuration.update({
        "group": {"type": "htgroup", "htgroup_filename": str(path), "htgroup_cache": "True"},
    }, "test")
    plugin = group.load(configuration)
    path.write_text("staff: alice\nstaff: bob\n", encoding="utf-8")
    assert plugin.groups("alice") == {"staff"}
    assert "REMINDER" not in caplog.text
    assert plugin._htgroup_not_ok_time > 0
    # The clock is already running and the interval has not elapsed.
    assert plugin.groups("alice") == {"staff"}
    assert "REMINDER" not in caplog.text


def test_rights_remove_and_add_ignore_absent_and_present_entries():
    assert set(rights.remove("RW", "x")) == set("RW")
    assert set(rights.remove("RW", "R")) == set("W")
    assert set(rights.remove("", "R")) == set()
    assert set(rights.add("RW", "R")) == set("RW")
    assert set(rights.add("R", "W")) == set("RW")
    assert set(rights.add("", "")) == set()


def test_owner_only_permissions_when_debug_is_disabled(monkeypatch):
    configuration = config.load()
    assert configuration.get("auth", "type") != "none"
    backend = rights.load(configuration.__class__(configuration._schema) if False else configuration)
    # owner_only is selected explicitly; the default rights type is not owner_only.
    configuration.update({"rights": {"type": "owner_only"}}, "test")
    backend = rights.load(configuration)
    calls = _silence_traces(monkeypatch)
    assert backend.authorization("", set(), "/user/") == ""
    assert backend.authorization("user", set(), "/") == "R"
    assert backend.authorization("user", set(), "/other/cal/") == ""
    assert backend.authorization("user", set(), "/user") == "RW"
    assert backend.authorization("user", set(), "/user/cal/") == "rw"
    assert backend.authorization("user", set(), "/user/cal/item") == ""
    assert calls == []


def test_from_file_missing_unreadable_and_runtime_errors(tmp_path, monkeypatch, caplog):
    caplog.set_level(logging.DEBUG)
    missing = tmp_path / "missing.rights"
    configuration = config.load()
    configuration.update({"rights": {"type": "from_file", "file": str(missing)}}, "test")
    with pytest.raises(RuntimeError, match="Failed to load rights file"):
        rights.load(configuration)

    unreadable = tmp_path / "rights"
    unreadable.write_text("[a]\nuser = .+\ncollection = .*\npermissions = R\n", encoding="utf-8")
    os.chmod(unreadable, 0)
    try:
        configuration.update({"rights": {"file": str(unreadable)}}, "test")
        with pytest.raises(RuntimeError, match="Failed to load rights file"):
            rights.load(configuration)
    finally:
        os.chmod(unreadable, 0o644)

    conflict = tmp_path / "conflict.rights"
    conflict.write_text("[a]\nuser = .+\ncollection = .*\npermissions = dD\n", encoding="utf-8")
    configuration.update({"rights": {"file": str(conflict)}}, "test")
    with pytest.raises(RuntimeError, match="conflicting 'd'"):
        rights.load(configuration)

    bad_group = tmp_path / "groupref.rights"
    bad_group.write_text("[a]\nuser = .+\ncollection = {1}\npermissions = R\n", encoding="utf-8")
    configuration.update({"rights": {"file": str(bad_group)}}, "test")
    backend = rights.load(configuration)
    with pytest.raises(RuntimeError, match="Error in section"):
        backend.authorization("user", set(), "/user/")

    swallow = tmp_path / "swallow.rights"
    swallow.write_text(
        "[by-user]\nuser = .+\ncollection = {user}\npermissions = RW\n",
        encoding="utf-8")
    configuration.update({
        "rights": {"file": str(swallow)},
        "logging": {"rights_rule_doesnt_match_on_debug": "False"},
    }, "test")
    backend = rights.load(configuration)
    calls = _silence_traces(monkeypatch)
    # user_groups has no intersection(); the lookup is ignored and the user rule still matches.
    assert backend.authorization("user", ["not-a-set"], "/user") == "RW"  # type: ignore[arg-type]
    assert calls == []


def test_from_file_empty_user_pattern_matches_by_group(tmp_path):
    path = tmp_path / "groups.rights"
    path.write_text(
        "[by-group]\nuser =\ncollection = groupcal\ngroups = staff,ops\npermissions = r\n",
        encoding="utf-8")
    configuration = config.load()
    configuration.update({"rights": {"type": "from_file", "file": str(path)}}, "test")
    backend = rights.load(configuration)
    assert backend.authorization("nobody", {"staff"}, "/groupcal") == "r"
    assert backend.authorization("nobody", {"other"}, "/groupcal") == ""
    assert backend.authorization("nobody", set(), "/groupcal") == ""


# --- xml, http ----------------------------------------------------------------


def test_pretty_xml_preserves_existing_text_and_tail_and_rejects_none():
    assert xmlutils.pretty_xml(None) == ""
    root = ET.Element("root")
    root.text = "keep"
    root.tail = "rtail"
    child = ET.SubElement(root, "child")
    child.tail = "middle"
    last = ET.SubElement(root, "last")
    last.tail = "end"
    text = xmlutils.pretty_xml(root)
    assert ">keep<" in text or "keep" in text
    assert "middle" in text
    assert "end" in text
    assert "rtail" in text
    # A blank tree still gets indentation, the boundary against the preserved text.
    blank = ET.Element("blank")
    ET.SubElement(blank, "only")
    indented = xmlutils.pretty_xml(blank)
    assert "\n" in indented


def test_make_clark_and_human_tag_boundaries():
    assert xmlutils.make_clark("D:href") == "{DAV:}href"
    with pytest.raises(ValueError, match="Invalid XML tag"):
        xmlutils.make_clark("{}")
    with pytest.raises(ValueError, match="Invalid XML tag"):
        xmlutils.make_clark("{DAV:}")
    with pytest.raises(ValueError, match="Invalid XML tag"):
        xmlutils.make_clark(":href")
    with pytest.raises(ValueError, match="Invalid XML tag"):
        xmlutils.make_clark("D:")
    with pytest.raises(ValueError, match="Unknown XML namespace prefix"):
        xmlutils.make_clark("ZZ:href")
    assert xmlutils.make_human_tag("D:href") == "D:href"
    with pytest.raises(ValueError, match="Invalid XML tag"):
        xmlutils.make_human_tag(":href")
    with pytest.raises(ValueError, match="Invalid XML tag"):
        xmlutils.make_human_tag("D:")
    with pytest.raises(ValueError, match="Unknown XML namespace prefix"):
        xmlutils.make_human_tag("ZZ:href")
    with pytest.raises(ValueError, match="Invalid XML tag"):
        xmlutils.make_human_tag("{}")
    with pytest.raises(ValueError, match="Invalid XML tag"):
        xmlutils.make_human_tag("{DAV:}")
    unknown = "{http://example.com/ns}item"
    assert xmlutils.make_human_tag(unknown) == unknown
    assert xmlutils.make_human_tag("{DAV:}href") == "D:href"


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


def test_props_from_request_ignores_unknown_elements_and_maps_resources():
    ignored = ET.Element(xmlutils.make_clark("D:prop"))
    assert xmlutils.props_from_request(_propupdate(ignored)) == {}
    assert xmlutils.props_from_request(None) == {}

    removed = ET.Element(xmlutils.make_clark("D:resourcetype"))
    props = xmlutils.props_from_request(_propupdate(_set_or_remove("remove", removed)))
    assert props["tag"] is None

    unknown_inner = ET.Element(xmlutils.make_clark("D:resourcetype"))
    ET.SubElement(unknown_inner, xmlutils.make_clark("D:collection"))
    props = xmlutils.props_from_request(_propupdate(_set_or_remove("set", unknown_inner)))
    assert props["tag"] is None

    for human, expected in (
            ("C:calendar", "VCALENDAR"),
            ("CS:subscribed", "VSUBSCRIBED"),
            ("CR:addressbook", "VADDRESSBOOK")):
        element = ET.Element(xmlutils.make_clark("D:resourcetype"))
        ET.SubElement(element, xmlutils.make_clark(human))
        props = xmlutils.props_from_request(_propupdate(_set_or_remove("set", element)))
        assert props["tag"] == expected

    comp = ET.Element(xmlutils.make_clark("C:supported-calendar-component-set"))
    ET.SubElement(comp, xmlutils.make_clark("C:comp"), {"name": "VEVENT"})
    ET.SubElement(comp, xmlutils.make_clark("D:href"))
    ET.SubElement(comp, xmlutils.make_clark("C:comp"), {"name": "VTODO"})
    props = xmlutils.props_from_request(_propupdate(_set_or_remove("set", comp)))
    assert props["C:supported-calendar-component-set"] == "VEVENT,VTODO"
    props = xmlutils.props_from_request(_propupdate(_set_or_remove("remove", comp)))
    assert props["C:supported-calendar-component-set"] is None

    display = ET.Element(xmlutils.make_clark("D:displayname"))
    display.text = "Hello"
    props = xmlutils.props_from_request(_propupdate(_set_or_remove("set", display)))
    assert props["D:displayname"] == "Hello"
    display.text = None
    props = xmlutils.props_from_request(_propupdate(_set_or_remove("set", display)))
    assert props["D:displayname"] == ""
    props = xmlutils.props_from_request(_propupdate(_set_or_remove("remove", display)))
    assert props["D:displayname"] is None


def test_read_request_body_skips_debug_logs_and_still_returns_the_body(monkeypatch):
    logger.setLevel(logging.ERROR)
    calls = _silence_traces(monkeypatch)
    configuration = config.load()
    environ = {"CONTENT_LENGTH": "4", "wsgi.input": io.BytesIO(b"abcd")}

    configuration.update({"logging": {"request_content_on_debug": "True"}}, "test")
    assert httputils.read_request_body(configuration, environ, {"method": "GET"}) == "abcd"

    configuration.update({
        "logging": {
            "request_content_on_debug": "False",
            "request_content_on_notice_condition": json.dumps(
                {"method": {"match": "equal", "value": "GET"}}),
        },
    }, "test")
    environ["wsgi.input"] = io.BytesIO(b"abcd")
    assert httputils.read_request_body(configuration, environ, {"method": "GET"}) == "abcd"
    environ["wsgi.input"] = io.BytesIO(b"abcd")
    assert httputils.read_request_body(configuration, environ, {"method": "POST"}) == "abcd"

    configuration.update({"logging": {"request_content_on_notice_condition": ""}}, "test")
    environ["wsgi.input"] = io.BytesIO(b"abcd")
    assert httputils.read_request_body(configuration, environ, {}) == "abcd"
    assert calls == []
    # Empty body is the boundary against a one-byte body.
    assert httputils.read_raw_request_body(configuration, {"wsgi.input": io.BytesIO(b"z")}) == b""


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


def test_serve_traversable_status_and_body(tmp_path):
    folder = tmp_path / "internal_data"
    infcloud = folder / "infcloud"
    infcloud.mkdir(parents=True)
    (folder / "index.html").write_bytes(b"class='infcloudlink-hidden'")
    (infcloud / "index.html").write_bytes(b"infcloud")
    (infcloud / "config.js").write_bytes(
        b"location.pathname.replace(RegExp('/+[^/]+/*(index\\.html)?$'),'')+"
        b"'/caldav.php/',settingsAccount: true,")
    (infcloud / "main.js").write_bytes(
        b"'InfCloud - the open source CalDAV/CardDAV web client'")
    (folder / "plain.txt").write_bytes(b"plain-body")
    (folder / "subdir").mkdir()
    (folder / "idxdir").mkdir()

    status, headers, body, _ = httputils.serve_folder(
        str(folder), "", "/.web/", "/.web", "index.html", {".html": "text/html"}, "text/plain")
    assert status == 200
    assert b"infcloudlink-hidden" not in body
    assert b"infcloud" in body
    assert "Last-Modified" in headers

    status, _, body, _ = httputils.serve_folder(
        str(folder), "", "/.web/index.html", "/.web", "index.html", {}, "text/plain")
    assert status == 200
    assert b"infcloudlink-hidden" not in body

    status, _, body, _ = httputils.serve_folder(
        str(folder), "", "/.web/infcloud/config.js", "/.web", "index.html", {}, "text/plain")
    assert status == 200
    assert b"/\\.web\\.infcloud/" in body
    assert b"'/'," in body
    assert b"settingsAccount: false," in body

    status, _, body, _ = httputils.serve_folder(
        str(folder), "", "/.web/infcloud/main.js", "/.web", "index.html", {}, "text/plain")
    assert status == 200
    assert b"served through Radicale" in body

    status, _, body, _ = httputils.serve_folder(
        str(folder), "", "/.web/plain.txt", "/.web", "index.html", {}, "text/plain")
    assert status == 200
    assert body == b"plain-body"

    status, headers, body, _ = httputils.serve_folder(
        str(folder), "", "/.web/subdir", "/.web", "index.html", {}, "text/plain")
    assert status == 302
    assert headers["Location"].endswith("/.web/subdir/")

    status, _, body, _ = httputils.serve_folder(
        str(folder), "", "/.web/foo~", "/.web", "index.html", {}, "text/plain")
    assert status == 404
    assert "could not be found" in body

    status, _, _, _ = httputils.serve_folder(
        str(folder), "", "/.web/missing.txt", "/.web", "index.html", {}, "text/plain")
    assert status == 404
    status, _, _, _ = httputils.serve_folder(
        str(folder), "", "/.web/", "/.web", "", {}, "text/plain")
    assert status == 404
    status, _, _, _ = httputils.serve_folder(
        str(folder), "", "/.web/", "/.web", "idxdir", {}, "text/plain")
    assert status == 404
    with pytest.raises(ValueError, match="path must start with path_prefix"):
        httputils.serve_folder(str(folder), "", "/other", "/.web")

    node = _Node("root", directory=True, children={
        "file.txt": _Node("file.txt", b"from-node"),
    })
    status, headers, body, _ = httputils._serve_traversable(
        node, "", "/.web/file.txt", "/.web", "index.html", {".txt": "text/plain"}, "application/octet-stream")
    assert status == 200
    assert body == b"from-node"
    assert "Last-Modified" not in headers


# --- pathutils, utils ---------------------------------------------------------


def test_rwlock_invalid_mode_flock_failure_and_broken_guarantee(tmp_path, monkeypatch):
    lock_path = tmp_path / "lock"
    lock = pathutils.RwLock(str(lock_path))
    with pytest.raises(ValueError, match="Invalid mode: 'x'"):
        with lock.acquire("x"):
            pass
    assert lock.locked == ""

    def fail_flock(*_args):
        raise OSError(errno.EIO, "flock failed")

    monkeypatch.setattr(pathutils.fcntl, "flock", fail_flock)
    with pytest.raises(RuntimeError, match="Locking the storage failed"):
        with lock.acquire("w"):
            pass

    monkeypatch.undo()
    lock = pathutils.RwLock(str(lock_path))
    lock._readers = 1
    with pytest.raises(RuntimeError, match="Guarantees failed"):
        with lock.acquire("w"):
            pass
    assert lock.locked == "r"


def test_rename_exchange_success_inval_and_other_errno(tmp_path, monkeypatch):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.write_text("source", encoding="utf-8")
    dst.write_text("dest", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid arguments"):
        pathutils.rename_exchange(str(tmp_path) + "/", str(dst))
    with pytest.raises(ValueError, match="Invalid arguments"):
        pathutils.rename_exchange("", "no-base")

    def forbid_fallback(*_args, **_kwargs):
        raise AssertionError("fallback used")

    monkeypatch.setattr(pathutils, "TemporaryDirectory", forbid_fallback)
    pathutils.rename_exchange(str(src), str(dst))
    assert src.read_text(encoding="utf-8") == "dest"
    assert dst.read_text(encoding="utf-8") == "source"
    monkeypatch.undo()

    def reject(*_args):
        return -1

    monkeypatch.setattr(pathutils, "renameat2", reject)
    monkeypatch.setattr(pathutils.ctypes, "get_errno", lambda: errno.EPERM)
    with pytest.raises(OSError) as exc_info:
        pathutils.rename_exchange(str(src), str(dst))
    assert exc_info.value.errno == errno.EPERM
    assert src.read_text(encoding="utf-8") == "dest"

    monkeypatch.setattr(pathutils.ctypes, "get_errno", lambda: errno.EINVAL)
    pathutils.rename_exchange(str(src), str(dst))
    assert src.read_text(encoding="utf-8") == "source"
    assert dst.read_text(encoding="utf-8") == "dest"


def test_renameat2_attributeerror_uses_the_copy_fallback(tmp_path):
    real_cdll = ctypes.CDLL

    class _MissingRename:
        def __getattr__(self, name):
            raise AttributeError(name)

    try:
        ctypes.CDLL = lambda *_args, **_kwargs: _MissingRename()  # type: ignore[assignment]
        importlib.reload(pathutils)
        assert pathutils.renameat2 is None
        src = tmp_path / "a"
        dst = tmp_path / "b"
        src.write_text("A", encoding="utf-8")
        dst.write_text("B", encoding="utf-8")
        pathutils.rename_exchange(str(src), str(dst))
        assert src.read_text(encoding="utf-8") == "B"
        assert dst.read_text(encoding="utf-8") == "A"
    finally:
        ctypes.CDLL = real_cdll
        importlib.reload(pathutils)


def test_fsync_darwin_fullfsync_einval_and_other_errno(tmp_path, monkeypatch):
    path = tmp_path / "data"
    path.write_text("x", encoding="utf-8")
    fd = os.open(str(path), os.O_RDWR)
    monkeypatch.setattr(pathutils.sys, "platform", "darwin", raising=False)
    monkeypatch.setattr(pathutils, "F_FULLFSYNC", 51, raising=False)
    seen = {}

    def full(_fd, cmd):
        seen["cmd"] = cmd
        return 0

    def no_fsync(_fd):
        raise AssertionError("os.fsync")

    monkeypatch.setattr(pathutils.fcntl, "fcntl", full)
    monkeypatch.setattr(pathutils.os, "fsync", no_fsync)
    assert pathutils.fsync(fd) is None
    assert seen["cmd"] == 51

    def inval(_fd, _cmd):
        raise OSError(errno.EINVAL, "no fullfsync")

    called = {}
    monkeypatch.setattr(pathutils.fcntl, "fcntl", inval)
    monkeypatch.setattr(pathutils.os, "fsync", lambda _fd: called.setdefault("yes", True))
    assert pathutils.fsync(fd) is None
    assert called["yes"] is True

    def eio(_fd, _cmd):
        raise OSError(errno.EIO, "fsync io")

    monkeypatch.setattr(pathutils.fcntl, "fcntl", eio)
    with pytest.raises(OSError) as exc_info:
        pathutils.fsync(fd)
    assert exc_info.value.errno == errno.EIO
    os.close(fd)


def test_path_to_filesystem_collision_and_collision_free(tmp_path, monkeypatch):
    root = tmp_path / "root"
    (root / "Cal").mkdir(parents=True)
    assert pathutils.path_to_filesystem(str(root), "") == str(root)

    class _Entries:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def __iter__(self):
            yield SimpleNamespace(name="other")

    monkeypatch.setattr(pathutils.os, "scandir", lambda _path: _Entries())
    with pytest.raises(pathutils.CollidingPathError, match="Cal"):
        pathutils.path_to_filesystem(str(root), "Cal", False)
    found = pathutils.path_to_filesystem(str(root), "Cal", True)
    assert found.endswith("Cal")


def test_name_from_path_and_permission_lookup_failures(tmp_path, monkeypatch):
    collection = _CollectionPath("user/cal")
    assert pathutils.name_from_path("/user/cal/item.ics", collection) == "item.ics"
    with pytest.raises(ValueError, match="doesn't start with"):
        pathutils.name_from_path("/other/item.ics", collection)
    with pytest.raises(ValueError, match="not a component"):
        pathutils.name_from_path("/user/cal/a/b", collection)

    def explode(self, *_args, **_kwargs):
        raise NotImplementedError("stat")

    monkeypatch.setattr(pathlib.Path, "stat", explode)
    monkeypatch.setattr(pathlib.Path, "owner", lambda self: (_ for _ in ()).throw(KeyError("owner")))
    monkeypatch.setattr(pathlib.Path, "group", lambda self: (_ for _ in ()).throw(KeyError("group")))
    target = tmp_path / "file"
    target.write_text("x", encoding="utf-8")
    assert pathutils.path_permissions(str(target)) == ["UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"]
    assert "UNKNOWN" in pathutils.path_permissions_as_string(str(target))


def test_filesystem_feature_probes_report_failures(tmp_path, monkeypatch):
    a_file = tmp_path / "file"
    a_file.write_text("x", encoding="utf-8")
    for probe in (
            pathutils.path_supports_symlink,
            pathutils.path_is_collision_free_case_sensitive,
            pathutils.path_is_collision_free_no_short_filename,
            pathutils.path_supports_unicode,
            pathutils.path_supports_trailing_whitespace,
            pathutils.path_supports_problematic_chars):
        with pytest.raises(ValueError, match="is not a path"):
            probe(str(a_file))

    def deny_symlink(*_args, **_kwargs):
        raise PermissionError("symlink")

    monkeypatch.setattr(pathutils.os, "symlink", deny_symlink)
    assert pathutils.path_supports_symlink(str(tmp_path)) is False
    monkeypatch.setattr(pathutils.os, "symlink", lambda *_a, **_k: (_ for _ in ()).throw(OSError("symlink")))
    assert pathutils.path_supports_symlink(str(tmp_path)) is False

    real_mkdir = pathutils.os.mkdir

    def mkdir(path, *args, **kwargs):
        base = os.path.basename(str(path))
        if base == "testdir" or base.endswith("~1"):
            raise FileExistsError(path)
        if any(token in base for token in ("*", "?", " ", "\U0001f600")):
            raise OSError(errno.EINVAL, "bad", path)
        return real_mkdir(path, *args, **kwargs)

    monkeypatch.setattr(pathutils.os, "mkdir", mkdir)
    assert pathutils.path_is_collision_free_case_sensitive(str(tmp_path)) is False
    assert pathutils.path_is_collision_free_no_short_filename(str(tmp_path)) is False
    assert pathutils.path_supports_unicode(str(tmp_path)) is False
    assert pathutils.path_supports_trailing_whitespace(str(tmp_path)) is False
    assert pathutils.path_supports_problematic_chars(str(tmp_path)) is False

    monkeypatch.undo()
    real_scandir = os.scandir

    class _Hide:
        def __init__(self, path):
            self._inner = real_scandir(path)

        def __enter__(self):
            self._inner.__enter__()
            return self

        def __exit__(self, *args):
            return self._inner.__exit__(*args)

        def __iter__(self):
            for entry in self._inner:
                if entry.name.startswith("TEST") or "*" in entry.name or "?" in entry.name:
                    continue
                yield entry

    monkeypatch.setattr(pathutils.os, "scandir", lambda path: _Hide(path))
    assert pathutils.path_supports_unicode(str(tmp_path)) is False
    assert pathutils.path_supports_trailing_whitespace(str(tmp_path)) is False
    assert pathutils.path_supports_problematic_chars(str(tmp_path)) is False


def test_user_groups_unknown_names_and_win32_string(monkeypatch):
    def no_user(_uid):
        raise KeyError("user")

    monkeypatch.setattr(utils.pwd, "getpwuid", no_user)
    monkeypatch.setattr(utils.os, "getgrouplist", lambda *_a, **_k: (_ for _ in ()).throw(OSError("groups")))
    monkeypatch.setattr(utils.grp, "getgrnam", lambda *_a, **_k: (_ for _ in ()).throw(KeyError("nam")))

    def all_groups():
        yield ("found", "x", os.getegid(), [])
        yield ("other", "x", os.getegid() + 1, [])

    monkeypatch.setattr(utils.grp, "getgrall", all_groups)
    text = utils.user_groups_as_string()
    assert "UNKNOWN(%d)" % os.geteuid() in text
    assert "found(%d)" % os.getegid() in text

    monkeypatch.setattr(utils.grp, "getgrall", lambda: [("nope", "x", os.getegid() + 9, [])])
    text = utils.user_groups_as_string()
    assert "UNKNOWN(%d)" % os.getegid() in text

    monkeypatch.undo()
    monkeypatch.setattr(utils.os, "getgrouplist", lambda name, gid: [gid, gid + 50])

    def grgid(gid):
        raise KeyError(gid)

    monkeypatch.setattr(utils.grp, "getgrgid", grgid)
    text = utils.user_groups_as_string()
    assert "UNKNOWN(%d)" % (os.getegid() + 50) in text

    monkeypatch.setattr(utils.sys, "platform", "win32")
    monkeypatch.setattr(utils.os, "getlogin", lambda: "covuser")
    assert utils.user_groups_as_string() == "user=covuser"


def test_format_ut_win32_old_python_and_small_pointer(monkeypatch):
    monkeypatch.setattr(utils.sys, "platform", "win32")
    assert utils.format_ut(0) == "0"
    assert utils.format_ut(1_700_000_000) == "1700000000"
    monkeypatch.setattr(utils.sys, "platform", "linux")

    class _DateTime:
        def __new__(cls, *args, **kwargs):
            return datetime.datetime(*args, **kwargs)

        @staticmethod
        def utcfromtimestamp(ts):
            assert ts == 1_700_000_000
            return datetime.datetime(1999, 1, 2)

        @staticmethod
        def fromtimestamp(*_args, **_kwargs):
            raise AssertionError("fromtimestamp")

    monkeypatch.setattr(utils, "datetime", SimpleNamespace(
        datetime=_DateTime,
        timedelta=datetime.timedelta,
        timezone=datetime.timezone,
        UTC=getattr(datetime, "UTC", datetime.timezone.utc)))
    monkeypatch.setattr(utils.sys, "version_info", (3, 9, 0))
    assert "1999-01-02" in utils.format_ut(1_700_000_000)

    monkeypatch.setattr(utils.sys, "maxsize", 2 ** 31)
    monkeypatch.setattr(utils.sys, "version_info", sys.version_info)
    assert "2023-11-14T22:13:20Z" in utils.format_ut(1_700_000_000)


def test_data_to_special_and_hexdump_line_limit():
    assert utils.dataToSpecial(bytes([0xf0]), 1) == "4"
    assert utils.dataToSpecial(bytes([0xf7]), 1) == "4"
    assert utils.dataToSpecial(bytes([0xf8]), 1) == "3"
    assert utils.dataToSpecial(bytes([0xff]), 1) == "3"
    assert utils.dataToSpecial(bytes([0xe0]), 1) == "2"
    assert utils.dataToSpecial(bytes([0xdf]), 1) == "."
    dumped = utils.hexdump_line("a" * 250, limit=200)
    assert dumped.startswith("250/250")
    assert dumped.count("61 ") == 200
    short = utils.hexdump_line("ab", limit=200)
    assert short.count("61 ") == 1
    assert short.count("62 ") == 1


def test_ssl_get_protocols_skips_sslv3_when_minimum_is_tlsv1():
    context = SimpleNamespace(
        options=0,
        minimum_version=ssl.TLSVersion.TLSv1,
        maximum_version=ssl.TLSVersion.TLSv1_3)
    protocols = utils.ssl_get_protocols(context)
    assert "SSLv3" not in protocols
    assert "TLSv1" in protocols
    context.minimum_version = ssl.TLSVersion.SSLv3
    assert "SSLv3" in utils.ssl_get_protocols(context)


# --- log, config, package init, main -----------------------------------------


def test_radicale_logger_levels_and_type_checking_aliases():
    import typing
    typing.TYPE_CHECKING = True
    try:
        importlib.reload(log)
        assert log.RadicaleLogger.trace is logging.Logger.debug
        assert log.RadicaleLogger.notice is logging.Logger.info
        assert log.RadicaleLogger.alert is logging.Logger.critical
    finally:
        typing.TYPE_CHECKING = False
        importlib.reload(log)
    previous_class = logging.getLoggerClass()
    logging.setLoggerClass(log.RadicaleLogger)
    try:
        custom = logging.getLogger("cov-radicale-logger")
        custom.propagate = False
        custom.handlers.clear()
        custom.setLevel(log.LOG_LEVEL_TRACE)
        seen = []

        class _Handler(logging.Handler):
            def emit(self, record):
                seen.append(record.getMessage())

        custom.addHandler(_Handler())
        custom.trace("t-msg")
        custom.notice("n-msg")
        custom.alert("a-msg")
        assert seen == ["t-msg", "n-msg", "a-msg"]
        custom.setLevel(log.LOG_LEVEL_ALERT + 1)
        custom.trace("no-t")
        custom.notice("no-n")
        custom.alert("no-a")
        assert seen == ["t-msg", "n-msg", "a-msg"]
    finally:
        logging.setLoggerClass(previous_class)


def test_ident_factory_thread_edges_and_journal_stream(monkeypatch, tmp_path, caplog):
    caplog.set_level(logging.ERROR)

    def upstream(*args, **kwargs):
        record = logging.LogRecord(*args, **kwargs)
        record.thread = None
        record.threadName = ""
        return record

    factory = log.IdentLogRecordFactory(upstream)
    record = factory("radicale", logging.INFO, __file__, 1, "none-thread", (), None)
    assert "/" not in str(record.ident)
    assert record.tid is None

    def other_thread(*args, **kwargs):
        record = logging.LogRecord(*args, **kwargs)
        record.thread = 2 ** 40
        record.threadName = ""
        return record

    record = log.IdentLogRecordFactory(other_thread)(
        "radicale", logging.INFO, __file__, 1, "other", (), None)
    assert record.ident.endswith("/unknown")
    assert record.tid is None

    monkeypatch.delattr(log.threading, "get_native_id", raising=False)

    def same_thread(*args, **kwargs):
        record = logging.LogRecord(*args, **kwargs)
        record.thread = threading.get_ident()
        return record

    record = log.IdentLogRecordFactory(same_thread)(
        "radicale", logging.INFO, __file__, 1, "native", (), None)
    assert record.tid is None

    monkeypatch.setenv("JOURNAL_STREAM", "7:8")
    handler = log.ThreadedStreamHandler()
    assert handler._journal_stream_id == (7, 8)
    monkeypatch.setenv("JOURNAL_STREAM", "nope")
    assert log.ThreadedStreamHandler()._journal_stream_id is None
    monkeypatch.setenv("JOURNAL_STREAM", "1:x")
    assert log.ThreadedStreamHandler()._journal_stream_id is None

    stream_path = tmp_path / "journal-stream"
    stream = stream_path.open("w+b")
    try:
        stat = os.fstat(stream.fileno())
        handler = log.ThreadedStreamHandler("verbose")
        handler._journal_stream_id = (stat.st_dev, stat.st_ino)
        handler._try_emit_journal = lambda _record: True  # type: ignore[assignment]
        record = logging.LogRecord("radicale", logging.INFO, __file__, 1, "journaled", (), None)
        with handler.register_stream(stream):
            handler.emit(record)
        stream.seek(0)
        assert stream.read() == b""
    finally:
        stream.close()

    class _Broken(io.IOBase):
        def write(self, _data):
            raise OSError("disk full")

        def flush(self):
            return None

        def fileno(self):
            raise OSError("no fileno")

    handler = log.ThreadedStreamHandler("verbose")
    stderr = io.StringIO()
    monkeypatch.setattr(sys, "stderr", stderr)
    record = logging.LogRecord("radicale", logging.INFO, __file__, 1, "lost-line", (), None)
    with handler.register_stream(_Broken()):
        handler.emit(record)
    assert "Logging error" in stderr.getvalue()
    assert "lost-line" in stderr.getvalue()

    def socket_fails(*_args, **_kwargs):
        raise OSError("socket exploded")

    monkeypatch.setattr(log.socket, "socket", socket_fails)
    handler = log.ThreadedStreamHandler()
    record = logging.LogRecord("radicale", logging.ERROR, __file__, 1, "j", (), None)
    assert handler._try_emit_journal(record) is False
    assert handler._journal_socket is None
    assert "socket exploded" in caplog.text
    assert "Failed to connect to systemd journal" in caplog.text


def test_set_level_skips_repeated_backtrace_messages_and_disabled_trace(caplog):
    caplog.set_level(logging.DEBUG)
    log.logger_display_backtrace_enabled = True
    log.set_level(logging.DEBUG, True)
    assert "enabled by option" not in caplog.text
    assert "Logging level set to" in caplog.text
    log.logger_display_backtrace_disabled = True
    log.set_level(logging.INFO, True)
    assert caplog.text.count("disabled in this loglevel") == 0

    logging.disable(logging.DEBUG)
    try:
        log.set_level("trace", True, "auth/")
        log.set_level("trace", True, "")
    finally:
        logging.disable(logging.NOTSET)
    assert logger.level == log.LOG_LEVEL_TRACE


def test_log_conditional_match_boundaries_with_and_without_debug():
    logger.setLevel(logging.DEBUG)
    assert log.log_conditional("n", {"host": {"match": "equal", "value": "192.0.2.10"}}, {"host": "192.0.2.11"}) is False
    assert log.log_conditional("n", {"host": {"match": "equal", "value": "192.0.2.10"}}, {"host": "192.0.2.10"}) is True
    assert log.log_conditional(
        "n",
        {"host": {"match": "included", "value": "2001:db8::/32"}},
        {"host": "2001:db9::1/128"}) is False
    assert log.log_conditional(
        "n",
        {"host": {"match": "included", "value": "2001:db8::/32"}},
        {"host": "2001:db8::1/128"}) is True
    assert log.log_conditional(
        "n",
        {"host": {"match": "excluded", "value": "2001:db8::/32"}},
        {"host": "2001:db9::1/128"}) is True
    assert log.log_conditional(
        "n",
        {"host": {"match": "excluded", "value": "192.0.2.0/24"}},
        {"host": "unknown"}) is True
    logger.setLevel(logging.ERROR)
    assert log.log_conditional(
        "n", {"method": {"match": "contains", "value": "GET"}}, {"method": "GET"}) is True
    assert log.log_conditional(
        "n", {"status": {"match": "between", "value": "200"}}, {"status": 200}) is True
    assert log.log_conditional(
        "n", {"host": {"match": "fuzzy", "value": "192.0.2.1"}}, {"host": "192.0.2.1"}) is True
    log.LOG_CONDITION_TOKEN["weird"] = "other"
    try:
        assert log.log_conditional(
            "n", {"weird": {"match": "equal", "value": "x"}}, {"weird": "x"}) is True
    finally:
        del log.LOG_CONDITION_TOKEN["weird"]
    assert log.log_conditional("n", {}, {}) is False


def test_config_validators_and_missing_lookups(monkeypatch):
    with pytest.raises(ValueError, match="infinite"):
        config.positive_float(float("inf"))
    real_isfinite = config.math.isfinite
    monkeypatch.setattr(config.math, "isfinite", lambda value: True if value != value else real_isfinite(value))
    with pytest.raises(ValueError, match="not a number"):
        config.positive_float(float("nan"))
    assert config.positive_float(0) == 0
    assert config.positive_float("1.5") == 1.5

    with pytest.raises(ValueError, match="unsupported permission"):
        config.rights_permission("R#")
    with pytest.raises(ValueError, match="P\\+p"):
        config.rights_permission("Pp")
    with pytest.raises(ValueError, match="E\\+e"):
        config.rights_permission("Ee")
    assert config.rights_permission("RW") == "RW"
    with pytest.raises(ValueError, match="unsupported level"):
        config.logging_level("verbose")
    with pytest.raises(ValueError, match="unsupported validation type"):
        config.validate_types("loose")
    with pytest.raises(ValueError, match="unsupported profiling"):
        config.profiling("always")
    assert config.validate_types("strict") == "strict"
    assert config.profiling("none") == "none"

    monkeypatch.setattr(config.sys, "platform", "win32")
    monkeypatch.setenv("COV_STORAGE_DIR", "/tmp/cov-storage")

    def expandvars(value):
        return value.replace("%COV_STORAGE_DIR%", os.environ["COV_STORAGE_DIR"])

    monkeypatch.setattr(config.os.path, "expandvars", expandvars)
    expanded = config.filepath("%COV_STORAGE_DIR%/sub")
    assert expanded == os.path.abspath("/tmp/cov-storage/sub")
    assert config.filepath("plain") == os.path.abspath("plain")
    assert config.filepath("") == ""

    assert config.json_str_condition("") == {}
    assert config.json_str_condition(None) == {}
    with pytest.raises(ValueError, match="unsupported log condition token"):
        config.json_str_condition(json.dumps({"nope": {"match": "equal", "value": "a"}}))
    with pytest.raises(ValueError, match="unsupported log condition"):
        config.json_str_condition(json.dumps({"method": {"nope": "x", "match": "equal", "value": "a"}}))
    with pytest.raises(ValueError, match="unsupported log match"):
        config.json_str_condition(json.dumps({"method": {"match": "nope", "value": "a"}}))
    with pytest.raises(ValueError, match="unsupported log match"):
        config.json_str_condition(json.dumps({"status": {"match": "nope", "value": "200"}}))
    with pytest.raises(ValueError, match="unsupported log match"):
        config.json_str_condition(json.dumps({"host": {"match": "nope", "value": "192.0.2.1"}}))
    log.LOG_CONDITION_TOKEN["weird"] = "other"
    try:
        with pytest.raises(RuntimeError, match="unsupported log match"):
            config.json_str_condition(json.dumps({"weird": {"match": "equal", "value": "a"}}))
    finally:
        del log.LOG_CONDITION_TOKEN["weird"]
    parsed = config.json_str_condition(json.dumps({"method": {"match": "re", "value": "T.*"}}))
    assert parsed["method"]["value"] == "T.*"
    parsed = config.json_str_condition(json.dumps({"method": {"match": "re", "value": "Nope"}}))
    assert parsed["method"]["value"] == "Nope"
    with pytest.raises(ValueError, match="unsupported log match value\\(int\\)"):
        config.json_str_condition(json.dumps({"status": {"match": "equal", "value": "01"}}))
    log.LOG_CONDITION_TOKEN["count"] = "int"
    try:
        parsed = config.json_str_condition(json.dumps({"count": {"match": "equal", "value": "5"}}))
        assert parsed["count"]["value"] == "5"
    finally:
        del log.LOG_CONDITION_TOKEN["count"]
    parsed = config.json_str_condition(json.dumps({"host": {"match": "equal", "value": "192.0.2.1"}}))
    assert parsed["host"]["value"] == "192.0.2.1"
    parsed = config.json_str_condition(json.dumps({"host": {"match": "included", "value": "192.0.2.0/24"}}))
    assert parsed["host"]["match"] == "included"
    with pytest.raises(ValueError, match="unsupported log match value\\(ipaddress\\)"):
        config.json_str_condition(json.dumps({"host": {"match": "equal", "value": "not-an-ip"}}))
    with pytest.raises(ValueError, match="incomplete condition"):
        config.json_str_condition(json.dumps({"method": {"match": "equal"}}))

    configuration = config.load()
    with pytest.raises(RuntimeError, match="unspecified config"):
        configuration.update({"server": {"timeout": "nope"}})
    with pytest.raises(KeyError) as exc_info:
        configuration.get("server", "missing-option")
    assert exc_info.value.args == ("server", "missing-option")
    with pytest.raises(KeyError) as exc_info:
        configuration.get_raw("server", "missing-option")
    assert exc_info.value.args == ("server", "missing-option")
    with pytest.raises(KeyError) as exc_info:
        configuration.get_source("server", "missing-option")
    assert exc_info.value.args == ("server", "missing-option")
    assert configuration.get_source("server", "timeout") == "default config"


def test_wsgi_application_warns_when_only_the_default_config_is_active(monkeypatch, caplog, tmp_path):
    caplog.set_level(logging.WARNING)
    radicale._application_instance = None
    radicale._application_config_path = None
    monkeypatch.setenv("RADICALE_CONFIG", "")
    option = config.DEFAULT_CONFIG_SCHEMA["storage"]["filesystem_folder"]
    saved_folder = option["value"]
    option["value"] = str(tmp_path / "collections")
    errors = io.StringIO()
    captured = {}

    def start_response(status, headers, exc_info=None):
        captured["status"] = status
        return errors.write

    environ = {
        "REQUEST_METHOD": "GET",
        "PATH_INFO": "/",
        "SCRIPT_NAME": "",
        "QUERY_STRING": "",
        "SERVER_NAME": "127.0.0.1",
        "SERVER_PORT": "5232",
        "SERVER_PROTOCOL": "HTTP/1.1",
        "wsgi.version": (1, 0),
        "wsgi.url_scheme": "http",
        "wsgi.input": io.BytesIO(),
        "wsgi.errors": errors,
        "wsgi.multithread": False,
        "wsgi.multiprocess": False,
        "wsgi.run_once": False,
        "RADICALE_CONFIG": "",
    }
    try:
        body = b"".join(radicale.application(environ, start_response))
    finally:
        option["value"] = saved_folder
        radicale._application_instance = None
        radicale._application_config_path = None
    assert captured["status"].startswith("302")
    assert body
    assert "only default config is active" in caplog.text or "only default config is active" in errors.getvalue()


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


def test_first_signal_handler_exits_and_hidden_sections_are_omitted(capsys, caplog):
    recorded = []
    real_signal = signal.signal

    def spy(number, handler):
        recorded.append(handler)
        return real_signal(number, handler)

    signal.signal = spy  # type: ignore[assignment]
    try:
        assert _run_cli(["--version"]) == 0
    finally:
        signal.signal = real_signal
    assert recorded
    with pytest.raises(SystemExit) as exc_info:
        recorded[0](signal.SIGTERM, None)
    assert exc_info.value.code == 1

    config.DEFAULT_CONFIG_SCHEMA["_hidden"] = OrderedDict()
    config.DEFAULT_CONFIG_SCHEMA["plugins"] = OrderedDict([
        ("_allow_extra", str),
        ("sample", {"value": "x", "help": "sample option", "type": str}),
    ])
    try:
        code = _run_cli(["--help"])
    except SystemExit as exc:
        code = exc.code
    captured = capsys.readouterr().out
    assert code == 0
    assert "_hidden" not in captured
    assert "--plugins-sample" in captured
    assert captured.count("e.g. --headers-Pragma=no-cache") == 1
    assert "additional options allowed" in captured


def test_verify_sharing_exception_exits(monkeypatch, caplog, tmp_path):
    caplog.set_level(logging.DEBUG)
    from radicale import __main__ as main

    class _Broken:
        def verify(self):
            raise RuntimeError("sharing exploded")

    monkeypatch.setattr(main.sharing, "load", lambda _configuration: _Broken())
    folder = tmp_path / "collections"
    folder.mkdir()
    code = _run_cli(["--verify-sharing", "--storage-filesystem-folder", str(folder)])
    assert code == 1
    assert "An exception occurred during sharing database verification" in caplog.text
    assert "sharing exploded" in caplog.text


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
    assert any(msg == "storage/has_uid" for msg in calls)

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
    (0, "result: 1 ns", "info"),
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
    with pytest.raises(RuntimeError, match="Fsync'ing directory"):
        storage_._sync_directory(str(tmp_path))

    monkeypatch.setattr(storage_base.sys, "platform", "win32")

    def opened(*_args, **_kwargs):
        raise AssertionError("directory was opened")

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
        handle.write(b"not pickle")
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

    storage_._group_collections_folder = "GROUPS"
    os.makedirs(os.path.join(storage_._get_collection_root_folder(), "GROUPS"))
    calls = _capture_traces(monkeypatch)
    list(storage_.discover("/", "1", user_groups={"staff"}))
    assert any("searching for collection by user group in folder" in msg for msg in calls)
    assert any("is not existing (skip)" in msg for msg in calls)

    root = storage_._get_collection_root_folder()
    encoded = base64.b64encode(b"staff").decode("ascii")
    os.makedirs(os.path.join(root, "GROUPS", encoded))
    calls = _capture_traces(monkeypatch)
    grouped = [item for item in storage_.discover("/", "1", user_groups={"staff"})
               if isinstance(item, storage.BaseCollection)]
    assert any(item.path == "GROUPS/%s" % encoded for item in grouped)
    assert any("child_path" in msg for msg in calls)

    calls = _silence_traces(monkeypatch)
    encoded_other = base64.b64encode(b"other").decode("ascii")
    grouped = [item for item in storage_.discover("/", "1", user_groups={"other"})
               if isinstance(item, storage.BaseCollection)]
    assert not any(item.path == "GROUPS/%s" % encoded_other for item in grouped)
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
        handle.write(b"not pickle")
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
    storage_ = _storage(tmp_path / "ok", {"storage": {
        "hook": "echo hook-out; echo hook-out > %s; echo hook-err >&2" % marker}})
    _calendar(storage_, items=[_event()])
    assert marker.read_text(encoding="utf-8").strip() == "hook-out"
    assert "Captured stdout from storage hook" in caplog.text
    assert "hook-out" in caplog.text
    assert "Captured stderr from storage hook" in caplog.text
    assert "hook-err" in caplog.text

    caplog.clear()
    failing = _storage(tmp_path / "fail", {"storage": {"hook": "echo ran; exit 3"}})
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

    monkeypatch.setattr(storage_lock.os, "killpg", killpg)
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

    monkeypatch.setattr(storage_lock.os, "setpgrp", setpgrp)
    old = _storage(tmp_path / "py39", {"storage": {"hook": "echo old-python"}})
    _calendar(old, href="/user/cal/", items=[_event()])
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
            handle.write(b"not pickle")
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
                raise OSError(errno.EINVAL, "bad name")
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
    assert storage_.verify() is True
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
    assert storage_.verify() is True
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


def test_server_compat_constants_when_socket_names_are_missing():
    """Missing socket names take the Windows fallback, then stay unset."""
    import radicale.server_cheroot as server_cheroot
    names = ("EAI_ADDRFAMILY", "EAI_NODATA", "EAI_NONAME", "IPPROTO_IPV6")
    saved_attrs = {}
    for name in names:
        if hasattr(socket, name):
            saved_attrs[name] = getattr(socket, name)
    saved_platform = sys.platform
    try:
        for name in ("EAI_ADDRFAMILY", "EAI_NODATA", "IPPROTO_IPV6"):
            if hasattr(socket, name):
                delattr(socket, name)
        sys.platform = "win32"
        importlib.reload(server)
        importlib.reload(server_cheroot)
        assert server.COMPAT_EAI_ADDRFAMILY == saved_attrs["EAI_NONAME"]
        assert server.COMPAT_EAI_NODATA == saved_attrs["EAI_NONAME"]
        assert server.COMPAT_IPPROTO_IPV6 == 41
        assert server_cheroot.COMPAT_IPPROTO_IPV6 == 41

        if hasattr(socket, "EAI_NONAME"):
            delattr(socket, "EAI_NONAME")
        sys.platform = "linux"
        server.COMPAT_EAI_ADDRFAMILY = -1
        server.COMPAT_EAI_NODATA = -1
        server.COMPAT_IPPROTO_IPV6 = -1
        server_cheroot.COMPAT_IPPROTO_IPV6 = -1
        importlib.reload(server)
        importlib.reload(server_cheroot)
        assert server.COMPAT_EAI_ADDRFAMILY == -1
        assert server.COMPAT_EAI_NODATA == -1
        assert server.COMPAT_IPPROTO_IPV6 == -1
        assert server_cheroot.COMPAT_IPPROTO_IPV6 == -1
    finally:
        sys.platform = saved_platform
        for name, value in saved_attrs.items():
            setattr(socket, name, value)
        importlib.reload(server)
        importlib.reload(server_cheroot)
    assert server.COMPAT_IPPROTO_IPV6 == socket.IPPROTO_IPV6
    assert server_cheroot.COMPAT_IPPROTO_IPV6 == socket.IPPROTO_IPV6


def test_builtin_timeout_zero_skips_settimeout_and_positive_applies(tmp_path, monkeypatch):
    seen = []
    real_settimeout = socket.socket.settimeout

    def spy(self, value):
        seen.append(value)
        return real_settimeout(self, value)

    monkeypatch.setattr(socket.socket, "settimeout", spy)
    port = _free_port()
    left, right = socket.socketpair()
    thread, holder = _thread_result(
        lambda: server.serve(_bind_server(tmp_path / "zero", port, timeout="0"), right))
    try:
        status, body = _http_get(port)
        assert status == 302
        assert body
        assert 0 not in seen and 0.0 not in seen
    finally:
        left.close()
        thread.join(10)
        right.close()
    assert "exc" not in holder

    seen.clear()
    port = _free_port()
    left, right = socket.socketpair()
    thread, holder = _thread_result(
        lambda: server.serve(_bind_server(tmp_path / "one", port, timeout="1"), right))
    try:
        status, _body = _http_get(port)
        assert status == 302
        assert 1.0 in seen
    finally:
        left.close()
        thread.join(10)
        right.close()
    assert "exc" not in holder


def test_builtin_unlimited_and_single_connection_limit(tmp_path, monkeypatch):
    port = _free_port()
    left, right = socket.socketpair()
    thread, holder = _thread_result(lambda: server.serve(
        _bind_server(tmp_path / "unlimited", port, max_connections="0"), right))
    try:
        status, _body = _http_get(port)
        assert status == 302
    finally:
        left.close()
        thread.join(10)
        right.close()
    assert "exc" not in holder

    entered = []
    release = threading.Event()
    real_handle = server.RequestHandler.handle

    def slow(self):
        entered.append(1)
        if len(entered) == 1:
            assert release.wait(5)
        return real_handle(self)

    monkeypatch.setattr(server.RequestHandler, "handle", slow)
    port = _free_port()
    left, right = socket.socketpair()
    thread, holder = _thread_result(lambda: server.serve(
        _bind_server(tmp_path / "one", port, max_connections="1"), right))
    results = []

    def client():
        results.append(_http_get(port))

    try:
        first = threading.Thread(target=client)
        first.start()
        deadline = time.monotonic() + 5
        while len(entered) < 1:
            assert time.monotonic() < deadline
            time.sleep(0.02)
        second = threading.Thread(target=client)
        second.start()
        time.sleep(0.3)
        assert len(entered) == 1
        release.set()
        first.join(5)
        second.join(5)
        assert [item[0] for item in results] == [302, 302]
    finally:
        release.set()
        left.close()
        thread.join(10)
        right.close()
    assert "exc" not in holder


def test_builtin_loop_ignores_a_stray_socket_and_stops_without_one(tmp_path, monkeypatch):
    extra, extra_out = socket.socketpair()
    state = {"n": 0}
    real_select = server.select.select

    def select_with_extra(rlist, wlist, xlist, timeout=None):
        state["n"] += 1
        if state["n"] == 1:
            return [extra], [], []
        return real_select(rlist, wlist, xlist, timeout)

    monkeypatch.setattr(server.select, "select", select_with_extra)
    port = _free_port()
    left, right = socket.socketpair()
    thread, holder = _thread_result(
        lambda: server.serve(_bind_server(tmp_path / "stray", port), right))
    try:
        status, _body = _http_get(port)
        assert status == 302
        assert state["n"] >= 2
    finally:
        left.close()
        thread.join(10)
        right.close()
        extra.close()
        extra_out.close()
    assert "exc" not in holder
    monkeypatch.undo()

    def select_stop(rlist, wlist, xlist, timeout=None):
        raise RuntimeError("stop-loop")

    monkeypatch.setattr(server.select, "select", select_stop)
    port = _free_port()
    thread, holder = _thread_result(
        lambda: server.serve(_bind_server(tmp_path / "nostop", port), None))
    thread.join(10)
    assert not thread.is_alive()
    assert isinstance(holder.get("exc"), RuntimeError)
    assert "stop-loop" in str(holder["exc"])


def test_builtin_waits_for_workers_and_uses_windows_select_timeout(tmp_path, monkeypatch):
    release = threading.Event()
    started = threading.Event()
    real_handle = server.RequestHandler.handle

    def slow(self):
        started.set()
        assert release.wait(5)
        return real_handle(self)

    monkeypatch.setattr(server.RequestHandler, "handle", slow)
    port = _free_port()
    left, right = socket.socketpair()
    result = {}

    def client():
        try:
            result["resp"] = _http_get(port)
        except BaseException as exc:  # noqa: BLE001
            result["exc"] = exc

    thread, holder = _thread_result(
        lambda: server.serve(_bind_server(tmp_path / "workers", port), right))
    client_thread = threading.Thread(target=client)
    try:
        client_thread.start()
        assert started.wait(5)
        left.close()
        time.sleep(0.3)
        assert thread.is_alive()
        release.set()
        client_thread.join(5)
        thread.join(5)
    finally:
        release.set()
        left.close()
        thread.join(5)
        right.close()
    assert "exc" not in holder and "exc" not in result
    assert result["resp"][0] == 302
    monkeypatch.undo()

    timeouts = []
    real_select = server.select.select

    def select_timeout(rlist, wlist, xlist, timeout=None):
        timeouts.append(timeout)
        if timeout == 1.0:
            timeout = 0.01
        return real_select(rlist, wlist, xlist, timeout)

    monkeypatch.setattr(server.sys, "platform", "win32")
    monkeypatch.setattr(server.os, "getlogin", lambda: "cov-user")
    monkeypatch.setattr(server.select, "select", select_timeout)
    port = _free_port()
    left, right = socket.socketpair()
    thread, holder = _thread_result(
        lambda: server.serve(_bind_server(tmp_path / "win", port), right))
    try:
        status, _body = _http_get(port)
        assert status == 302
        assert 1.0 in timeouts
    finally:
        left.close()
        thread.join(10)
        right.close()
    assert "exc" not in holder


def test_builtin_logs_pythonpath_request_errors_and_long_lines(tmp_path, monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    logger.setLevel(logging.INFO)
    monkeypatch.setenv("PYTHONPATH", "/tmp/cov-py")
    port = _free_port()
    left, right = socket.socketpair()
    thread, holder = _thread_result(
        lambda: server.serve(_bind_server(tmp_path / "py", port), right))
    try:
        status, _body = _http_get(port)
        assert status == 302
        assert "with PYTHONPATH='/tmp/cov-py'" in caplog.text or \
            'with PYTHONPATH="/tmp/cov-py"' in caplog.text
        sock = socket.create_connection(("127.0.0.1", port), timeout=5)
        try:
            sock.sendall(b"GET /" + (b"A" * 65537) + b"\r\n\r\n")
            sock.settimeout(5)
            data = b""
            while b"414" not in data:
                chunk = sock.recv(4096)
                assert chunk
                data += chunk
            assert b"414" in data
        finally:
            sock.close()
    finally:
        left.close()
        thread.join(10)
        right.close()
    assert "exc" not in holder

    try:
        raise socket.timeout("slow-client")
    except socket.timeout:
        server.ParallelHTTPServer.handle_error(None, None, ("127.0.0.1", 9))
    assert "Client timed out" in caplog.text
    caplog.clear()
    try:
        raise RuntimeError("boom-request")
    except RuntimeError:
        server.ParallelHTTPServer.handle_error(None, None, ("127.0.0.1", 9))
    assert "An exception occurred during request" in caplog.text
    assert "boom-request" in caplog.text

    handler = server.ServerHandler(
        io.BytesIO(), io.BytesIO(), io.StringIO(), {"SERVER_NAME": "localhost"})
    try:
        raise RuntimeError("logged-exc")
    except RuntimeError:
        handler.log_exception(sys.exc_info())
    assert "logged-exc" in caplog.text
    request_handler = server.RequestHandler.__new__(server.RequestHandler)
    request_handler.log_error("bad %s", "thing")
    assert "An error occurred during request: bad thing" in caplog.text


def test_ssl_handshake_timeout_stays_a_timeout():
    seen = []

    class Dummy:
        def handle_error(self, request, client_address):
            seen.append(sys.exc_info()[1])

        def shutdown_request(self, request):
            seen.append("shutdown")

    class Req:
        def do_handshake(self):
            raise socket.timeout("hs-timeout")

    server.ParallelHTTPSServer.finish_request_locked(
        Dummy(), Req(), ("127.0.0.1", 1))
    assert seen[1] == "shutdown"
    assert isinstance(seen[0], socket.timeout)
    assert "SSL handshake failed" not in str(seen[0])


def test_hypercorn_bind_falls_back_when_lookup_fails_or_is_empty(monkeypatch, caplog):
    caplog.set_level(logging.WARNING)
    logger.setLevel(logging.WARNING)

    def boom(*_args, **_kwargs):
        raise OSError("lookup-down")

    monkeypatch.setattr(server.socket, "getaddrinfo", boom)
    failed = server.hypercorn_bind([("::1", 9), ("mail.example", 9)])
    assert failed == ["[::1]:9", "mail.example:9"]
    assert "cannot retrieve" in caplog.text
    caplog.clear()
    monkeypatch.setattr(server.socket, "getaddrinfo", lambda *_args, **_kwargs: [])
    empty = server.hypercorn_bind([("2001:db8::1", 9), ("127.0.0.1", 9)])
    assert empty == ["[2001:db8::1]:9", "127.0.0.1:9"]
    assert "cannot retrieve" not in caplog.text


def test_hypercorn_warns_on_protocol_and_runs_until_released(tmp_path, monkeypatch, caplog):
    import asyncio
    caplog.set_level(logging.INFO)
    logger.setLevel(logging.INFO)
    port = _free_port()
    left, right = socket.socketpair()
    thread, holder = _thread_result(lambda: server.serve(_bind_server(
        tmp_path / "ssl", port, type="hypercorn", ssl="True",
        certificate=get_file_path("cert.pem"), key=get_file_path("key.pem"),
        protocol="TLSv1.2"), right))
    try:
        deadline = time.monotonic() + 10
        while "is not supported by hypercorn" not in caplog.text:
            assert time.monotonic() < deadline
            if "exc" in holder:
                raise holder["exc"]
            time.sleep(0.05)
    finally:
        left.close()
        thread.join(15)
        right.close()
    assert "exc" not in holder
    assert "Stopping Radicale" in caplog.text

    released = threading.Event()
    real_event = asyncio.Event

    class _Gate:
        def wait(self):
            loop = asyncio.get_running_loop()
            return loop.run_in_executor(None, released.wait)

    def event_factory(*args, **kwargs):
        for frame in __import__("traceback").extract_stack():
            if (getattr(frame, "name", None) == "run_forever" and
                    str(getattr(frame, "filename", "")).endswith("radicale/server.py")):
                return _Gate()
        return real_event(*args, **kwargs)

    monkeypatch.setattr(server.asyncio, "Event", event_factory)
    port = _free_port()
    thread, holder = _thread_result(lambda: server.serve(
        _bind_server(tmp_path / "forever", port, type="hypercorn"), None))
    try:
        status, _body = _http_get(port)
        assert status == 302
    finally:
        released.set()
        thread.join(15)
    assert not thread.is_alive()
    assert "exc" not in holder


def test_cheroot_utf8_ipv6_ssl_and_errors(tmp_path, monkeypatch, caplog):
    import radicale.server_cheroot as server_cheroot
    caplog.set_level(logging.INFO)
    logger.setLevel(logging.DEBUG)
    seen = []

    def app(environ, start_response):
        seen.append((environ.get("PATH_INFO"), environ.get("QUERY_STRING")))
        start_response("204 No Content", [])
        return [b""]

    wrapped = server_cheroot._decode_utf8_environ(app)

    def start(status, headers, exc_info=None):
        seen.append(status)

    class Empty(str):
        def encode(self, encoding="utf-8", errors="strict"):
            raise AssertionError("encoded empty")

    wrapped({"PATH_INFO": Empty(""), "QUERY_STRING": Empty("")}, start)
    raw = "é".encode("utf-8").decode("latin-1")
    wrapped({"PATH_INFO": raw, "QUERY_STRING": raw}, start)
    wrapped({"PATH_INFO": "\xff", "QUERY_STRING": "ok"}, start)
    assert seen[0] == ("", "")
    assert seen[2] == ("é", "é")
    assert seen[4] == ("\xff", "ok")

    try:
        raise RuntimeError("cheroot-boom")
    except RuntimeError:
        server_cheroot._Server.error_log(None, "failed-tb", traceback=True)
        server_cheroot._Server.error_log(None, "failed-plain", traceback=False)
    traced = [record for record in caplog.records if record.getMessage() == "failed-tb"]
    plain = [record for record in caplog.records if record.getMessage() == "failed-plain"]
    assert traced and isinstance(traced[0].exc_info[1], RuntimeError)
    assert "cheroot-boom" in str(traced[0].exc_info[1])
    assert plain and not plain[0].exc_info

    sock = server_cheroot._Server.prepare_socket(
        ("::", 0), socket.AF_INET6, socket.SOCK_STREAM, socket.IPPROTO_TCP,
        False, None)
    try:
        assert sock.getsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY) == 1
    finally:
        sock.close()

    real_setsockopt = socket.socket.setsockopt

    def refuse_v6only(self, level, opt, value):
        if level == socket.IPPROTO_IPV6 and opt == socket.IPV6_V6ONLY and value == 1:
            raise OSError(errno.ENOPROTOOPT, "v6only")
        return real_setsockopt(self, level, opt, value)

    monkeypatch.setattr(socket.socket, "setsockopt", refuse_v6only)
    sock = server_cheroot._Server.prepare_socket(
        ("::", 0), socket.AF_INET6, socket.SOCK_STREAM, socket.IPPROTO_TCP,
        False, None)
    try:
        assert sock.family == socket.AF_INET6
    finally:
        sock.close()
    monkeypatch.undo()

    monkeypatch.delattr(socket, "IPV6_V6ONLY")
    sock = server_cheroot._Server.prepare_socket(
        ("::", 0), socket.AF_INET6, socket.SOCK_STREAM, socket.IPPROTO_TCP,
        False, None)
    try:
        assert sock.family == socket.AF_INET6
    finally:
        sock.close()
    monkeypatch.undo()

    missing = tmp_path / "missing-cert.pem"
    bad = _bind_server(
        tmp_path / "bad", _free_port(), ssl="True",
        certificate=str(missing), key=get_file_path("key.pem"))
    with pytest.raises(RuntimeError, match="missing-cert.pem"):
        server_cheroot.serve(bad, None)

    explicit = _bind_server(
        tmp_path / "ssl", _free_port(), ssl="True",
        certificate=get_file_path("cert.pem"), key=get_file_path("key.pem"),
        protocol="TLSv1.2", ciphersuite="ECDHE+AESGCM",
        certificate_authority=get_file_path("cert.pem"))
    adapter = server_cheroot._build_ssl_adapter(explicit)
    assert adapter.context.verify_mode == ssl.CERT_REQUIRED
    assert "SSL set explicit protocols" in caplog.text
    assert "SSL set explicit ciphersuite" in caplog.text
    assert "mandatory client certificate" in caplog.text

    inactive = _bind_server(
        tmp_path / "min", _free_port(), ssl="True",
        certificate=get_file_path("cert.pem"), key=get_file_path("key.pem"),
        protocol="-ALL")
    with pytest.raises(RuntimeError, match="No SSL minimum protocol active"):
        server_cheroot._build_ssl_adapter(inactive)
    monkeypatch.setattr(
        server_cheroot.utils, "ssl_context_minimum_version_by_options",
        lambda _options: ssl.TLSVersion.TLSv1_2)
    with pytest.raises(RuntimeError, match="No SSL maximum protocol active"):
        server_cheroot._build_ssl_adapter(inactive)

    caplog.clear()
    defaults = _bind_server(
        tmp_path / "default", _free_port(), ssl="True",
        certificate=get_file_path("cert.pem"), key=get_file_path("key.pem"))
    server_cheroot._build_ssl_adapter(defaults)
    assert "SSL active protocols: (system-default)" in caplog.text
    assert "SSL active ciphersuite: (system-default)" in caplog.text

    def lookup_down(*_args, **_kwargs):
        raise OSError("lookup-down")

    monkeypatch.setattr(server_cheroot.socket, "getaddrinfo", lookup_down)
    with pytest.raises(RuntimeError, match="No servers started"):
        server_cheroot.serve(_bind_server(tmp_path / "lookup", _free_port()), None)
    assert "cannot retrieve IPv4 or IPv6 address" in caplog.text
    monkeypatch.undo()

    def prepare_down(self):
        raise OSError(errno.EADDRINUSE, "busy")

    monkeypatch.setattr(server_cheroot._Server, "prepare", prepare_down)
    with pytest.raises(RuntimeError, match="No servers started"):
        server_cheroot.serve(_bind_server(tmp_path / "bind", _free_port()), None)
    assert "cannot create server socket" in caplog.text


def test_cheroot_serve_joins_when_shutdown_socket_is_absent(tmp_path, monkeypatch):
    import radicale.server_cheroot as server_cheroot
    port = _free_port()
    started = threading.Event()
    skipped = {"done": False}
    real_join = threading.Thread.join

    def join(self, timeout=None):
        frame = sys._getframe(1)
        if (frame.f_code.co_name == "serve" and
                frame.f_globals.get("__name__") == "radicale.server_cheroot" and
                not skipped["done"]):
            skipped["done"] = True
            assert started.wait(10)
            return None
        return real_join(self, timeout)

    monkeypatch.setattr(threading.Thread, "join", join)
    thread, holder = _thread_result(lambda: server_cheroot.serve(
        _bind_server(tmp_path, port, type="cheroot"), None))
    try:
        status, _body = _http_get(port)
        assert status == 302
    finally:
        started.set()
        thread.join(10)
    assert not thread.is_alive()
    assert "exc" not in holder


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


def test_set_level_trace_without_a_filter_emits_the_enabled_line():
    calls: List[str] = []
    original = logger.trace

    def trace(msg, *args, **kwargs):
        calls.append(msg % args if args else msg)

    logger.trace = trace
    try:
        log.logger_display_backtrace_enabled = False
        log.set_level("trace", True, "")
        assert logger.level == log.LOG_LEVEL_TRACE
        assert calls == ["Logging messages on 'trace' level enabled"]
        calls.clear()
        log.set_level("trace", True, "auth/")
        assert calls == [
            "Logging messages on 'trace' level enabled but filtered by prefix: 'auth/'"]
        assert any(isinstance(filt, log.PassTRACETOKENFilter)
                   for filt in logger.filters)
    finally:
        logger.trace = original


def test_log_conditional_excluded_falls_through_when_debug_is_off():
    original = logger.trace
    calls: List[str] = []

    def trace(msg, *args, **kwargs):
        calls.append(msg % args if args else msg)

    logger.setLevel(logging.ERROR)
    logger.trace = trace
    try:
        assert log.log_conditional(
            "quiet",
            {
                "host": {"match": "excluded", "value": "2001:db8::/32"},
                "method": {"match": "equal", "value": "GET"},
            },
            {"host": "2001:db9::1", "method": "GET"},
        ) is True
        assert log.log_conditional(
            "quiet",
            {
                "host": {"match": "excluded", "value": "2001:db8::/32"},
                "method": {"match": "equal", "value": "GET"},
            },
            {"host": "2001:db9::1", "method": "PUT"},
        ) is False
        assert log.log_conditional(
            "quiet",
            {"host": {"match": "excl", "value": "192.0.2.0/24"}},
            {"host": "192.0.2.10"},
        ) is False
        assert log.log_conditional(
            "quiet",
            {"host": {"match": "excl", "value": "192.0.2.0/24"}},
            {"host": "2001:db8::5"},
        ) is True
        assert log.log_conditional(
            "quiet",
            {"host": {"match": "excluded", "value": "192.0.2.0/24"}},
            {"host": "unknown"},
        ) is True
        assert calls == []
        assert log.log_conditional(
            "shift",
            {"host": {"match": _ShiftingMatch(), "value": "192.0.2.0/24"}},
            {"host": "not-an-ip"},
        ) is True
        assert calls == []
    finally:
        logger.trace = original

    logger.setLevel(logging.DEBUG)
    traced = _capture_traces_direct()
    try:
        assert log.log_conditional(
            "shift",
            {"host": {"match": _ShiftingMatch(), "value": "192.0.2.0/24"}},
            {"host": "not-an-ip"},
        ) is True
    finally:
        logger.trace = original
    assert any("/ip/PASSED" in msg for msg in traced)
    assert not any("/ip/SKIPPED" in msg for msg in traced)


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


def test_discover_existing_group_is_yielded_without_a_trace(tmp_path, monkeypatch):
    storage_ = _storage(tmp_path)
    storage_._group_collections_folder = "GROUPS"
    root = storage_._get_collection_root_folder()
    encoded = base64.b64encode(b"staff").decode("ascii")
    os.makedirs(os.path.join(root, "GROUPS", encoded))
    calls = _silence_traces(monkeypatch)
    grouped = [item for item in storage_.discover("/", "1", user_groups={"staff"})
               if isinstance(item, storage.BaseCollection)]
    assert any(item.path == "GROUPS/%s" % encoded for item in grouped)
    assert calls == []
    calls = _silence_traces(monkeypatch)
    ungrouped = [item for item in storage_.discover("/", "1", user_groups=set())
                 if isinstance(item, storage.BaseCollection)]
    assert not any(item.path == "GROUPS/%s" % encoded for item in ungrouped)
    assert calls == []


def test_get_fifo_reload_hit_and_missing_href(tmp_path, monkeypatch):
    storage_ = _storage(tmp_path)
    collection = _calendar(storage_, items=[_event()])[0]
    storage_._use_mtime_and_size_for_item_cache = True
    pipe = os.path.join(collection._filesystem_path, "pipe.ics")
    os.mkfifo(pipe)
    os.chmod(pipe, 0)
    try:
        with pytest.raises(PermissionError):
            collection._get("pipe.ics")
    finally:
        os.chmod(pipe, 0o644)
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


def test_builtin_serve_returns_without_closing_a_cleared_shutdown_socket(tmp_path, caplog):
    caplog.set_level(logging.INFO)
    logger.setLevel(logging.INFO)
    port = _free_port()
    left, right = socket.socketpair()
    previous = threading.gettrace()

    def trace(frame, event, arg):
        if (event == "line" and frame.f_lineno == 517 and
                frame.f_code.co_name == "serve" and
                frame.f_code.co_filename.endswith("radicale/server.py")):
            frame.f_locals["shutdown_socket"] = None
        if previous is None:
            return trace
        return previous(frame, event, arg)

    threading.settrace(trace)
    thread, holder = _thread_result(lambda: server.serve(
        _bind_server(tmp_path / "clear", port), right))
    try:
        status, _body = _http_get(port)
        assert status == 302
    finally:
        left.close()
        thread.join(10)
        threading.settrace(previous)
    assert not thread.is_alive()
    assert "exc" not in holder
    assert "Stopping Radicale" in caplog.text
    assert right.fileno() >= 0
    right.close()
