# This file is part of Radicale Server - Calendar Server
# Copyright © 2011-2017 Guillaume Ayoub
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
Radicale executable module.

This module can be executed from a command line with ``$python -m radicale``.

"""

import argparse
import os
import signal
import socket

from radicale import VERSION, config, log, server, share, storage
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
        "-C", "--config", help="use a specific configuration file")
    parser.add_argument("-D", "--debug", action="store_true",
                        help="print debug information")

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

    # Preliminary configure logging
    if args.debug:
        args.logging_level = "debug"
    if args.logging_level is not None:
        log.set_level(args.logging_level)

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
        logger.fatal("Invalid configuration: %s", e, exc_info=True)
        exit(1)

    # Update Radicale configuration according to arguments
    for group, actions in groups.items():
        section = group.title
        for action in actions:
            value = getattr(args, action)
            if value is not None:
                configuration.set(section, action.split('_', 1)[1], value)

    # Configure logging
    log.set_level(configuration.get("logging", "level"))

    if args.verify_storage:
        logger.info("Verifying storage")
        try:
            shares = share.load(configuration)
            Collection = storage.load(configuration, shares)
            with Collection.acquire_lock("r"):
                if not Collection.verify():
                    logger.fatal("Storage verifcation failed")
                    exit(1)
        except Exception as e:
            logger.fatal("An exception occurred during storage verification: "
                         "%s", e, exc_info=True)
            exit(1)
        return

    # Create a socket pair to notify the server of program shutdown
    shutdown_socket, shutdown_socket_out = socket.socketpair()

    # SIGTERM and SIGINT (aka KeyboardInterrupt) shutdown the server
    def shutdown(*args):
        shutdown_socket.sendall(b" ")
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    try:
        server.serve(configuration, shutdown_socket_out)
    except Exception as e:
        logger.fatal("An exception occurred during server startup: %s", e,
                     exc_info=True)
        exit(1)


if __name__ == "__main__":
    run()
