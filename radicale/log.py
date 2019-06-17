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
Radicale logging module.

Manage logging from a configuration file. For more information, see:
http://docs.python.org/library/logging.config.html

"""

import contextlib
import io
import logging
import multiprocessing
import os
import sys
import tempfile
import threading

from radicale import pathutils

try:
    import systemd.journal
except ImportError:
    systemd = None

LOGGER_NAME = "radicale"
LOGGER_FORMAT = "[%(ident)s] %(levelname)s: %(message)s"

logger = logging.getLogger(LOGGER_NAME)


class RemoveTracebackFilter(logging.Filter):
    def filter(self, record):
        record.exc_info = None
        return True


removeTracebackFilter = RemoveTracebackFilter()


class IdentLogRecordFactory:
    """LogRecordFactory that adds ``ident`` attribute."""

    def __init__(self, upstream_factory):
        self.upstream_factory = upstream_factory
        self.main_pid = os.getpid()

    def __call__(self, *args, **kwargs):
        record = self.upstream_factory(*args, **kwargs)
        pid = os.getpid()
        ident = "%x" % self.main_pid
        if pid != self.main_pid:
            ident += "%+x" % (pid - self.main_pid)
        main_thread = threading.main_thread()
        current_thread = threading.current_thread()
        if current_thread.name and main_thread != current_thread:
            ident += "/%s" % current_thread.name
        record.ident = ident
        return record


class RwLockWrapper():

    def __init__(self):
        self._file = tempfile.NamedTemporaryFile()
        self._lock = pathutils.RwLock(self._file.name)
        self._cm = None

    def acquire(self, blocking=True):
        assert self._cm is None
        if not blocking:
            raise NotImplementedError
        cm = self._lock.acquire("w")
        cm.__enter__()
        self._cm = cm

    def release(self):
        assert self._cm is not None
        self._cm.__exit__(None, None, None)
        self._cm = None


class ThreadStreamsHandler(logging.Handler):

    terminator = "\n"

    def __init__(self, fallback_stream, fallback_handler):
        super().__init__()
        self._streams = {}
        self.fallback_stream = fallback_stream
        self.fallback_handler = fallback_handler

    def createLock(self):
        try:
            self.lock = multiprocessing.Lock()
        except Exception:
            # HACK: Workaround for Android
            self.lock = RwLockWrapper()

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
        if (systemd and
                st.st_dev == journal_dev and st.st_ino == journal_ino):
            handler = systemd.journal.JournalHandler(
                SYSLOG_IDENTIFIER=LOGGER_NAME)
    return handler


@contextlib.contextmanager
def register_stream(stream):
    """Register global errors stream for the current thread."""
    yield


def setup():
    """Set global logging up."""
    global register_stream
    handler = ThreadStreamsHandler(sys.stderr, get_default_handler())
    logging.basicConfig(format=LOGGER_FORMAT, handlers=[handler])
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
        logger.removeFilter(removeTracebackFilter)
    else:
        logger.addFilter(removeTracebackFilter)
