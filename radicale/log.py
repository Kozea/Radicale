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
Radicale logging module.

Manage logging from a configuration file. For more information, see:
http://docs.python.org/library/logging.config.html

"""

import logging
import logging.config
import os
import signal
import sys


def configure_from_file(logger, filename, debug):
    logging.config.fileConfig(filename, disable_existing_loggers=False)
    if debug:
        logger.setLevel(logging.DEBUG)
        for handler in logger.handlers:
            handler.setLevel(logging.DEBUG)
    return logger


def start(name="radicale", filename=None, debug=False):
    """Start the logging according to the configuration."""
    logger = logging.getLogger(name)
    if filename and os.path.exists(filename):
        # Configuration taken from file
        configure_from_file(logger, filename, debug)
        # Reload config on SIGHUP (UNIX only)
        if hasattr(signal, "SIGHUP"):
            def handler(signum, frame):
                configure_from_file(logger, filename, debug)
            signal.signal(signal.SIGHUP, handler)
    else:
        # Default configuration, standard output
        if filename:
            logger.warning(
                "Logging configuration file '%s' not found, using stderr." %
                filename)
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(
            logging.Formatter("[%(thread)x] %(levelname)s: %(message)s"))
        logger.addHandler(handler)
    if debug:
        logger.setLevel(logging.DEBUG)
    return logger
