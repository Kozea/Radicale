# This file is part of Radicale Server - Calendar Server
# Copyright © 2008 Nicolas Kandel
# Copyright © 2008 Pascal Halter
# Copyright © 2008-2017 Guillaume Ayoub
# Copyright © 2017-2018 Unrud<unrud@outlook.com>
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
Radicale WSGI server.

"""

import contextlib
import multiprocessing
import os
import select
import socket
import socketserver
import ssl
import sys
import wsgiref.simple_server
from configparser import ConfigParser
from urllib.parse import unquote

from radicale import Application
from radicale.log import logger

if os.name == "posix":
    ParallelizationMixIn = socketserver.ForkingMixIn
else:
    ParallelizationMixIn = socketserver.ThreadingMixIn


class ParallelHTTPServer(ParallelizationMixIn,
                         wsgiref.simple_server.WSGIServer):

    # These class attributes must be set before creating instance
    client_timeout = None
    max_connections = None

    def __init__(self, address, handler, bind_and_activate=True):
        """Create server."""
        ipv6 = ":" in address[0]

        if ipv6:
            self.address_family = socket.AF_INET6

        # Do not bind and activate, as we might change socket options
        super().__init__(address, handler, False)

        if ipv6:
            # Only allow IPv6 connections to the IPv6 socket
            self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)

        if self.max_connections:
            self.connections_guard = multiprocessing.BoundedSemaphore(
                self.max_connections)
        else:
            # use dummy context manager
            self.connections_guard = contextlib.ExitStack()

        if bind_and_activate:
            try:
                self.server_bind()
                self.server_activate()
            except BaseException:
                self.server_close()
                raise

    def get_request(self):
        # Set timeout for client
        socket_, address = super().get_request()
        if self.client_timeout:
            socket_.settimeout(self.client_timeout)
        return socket_, address

    def finish_request_locked(self, request, client_address):
        return super().finish_request(request, client_address)

    def finish_request(self, request, client_address):
        with self.connections_guard:
            return self.finish_request_locked(request, client_address)

    def handle_error(self, request, client_address):
        if issubclass(sys.exc_info()[0], socket.timeout):
            logger.info("client timed out", exc_info=True)
        else:
            logger.error("An exception occurred during request: %s",
                         sys.exc_info()[1], exc_info=True)


class ParallelHTTPSServer(ParallelHTTPServer):

    # These class attributes must be set before creating instance
    certificate = None
    key = None
    protocol = None
    ciphers = None
    certificate_authority = None

    def __init__(self, address, handler, bind_and_activate=True):
        """Create server by wrapping HTTP socket in an SSL socket."""

        # Do not bind and activate, as we change the socket
        super().__init__(address, handler, False)

        self.socket = ssl.wrap_socket(
            self.socket, self.key, self.certificate, server_side=True,
            cert_reqs=ssl.CERT_REQUIRED if self.certificate_authority else
            ssl.CERT_NONE,
            ca_certs=self.certificate_authority or None,
            ssl_version=self.protocol, ciphers=self.ciphers,
            do_handshake_on_connect=False)

        if bind_and_activate:
            try:
                self.server_bind()
                self.server_activate()
            except BaseException:
                self.server_close()
                raise

    def finish_request(self, request, client_address):
        with self.connections_guard:
            try:
                try:
                    request.do_handshake()
                except socket.timeout:
                    raise
                except Exception as e:
                    raise RuntimeError("SSL handshake failed: %s" % e) from e
            except Exception:
                try:
                    self.handle_error(request, client_address)
                finally:
                    self.shutdown_request(request)
                return
            return super().finish_request_locked(request, client_address)


class ServerHandler(wsgiref.simple_server.ServerHandler):

    # Don't pollute WSGI environ with OS environment
    os_environ = {}

    def log_exception(self, exc_info):
        logger.error("An exception occurred during request: %s",
                     exc_info[1], exc_info=exc_info)


class RequestHandler(wsgiref.simple_server.WSGIRequestHandler):
    """HTTP requests handler."""

    def log_request(self, code="-", size="-"):
        """Disable request logging."""

    def log_error(self, format, *args):
        msg = format % args
        logger.error("An error occurred during request: %s" % msg)

    def get_environ(self):
        env = super().get_environ()
        if hasattr(self.connection, "getpeercert"):
            # The certificate can be evaluated by the auth module
            env["REMOTE_CERTIFICATE"] = self.connection.getpeercert()
        # Parent class only tries latin1 encoding
        env["PATH_INFO"] = unquote(self.path.split("?", 1)[0])
        return env

    def handle(self):
        """Copy of WSGIRequestHandler.handle with different ServerHandler"""

        self.raw_requestline = self.rfile.readline(65537)
        if len(self.raw_requestline) > 65536:
            self.requestline = ""
            self.request_version = ""
            self.command = ""
            self.send_error(414)
            return

        if not self.parse_request():
            return

        handler = ServerHandler(
            self.rfile, self.wfile, self.get_stderr(), self.get_environ()
        )
        handler.request_handler = self
        handler.run(self.server.get_app())


def serve(configuration, shutdown_socket=None):
    """Serve radicale from configuration."""
    logger.info("Starting Radicale")
    # Copy configuration before modifying
    config_copy = ConfigParser()
    config_copy.read_dict(configuration)
    configuration = config_copy
    configuration["internal"]["internal_server"] = "True"

    # Create collection servers
    servers = {}
    if configuration.getboolean("server", "ssl"):
        server_class = ParallelHTTPSServer
    else:
        server_class = ParallelHTTPServer

    class ServerCopy(server_class):
        """Copy, avoids overriding the original class attributes."""
    ServerCopy.client_timeout = configuration.getint("server", "timeout")
    ServerCopy.max_connections = configuration.getint(
        "server", "max_connections")
    if configuration.getboolean("server", "ssl"):
        ServerCopy.certificate = configuration.get("server", "certificate")
        ServerCopy.key = configuration.get("server", "key")
        ServerCopy.certificate_authority = configuration.get(
            "server", "certificate_authority")
        ServerCopy.ciphers = configuration.get("server", "ciphers")
        ServerCopy.protocol = getattr(
            ssl, configuration.get("server", "protocol"), ssl.PROTOCOL_SSLv23)
        # Test if the SSL files can be read
        for name in ["certificate", "key"] + (
                ["certificate_authority"]
                if ServerCopy.certificate_authority else []):
            filename = getattr(ServerCopy, name)
            try:
                open(filename, "r").close()
            except OSError as e:
                raise RuntimeError("Failed to read SSL %s %r: %s" %
                                   (name, filename, e)) from e

    class RequestHandlerCopy(RequestHandler):
        """Copy, avoids overriding the original class attributes."""
    if not configuration.getboolean("server", "dns_lookup"):
        RequestHandlerCopy.address_string = lambda self: self.client_address[0]

    for host in configuration.get("server", "hosts").split(","):
        try:
            address, port = host.strip().rsplit(":", 1)
            address, port = address.strip("[] "), int(port)
        except ValueError as e:
            raise RuntimeError(
                "Failed to parse address %r: %s" % (host, e)) from e
        application = Application(configuration)
        try:
            server = wsgiref.simple_server.make_server(
                address, port, application, ServerCopy, RequestHandlerCopy)
        except OSError as e:
            raise RuntimeError(
                "Failed to start server %r: %s" % (host, e)) from e
        servers[server.socket] = server
        logger.info("Listening to %r on port %d%s",
                    server.server_name, server.server_port, " using SSL"
                    if configuration.getboolean("server", "ssl") else "")

    # Main loop: wait for requests on any of the servers or program shutdown
    sockets = list(servers.keys())
    # Use socket pair to get notified of program shutdown
    if shutdown_socket:
        sockets.append(shutdown_socket)
    select_timeout = None
    if os.name == "nt":
        # Fallback to busy waiting. (select.select blocks SIGINT on Windows.)
        select_timeout = 1.0
    logger.info("Radicale server ready")
    while True:
        rlist, _, xlist = select.select(sockets, [], sockets, select_timeout)
        if xlist:
            raise RuntimeError("unhandled socket error")
        if shutdown_socket in rlist:
            logger.info("Stopping Radicale")
            break
        if rlist:
            server = servers.get(rlist[0])
            if server:
                server.handle_request()
