# This file is part of Radicale - CalDAV and CardDAV server
# Copyright © 2018-2022 Unrud <unrud@outlook.com>
# Copyright © 2024-2026 Peter Bieringer <pb@bieringer.de>
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
Test the internal server.

"""

import errno
import logging
import os
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import time
from configparser import RawConfigParser
from http.client import HTTPMessage
from typing import IO, Callable, Dict, List, Optional, Tuple, cast
from urllib import request
from urllib.error import HTTPError, URLError

import pytest

from radicale import config, server
from radicale.tests import BaseTest
from radicale.tests.helpers import configuration_to_dict, get_file_path


class DisabledRedirectHandler(request.HTTPRedirectHandler):
    def redirect_request(
            self, req: request.Request, fp: IO[bytes], code: int, msg: str,
            headers: HTTPMessage, newurl: str) -> None:
        return None


class TestBaseServerRequests(BaseTest):
    """Test the internal server."""

    shutdown_socket: socket.socket
    thread: threading.Thread
    opener: request.OpenerDirector

    def setup_method(self) -> None:
        super().setup_method()
        self.shutdown_socket, shutdown_socket_out = socket.socketpair()
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            # Find available port
            sock.bind(("127.0.0.1", 0))
            self.sockfamily = socket.AF_INET
            self.sockname = sock.getsockname()
        self.configure({"server": {"hosts": "%s:%d" % self.sockname},
                        # Enable debugging for new processes
                        "logging": {"level": "debug"}})
        self.thread = threading.Thread(target=server.serve, args=(
            self.configuration, shutdown_socket_out))
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        self.opener = request.build_opener(
            request.HTTPSHandler(context=ssl_context),
            DisabledRedirectHandler)

    def teardown_method(self) -> None:
        self.shutdown_socket.close()
        try:
            self.thread.join()
        except RuntimeError:  # Thread never started
            pass
        super().teardown_method()

    def request(self, method: str, path: str, data: Optional[str] = None,
                check: Optional[int] = None, **kwargs
                ) -> Tuple[int, Dict[str, str], str]:
        """Send a request."""
        login = kwargs.pop("login", None)
        if login is not None and not isinstance(login, str):
            raise TypeError("login argument must be %r, not %r" %
                            (str, type(login)))
        if login:
            raise NotImplementedError
        is_alive_fn: Optional[Callable[[], bool]] = kwargs.pop(
            "is_alive_fn", None)
        headers: Dict[str, str] = kwargs
        for k, v in headers.items():
            if not isinstance(v, str):
                raise TypeError("type of %r is %r, expected %r" %
                                (k, type(v), str))
        if is_alive_fn is None:
            is_alive_fn = self.thread.is_alive
        encoding: str = self.configuration.get("encoding", "request")
        scheme = "https" if self.configuration.get("server", "ssl") else "http"
        data_bytes = None
        if data:
            data_bytes = data.encode(encoding)
        if self.sockfamily == socket.AF_INET6:
            req_host = ("[%s]" % self.sockname[0])
        else:
            req_host = self.sockname[0]
        req = request.Request(
            "%s://%s:%d%s" % (scheme, req_host, self.sockname[1], path),
            data=data_bytes, headers=headers, method=method)
        while True:
            assert is_alive_fn()
            try:
                with self.opener.open(req) as f:
                    return f.getcode(), dict(f.info()), f.read().decode()
            except HTTPError as e:
                assert check is None or e.code == check, "%d != %d" % (e.code,
                                                                       check)
                return e.code, dict(e.headers), e.read().decode()
            except URLError as e:
                if not isinstance(e.reason, ConnectionRefusedError):
                    raise
            time.sleep(0.1)

    def test_root(self) -> None:
        self.thread.start()
        self.get("/", check=302)

    def test_ssl(self) -> None:
        self.configure({"server": {"ssl": "True",
                                   "certificate": get_file_path("cert.pem"),
                                   "key": get_file_path("key.pem")}})
        self.thread.start()
        self.get("/", check=302)

    def test_bind_fail(self) -> None:
        for address_family, address in [(socket.AF_INET, "::1"),
                                        (socket.AF_INET6, "127.0.0.1")]:
            try:
                with socket.socket(address_family, socket.SOCK_STREAM) as sock:
                    if address_family == socket.AF_INET6:
                        # Only allow IPv6 connections to the IPv6 socket
                        sock.setsockopt(server.COMPAT_IPPROTO_IPV6,
                                        socket.IPV6_V6ONLY, 1)
                    with pytest.raises(OSError) as exc_info:
                        sock.bind((address, 0))
            except OSError as e:
                if e.errno in (errno.EADDRNOTAVAIL, errno.EAFNOSUPPORT,
                               errno.EPROTONOSUPPORT):
                    continue
                raise
            # See ``radicale.server.serve``
            assert (isinstance(exc_info.value, socket.gaierror) and
                    exc_info.value.errno in (
                        socket.EAI_NONAME, server.COMPAT_EAI_ADDRFAMILY,
                        server.COMPAT_EAI_NODATA) or
                    str(exc_info.value) == "address family mismatched" or
                    exc_info.value.errno in (
                        errno.EADDRNOTAVAIL, errno.EAFNOSUPPORT,
                        errno.EPROTONOSUPPORT))

    def test_ipv6(self) -> None:
        try:
            with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as sock:
                # Only allow IPv6 connections to the IPv6 socket
                sock.setsockopt(
                    server.COMPAT_IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
                # Find available port
                sock.bind(("::1", 0))
                self.sockfamily = socket.AF_INET6
                self.sockname = sock.getsockname()[:2]
        except OSError as e:
            if e.errno in (errno.EADDRNOTAVAIL, errno.EAFNOSUPPORT,
                           errno.EPROTONOSUPPORT):
                pytest.skip("IPv6 not supported")
            raise
        self.configure({"server": {"hosts": "[%s]:%d" % self.sockname}})
        self.thread.start()
        self.get("/", check=302)

    def test_command_line_interface(self, with_bool_options=False) -> None:
        self.configure({"headers": {"Test-Server": "test"}})
        config_args = []
        for section in self.configuration.sections():
            if section.startswith("_"):
                continue
            for option in self.configuration.options(section):
                if option.startswith("_"):
                    continue
                long_name = "--%s-%s" % (section, option.replace("_", "-"))
                if with_bool_options and config.DEFAULT_CONFIG_SCHEMA.get(
                        section, {}).get(option, {}).get("type") == bool:
                    if not cast(bool, self.configuration.get(section, option)):
                        long_name = "--no%s" % long_name[1:]
                    config_args.append(long_name)
                else:
                    config_args.append(long_name)
                    raw_value = self.configuration.get_raw(section, option)
                    assert isinstance(raw_value, str)
                    config_args.append(raw_value)
        config_args.append("--headers-Test-Header=test")
        p = subprocess.Popen(
            [sys.executable, "-m", "radicale"] + config_args,
            env={**os.environ, "PYTHONPATH": os.pathsep.join(sys.path)})
        try:
            status, headers, _ = self.request(
                "GET", "/", check=302, is_alive_fn=lambda: p.poll() is None)
            for key in self.configuration.options("headers"):
                assert headers.get(key) == self.configuration.get(
                    "headers", key)
        finally:
            p.terminate()
            p.wait()
        if sys.platform != "win32":
            assert p.returncode == 0

    def test_command_line_interface_with_bool_options(self) -> None:
        self.test_command_line_interface(with_bool_options=True)

    def test_server_port_config(self) -> None:
        # check for invalid port
        logging.info("Try invalid port: 0")
        try:
            self.configure({"server": {"hosts": "localhost:0"}})
        except RuntimeError as e:
            logging.info("Exception: %s", str(e))
        else:
            raise

        # check for invalid port
        logging.info("Try invalid port: 65535")
        try:
            self.configure({"server": {"hosts": "localhost:65535"}})
        except RuntimeError as e:
            logging.info("Exception: %s", str(e))
        else:
            raise

        # check for valid port
        logging.info("Try valid port")
        self.configure({"server": {"hosts": "localhost:5232"}})

    def test_wsgi_server(self) -> None:
        config_path = os.path.join(self.colpath, "config")
        parser = RawConfigParser()
        parser.read_dict(configuration_to_dict(self.configuration))
        with open(config_path, "w") as f:
            parser.write(f)
        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join(sys.path)
        env["RADICALE_CONFIG"] = config_path
        raw_server_hosts = self.configuration.get_raw("server", "hosts")
        assert isinstance(raw_server_hosts, str)
        p = subprocess.Popen([
            sys.executable, "-m", "waitress", "--listen", raw_server_hosts,
            "radicale:application"], env=env)
        try:
            self.get("/", is_alive_fn=lambda: p.poll() is None, check=302)
        finally:
            p.terminate()
            p.wait()


class TestHypercornConfiguration:
    """`[server] type = hypercorn`, which is an optional dependency.

    The real thing is an integration test of its own (``TestHypercornServerRequests``, skipped when
    the dependency is not installed); here the mapping from Radicale's configuration to hypercorn's
    is pinned without it, and so is the error that names the extra when it is missing.

    """

    def _configuration(self, **server: str) -> config.Configuration:
        configuration = config.load()
        # Nothing is written to the storage folder. A pytest temporary directory cannot be used
        # instead: the VFAT and NTFS jobs fail its ownership check, because those filesystems
        # report one fixed uid.
        configuration.update({"server": dict(server, type="hypercorn"),
                              "storage": {"filesystem_folder": tempfile.mkdtemp()}},
                             "test", privileged=True)
        return configuration

    def test_missing_dependency(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # `None` in sys.modules makes the import fail, whatever is installed on this machine
        monkeypatch.setitem(sys.modules, "hypercorn", None)
        monkeypatch.setitem(sys.modules, "hypercorn.asyncio", None)
        monkeypatch.setitem(sys.modules, "hypercorn.config", None)
        with pytest.raises(RuntimeError) as exc_info:
            server.serve_hypercorn(self._configuration(), None)
        assert "radicale[h2]" in str(exc_info.value)
        assert "hypercorn>=0.17" in str(exc_info.value)

    def test_translates_the_configuration(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from types import ModuleType
        recorded: Dict[str, object] = {}

        class FakeConfig:
            bind: List[str] = []
            alpn_protocols: List[str] = []
            wsgi_max_body_size: int = 0
            certfile: Optional[str] = None
            keyfile: Optional[str] = None
            ca_certs: Optional[str] = None
            verify_mode: Optional[int] = None
            ciphers: str = "ECDHE+AESGCM"

        async def fake_serve(app: Callable, config_: object, *,
                             shutdown_trigger: object = None,
                             mode: Optional[str] = None) -> None:
            recorded.update(app=app, config=config_, mode=mode,
                            shutdown_trigger=shutdown_trigger)

        hypercorn_module = ModuleType("hypercorn")
        asyncio_module = ModuleType("hypercorn.asyncio")
        asyncio_module.serve = fake_serve  # type:ignore[attr-defined]
        config_module = ModuleType("hypercorn.config")
        config_module.Config = FakeConfig  # type:ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "hypercorn", hypercorn_module)
        monkeypatch.setitem(sys.modules, "hypercorn.asyncio", asyncio_module)
        monkeypatch.setitem(sys.modules, "hypercorn.config", config_module)

        server.serve_hypercorn(self._configuration(
            hosts="127.0.0.1:5233,[::1]:5234", ssl="True",
            max_content_length="2000000",
            certificate=get_file_path("cert.pem"), key=get_file_path("key.pem"),
            certificate_authority=get_file_path("cert.pem"),
            ciphersuite="ECDHE+AESGCM"), None)

        hypercorn_config = cast(FakeConfig, recorded["config"])
        # IPv6 addresses are bracketed, or hypercorn reads the last colon as the port separator
        assert hypercorn_config.bind == ["127.0.0.1:5233", "[::1]:5234"]
        # the reason to run hypercorn at all: HTTP/2 over cleartext (H2C) and HTTP/1.1 on one socket
        assert hypercorn_config.alpn_protocols == ["h2", "http/1.1"]
        # hypercorn's own WSGI body limit is 16 Mbyte, so the application's has to be handed over
        assert hypercorn_config.wsgi_max_body_size == 2000000
        assert hypercorn_config.certfile == get_file_path("cert.pem")
        assert hypercorn_config.keyfile == get_file_path("key.pem")
        assert hypercorn_config.ca_certs == get_file_path("cert.pem")
        assert hypercorn_config.verify_mode == ssl.CERT_REQUIRED
        assert hypercorn_config.ciphers == "ECDHE+AESGCM"
        # the WSGI application is handed over as one, and there is no shutdown socket to wait on
        assert recorded["app"] is not None
        assert recorded["mode"] == "wsgi"
        assert callable(recorded["shutdown_trigger"])

    def test_hostname_binds_every_address_it_has(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # A host name has more than one address, and the built-in server binds all of them; a
        # hypercorn that resolved `localhost` to IPv4 only would drop the IPv6 half of the service
        def getaddrinfo(*args: object, **kwargs: object) -> List[Tuple]:
            return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "",
                     ("127.0.0.1", 5232)),
                    (socket.AF_INET6, socket.SOCK_STREAM, socket.IPPROTO_TCP, "",
                     ("::1", 5232, 0, 0)),
                    (socket.AF_INET6, socket.SOCK_STREAM, socket.IPPROTO_TCP, "",
                     ("::1", 5232, 0, 0))]

        monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)
        assert server.hypercorn_bind([("localhost", 5232)]) == [
            "127.0.0.1:5232", "[::1]:5232"]

    def test_no_limit_is_no_limit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from types import ModuleType
        recorded: Dict[str, object] = {}

        class FakeConfig:
            bind: List[str] = []
            alpn_protocols: List[str] = []
            wsgi_max_body_size: int = 0
            certfile: Optional[str] = None
            keyfile: Optional[str] = None
            ca_certs: Optional[str] = None
            verify_mode: Optional[int] = None
            ciphers: str = "ECDHE+AESGCM"

        async def fake_serve(app: Callable, config_: object, *,
                             shutdown_trigger: object = None,
                             mode: Optional[str] = None) -> None:
            recorded["config"] = config_

        hypercorn_module = ModuleType("hypercorn")
        asyncio_module = ModuleType("hypercorn.asyncio")
        asyncio_module.serve = fake_serve  # type:ignore[attr-defined]
        config_module = ModuleType("hypercorn.config")
        config_module.Config = FakeConfig  # type:ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "hypercorn", hypercorn_module)
        monkeypatch.setitem(sys.modules, "hypercorn.asyncio", asyncio_module)
        monkeypatch.setitem(sys.modules, "hypercorn.config", config_module)

        # max_content_length=0 is "no limit" in Radicale, and the wrapper has no such value: a
        # number nothing reaches is how it is said
        server.serve_hypercorn(self._configuration(
            hosts="127.0.0.1:5233", max_content_length="0"), None)
        assert cast(FakeConfig, recorded["config"]).wsgi_max_body_size == sys.maxsize

    def test_shutdown_socket_is_the_trigger(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from types import ModuleType
        recorded: Dict[str, object] = {}

        class FakeConfig:
            bind: List[str] = []
            alpn_protocols: List[str] = []
            wsgi_max_body_size: int = 0
            certfile: Optional[str] = None
            keyfile: Optional[str] = None
            ca_certs: Optional[str] = None
            verify_mode: Optional[int] = None
            ciphers: str = "ECDHE+AESGCM"

        async def fake_serve(app: Callable, config_: object, *,
                             shutdown_trigger: object = None,
                             mode: Optional[str] = None) -> None:
            recorded["shutdown_trigger"] = shutdown_trigger

        hypercorn_module = ModuleType("hypercorn")
        asyncio_module = ModuleType("hypercorn.asyncio")
        asyncio_module.serve = fake_serve  # type:ignore[attr-defined]
        config_module = ModuleType("hypercorn.config")
        config_module.Config = FakeConfig  # type:ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "hypercorn", hypercorn_module)
        monkeypatch.setitem(sys.modules, "hypercorn.asyncio", asyncio_module)
        monkeypatch.setitem(sys.modules, "hypercorn.config", config_module)

        shutdown_socket, _ = socket.socketpair()
        try:
            server.serve_hypercorn(self._configuration(hosts="127.0.0.1:5233"),
                                   shutdown_socket)
        finally:
            shutdown_socket.close()
        assert callable(recorded["shutdown_trigger"])


class TestHypercornServerRequests(BaseTest):
    """The same server over the wire, with hypercorn installed.

    H2C is what this server type exists for, and it is what the built-in one cannot do: its WSGI
    server parses the request line with HTTP/1.1 only, so a cleartext HTTP/2 request is answered
    ``505 Invalid HTTP version (2.0)``.

    """

    shutdown_socket: socket.socket
    thread: threading.Thread
    sockname: Tuple[str, int]

    def setup_method(self) -> None:
        pytest.importorskip("hypercorn")
        super().setup_method()
        self.shutdown_socket, shutdown_socket_out = socket.socketpair()
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            # Find available port
            sock.bind(("127.0.0.1", 0))
            self.sockname = cast(Tuple[str, int], sock.getsockname())
        self.configure({"server": {"hosts": "%s:%d" % self.sockname,
                                   "type": "hypercorn"}})
        self.thread = threading.Thread(target=server.serve, args=(
            self.configuration, shutdown_socket_out))

    def teardown_method(self) -> None:
        self.shutdown_socket.close()
        self.thread.join(30)
        # the shutdown socket is the trigger: a server that ignored it would still be running
        assert not self.thread.is_alive()
        super().teardown_method()

    def h2c_get(self, path: str) -> int:
        """The status of a GET over cleartext HTTP/2 the way a proxy speaks it (prior knowledge)."""
        from h2.connection import H2Connection
        from h2.events import ResponseReceived, StreamEnded

        # The server is bound from its own thread, so the port is not listening yet when this runs
        deadline = time.monotonic() + 10
        while True:
            try:
                sock = socket.create_connection(self.sockname, timeout=10)
                break
            except ConnectionRefusedError:
                assert time.monotonic() < deadline, "the server did not start"
                time.sleep(0.1)
        connection = H2Connection()
        connection.initiate_connection()
        with sock:
            sock.sendall(connection.data_to_send())
            stream_id = connection.get_next_available_stream_id()
            connection.send_headers(stream_id, [
                (":method", "GET"), (":path", path), (":scheme", "http"),
                (":authority", "%s:%d" % self.sockname)], end_stream=True)
            sock.sendall(connection.data_to_send())
            status: Optional[int] = None
            while True:
                data = sock.recv(65536)
                assert data, "the server closed the connection without a response"
                for event in connection.receive_data(data):
                    if isinstance(event, ResponseReceived):
                        status = int(dict(event.headers)[b":status"])
                    elif isinstance(event, StreamEnded):
                        # Read the response to its end and end the HTTP/2 connection the way a
                        # client does. A socket closed with the stream still open leaves hypercorn
                        # flushing a write into a connection that never drains, and Python 3.13+
                        # then waits for that connection in `Server.wait_closed`, so the server
                        # itself never returns from its shutdown.
                        assert status is not None
                        connection.close_connection()
                        sock.sendall(connection.data_to_send())
                        return status
                sock.sendall(connection.data_to_send())

    def test_root_over_h2c(self) -> None:
        self.thread.start()
        assert self.h2c_get("/") == 302

    def test_http11_on_the_same_socket(self) -> None:
        """H2C is added to HTTP/1.1, not instead of it: a proxy may speak either."""
        self.thread.start()
        deadline = time.monotonic() + 10
        while True:
            try:
                sock = socket.create_connection(self.sockname, timeout=10)
                break
            except ConnectionRefusedError:
                assert time.monotonic() < deadline, "the server did not start"
                time.sleep(0.1)
        with sock:
            sock.sendall(b"GET / HTTP/1.1\r\nHost: %s:%d\r\nConnection: close\r\n\r\n"
                         % (self.sockname[0].encode(), self.sockname[1]))
            status = sock.recv(1024).split(b"\r\n", 1)[0]
        # the reason phrase is optional and hypercorn leaves it out, so the code is what is compared
        assert status.split(b" ")[1] == b"302", status
