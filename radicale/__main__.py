# This file is part of Radicale Server - Calendar Server
# Copyright © 2011-2016 Guillaume Ayoub
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

import atexit
import os
import sys
import optparse
import select
import signal
import socket
from wsgiref.simple_server import make_server

from . import (
    Application, config, HTTPServer, HTTPSServer, log, RequestHandler, VERSION)


# This is a script, many branches and variables
# pylint: disable=R0912,R0914

def run():
    """Run Radicale as a standalone server."""
    # Get command-line options
    parser = optparse.OptionParser(version=VERSION)
    parser.add_option(
        "-d", "--daemon", action="store_true",
        help="launch as daemon")
    parser.add_option(
        "-p", "--pid",
        help="set PID filename for daemon mode")
    parser.add_option(
        "-f", "--foreground", action="store_false", dest="daemon",
        help="launch in foreground (opposite of --daemon)")
    parser.add_option(
        "-H", "--hosts",
        help="set server hostnames and ports")
    parser.add_option(
        "-s", "--ssl", action="store_true",
        help="use SSL connection")
    parser.add_option(
        "-S", "--no-ssl", action="store_false", dest="ssl",
        help="do not use SSL connection (opposite of --ssl)")
    parser.add_option(
        "-k", "--key",
        help="set private key file")
    parser.add_option(
        "-c", "--certificate",
        help="set certificate file")
    parser.add_option(
        "-D", "--debug", action="store_true",
        help="print debug information")
    parser.add_option(
        "-C", "--config",
        help="use a specific configuration file")

    options = parser.parse_args()[0]

    # Read in the configuration specified by the command line (if specified)
    configuration_found = (
        config.read(options.config) if options.config else True)

    # Update Radicale configuration according to options
    for option in parser.option_list:
        key = option.dest
        if key:
            section = "logging" if key == "debug" else "server"
            value = getattr(options, key)
            if value is not None:
                config.set(section, key, str(value))

    # Start logging
    log.start()

    # Log a warning if the configuration file of the command line is not found
    if not configuration_found:
        log.LOGGER.warning(
            "Configuration file '%s' not found" % options.config)

    # Fork if Radicale is launched as daemon
    if config.getboolean("server", "daemon"):
        # Check and create PID file in a race-free manner
        if config.get("server", "pid"):
            try:
                pid_fd = os.open(
                    config.get("server", "pid"),
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except:
                raise OSError(
                    "PID file exists: %s" % config.get("server", "pid"))
        pid = os.fork()
        if pid:
            sys.exit()
        # Write PID
        if config.get("server", "pid"):
            with os.fdopen(pid_fd, "w") as pid_file:
                pid_file.write(str(os.getpid()))
        # Decouple environment
        os.umask(0)
        os.chdir("/")
        os.setsid()
        with open(os.devnull, "r") as null_in:
            os.dup2(null_in.fileno(), sys.stdin.fileno())
        with open(os.devnull, "w") as null_out:
            os.dup2(null_out.fileno(), sys.stdout.fileno())
            os.dup2(null_out.fileno(), sys.stderr.fileno())

    if config.get("storage", "umask"):
        os.umask(int(config.get("storage", "umask")));

    # Register exit function
    def cleanup():
        """Remove the PID files."""
        log.LOGGER.debug("Cleaning up")
        # Remove PID file
        if (config.get("server", "pid") and
                config.getboolean("server", "daemon")):
            os.unlink(config.get("server", "pid"))

    atexit.register(cleanup)
    log.LOGGER.info("Starting Radicale")

    log.LOGGER.debug(
        "Base URL prefix: %s" % config.get("server", "base_prefix"))

    # Create collection servers
    servers = {}
    server_class = (
        HTTPSServer if config.getboolean("server", "ssl") else HTTPServer)
    shutdown_program = [False]

    for host in config.get("server", "hosts").split(","):
        address, port = host.strip().rsplit(":", 1)
        address, port = address.strip("[] "), int(port)
        server = make_server(address, port, Application(),
                             server_class, RequestHandler)
        servers[server.socket] = server
        log.LOGGER.debug(
            "Listening to %s port %s" % (
                server.server_name, server.server_port))
        if config.getboolean("server", "ssl"):
            log.LOGGER.debug("Using SSL")

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
        if shutdown_program[0]:
            # Ignore following signals
            return
        log.LOGGER.info("Stopping Radicale")
        shutdown_program[0] = True
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
    else:
        # Fallback to busy waiting
        select_timeout = 1.0
    log.LOGGER.debug("Radicale server ready")
    while not shutdown_program[0]:
        try:
            rlist, _, xlist = select.select(
                sockets, [], sockets, select_timeout)
        except (KeyboardInterrupt, select.error):
            # SIGINT is handled by signal handler above
            rlist, xlist = [], []
        if xlist:
            raise RuntimeError("Unhandled socket error")
        if rlist:
            server = servers.get(rlist[0])
            if server:
                server.handle_request()

# pylint: enable=R0912,R0914


if __name__ == "__main__":
    run()
