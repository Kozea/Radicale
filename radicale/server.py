# This file is part of Radicale - CalDAV and CardDAV server
# Copyright © 2008 Nicolas Kandel
# Copyright © 2008 Pascal Halter
# Copyright © 2008-2017 Guillaume Ayoub
# Copyright © 2017-2023 Unrud <unrud@outlook.com>
# Copyright © 2024-2024 Peter Bieringer <pb@bieringer.de>
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

import http
import select
import socket
import socketserver
import ssl
import sys
import wsgiref.simple_server
from typing import (Any, Callable, Dict, List, MutableMapping, Optional, Set,
                    Tuple, Union)
from urllib.parse import unquote

from radicale import Application, config, utils
from radicale.log import logger

COMPAT_EAI_ADDRFAMILY: int
if hasattr(socket, "EAI_ADDRFAMILY"):
    COMPAT_EAI_ADDRFAMILY = socket.EAI_ADDRFAMILY  # type:ignore[attr-defined]
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
elif sys.platform == "win32":
    # HACK: https://bugs.python.org/issue29515
    COMPAT_IPPROTO_IPV6 = 41


# IPv4 (host, port) and IPv6 (host, port, flowinfo, scopeid)
ADDRESS_TYPE = Union[Tuple[Union[str, bytes, bytearray], int],
                     Tuple[str, int, int, int]]


def format_address(address: ADDRESS_TYPE) -> str:
    host, port, *_ = address
    if not isinstance(host, str):
        raise NotImplementedError("Unsupported address format: %r" %
                                  (address,))
    if host.find(":") == -1:
        return "%s:%d" % (host, port)
    else:
        return "[%s]:%d" % (host, port)


