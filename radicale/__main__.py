# -*- coding: utf-8 -*-
#
# This file is part of Radicale Server - Calendar Server
# Copyright © 2011-2013 Guillaume Ayoub
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
import signal
import threading
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
        if os.path.exists(config.get("server", "pid")):
            raise OSError("PID file exists: %s" % config.get("server", "pid"))
        pid = os.fork()
        if pid:
            try:
                if config.get("server", "pid"):
                    open(config.get("server", "pid"), "w").write(str(pid))
            finally:
                sys.exit()
        sys.stdout = sys.stderr = open(os.devnull, "w")

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

    # Create collection servers
    servers = []
    server_class = (
        HTTPSServer if config.getboolean("server", "ssl") else HTTPServer)
    shutdown_program = threading.Event()

    for host in config.get("server", "hosts").split(","):
        address, port = host.strip().rsplit(":", 1)
        address, port = address.strip("[] "), int(port)
        servers.append(
            make_server(address, port, Application(),
                        server_class, RequestHandler))

    # SIGTERM and SIGINT (aka KeyboardInterrupt) should just mark this for
    # shutdown
    signal.signal(signal.SIGTERM, lambda *_: shutdown_program.set())
    signal.signal(signal.SIGINT, lambda *_: shutdown_program.set())

    def serve_forever(server):
        """Serve a server forever, cleanly shutdown when things go wrong."""
        try:
            server.serve_forever()
        finally:
            shutdown_program.set()

    log.LOGGER.debug(
        "Base URL prefix: %s" % config.get("server", "base_prefix"))

    # Start the servers in a different loop to avoid possible race-conditions,
    # when a server exists but another server is added to the list at the same
    # time
    for server in servers:
        log.LOGGER.debug(
            "Listening to %s port %s" % (
                server.server_name, server.server_port))
        if config.getboolean("server", "ssl"):
            log.LOGGER.debug("Using SSL")
        threading.Thread(target=serve_forever, args=(server,)).start()

    log.LOGGER.debug("Radicale server ready")

    # Main loop: wait until all servers are exited
    try:
        # We must do the busy-waiting here, as all ``.join()`` calls completly
        # block the thread, such that signals are not received
        while True:
            # The number is irrelevant, it only needs to be greater than 0.05
            # due to python implementing its own busy-waiting logic
            shutdown_program.wait(5.0)
            if shutdown_program.is_set():
                break
    finally:
        # Ignore signals, so that they cannot interfere
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        signal.signal(signal.SIGTERM, signal.SIG_IGN)

        log.LOGGER.info("Stopping Radicale")

        for server in servers:
            log.LOGGER.debug(
                "Closing server listening to %s port %s" % (
                    server.server_name, server.server_port))
            server.shutdown()

# pylint: enable=R0912,R0914


if __name__ == "__main__":
    run()
