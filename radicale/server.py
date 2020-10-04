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
Built-in WSGI server.

"""

import errno
import os
import select
import socket
import socketserver
import ssl
import sys
import wsgiref.simple_server
from typing import MutableMapping
from urllib.parse import unquote

from radicale import Application, config
from radicale.log import logger

COMPAT_EAI_ADDRFAMILY: int
if hasattr(socket, "EAI_ADDRFAMILY"):
    COMPAT_EAI_ADDRFAMILY = socket.EAI_ADDRFAMILY  # type: ignore[attr-defined]
elif hasattr(socket, "EAI_NONAME"):
    # Windows and BSD don't have a special error code for this
    COMPAT_EAI_ADDRFAMILY = socket.EAI_NONAME
COMPAT_EAI_NODATA: int
if hasattr(socket, "EAI_NODATA"):
    COMPAT_EAI_NODATA = socket.EAI_NODATA
elif hasattr(socket, "EAI_NONAME"):
    # Windows and BSD don't have a special error code for this
    COMPAT_EAI_NODATA = socket.EAI_NONAME
COMPAT_IPPROTO_IPV6: int
if hasattr(socket, "IPPROTO_IPV6"):
    COMPAT_IPPROTO_IPV6 = socket.IPPROTO_IPV6
elif os.name == "nt":
    # Workaround: https://bugs.python.org/issue29515
    COMPAT_IPPROTO_IPV6 = 41


def format_address(address):
    return "[%s]:%d" % address[:2]


class ParallelHTTPServer(socketserver.ThreadingMixIn,
                         wsgiref.simple_server.WSGIServer):

    # We wait for child threads ourself
    block_on_close = False
    daemon_threads = True

    def __init__(self, configuration, family, address, RequestHandlerClass):
        self.configuration = configuration
        self.address_family = family
        super().__init__(address, RequestHandlerClass)
        self.client_sockets = set()

    def server_bind(self):
        if self.address_family == socket.AF_INET6:
            # Only allow IPv6 connections to the IPv6 socket
            self.socket.setsockopt(COMPAT_IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
        super().server_bind()

    def get_request(self):
        # Set timeout for client
        request, client_address = super().get_request()
        timeout = self.configuration.get("server", "timeout")
        if timeout:
            request.settimeout(timeout)
        client_socket, client_socket_out = socket.socketpair()
        self.client_sockets.add(client_socket_out)
        return request, (*client_address, client_socket)

    def finish_request_locked(self, request, client_address):
        return super().finish_request(request, client_address)

    def finish_request(self, request, client_address):
        *client_address, client_socket = client_address
        client_address = tuple(client_address)
        try:
            return self.finish_request_locked(request, client_address)
        finally:
            client_socket.close()

    def handle_error(self, request, client_address):
        if issubclass(sys.exc_info()[0], socket.timeout):
            logger.info("Client timed out", exc_info=True)
        else:
            logger.error("An exception occurred during request: %s",
                         sys.exc_info()[1], exc_info=True)


class ParallelHTTPSServer(ParallelHTTPServer):

    def server_bind(self):
        super().server_bind()
        # Wrap the TCP socket in an SSL socket
        certfile = self.configuration.get("server", "certificate")
        keyfile = self.configuration.get("server", "key")
        cafile = self.configuration.get("server", "certificate_authority")
        # Test if the files can be read
        for name, filename in [("certificate", certfile), ("key", keyfile),
                               ("certificate_authority", cafile)]:
            type_name = config.DEFAULT_CONFIG_SCHEMA["server"][name][
                "type"].__name__
            source = self.configuration.get_source("server", name)
            if name == "certificate_authority" and not filename:
                continue
            try:
                open(filename, "r").close()
            except OSError as e:
                raise RuntimeError(
                    "Invalid %s value for option %r in section %r in %s: %r "
                    "(%s)" % (type_name, name, "server", source, filename,
                              e)) from e
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        context.load_cert_chain(certfile=certfile, keyfile=keyfile)
        if cafile:
            context.load_verify_locations(cafile=cafile)
            context.verify_mode = ssl.CERT_REQUIRED
        self.socket = context.wrap_socket(
            self.socket, server_side=True, do_handshake_on_connect=False)

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
    os_environ: MutableMapping[str, str] = {}

    def log_exception(self, exc_info):
        logger.error("An exception occurred during request: %s",
                     exc_info[1], exc_info=exc_info)


class RequestHandler(wsgiref.simple_server.WSGIRequestHandler):
    """HTTP requests handler."""

    def log_request(self, code="-", size="-"):
        pass  # Disable request logging.

    def log_error(self, format_, *args):
        logger.error("An error occurred during request: %s", format_ % args)

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
    """Serve radicale from configuration.

    `shutdown_socket` can be used to gracefully shutdown the server.
    The socket can be created with `socket.socketpair()`, when the other socket
    gets closed the server stops accepting new requests by clients and the
    function returns after all active requests are finished.

    """

    logger.info("Starting Radicale")
    # Copy configuration before modifying
    configuration = configuration.copy()
    configuration.update({"server": {"_internal_server": "True"}}, "server",
                         privileged=True)

    use_ssl = configuration.get("server", "ssl")
    server_class = ParallelHTTPSServer if use_ssl else ParallelHTTPServer
    application = Application(configuration)
    servers = {}
    try:
        for address in configuration.get("server", "hosts"):
            # Try to bind sockets for IPv4 and IPv6
            possible_families = (socket.AF_INET, socket.AF_INET6)
            bind_ok = False
            for i, family in enumerate(possible_families):
                is_last = i == len(possible_families) - 1
                try:
                    server = server_class(configuration, family, address,
                                          RequestHandler)
                except OSError as e:
                    # Ignore unsupported families (only one must work)
                    if ((bind_ok or not is_last) and (
                            isinstance(e, socket.gaierror) and (
                                # Hostname does not exist or doesn't have
                                # address for address family
                                # macOS: IPv6 address for INET address family
                                e.errno == socket.EAI_NONAME or
                                # Address not for address family
                                e.errno == COMPAT_EAI_ADDRFAMILY or
                                e.errno == COMPAT_EAI_NODATA) or
                            # Workaround for PyPy
                            str(e) == "address family mismatched" or
                            # Address family not available (e.g. IPv6 disabled)
                            # macOS: IPv4 address for INET6 address family with
                            #        IPV6_V6ONLY set
                            e.errno == errno.EADDRNOTAVAIL or
                            # Address family not supported
                            e.errno == errno.EAFNOSUPPORT or
                            # Protocol not supported
                            e.errno == errno.EPROTONOSUPPORT)):
                        continue
                    raise RuntimeError("Failed to start server %r: %s" % (
                                           format_address(address), e)) from e
                servers[server.socket] = server
                bind_ok = True
                server.set_app(application)
                logger.info("Listening on %r%s",
                            format_address(server.server_address),
                            " with SSL" if use_ssl else "")
        if not servers:
            raise RuntimeError("No servers started")

        # Mainloop
        select_timeout = None
        if os.name == "nt":
            # Fallback to busy waiting. (select(...) blocks SIGINT on Windows.)
            select_timeout = 1.0
        max_connections = configuration.get("server", "max_connections")
        logger.info("Radicale server ready")
        while True:
            rlist = []
            # Wait for finished clients
            for server in servers.values():
                rlist.extend(server.client_sockets)
            # Accept new connections if max_connections is not reached
            if max_connections <= 0 or len(rlist) < max_connections:
                rlist.extend(servers)
            # Use socket to get notified of program shutdown
            if shutdown_socket is not None:
                rlist.append(shutdown_socket)
            rlist, _, _ = select.select(rlist, [], [], select_timeout)
            rlist = set(rlist)
            if shutdown_socket in rlist:
                logger.info("Stopping Radicale")
                break
            for server in servers.values():
                finished_sockets = server.client_sockets.intersection(rlist)
                for s in finished_sockets:
                    s.close()
                    server.client_sockets.remove(s)
                    rlist.remove(s)
                if finished_sockets:
                    server.service_actions()
            if rlist:
                server = servers.get(rlist.pop())
                if server:
                    server.handle_request()
    finally:
        # Wait for clients to finish and close servers
        for server in servers.values():
            for s in server.client_sockets:
                s.recv(1)
                s.close()
            server.server_close()
