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

"""Outcome tests for the builtin, cheroot, and hypercorn servers."""

import errno
import http.client
import importlib
import io
import logging
import os
import signal
import socket
import ssl
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
from radicale import log, server, storage, xmlutils
from radicale.log import logger
from radicale.storage import multifilesystem
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


# --- server and server_cheroot ----------------------------------------------


def _bind_server(folder, port, **options):
    server_options = {"hosts": "127.0.0.1:%d" % port}
    server_options.update(options)
    return _configuration(folder, {"server": server_options})


def _is_server_source(filename):
    """True for ``radicale/server.py`` when the path uses either separator."""
    return str(filename).replace("\\", "/").endswith("radicale/server.py")


def _thread_result(target):
    holder = {}

    def run():
        try:
            target()
        except BaseException as exc:  # noqa: BLE001 - the server thread must report
            holder["exc"] = exc

    thread = threading.Thread(target=run)
    # A server that never observes its stop signal must not pin the process.
    thread.daemon = True
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
                    _is_server_source(getattr(frame, "filename", ""))):
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


def _capture_traces_direct():
    calls: List[str] = []

    def trace(msg, *args, **kwargs):
        try:
            calls.append(msg % args if args else msg)
        except Exception:
            calls.append(str(msg))

    logger.trace = trace
    return calls


def test_builtin_serve_returns_without_closing_a_cleared_shutdown_socket(tmp_path, caplog):
    caplog.set_level(logging.INFO)
    logger.setLevel(logging.INFO)
    port = _free_port()
    left, right = socket.socketpair()
    # threading.gettrace arrived in Python 3.10. 3.9 still has settrace.
    gettrace = getattr(threading, "gettrace", None)
    previous = gettrace() if gettrace is not None else None

    def trace(frame, event, arg):
        if (event == "line" and frame.f_lineno == 517 and
                frame.f_code.co_name == "serve" and
                _is_server_source(frame.f_code.co_filename)):
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
