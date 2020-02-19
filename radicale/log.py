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
Functions to set up Python's logging facility for Radicale's WSGI application.

Log messages are sent to the first available target of:

  - Error stream specified by the WSGI server in "wsgi.errors"
  - ``sys.stderr``

"""

import contextlib
import logging
import os
import sys
import threading

LOGGER_NAME = "radicale"
LOGGER_FORMAT = "[%(asctime)s] [%(ident)s] [%(levelname)s] %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S %z"

logger = logging.getLogger(LOGGER_NAME)


class RemoveTracebackFilter(logging.Filter):
    def filter(self, record):
        record.exc_info = None
        return True


REMOVE_TRACEBACK_FILTER = RemoveTracebackFilter()


class IdentLogRecordFactory:
    """LogRecordFactory that adds ``ident`` attribute."""

    def __init__(self, upstream_factory):
        self.upstream_factory = upstream_factory

    def __call__(self, *args, **kwargs):
        record = self.upstream_factory(*args, **kwargs)
        ident = "%d" % os.getpid()
        main_thread = threading.main_thread()
        current_thread = threading.current_thread()
        if current_thread.name and main_thread != current_thread:
            ident += "/%s" % current_thread.name
        record.ident = ident
        return record


class ThreadedStreamHandler(logging.Handler):
    """Sends logging output to the stream registered for the current thread or
       ``sys.stderr`` when no stream was registered."""

    terminator = "\n"

    def __init__(self):
        super().__init__()
        self._streams = {}

    def emit(self, record):
        try:
            stream = self._streams.get(threading.get_ident(), sys.stderr)
            msg = self.format(record)
            stream.write(msg)
            stream.write(self.terminator)
            if hasattr(stream, "flush"):
                stream.flush()
        except Exception:
            self.handleError(record)

    @contextlib.contextmanager
    def register_stream(self, stream):
        """Register stream for logging output of the current thread."""
        key = threading.get_ident()
        self._streams[key] = stream
        try:
            yield
        finally:
            del self._streams[key]


@contextlib.contextmanager
def register_stream(stream):
    """Register stream for logging output of the current thread."""
    yield


def setup():
    """Set global logging up."""
    global register_stream
    handler = ThreadedStreamHandler()
    logging.basicConfig(format=LOGGER_FORMAT, datefmt=DATE_FORMAT,
                        handlers=[handler])
    register_stream = handler.register_stream
    log_record_factory = IdentLogRecordFactory(logging.getLogRecordFactory())
    logging.setLogRecordFactory(log_record_factory)
    set_level(logging.WARNING)


def set_level(level):
    """Set logging level for global logger."""
    if isinstance(level, str):
        level = getattr(logging, level.upper())
    logger.setLevel(level)
    if level == logging.DEBUG:
        logger.removeFilter(REMOVE_TRACEBACK_FILTER)
    else:
        logger.addFilter(REMOVE_TRACEBACK_FILTER)
