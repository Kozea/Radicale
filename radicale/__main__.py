# This file is part of Radicale - CalDAV and CardDAV server
# Copyright © 2011-2017 Guillaume Ayoub
# Copyright © 2017-2022 Unrud <unrud@outlook.com>
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
from types import FrameType
from typing import List, Optional, cast

from radicale import VERSION, config, log, server, storage, types
from radicale.log import logger


def run() -> None:
    """Run Radicale as a standalone server."""
    exit_signal_numbers = [signal.SIGTERM, signal.SIGINT]
    if sys.platform == "win32":
        exit_signal_numbers.append(signal.SIGBREAK)
    else:
        exit_signal_numbers.append(signal.SIGHUP)
        exit_signal_numbers.append(signal.SIGQUIT)

    # Raise SystemExit when signal arrives to run cleanup code
    # (like destructors, try-finish etc.), otherwise the process exits
    # without running any of them
    def exit_signal_handler(signal_number: int,
                            stack_frame: Optional[FrameType]) -> None:
        sys.exit(1)
    for signal_number in exit_signal_numbers:
        signal.signal(signal_number, exit_signal_handler)

    log.setup()

    # Get command-line arguments
    # Configuration options are stored in dest with format "c:SECTION:OPTION"
    parser = argparse.ArgumentParser(
        prog="radicale", usage="%(prog)s [OPTIONS]", allow_abbrev=False)

    parser.add_argument("--version", action="version", version=VERSION)
    parser.add_argument("--verify-storage", action="store_true",
                        help="check the storage for errors and exit")
    parser.add_argument("-C", "--config",
                        help="use specific configuration files", nargs="*")
    parser.add_argument("-D", "--debug", action="store_const", const="debug",
                        dest="c:logging:level", default=argparse.SUPPRESS,
                        help="print debug information")

    for section, section_data in config.DEFAULT_CONFIG_SCHEMA.items():
        if section.startswith("_"):
            continue
        assert ":" not in section  # check field separator
        assert "-" not in section and "_" not in section  # not implemented
        group_description = None
        if section_data.get("_allow_extra"):
            group_description = "additional options allowed"
            if section == "headers":
                group_description += " (e.g. --headers-Pragma=no-cache)"
        elif "type" in section_data:
            group_description = "backend specific options omitted"
        group = parser.add_argument_group(section, group_description)
        for option, data in section_data.items():
            if option.startswith("_"):
                continue
            kwargs = data.copy()
            long_name = "--%s-%s" % (section, option.replace("_", "-"))
            args: List[str] = list(kwargs.pop("aliases", ()))
            args.append(long_name)
            kwargs["dest"] = "c:%s:%s" % (section, option)
            kwargs["metavar"] = "VALUE"
            kwargs["default"] = argparse.SUPPRESS
            del kwargs["value"]
            with contextlib.suppress(KeyError):
                del kwargs["internal"]

            if kwargs["type"] == bool:
                del kwargs["type"]
                opposite_args = list(kwargs.pop("opposite_aliases", ()))
                opposite_args.append("--no%s" % long_name[1:])
                group.add_argument(*args, nargs="?", const="True", **kwargs)
                # Opposite argument
                kwargs["help"] = "do not %s (opposite of %s)" % (
                    kwargs["help"], long_name)
                group.add_argument(*opposite_args, action="store_const",
                                   const="False", **kwargs)
            else:
                del kwargs["type"]
                group.add_argument(*args, **kwargs)

    args_ns, remaining_args = parser.parse_known_args()
    unrecognized_args = []
    while remaining_args:
        arg = remaining_args.pop(0)
        for section, data in config.DEFAULT_CONFIG_SCHEMA.items():
            if "type" not in data and not data.get("_allow_extra"):
                continue
            prefix = "--%s-" % section
            if arg.startswith(prefix):
                arg = arg[len(prefix):]
                break
        else:
            unrecognized_args.append(arg)
            continue
        value = ""
        if "=" in arg:
            arg, value = arg.split("=", maxsplit=1)
        elif remaining_args and not remaining_args[0].startswith("-"):
            value = remaining_args.pop(0)
        option = arg
        if not data.get("_allow_extra"):  # preserve dash in HTTP header names
            option = option.replace("-", "_")
        vars(args_ns)["c:%s:%s" % (section, option)] = value
    if unrecognized_args:
        parser.error("unrecognized arguments: %s" %
                     " ".join(unrecognized_args))

    # Preliminary configure logging
    with contextlib.suppress(ValueError):
        log.set_level(config.DEFAULT_CONFIG_SCHEMA["logging"]["level"]["type"](
            vars(args_ns).get("c:logging:level", "")), True)

    # Update Radicale configuration according to arguments
    arguments_config: types.MUTABLE_CONFIG = {}
    for key, value in vars(args_ns).items():
        if key.startswith("c:"):
            _, section, option = key.split(":", maxsplit=2)
            arguments_config[section] = arguments_config.get(section, {})
            arguments_config[section][option] = value

    try:
        configuration = config.load(config.parse_compound_paths(
            config.DEFAULT_CONFIG_PATH,
            os.environ.get("RADICALE_CONFIG"),
            os.pathsep.join(args_ns.config) if args_ns.config is not None
            else None))
        if arguments_config:
            configuration.update(arguments_config, "command line arguments")
    except Exception as e:
        logger.critical("Invalid configuration: %s", e, exc_info=True)
        sys.exit(1)

    # Configure logging
    log.set_level(cast(str, configuration.get("logging", "level")), configuration.get("logging", "backtrace_on_debug"))

    # Log configuration after logger is configured
    default_config_active = True
    for source, miss in configuration.sources():
        logger.info("%s %s", "Skipped missing/unreadable" if miss else "Loaded", source)
        if not miss and source != "default config":
            default_config_active = False

    if default_config_active:
        logger.warning("%s", "No config file found/readable - only default config is active")

    if args_ns.verify_storage:
        logger.info("Verifying storage")
        try:
            storage_ = storage.load(configuration)
            with storage_.acquire_lock("r"):
                if not storage_.verify():
                    logger.critical("Storage verification failed")
                    sys.exit(1)
        except Exception as e:
            logger.critical("An exception occurred during storage "
                            "verification: %s", e, exc_info=True)
            sys.exit(1)
        return

    # Create a socket pair to notify the server of program shutdown
    shutdown_socket, shutdown_socket_out = socket.socketpair()

    # Shutdown server when signal arrives
    def shutdown_signal_handler(signal_number: int,
                                stack_frame: Optional[FrameType]) -> None:
        shutdown_socket.close()
    for signal_number in exit_signal_numbers:
        signal.signal(signal_number, shutdown_signal_handler)

    try:
        server.serve(configuration, shutdown_socket_out)
    except Exception as e:
        logger.critical("An exception occurred during server startup: %s", e,
                        exc_info=False)
        sys.exit(1)


if __name__ == "__main__":
    run()
