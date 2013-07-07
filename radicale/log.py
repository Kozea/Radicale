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
Radicale logging module.

Manage logging from a configuration file. For more information, see:
http://docs.python.org/library/logging.config.html

"""

import os
import sys
import logging
import logging.config

from . import config


LOGGER = logging.getLogger()

def start():
    filename = os.path.expanduser(config.get("logging", "config"))
    debug = config.getboolean("logging", "debug")

    """Start the logging according to the configuration."""
    if os.path.exists(filename):
        # Configuration taken from file
        logging.config.fileConfig(filename)
        if debug:
            LOGGER.setLevel(logging.DEBUG)
            for handler in LOGGER.handlers:
                handler.setLevel(logging.DEBUG)
    else:
        # Default configuration, standard output
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(message)s"))
        LOGGER.addHandler(handler)
        if debug:
            LOGGER.setLevel(logging.DEBUG)
            LOGGER.debug("Logging configuration file '%s' not found, using stdout."
                         % filename)
