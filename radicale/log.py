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

import contextlib
import io
import logging
import os
import sys
import threading

try:
    from systemd import journal
except ImportError:
    journal = None

LOGGER_NAME = "radicale"
LOGGER_FORMAT = "[%(processName)s/%(threadName)s] %(levelname)s: %(message)s"

root_logger = logging.getLogger()
logger = logging.getLogger(LOGGER_NAME)


class RemoveTracebackFilter(logging.Filter):
    def filter(self, record):
        record.exc_info = None
        return True


removeTracebackFilter = RemoveTracebackFilter()


class ThreadStreamsHandler(logging.Handler):

    terminator = "\n"

    def __init__(self, fallback_stream, fallback_handler):
        super().__init__()
        self._streams = {}
        self.fallback_stream = fallback_stream
        self.fallback_handler = fallback_handler

    def setFormatter(self, form):
        super().setFormatter(form)
        self.fallback_handler.setFormatter(form)

    def emit(self, record):
        try:
            stream = self._streams.get(threading.get_ident())
            if stream is None:
                self.fallback_handler.emit(record)
            else:
                msg = self.format(record)
                stream.write(msg)
                stream.write(self.terminator)
                if hasattr(stream, "flush"):
                    stream.flush()
        except Exception:
            self.handleError(record)

    @contextlib.contextmanager
    def register_stream(self, stream):
        if stream == self.fallback_stream:
            yield
            return
        key = threading.get_ident()
        self._streams[key] = stream
        try:
            yield
        finally:
            del self._streams[key]


def get_default_handler():
    handler = logging.StreamHandler(sys.stderr)
    # Detect systemd journal
    with contextlib.suppress(ValueError, io.UnsupportedOperation):
        journal_dev, journal_ino = map(
            int, os.environ.get("JOURNAL_STREAM", "").split(":"))
        st = os.fstat(sys.stderr.fileno())
        if (journal and
                st.st_dev == journal_dev and st.st_ino == journal_ino):
            handler = journal.JournalHandler(SYSLOG_IDENTIFIER=LOGGER_NAME)
    return handler


@contextlib.contextmanager
def register_stream(stream):
    """Register global errors stream for the current thread."""
    yield


def setup():
    """Set global logging up."""
    global register_stream, unregister_stream
    handler = ThreadStreamsHandler(sys.stderr, get_default_handler())
    logging.basicConfig(format=LOGGER_FORMAT, handlers=[handler])
    register_stream = handler.register_stream
    set_level(logging.DEBUG)


def set_level(level):
    """Set logging level for global logger."""
    if isinstance(level, str):
        level = getattr(logging, level.upper())
    root_logger.setLevel(level)
    logger.setLevel(level)
    if level == logging.DEBUG:
        logger.removeFilter(removeTracebackFilter)
    else:
        logger.addFilter(removeTracebackFilter)
