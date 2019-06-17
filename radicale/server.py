# This file is part of Radicale Server - Calendar Server
# Copyright © 2008 Nicolas Kandel
# Copyright © 2008 Pascal Halter
# Copyright © 2008-2017 Guillaume Ayoub
# Copyright © 2017-2019 Unrud <unrud@outlook.com>
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
import threading
import wsgiref.simple_server
from urllib.parse import unquote

from radicale import Application
from radicale.log import logger

try:
    import systemd.daemon
except ImportError:
    systemd = None

USE_FORKING = hasattr(os, "fork")
try:
    multiprocessing.BoundedSemaphore()
except Exception:
    # HACK: Workaround for Android
    USE_FORKING = False

if USE_FORKING:
    ParallelizationMixIn = socketserver.ForkingMixIn
else:
    ParallelizationMixIn = socketserver.ThreadingMixIn

HAS_IPV6 = socket.has_ipv6
if hasattr(socket, "EAI_NONAME"):
    EAI_NONAME = socket.EAI_NONAME
else:
    HAS_IPV6 = False
if hasattr(socket, "EAI_ADDRFAMILY"):
    EAI_ADDRFAMILY = socket.EAI_ADDRFAMILY
elif os.name == "nt":
    EAI_ADDRFAMILY = None
else:
    HAS_IPV6 = False
if hasattr(socket, "IPPROTO_IPV6"):
    IPPROTO_IPV6 = socket.IPPROTO_IPV6
elif os.name == "nt":
    IPPROTO_IPV6 = 41
else:
    HAS_IPV6 = False
if hasattr(socket, "IPV6_V6ONLY"):
    IPV6_V6ONLY = socket.IPV6_V6ONLY
elif os.name == "nt":
    IPV6_V6ONLY = 27
else:
    HAS_IPV6 = False


class ParallelHTTPServer(ParallelizationMixIn,
                         wsgiref.simple_server.WSGIServer):

    # wait for child processes/threads
    _block_on_close = True

    # These class attributes must be set before creating instance
    client_timeout = None
    max_connections = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if USE_FORKING:
            sema_class = multiprocessing.BoundedSemaphore
        else:
            sema_class = threading.BoundedSemaphore
        if self.max_connections:
            self.connections_guard = sema_class(self.max_connections)
        else:
            # use dummy context manager
            self.connections_guard = contextlib.ExitStack()

    def server_bind(self):
        if isinstance(self.server_address, socket.socket):
            # Socket activation
            self.socket = self.server_address
            self.server_address = self.socket.getsockname()
            host, port = self.server_address[:2]
            self.server_name = socket.getfqdn(host)
            self.server_port = port
            self.setup_environ()
            return
        try:
            super().server_bind()
        except socket.gaierror as e:
            if (not HAS_IPV6 or self.address_family != socket.AF_INET or
                    e.errno not in (EAI_NONAME, EAI_ADDRFAMILY)):
                raise
            # Try again with IPv6
            self.address_family = socket.AF_INET6
            self.socket = socket.socket(self.address_family, self.socket_type)
            # Only allow IPv6 connections to the IPv6 socket
            self.socket.setsockopt(IPPROTO_IPV6, IPV6_V6ONLY, 1)
            super().server_bind()

    def get_request(self):
        # Set timeout for client
        socket_, address = super().get_request()
        if self.client_timeout:
            socket_.settimeout(self.client_timeout)
        return socket_, address

    def process_request(self, request, client_address):
        try:
            return super().process_request(request, client_address)
        finally:
            # Modify OpenSSL's RNG state, in case process forked
            # See https://docs.python.org/3.7/library/ssl.html#multi-processing
            ssl.RAND_add(os.urandom(8), 0.0)

    def finish_request_locked(self, request, client_address):
        return super().finish_request(request, client_address)

    def finish_request(self, request, client_address):
        """Don't overwrite this! (Modified by tests.)"""
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

    def server_bind(self):
        super().server_bind()
        """Create server by wrapping HTTP socket in an SSL socket."""
        self.socket = ssl.wrap_socket(
            self.socket, self.key, self.certificate, server_side=True,
            cert_reqs=ssl.CERT_REQUIRED if self.certificate_authority else
            ssl.CERT_NONE,
            ca_certs=self.certificate_authority or None,
            ssl_version=self.protocol, ciphers=self.ciphers,
            do_handshake_on_connect=False)

    def finish_request_locked(self, request, client_address):
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
    configuration = configuration.copy()
    configuration.update({"internal": {"internal_server": "True"}}, "server")

    # Create collection servers
    servers = {}
    if configuration.get("server", "ssl"):
        server_class = ParallelHTTPSServer
    else:
        server_class = ParallelHTTPServer

    class ServerCopy(server_class):
        """Copy, avoids overriding the original class attributes."""
    ServerCopy.client_timeout = configuration.get("server", "timeout")
    ServerCopy.max_connections = configuration.get("server", "max_connections")
    if configuration.get("server", "ssl"):
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
    if not configuration.get("server", "dns_lookup"):
        RequestHandlerCopy.address_string = lambda self: self.client_address[0]

    if systemd:
        listen_fds = systemd.daemon.listen_fds()
    else:
        listen_fds = []

    server_addresses = []
    if listen_fds:
        logger.info("Using socket activation")
        ServerCopy.address_family = socket.AF_UNIX
        for fd in listen_fds:
            server_addresses.append(socket.fromfd(
                fd, ServerCopy.address_family, ServerCopy.socket_type))
    else:
        for address, port in configuration.get("server", "hosts"):
            server_addresses.append((address, port))

    application = Application(configuration)
    for server_address in server_addresses:
        try:
            server = ServerCopy(server_address, RequestHandlerCopy)
            server.set_app(application)
        except OSError as e:
            raise RuntimeError(
                "Failed to start server %r: %s" % (server_address, e)) from e
        servers[server.socket] = server
        logger.info("Listening to %r on port %d%s",
                    server.server_name, server.server_port, " using SSL"
                    if configuration.get("server", "ssl") else "")

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

    with contextlib.ExitStack() as stack:
        for _, server in servers.items():
            stack.callback(server.server_close)
        while True:
            rlist, _, xlist = select.select(
                sockets, [], sockets, select_timeout)
            if xlist:
                raise RuntimeError("unhandled socket error")
            if shutdown_socket in rlist:
                logger.info("Stopping Radicale")
                break
            if rlist:
                server = servers.get(rlist[0])
                if server:
                    server.handle_request()
                    server.service_actions()
