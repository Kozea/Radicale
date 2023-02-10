# This file is part of Radicale - CalDAV and CardDAV server
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

import logging
import os
import sys
import threading
from typing import Any, Callable, ClassVar, Dict, Iterator, Union

from radicale import types

LOGGER_NAME: str = "radicale"
LOGGER_FORMAT: str = "[%(asctime)s] [%(ident)s] [%(levelname)s] %(message)s"
DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S %z"

logger: logging.Logger = logging.getLogger(LOGGER_NAME)


class RemoveTracebackFilter(logging.Filter):

    def filter(self, record: logging.LogRecord) -> bool:
        record.exc_info = None
        return True


REMOVE_TRACEBACK_FILTER: logging.Filter = RemoveTracebackFilter()


class IdentLogRecordFactory:
    """LogRecordFactory that adds ``ident`` attribute."""

    def __init__(self, upstream_factory: Callable[..., logging.LogRecord]
                 ) -> None:
        self._upstream_factory = upstream_factory

    def __call__(self, *args: Any, **kwargs: Any) -> logging.LogRecord:
        record = self._upstream_factory(*args, **kwargs)
        ident = "%d" % os.getpid()
        main_thread = threading.main_thread()
        current_thread = threading.current_thread()
        if current_thread.name and main_thread != current_thread:
            ident += "/%s" % current_thread.name
        record.ident = ident  # type:ignore[attr-defined]
        return record


class ThreadedStreamHandler(logging.Handler):
    """Sends logging output to the stream registered for the current thread or
       ``sys.stderr`` when no stream was registered."""

    terminator: ClassVar[str] = "\n"

    _streams: Dict[int, types.ErrorStream]

    def __init__(self) -> None:
        super().__init__()
        self._streams = {}

    def emit(self, record: logging.LogRecord) -> None:
        try:
            stream = self._streams.get(threading.get_ident(), sys.stderr)
            msg = self.format(record)
            stream.write(msg)
            stream.write(self.terminator)
            if hasattr(stream, "flush"):
                stream.flush()
        except Exception:
            self.handleError(record)

    @types.contextmanager
    def register_stream(self, stream: types.ErrorStream) -> Iterator[None]:
        """Register stream for logging output of the current thread."""
        key = threading.get_ident()
        self._streams[key] = stream
        try:
            yield
        finally:
            del self._streams[key]


@types.contextmanager
def register_stream(stream: types.ErrorStream) -> Iterator[None]:
    """Register stream for logging output of the current thread."""
    yield


def setup() -> None:
    """Set global logging up."""
    global register_stream
    handler = ThreadedStreamHandler()
    logging.basicConfig(format=LOGGER_FORMAT, datefmt=DATE_FORMAT,
                        handlers=[handler])
    register_stream = handler.register_stream
    log_record_factory = IdentLogRecordFactory(logging.getLogRecordFactory())
    logging.setLogRecordFactory(log_record_factory)
    set_level(logging.WARNING)


def set_level(level: Union[int, str]) -> None:
    """Set logging level for global logger."""
    if isinstance(level, str):
        level = getattr(logging, level.upper())
        assert isinstance(level, int)
    logger.setLevel(level)
    logger.removeFilter(REMOVE_TRACEBACK_FILTER)
    if level > logging.DEBUG:
        logger.addFilter(REMOVE_TRACEBACK_FILTER)
