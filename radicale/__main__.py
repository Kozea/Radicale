# This file is part of Radicale Server - Calendar Server
# Copyright © 2011-2017 Guillaume Ayoub
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
Radicale executable module.

This module can be executed from a command line with ``$python -m radicale``.
Uses the built-in WSGI server.

"""

import argparse
import contextlib
import os
import signal
import socket
import sys

from radicale import VERSION, config, log, server, storage
from radicale.log import logger


def run():
    """Run Radicale as a standalone server."""
    log.setup()

    # Get command-line arguments
    parser = argparse.ArgumentParser(usage="radicale [OPTIONS]")

    parser.add_argument("--version", action="version", version=VERSION)
    parser.add_argument("--verify-storage", action="store_true",
                        help="check the storage for errors and exit")
    parser.add_argument(
        "-C", "--config", help="use specific configuration files", nargs="*")
    parser.add_argument("-D", "--debug", action="store_true",
                        help="print debug information")

    groups = {}
    for section, values in config.DEFAULT_CONFIG_SCHEMA.items():
        if values.get("_internal", False):
            continue
        group = parser.add_argument_group(section)
        groups[group] = []
        for option, data in values.items():
            if option.startswith("_"):
                continue
            kwargs = data.copy()
            long_name = "--%s-%s" % (section, option.replace("_", "-"))
            args = kwargs.pop("aliases", [])
            args.append(long_name)
            kwargs["dest"] = "%s_%s" % (section, option)
            groups[group].append(kwargs["dest"])
            del kwargs["value"]
            if "internal" in kwargs:
                del kwargs["internal"]

            if kwargs["type"] == bool:
                del kwargs["type"]
                kwargs["action"] = "store_const"
                kwargs["const"] = "True"
                opposite_args = kwargs.pop("opposite", [])
                opposite_args.append("--no%s" % long_name[1:])
                group.add_argument(*args, **kwargs)

                kwargs["const"] = "False"
                kwargs["help"] = "do not %s (opposite of %s)" % (
                    kwargs["help"], long_name)
                group.add_argument(*opposite_args, **kwargs)
            else:
                del kwargs["type"]
                group.add_argument(*args, **kwargs)

    args = parser.parse_args()

    # Preliminary configure logging
    if args.debug:
        args.logging_level = "debug"
    with contextlib.suppress(ValueError):
        log.set_level(config.DEFAULT_CONFIG_SCHEMA["logging"]["level"]["type"](
            args.logging_level))

    # Update Radicale configuration according to arguments
    arguments_config = {}
    for group, actions in groups.items():
        section = group.title
        section_config = {}
        for action in actions:
            value = getattr(args, action)
            if value is not None:
                section_config[action.split('_', 1)[1]] = value
        if section_config:
            arguments_config[section] = section_config

    try:
        configuration = config.load(config.parse_compound_paths(
            config.DEFAULT_CONFIG_PATH,
            os.environ.get("RADICALE_CONFIG"),
            os.pathsep.join(args.config) if args.config else None))
        if arguments_config:
            configuration.update(arguments_config, "arguments")
    except Exception as e:
        logger.fatal("Invalid configuration: %s", e, exc_info=True)
        sys.exit(1)

    # Configure logging
    log.set_level(configuration.get("logging", "level"))

    # Log configuration after logger is configured
    configuration.log_config_sources()

    if args.verify_storage:
        logger.info("Verifying storage")
        try:
            storage_ = storage.load(configuration)
            with storage_.acquire_lock("r"):
                if not storage_.verify():
                    logger.fatal("Storage verifcation failed")
                    sys.exit(1)
        except Exception as e:
            logger.fatal("An exception occurred during storage verification: "
                         "%s", e, exc_info=True)
            sys.exit(1)
        return

    # Create a socket pair to notify the server of program shutdown
    shutdown_socket, shutdown_socket_out = socket.socketpair()

    # SIGTERM and SIGINT (aka KeyboardInterrupt) shutdown the server
    def shutdown(signal_number, stack_frame):
        shutdown_socket.sendall(b" ")
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    try:
        server.serve(configuration, shutdown_socket_out)
    except Exception as e:
        logger.fatal("An exception occurred during server startup: %s", e,
                     exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    run()
