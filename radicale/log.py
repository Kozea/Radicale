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
import sys
import threading


LOGGER_NAME = "radicale"
LOGGER_FORMAT = "[%(processName)s/%(threadName)s] %(levelname)s: %(message)s"

root_logger = logging.getLogger()
logger = logging.getLogger(LOGGER_NAME)


class RemoveTracebackFilter(logging.Filter):
    def filter(self, record):
        record.exc_info = None
        return True


removeTracebackFilter = RemoveTracebackFilter()


def get_default_handler():
    handler = logging.StreamHandler(sys.stderr)
    return handler


def setup():
    """Set global logging up."""
    global register_stream, unregister_stream
    handler = get_default_handler()
    logging.basicConfig(format=LOGGER_FORMAT, handlers=[handler])
    set_debug(True)


def set_debug(debug):
    """Set debug mode for global logger."""
    if debug:
        root_logger.setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)
        logger.removeFilter(removeTracebackFilter)
    else:
        root_logger.setLevel(logging.WARNING)
        logger.setLevel(logging.WARNING)
        logger.addFilter(removeTracebackFilter)