class ParallelHTTPServer(socketserver.ThreadingMixIn,
                         wsgiref.simple_server.WSGIServer):

    configuration: config.Configuration
    worker_sockets: Set[socket.socket]
    _timeout: float

    # We wait for child threads ourself (ThreadingMixIn)
    block_on_close: bool = False
    daemon_threads: bool = True

    def __init__(self, configuration: config.Configuration, family: int,
                 address: Tuple[str, int], RequestHandlerClass:
                 Callable[..., http.server.BaseHTTPRequestHandler]) -> None:
        self.configuration = configuration
        self.address_family = family
        super().__init__(address, RequestHandlerClass)
        self.worker_sockets = set()
        self._timeout = configuration.get("server", "timeout")

    def server_bind(self) -> None:
        if self.address_family == socket.AF_INET6:
            # Only allow IPv6 connections to the IPv6 socket
            self.socket.setsockopt(COMPAT_IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
        super().server_bind()

    def get_request(  # type:ignore[override]
            self) -> Tuple[socket.socket, Tuple[ADDRESS_TYPE, socket.socket]]:
        # Set timeout for client
        request: socket.socket
        client_address: ADDRESS_TYPE
        request, client_address = super().get_request()  # type:ignore[misc]
        if self._timeout > 0:
            request.settimeout(self._timeout)
        worker_socket, worker_socket_out = socket.socketpair()
        self.worker_sockets.add(worker_socket_out)
        # HACK: Forward `worker_socket` via `client_address` return value
        # to worker thread.
        # The super class calls `verify_request`, `process_request` and
        # `handle_error` with modified `client_address` value.
        return request, (client_address, worker_socket)

    def verify_request(  # type:ignore[override]
            self, request: socket.socket, client_address_and_socket:
            Tuple[ADDRESS_TYPE, socket.socket]) -> bool:
        return True

    def process_request(  # type:ignore[override]
            self, request: socket.socket, client_address_and_socket:
            Tuple[ADDRESS_TYPE, socket.socket]) -> None:
        # HACK: Super class calls `finish_request` in new thread with
        # `client_address_and_socket`
        return super().process_request(
            request, client_address_and_socket)  # type:ignore[arg-type]

    def finish_request(  # type:ignore[override]
            self, request: socket.socket, client_address_and_socket:
            Tuple[ADDRESS_TYPE, socket.socket]) -> None:
        # HACK: Unpack `client_address_and_socket` and call super class
        # `finish_request` with original `client_address`
        client_address, worker_socket = client_address_and_socket
        try:
            return self.finish_request_locked(request, client_address)
        finally:
            worker_socket.close()

    def finish_request_locked(self, request: socket.socket,
                              client_address: ADDRESS_TYPE) -> None:
        return super().finish_request(
            request, client_address)  # type:ignore[arg-type]

    def handle_error(  # type:ignore[override]
            self, request: socket.socket,
            client_address_or_client_address_and_socket:
            Union[ADDRESS_TYPE, Tuple[ADDRESS_TYPE, socket.socket]]) -> None:
        # HACK: This method can be called with the modified
        # `client_address_and_socket` or the original `client_address` value
        e = sys.exc_info()[1]
        assert e is not None
        if isinstance(e, socket.timeout):
            logger.info("Client timed out", exc_info=True)
        else:
            logger.error("An exception occurred during request: %s",
                         sys.exc_info()[1], exc_info=True)


class ParallelHTTPSServer(ParallelHTTPServer):

    def server_bind(self) -> None:
        super().server_bind()
        # Wrap the TCP socket in an SSL socket
        certfile: str = self.configuration.get("server", "certificate")
        keyfile: str = self.configuration.get("server", "key")
        cafile: str = self.configuration.get("server", "certificate_authority")
        protocol: str = self.configuration.get("server", "protocol")
        ciphersuite: str = self.configuration.get("server", "ciphersuite")
        # Test if the files can be read
        for name, filename in [("certificate", certfile), ("key", keyfile),
                               ("certificate_authority", cafile)]:
            type_name = config.DEFAULT_CONFIG_SCHEMA["server"][name][
                "type"].__name__
            source = self.configuration.get_source("server", name)
            if name == "certificate_authority" and not filename:
                continue
            try:
                open(filename).close()
            except OSError as e:
                raise RuntimeError(
                    "Invalid %s value for option %r in section %r in %s: %r "
                    "(%s)" % (type_name, name, "server", source, filename,
                              e)) from e
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        logger.info("SSL load files certificate='%s' key='%s'", certfile, keyfile)
        context.load_cert_chain(certfile=certfile, keyfile=keyfile)
        if protocol:
            logger.info("SSL set explicit protocols (maybe not all supported by underlying OpenSSL): '%s'", protocol)
            context.options = utils.ssl_context_options_by_protocol(protocol, context.options)
            context.minimum_version = utils.ssl_context_minimum_version_by_options(context.options)
            if (context.minimum_version == 0):
                raise RuntimeError("No SSL minimum protocol active")
            context.maximum_version = utils.ssl_context_maximum_version_by_options(context.options)
            if (context.maximum_version == 0):
                raise RuntimeError("No SSL maximum protocol active")
        else:
            logger.info("SSL active protocols: (system-default)")
        logger.debug("SSL minimum acceptable protocol: %s", context.minimum_version)
        logger.debug("SSL maximum acceptable protocol: %s", context.maximum_version)
        logger.info("SSL accepted protocols: %s", ' '.join(utils.ssl_get_protocols(context)))
        if ciphersuite:
            logger.info("SSL set explicit ciphersuite (maybe not all supported by underlying OpenSSL): '%s'", ciphersuite)
            context.set_ciphers(ciphersuite)
        else:
            logger.info("SSL active ciphersuite: (system-default)")
        cipherlist = []
        for entry in context.get_ciphers():
            cipherlist.append(entry["name"])
        logger.info("SSL accepted ciphers: %s", ' '.join(cipherlist))
        if cafile:
            logger.info("SSL enable mandatory client certificate verification using CA file='%s'", cafile)
            context.load_verify_locations(cafile=cafile)
            context.verify_mode = ssl.CERT_REQUIRED
        self.socket = context.wrap_socket(
            self.socket, server_side=True, do_handshake_on_connect=False)

    def finish_request_locked(  # type:ignore[override]
            self, request: ssl.SSLSocket, client_address: ADDRESS_TYPE
            ) -> None:
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
                self.shutdown_request(request)  # type:ignore[attr-defined]
            return
        return super().finish_request_locked(request, client_address)


class ServerHandler(wsgiref.simple_server.ServerHandler):

    # Don't pollute WSGI environ with OS environment
    os_environ: MutableMapping[str, str] = {}

    def log_exception(self, exc_info) -> None:
        logger.error("An exception occurred during request: %s",
                     exc_info[1], exc_info=exc_info)  # type:ignore[arg-type]


class RequestHandler(wsgiref.simple_server.WSGIRequestHandler):
    """HTTP requests handler."""

    # HACK: Assigned in `socketserver.StreamRequestHandler`
    connection: socket.socket

    def log_request(self, code: Union[int, str] = "-",
                    size: Union[int, str] = "-") -> None:
        pass  # Disable request logging.

    def log_error(self, format_: str, *args: Any) -> None:
        logger.error("An error occurred during request: %s", format_ % args)

    def get_environ(self) -> Dict[str, Any]:
        env = super().get_environ()
        if isinstance(self.connection, ssl.SSLSocket):
            # The certificate can be evaluated by the auth module
            env["REMOTE_CERTIFICATE"] = self.connection.getpeercert()
        # Parent class only tries latin1 encoding
        env["PATH_INFO"] = unquote(self.path.split("?", 1)[0])
        return env

    def handle(self) -> None:
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
        handler.request_handler = self  # type:ignore[attr-defined]
        app = self.server.get_app()  # type:ignore[attr-defined]
        handler.run(app)


def serve(configuration: config.Configuration,
          shutdown_socket: Optional[socket.socket] = None) -> None:
    """Serve radicale from configuration.

    `shutdown_socket` can be used to gracefully shutdown the server.
    The socket can be created with `socket.socketpair()`, when the other socket
    gets closed the server stops accepting new requests by clients and the
    function returns after all active requests are finished.

    """

    logger.info("Starting Radicale (%s)", utils.packages_version())
    # Copy configuration before modifying
    configuration = configuration.copy()
    configuration.update({"server": {"_internal_server": "True"}}, "server",
                         privileged=True)

    use_ssl: bool = configuration.get("server", "ssl")
    server_class = ParallelHTTPSServer if use_ssl else ParallelHTTPServer
    application = Application(configuration)
    servers = {}
    try:
        hosts: List[Tuple[str, int]] = configuration.get("server", "hosts")
        for address_port in hosts:
            # retrieve IPv4/IPv6 address of address
            try:
                getaddrinfo = socket.getaddrinfo(address_port[0], address_port[1], 0, socket.SOCK_STREAM, socket.IPPROTO_TCP)
            except OSError as e:
                logger.warning("cannot retrieve IPv4 or IPv6 address of '%s': %s" % (format_address(address_port), e))
                continue
            logger.debug("getaddrinfo of '%s': %s" % (format_address(address_port), getaddrinfo))
            for (address_family, socket_kind, socket_proto, socket_flags, socket_address) in getaddrinfo:
                logger.debug("try to create server socket on '%s'" % (format_address(socket_address)))
                try:
                    server = server_class(configuration, address_family, (socket_address[0], socket_address[1]), RequestHandler)
                except OSError as e:
                    logger.warning("cannot create server socket on '%s': %s" % (format_address(socket_address), e))
                    continue
                servers[server.socket] = server
                server.set_app(application)
                logger.info("Listening on %r%s",
                            format_address(server.server_address),
                            " with SSL" if use_ssl else "")
        if not servers:
            raise RuntimeError("No servers started")

        # Mainloop
        select_timeout = None
        if sys.platform == "win32":
            # Fallback to busy waiting. (select(...) blocks SIGINT on Windows.)
            select_timeout = 1.0
        max_connections: int = configuration.get("server", "max_connections")
        logger.info("Radicale server ready")
        while True:
            rlist: List[socket.socket] = []
            # Wait for finished clients
            for server in servers.values():
                rlist.extend(server.worker_sockets)
            # Accept new connections if max_connections is not reached
            if max_connections <= 0 or len(rlist) < max_connections:
                rlist.extend(servers)
            # Use socket to get notified of program shutdown
            if shutdown_socket is not None:
                rlist.append(shutdown_socket)
            rlist, _, _ = select.select(rlist, [], [], select_timeout)
            rset = set(rlist)
            if shutdown_socket in rset:
                logger.info("Stopping Radicale")
                break
            for server in servers.values():
                finished_sockets = server.worker_sockets.intersection(rset)
                for s in finished_sockets:
                    s.close()
                    server.worker_sockets.remove(s)
                    rset.remove(s)
                if finished_sockets:
                    server.service_actions()
            if rset:
                active_server = servers.get(rset.pop())
                if active_server:
                    active_server.handle_request()
    finally:
        # Wait for clients to finish and close servers
        for server in servers.values():
            for s in server.worker_sockets:
                s.recv(1)
                s.close()
            server.server_close()
