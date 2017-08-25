# This file is part of Radicale Server - Calendar Server
# Copyright © 2011-2017 Guillaume Ayoub
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
Radicale executable module.

This module can be executed from a command line with ``$python -m radicale`` or
from a python programme with ``radicale.__main__.run()``.

"""

import argparse
import atexit
import os
import select
import signal
import socket
import ssl
import sys
from wsgiref.simple_server import make_server

from . import (VERSION, Application, RequestHandler, ThreadedHTTPServer,
               ThreadedHTTPSServer, config, log, storage)


def run():
    """Run Radicale as a standalone server."""
    # Get command-line arguments
    parser = argparse.ArgumentParser(usage="radicale [OPTIONS]")

    parser.add_argument("--version", action="version", version=VERSION)
    parser.add_argument("--verify-storage", action="store_true",
                        help="check the storage for errors and exit")
    parser.add_argument(
        "-C", "--config", help="use a specific configuration file")

    groups = {}
    for section, values in config.INITIAL_CONFIG.items():
        group = parser.add_argument_group(section)
        groups[group] = []
        for option, data in values.items():
            kwargs = data.copy()
            long_name = "--{0}-{1}".format(
                section, option.replace("_", "-"))
            args = kwargs.pop("aliases", [])
            args.append(long_name)
            kwargs["dest"] = "{0}_{1}".format(section, option)
            groups[group].append(kwargs["dest"])
            del kwargs["value"]
            if "internal" in kwargs:
                del kwargs["internal"]

            if kwargs["type"] == bool:
                del kwargs["type"]
                kwargs["action"] = "store_const"
                kwargs["const"] = "True"
                opposite_args = kwargs.pop("opposite", [])
                opposite_args.append("--no{0}".format(long_name[1:]))
                group.add_argument(*args, **kwargs)

                kwargs["const"] = "False"
                kwargs["help"] = "do not {0} (opposite of {1})".format(
                    kwargs["help"], long_name)
                group.add_argument(*opposite_args, **kwargs)
            else:
                group.add_argument(*args, **kwargs)

    args = parser.parse_args()
    if args.config is not None:
        config_paths = [args.config] if args.config else []
        ignore_missing_paths = False
    else:
        config_paths = ["/etc/radicale/config",
                        os.path.expanduser("~/.config/radicale/config")]
        if "RADICALE_CONFIG" in os.environ:
            config_paths.append(os.environ["RADICALE_CONFIG"])
        ignore_missing_paths = True
    try:
        configuration = config.load(config_paths,
                                    ignore_missing_paths=ignore_missing_paths)
    except Exception as e:
        print("ERROR: Invalid configuration: %s" % e, file=sys.stderr)
        if args.logging_debug:
            raise
        exit(1)

    # Update Radicale configuration according to arguments
    for group, actions in groups.items():
        section = group.title
        for action in actions:
            value = getattr(args, action)
            if value is not None:
                configuration.set(section, action.split('_', 1)[1], value)

    if args.verify_storage:
        # Write to stderr when storage verification is requested
        configuration["logging"]["config"] = ""

    # Start logging
    filename = os.path.expanduser(configuration.get("logging", "config"))
    debug = configuration.getboolean("logging", "debug")
    try:
        logger = log.start("radicale", filename, debug)
    except Exception as e:
        print("ERROR: Failed to start logger: %s" % e, file=sys.stderr)
        if debug:
            raise
        exit(1)

    if args.verify_storage:
        logger.info("Verifying storage")
        try:
            Collection = storage.load(configuration, logger)
            with Collection.acquire_lock("r"):
                if not Collection.verify():
                    logger.error("Storage verifcation failed")
                    exit(1)
        except Exception as e:
            logger.error("An exception occurred during storage verification: "
                         "%s", e, exc_info=True)
            exit(1)
        return

    try:
        serve(configuration, logger)
    except Exception as e:
        logger.error("An exception occurred during server startup: %s", e,
                     exc_info=True)
        exit(1)


def daemonize(configuration, logger):
    """Fork and decouple if Radicale is configured as daemon."""
    # Check and create PID file in a race-free manner
    if configuration.get("server", "pid"):
        try:
            pid_path = os.path.abspath(os.path.expanduser(
                configuration.get("server", "pid")))
            pid_fd = os.open(
                pid_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except OSError as e:
            raise OSError("PID file exists: %r" %
                          configuration.get("server", "pid")) from e
    pid = os.fork()
    if pid:
        # Write PID
        if configuration.get("server", "pid"):
            with os.fdopen(pid_fd, "w") as pid_file:
                pid_file.write(str(pid))
        sys.exit()
    if configuration.get("server", "pid"):
        os.close(pid_fd)

        # Register exit function
        def cleanup():
            """Remove the PID files."""
            logger.debug("Cleaning up")
            # Remove PID file
            os.unlink(pid_path)
        atexit.register(cleanup)
    # Decouple environment
    os.chdir("/")
    os.setsid()
    with open(os.devnull, "r") as null_in:
        os.dup2(null_in.fileno(), sys.stdin.fileno())
    with open(os.devnull, "w") as null_out:
        os.dup2(null_out.fileno(), sys.stdout.fileno())
        os.dup2(null_out.fileno(), sys.stderr.fileno())


def serve(configuration, logger):
    """Serve radicale from configuration."""
    logger.info("Starting Radicale")

    # Create collection servers
    servers = {}
    if configuration.getboolean("server", "ssl"):
        server_class = ThreadedHTTPSServer
        server_class.certificate = configuration.get("server", "certificate")
        server_class.key = configuration.get("server", "key")
        server_class.certificate_authority = configuration.get(
            "server", "certificate_authority")
        server_class.ciphers = configuration.get("server", "ciphers")
        server_class.protocol = getattr(
            ssl, configuration.get("server", "protocol"), ssl.PROTOCOL_SSLv23)
        # Test if the SSL files can be read
        for name in ["certificate", "key"] + (
                ["certificate_authority"]
                if server_class.certificate_authority else []):
            filename = getattr(server_class, name)
            try:
                open(filename, "r").close()
            except OSError as e:
                raise RuntimeError("Failed to read SSL %s %r: %s" %
                                   (name, filename, e)) from e
    else:
        server_class = ThreadedHTTPServer
    server_class.client_timeout = configuration.getint("server", "timeout")
    server_class.max_connections = configuration.getint(
        "server", "max_connections")
    server_class.logger = logger

    RequestHandler.logger = logger
    if not configuration.getboolean("server", "dns_lookup"):
        RequestHandler.address_string = lambda self: self.client_address[0]

    shutdown_program = False

    for host in configuration.get("server", "hosts").split(","):
        try:
            address, port = host.strip().rsplit(":", 1)
            address, port = address.strip("[] "), int(port)
        except ValueError as e:
            raise RuntimeError(
                "Failed to parse address %r: %s" % (host, e)) from e
        application = Application(configuration, logger)
        try:
            server = make_server(
                address, port, application, server_class, RequestHandler)
        except OSError as e:
            raise RuntimeError(
                "Failed to start server %r: %s" % (host, e)) from e
        servers[server.socket] = server
        logger.info("Listening to %r on port %d%s",
                    server.server_name, server.server_port, " using SSL"
                    if configuration.getboolean("server", "ssl") else "")

    # Create a socket pair to notify the select syscall of program shutdown
    # This is not available in python < 3.5 on Windows
    if hasattr(socket, "socketpair"):
        shutdown_program_socket_in, shutdown_program_socket_out = (
            socket.socketpair())
    else:
        shutdown_program_socket_in, shutdown_program_socket_out = None, None

    # SIGTERM and SIGINT (aka KeyboardInterrupt) should just mark this for
    # shutdown
    def shutdown(*args):
        nonlocal shutdown_program
        if shutdown_program:
            # Ignore following signals
            return
        logger.info("Stopping Radicale")
        shutdown_program = True
        if shutdown_program_socket_in:
            shutdown_program_socket_in.sendall(b"goodbye")
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    # Main loop: wait for requests on any of the servers or program shutdown
    sockets = list(servers.keys())
    if shutdown_program_socket_out:
        # Use socket pair to get notified of program shutdown
        sockets.append(shutdown_program_socket_out)
    select_timeout = None
    if not shutdown_program_socket_out or os.name == "nt":
        # Fallback to busy waiting. (select.select blocks SIGINT on Windows.)
        select_timeout = 1.0
    if configuration.getboolean("server", "daemon"):
        daemonize(configuration, logger)
    logger.info("Radicale server ready")
    while not shutdown_program:
        try:
            rlist, _, xlist = select.select(
                sockets, [], sockets, select_timeout)
        except (KeyboardInterrupt, select.error):
            # SIGINT is handled by signal handler above
            rlist, xlist = [], []
        if xlist:
            raise RuntimeError("unhandled socket error")
        if rlist:
            server = servers.get(rlist[0])
            if server:
                server.handle_request()


if __name__ == "__main__":
    run()
