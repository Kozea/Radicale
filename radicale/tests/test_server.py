# This file is part of Radicale Server - Calendar Server
# Copyright © 2018-2019 Unrud <unrud@outlook.com>
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
import os
import socket
import ssl
import subprocess
import sys
import threading
import time
from configparser import RawConfigParser
from typing import Callable, Dict, NoReturn, Optional, Tuple, cast
from urllib import request
from urllib.error import HTTPError, URLError

import pytest

from radicale import config, server
from radicale.tests import BaseTest
from radicale.tests.helpers import configuration_to_dict, get_file_path


class DisabledRedirectHandler(request.HTTPRedirectHandler):

    # HACK: typeshed annotation are wrong for `fp` and `msg`
    #       (https://github.com/python/typeshed/pull/5728)
    #       `headers` is incompatible with `http.client.HTTPMessage`
    #       (https://github.com/python/typeshed/issues/5729)
    def http_error_301(self, req: request.Request, fp, code: int,
                       msg, headers) -> NoReturn:
        raise HTTPError(req.full_url, code, msg, headers, fp)

    def http_error_302(self, req: request.Request, fp, code: int,
                       msg, headers) -> NoReturn:
        raise HTTPError(req.full_url, code, msg, headers, fp)

    def http_error_303(self, req: request.Request, fp, code: int,
                       msg, headers) -> NoReturn:
        raise HTTPError(req.full_url, code, msg, headers, fp)

    def http_error_307(self, req: request.Request, fp, code: int,
                       msg, headers) -> NoReturn:
        raise HTTPError(req.full_url, code, msg, headers, fp)


class TestBaseServerRequests(BaseTest):
    """Test the internal server."""

    shutdown_socket: socket.socket
    thread: threading.Thread
    opener: request.OpenerDirector

    def setup(self) -> None:
        super().setup()
        self.shutdown_socket, shutdown_socket_out = socket.socketpair()
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            # Find available port
            sock.bind(("127.0.0.1", 0))
            self.sockname = sock.getsockname()
        self.configuration.update({
            "server": {"hosts": "[%s]:%d" % self.sockname},
            # Enable debugging for new processes
            "logging": {"level": "debug"}},
            "test", privileged=True)
        self.thread = threading.Thread(target=server.serve, args=(
            self.configuration, shutdown_socket_out))
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        self.opener = request.build_opener(
            request.HTTPSHandler(context=ssl_context),
            DisabledRedirectHandler)

    def teardown(self) -> None:
        self.shutdown_socket.close()
        try:
            self.thread.join()
        except RuntimeError:  # Thread never started
            pass
        super().teardown()

    def request(self, method: str, path: str, data: Optional[str] = None,
                **kwargs) -> Tuple[int, Dict[str, str], str]:
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
        req = request.Request(
            "%s://[%s]:%d%s" % (scheme, *self.sockname, path),
            data=data_bytes, headers=headers, method=method)
        while True:
            assert is_alive_fn()
            try:
                with self.opener.open(req) as f:
                    return f.getcode(), dict(f.info()), f.read().decode()
            except HTTPError as e:
                return e.code, dict(e.headers), e.read().decode()
            except URLError as e:
                if not isinstance(e.reason, ConnectionRefusedError):
                    raise
            time.sleep(0.1)

    def test_root(self) -> None:
        self.thread.start()
        self.get("/", check=302)

    def test_ssl(self) -> None:
        self.configuration.update({
            "server": {"ssl": "True",
                       "certificate": get_file_path("cert.pem"),
                       "key": get_file_path("key.pem")}}, "test")
        self.thread.start()
        self.get("/", check=302)

    def test_bind_fail(self) -> None:
        for address_family, address in [(socket.AF_INET, "::1"),
                                        (socket.AF_INET6, "127.0.0.1")]:
            with socket.socket(address_family, socket.SOCK_STREAM) as sock:
                if address_family == socket.AF_INET6:
                    # Only allow IPv6 connections to the IPv6 socket
                    sock.setsockopt(server.COMPAT_IPPROTO_IPV6,
                                    socket.IPV6_V6ONLY, 1)
                with pytest.raises(OSError) as exc_info:
                    sock.bind((address, 0))
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
                self.sockname = sock.getsockname()[:2]
        except OSError as e:
            if e.errno in (errno.EADDRNOTAVAIL, errno.EAFNOSUPPORT,
                           errno.EPROTONOSUPPORT):
                pytest.skip("IPv6 not supported")
            raise
        self.configuration.update({
            "server": {"hosts": "[%s]:%d" % self.sockname}}, "test")
        self.thread.start()
        self.get("/", check=302)

    def test_command_line_interface(self) -> None:
        config_args = []
        for section, values in config.DEFAULT_CONFIG_SCHEMA.items():
            if section.startswith("_"):
                continue
            for option, data in values.items():
                if option.startswith("_"):
                    continue
                long_name = "--%s-%s" % (section, option.replace("_", "-"))
                if data["type"] == bool:
                    if not cast(bool, self.configuration.get(section, option)):
                        long_name = "--no%s" % long_name[1:]
                    config_args.append(long_name)
                else:
                    config_args.append(long_name)
                    raw_value = self.configuration.get_raw(section, option)
                    assert isinstance(raw_value, str)
                    config_args.append(raw_value)
        p = subprocess.Popen(
            [sys.executable, "-m", "radicale"] + config_args,
            env={**os.environ, "PYTHONPATH": os.pathsep.join(sys.path)})
        try:
            self.get("/", is_alive_fn=lambda: p.poll() is None, check=302)
        finally:
            p.terminate()
            p.wait()
        if os.name == "posix":
            assert p.returncode == 0

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
