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

"""Outcome tests for rights, XML, and filesystem paths."""

import ctypes
import errno
import http.client
import importlib
import io
import json
import logging
import os
import pathlib
import signal
import socket
import sys
import threading
import time
import xml.etree.ElementTree as ET
from types import SimpleNamespace
from typing import List, Optional

import pytest

import radicale
from radicale import config, group, httputils
from radicale import item as radicale_item
from radicale import log, pathutils, rights, storage, types, web, xmlutils
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
        if os.access(unreadable, os.R_OK):
            # Root reads mode 000. The file still grants R.
            backend = rights.load(configuration)
            assert backend.authorization("user", set(), "/user/") == "R"
        else:
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

    def fail_lock(*_args):
        raise OSError(errno.EIO, "lock failed")

    if sys.platform == "win32":
        monkeypatch.setattr(pathutils, "lock_file_ex", fail_lock)
    else:
        monkeypatch.setattr(pathutils.fcntl, "flock", fail_lock)
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

    if sys.platform == "linux" and getattr(pathutils, "renameat2", None):
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
    else:
        # Windows and macOS exchange by copying through a temporary directory.
        pathutils.rename_exchange(str(src), str(dst))
        assert src.read_text(encoding="utf-8") == "dest"
        assert dst.read_text(encoding="utf-8") == "source"


def test_renameat2_attributeerror_uses_the_copy_fallback(tmp_path):
    src = tmp_path / "a"
    dst = tmp_path / "b"
    src.write_text("A", encoding="utf-8")
    dst.write_text("B", encoding="utf-8")
    if sys.platform != "linux":
        assert not hasattr(pathutils, "renameat2")
        pathutils.rename_exchange(str(src), str(dst))
        assert src.read_text(encoding="utf-8") == "B"
        assert dst.read_text(encoding="utf-8") == "A"
        return

    real_cdll = ctypes.CDLL

    class _MissingRename:
        def __getattr__(self, name):
            raise AttributeError(name)

    try:
        ctypes.CDLL = lambda *_args, **_kwargs: _MissingRename()  # type: ignore[assignment]
        importlib.reload(pathutils)
        assert pathutils.renameat2 is None
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

    if not hasattr(pathutils, "fcntl"):
        monkeypatch.setattr(pathutils, "fcntl", SimpleNamespace(fcntl=full), raising=False)
    else:
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
