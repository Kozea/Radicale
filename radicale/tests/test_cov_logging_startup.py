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

"""Outcome tests for logging, configuration, and process startup."""

import datetime
import http.client
import importlib
import io
import json
import logging
import os
import signal
import socket
import ssl
import sys
import threading
import time
import xml.etree.ElementTree as ET
from collections import OrderedDict
from types import SimpleNamespace
from typing import List, Optional

import pytest

import radicale
from radicale import config
from radicale import item as radicale_item
from radicale import log, storage, utils, xmlutils
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


def test_user_groups_unknown_names_and_win32_string(monkeypatch):
    if sys.platform == "win32":
        # pwd and grp are not imported on Windows. The live path is getlogin.
        monkeypatch.setattr(utils.os, "getlogin", lambda: "covuser")
        assert utils.user_groups_as_string() == "user=covuser"
        return

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
    # A 32-bit process already has maxsize <= 2**32, so the old-Python arm
    # is unreachable until the pointer size is forced wide.
    monkeypatch.setattr(utils.sys, "maxsize", 2 ** 33)

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
    if hasattr(log.socket, "AF_UNIX"):
        assert "socket exploded" in caplog.text
        assert "Failed to connect to systemd journal" in caplog.text
    else:
        # No unix socket, so the handler returns before connect and logs nothing.
        assert "socket exploded" not in caplog.text
        assert "Failed to connect to systemd journal" not in caplog.text


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


def _exit_signals():
    """Signals ``radicale.__main__`` installs. Windows has no SIGHUP or SIGQUIT."""
    numbers = [signal.SIGTERM, signal.SIGINT]
    if sys.platform == "win32":
        numbers.append(signal.SIGBREAK)
    else:
        numbers.extend((signal.SIGHUP, signal.SIGQUIT))
    return numbers


def _run_cli(args):
    from radicale import __main__ as main
    saved = {number: signal.getsignal(number) for number in _exit_signals()}
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
