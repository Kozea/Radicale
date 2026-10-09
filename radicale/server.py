# This file is part of Radicale - CalDAV and CardDAV server
# Copyright © 2008 Nicolas Kandel
# Copyright © 2008 Pascal Halter
# Copyright © 2008-2017 Guillaume Ayoub
# Copyright © 2017-2023 Unrud <unrud@outlook.com>
# Copyright © 2024-2025 Peter Bieringer <pb@bieringer.de>
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
Built-in WSGI server, based on the pure-Python `cheroot` HTTP server.

"""

import contextlib
import os
import platform
import select
import socket
import ssl
import sys
import threading
from typing import Dict, List, Optional, Tuple

from cheroot import wsgi
from cheroot.ssl.builtin import BuiltinSSLAdapter

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
ADDRESS_TYPE = utils.ADDRESS_TYPE


class _Server(wsgi.Server):
    """`cheroot` WSGI server with Radicale-specific adjustments."""

    # Use the "WSGI u.0" gateway, which decodes ``PATH_INFO`` and
    # ``QUERY_STRING`` as UTF-8 instead of Latin-1 (the WSGI 1.0 default).
    wsgi_version = ("u", 0)

    def error_log(self, msg: str = "", level: int = 20,
                 traceback: bool = False) -> None:
        logger.log(level, "%s", msg,
                   exc_info=sys.exc_info() if traceback else None)

    @classmethod
    def prepare_socket(cls, bind_addr, family, type, proto,  # noqa: A002
                       nodelay, ssl_adapter, reuse_port=False):
        sock = super().prepare_socket(bind_addr, family, type, proto,
                                      nodelay, ssl_adapter, reuse_port)
        if family == socket.AF_INET6:
            # Only allow IPv6 connections to the IPv6 socket, so that an
            # IPv4 "any" address can still be listened on independently
            # (`cheroot` enables dual-stack sockets for "::" by default).
            with contextlib.suppress(AttributeError, OSError):
                sock.setsockopt(COMPAT_IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
        return sock


def _build_ssl_adapter(configuration: config.Configuration
                       ) -> BuiltinSSLAdapter:
    certfile: str = configuration.get("server", "certificate")
    keyfile: str = configuration.get("server", "key")
    cafile: str = configuration.get("server", "certificate_authority")
    protocol: str = configuration.get("server", "protocol")
    ciphersuite: str = configuration.get("server", "ciphersuite")
    # Test if the files can be read
    for name, filename in [("certificate", certfile), ("key", keyfile),
                           ("certificate_authority", cafile)]:
        type_name = config.DEFAULT_CONFIG_SCHEMA["server"][name][
            "type"].__name__
        source = configuration.get_source("server", name)
        if name == "certificate_authority" and not filename:
            continue
        try:
            open(filename).close()
        except OSError as e:
            raise RuntimeError(
                "Invalid %s value for option %r in section %r in %s: %r "
                "(%s)" % (type_name, name, "server", source, filename,
                          e)) from e
    logger.info("SSL load files certificate='%s' key='%s'", certfile, keyfile)
    adapter = BuiltinSSLAdapter(certfile, keyfile,
                                certificate_chain=cafile or None,
                                ciphers=ciphersuite or None)
    context = adapter.context
    if protocol:
        logger.info("SSL set explicit protocols (maybe not all supported by underlying OpenSSL): '%s'", protocol)
        context.options = utils.ssl_context_options_by_protocol(protocol, context.options)
        context.minimum_version = utils.ssl_context_minimum_version_by_options(context.options)
        if context.minimum_version == 0:
            raise RuntimeError("No SSL minimum protocol active")
        context.maximum_version = utils.ssl_context_maximum_version_by_options(context.options)
        if context.maximum_version == 0:
            raise RuntimeError("No SSL maximum protocol active")
    else:
        logger.info("SSL active protocols: (system-default)")
    logger.debug("SSL minimum acceptable protocol: %s", context.minimum_version)
    logger.debug("SSL maximum acceptable protocol: %s", context.maximum_version)
    logger.info("SSL accepted protocols: %s", ' '.join(utils.ssl_get_protocols(context)))
    if ciphersuite:
        logger.info("SSL set explicit ciphersuite (maybe not all supported by underlying OpenSSL): '%s'", ciphersuite)
    else:
        logger.info("SSL active ciphersuite: (system-default)")
    logger.info("SSL accepted ciphers: %s",
               ' '.join(entry["name"] for entry in context.get_ciphers()))
    if cafile:
        logger.info("SSL enable mandatory client certificate verification using CA file='%s'", cafile)
        context.verify_mode = ssl.CERT_REQUIRED
    return adapter


def serve(configuration: config.Configuration,
          shutdown_socket: Optional[socket.socket] = None) -> None:
    """Serve radicale from configuration.

    `shutdown_socket` can be used to gracefully shutdown the server.
    The socket can be created with `socket.socketpair()`, when the other socket
    gets closed the server stops accepting new requests by clients and the
    function returns after all active requests are finished.

    """

    if os.environ.get("PYTHONPATH"):
        info = "with PYTHONPATH=%r " % os.environ.get("PYTHONPATH")
    else:
        info = ""
    logger.info("Starting Radicale %s(%s) as %s on %s", info, utils.packages_version(), utils.user_groups_as_string(), platform.platform())
    # Copy configuration before modifying
    configuration = configuration.copy()
    configuration.update({"server": {"_internal_server": "True"}}, "server",
                         privileged=True)

    use_ssl: bool = configuration.get("server", "ssl")
    ssl_adapter = _build_ssl_adapter(configuration) if use_ssl else None
    application = Application(configuration)
    max_connections: int = configuration.get("server", "max_connections")
    timeout: float = configuration.get("server", "timeout")

    servers: Dict[socket.socket, _Server] = {}
    threads: List[threading.Thread] = []
    try:
        hosts: List[Tuple[str, int]] = configuration.get("server", "hosts")
        for address_port in hosts:
            # retrieve IPv4/IPv6 address of address
            try:
                getaddrinfo = socket.getaddrinfo(address_port[0], address_port[1], 0, socket.SOCK_STREAM, socket.IPPROTO_TCP)
            except OSError as e:
                logger.warning(
                    "cannot retrieve IPv4 or IPv6 address of '%s': %s",
                    utils.format_address(address_port), e)
                continue
            logger.debug(
                "getaddrinfo of '%s': %s",
                utils.format_address(address_port), getaddrinfo)
            for (address_family, socket_kind, socket_proto, socket_flags, socket_address) in getaddrinfo:
                bind_addr = (socket_address[0], socket_address[1])
                logger.debug(
                    "try to create server socket on '%s'",
                    utils.format_address(bind_addr))
                server = _Server(bind_addr, application,
                                 numthreads=max_connections, timeout=timeout)
                server.ssl_adapter = ssl_adapter
                try:
                    server.prepare()
                except OSError as e:
                    logger.warning(
                        "cannot create server socket on '%s': %s",
                        utils.format_address(bind_addr), e)
                    continue
                servers[server.socket] = server
                logger.info("Listening on %r%s",
                            utils.format_address(server.bind_addr),
                            " with SSL" if use_ssl else "")
        if not servers:
            raise RuntimeError("No servers started")

        logger.info("Maximum parallel connections: %d", max_connections)
        logger.info("Radicale server ready")

        for server in servers.values():
            thread = threading.Thread(target=server.serve)
            thread.start()
            threads.append(thread)

        if shutdown_socket is not None:
            # Block until the other end of ``shutdown_socket`` is closed
            # (or any data is received on it).
            select.select([shutdown_socket], [], [])
            logger.info("Stopping Radicale")
        else:
            for thread in threads:
                thread.join()
    finally:
        # Wait for clients to finish and close servers
        for server in servers.values():
            server.stop()
        for thread in threads:
            thread.join()
