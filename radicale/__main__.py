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
import traceback
from wsgiref.simple_server import make_server

from . import (
    Application, config, HTTPServer, HTTPSServer, log, RequestHandler, VERSION)


# This is a script, many branches and variables
# pylint: disable=R0912,R0914


def export_storage(config, path, debug=False):
    """Export the storage for Radicale 2.0.0."""
    import json
    import shutil
    import tempfile
    from . import ical, pathutils, storage
    storage.load()

    print("INFO: Exporting storage for Radicale 2.0.0 to %r" % path)

    temp = tempfile.mkdtemp(prefix="Radicale.export.")
    try:
        os.mkdir(os.path.join(temp, "root"))
        try:
            remaining_collections = list(
                ical.Collection.from_path("/", depth="0"))
        except Exception as e:
            print("ERROR: Failed to find collection %r: %s" % ("/", e))
            if debug:
                traceback.print_exc()
            exit(1)
        while remaining_collections:
            collection = remaining_collections.pop(0)
            if debug:
                print("DEBUG: Exporting collection %r" %
                      ("/" + collection.path))
            try:
                try:
                    filesystem_path = pathutils.path_to_filesystem(
                        collection.path,
                        os.path.join(temp, "root", "collection-root"))
                except ValueError as e:
                    print(
                        "WARNING: Skipping unsafe collection %r: %s" %
                        ("/" + collection.path, e))
                    if debug:
                        traceback.print_exc()
                    continue
                try:
                    remaining_collections.extend(collection.children(
                        collection.path))
                except Exception as e:
                    print("ERROR: Failed to find child collections of %r: %s" %
                          ("/" + collection.path, e))
                    if debug:
                        traceback.print_exc()
                    exit(1)
                os.makedirs(filesystem_path)
                with collection.props as props:
                    if props:
                        props_filename = os.path.join(
                            filesystem_path, ".Radicale.props")
                        with open(props_filename, "w") as f:
                            json.dump(props, f)
                for component in collection.components:
                    if debug:
                        print("DEBUG: Exporting component %r of collection %r"
                              % (component.name, "/" + collection.path))
                    try:
                        if not pathutils.is_safe_filesystem_path_component(
                                component.name):
                            print("WARNING: Skipping unsafe item %r from "
                                  "collection %r" %
                                  (component.name, "/" + collection.path))
                            continue
                        items = [component]
                        if collection.resource_type == "calendar":
                            items.extend(collection.timezones)
                        text = ical.serialize(
                            collection.tag, collection.headers, items)
                        component_filename = os.path.join(
                            filesystem_path, component.name)
                        with open(component_filename, "wb") as f:
                            f.write(text.encode("utf-8"))
                    except Exception as e:
                        print("ERROR: Failed to export component %r from "
                              "collection %r: %s" %
                              (component.name, "/" + collection.path, e))
                        if debug:
                            traceback.print_exc()
                        exit(1)
            except Exception as e:
                print("ERROR: Failed to export collection %r: %s" %
                      ("/" + collection.path, e))
                if debug:
                    traceback.print_exc()
                exit(1)
        try:
            # This check is prone to a race condition
            if os.path.exists(path):
                raise Exception("Destination path %r already exists" % path)
            shutil.move(os.path.join(temp, "root"), path)
        except Exception as e:
            print("ERROR: Can't create %r directory: %s" % (path, e))
            if debug:
                traceback.print_exc()
            exit(1)
    finally:
        shutil.rmtree(temp)


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
    parser.add_option(
        "--export-storage",
        help=("export the storage for Radicale 2.0.0 to the specified "
              "folder and exit"), metavar="FOLDER")

    options = parser.parse_args()[0]

    # Read in the configuration specified by the command line (if specified)
    configuration_found = (
        config.read(options.config) if options.config else True)

    # Update Radicale configuration according to options
    for option in parser.option_list:
        key = option.dest
        if key and key != "export_storage":
            section = "logging" if key == "debug" else "server"
            value = getattr(options, key)
            if value is not None:
                config.set(section, key, str(value))

    if options.export_storage is not None:
        config.set("logging", "config", "")
        config.set("logging", "debug", "True" if options.debug else "False")
        log.start()
        if not configuration_found:
            print("WARNING: Configuration file '%s' not found" %
                  options.config)
        export_storage(config, options.export_storage, debug=options.debug)
        exit(0)

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
