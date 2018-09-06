# This file is part of Radicale Server - Calendar Server
# Copyright © 2018 Unrud<unrud@outlook.com>
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

import os
import shutil
import socket
import ssl
import tempfile
import threading
import time
import warnings
from urllib import request
from urllib.error import HTTPError, URLError

from radicale import config, server

from .helpers import get_file_path

import pytest  # isort:skip


class DisabledRedirectHandler(request.HTTPRedirectHandler):
    def http_error_302(self, req, fp, code, msg, headers):
        raise HTTPError(req.full_url, code, msg, headers, fp)

    http_error_301 = http_error_303 = http_error_307 = http_error_302


class TestBaseServerRequests:
    """Test the internal server."""

    def setup(self):
        self.configuration = config.load()
        self.colpath = tempfile.mkdtemp()
        self.configuration["storage"]["filesystem_folder"] = self.colpath
        # Disable syncing to disk for better performance
        self.configuration["internal"]["filesystem_fsync"] = "False"
        self.shutdown_socket, shutdown_socket_out = socket.socketpair()
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            # Find available port
            sock.bind(("127.0.0.1", 0))
            self.sockname = sock.getsockname()
            self.configuration["server"]["hosts"] = "[%s]:%d" % self.sockname
        self.thread = threading.Thread(target=server.serve, args=(
            self.configuration, shutdown_socket_out))
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        self.opener = request.build_opener(
            request.HTTPSHandler(context=ssl_context),
            DisabledRedirectHandler)

    def teardown(self):
        self.shutdown_socket.sendall(b" ")
        try:
            self.thread.join()
        except RuntimeError:  # Thread never started
            pass
        shutil.rmtree(self.colpath)

    def request(self, method, path, data=None, **headers):
        """Send a request."""
        scheme = ("https" if self.configuration.getboolean("server", "ssl")
                  else "http")
        req = request.Request(
            "%s://[%s]:%d%s" % (scheme, *self.sockname, path),
            data=data, headers=headers, method=method)
        while True:
            assert self.thread.is_alive()
            try:
                with self.opener.open(req) as f:
                    return f.getcode(), f.info(), f.read().decode()
            except HTTPError as e:
                return e.code, e.headers, e.read().decode()
            except URLError as e:
                if not isinstance(e.reason, ConnectionRefusedError):
                    raise
            time.sleep(0.1)

    def test_root(self):
        self.thread.start()
        status, _, _ = self.request("GET", "/")
        assert status == 302

    def test_ssl(self):
        self.configuration["server"]["ssl"] = "True"
        self.configuration["server"]["certificate"] = get_file_path("cert.pem")
        self.configuration["server"]["key"] = get_file_path("key.pem")
        self.thread.start()
        status, _, _ = self.request("GET", "/")
        assert status == 302

    def test_ipv6(self):
        if not server.HAS_IPV6:
            pytest.skip("IPv6 not support")
        if os.name == "nt" and os.environ.get("WINE_PYTHON"):
            warnings.warn("WORKAROUND: incomplete errno conversion in WINE")
            server.EAI_ADDRFAMILY = -9
        with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as sock:
            sock.setsockopt(server.IPPROTO_IPV6, server.IPV6_V6ONLY, 1)
            # Find available port
            sock.bind(("::1", 0))
            self.sockname = sock.getsockname()[:2]
            self.configuration["server"]["hosts"] = "[%s]:%d" % self.sockname
        self.thread.start()
        status, _, _ = self.request("GET", "/")
        assert status == 302
