# This file is part of Radicale - CalDAV and CardDAV server
# Copyright © 2011-2017 Guillaume Ayoub
# Copyright © 2017-2023 Unrud <unrud@outlook.com>
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
Functions to set up Python's logging facility for Radicale's WSGI application.

Log messages are sent to the first available target of:

  - Error stream specified by the WSGI server in "wsgi.errors"
  - ``sys.stderr``

"""

import contextlib
import io
import logging
import os
import socket
import struct
import sys
import threading
import time
from typing import (Any, Callable, ClassVar, Dict, Iterator, Mapping, Optional,
                    Tuple, Union, cast)

from radicale import types

LOGGER_NAME: str = "radicale"
LOGGER_FORMATS: Mapping[str, str] = {
    "verbose": "[%(asctime)s] [%(ident)s] [%(levelname)s] %(message)s",
    "journal": "[%(ident)s] [%(levelname)s] %(message)s",
}
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
        ident = ("%d" % record.process if record.process is not None
                 else record.processName or "unknown")
        tid = None
        if record.thread is not None:
            if record.thread != threading.main_thread().ident:
                ident += "/%s" % (record.threadName or "unknown")
            if (sys.version_info >= (3, 8) and
                    record.thread == threading.get_ident()):
                tid = threading.get_native_id()
        record.ident = ident  # type:ignore[attr-defined]
        record.tid = tid  # type:ignore[attr-defined]
        return record


class ThreadedStreamHandler(logging.Handler):
    """Sends logging output to the stream registered for the current thread or
       ``sys.stderr`` when no stream was registered."""

    terminator: ClassVar[str] = "\n"

    _streams: Dict[int, types.ErrorStream]
    _journal_stream_id: Optional[Tuple[int, int]]
    _journal_socket: Optional[socket.socket]
    _journal_socket_failed: bool
    _formatters: Mapping[str, logging.Formatter]
    _formatter: Optional[logging.Formatter]

    def __init__(self, format_name: Optional[str] = None) -> None:
        super().__init__()
        self._streams = {}
        self._journal_stream_id = None
        with contextlib.suppress(TypeError, ValueError):
            dev, inode = os.environ.get("JOURNAL_STREAM", "").split(":", 1)
            self._journal_stream_id = (int(dev), int(inode))
        self._journal_socket = None
        self._journal_socket_failed = False
        self._formatters = {name: logging.Formatter(fmt, DATE_FORMAT)
                            for name, fmt in LOGGER_FORMATS.items()}
        self._formatter = (self._formatters[format_name]
                           if format_name is not None else None)

    def _get_formatter(self, default_format_name: str) -> logging.Formatter:
        return self._formatter or self._formatters[default_format_name]

    def _detect_journal(self, stream: types.ErrorStream) -> bool:
        if not self._journal_stream_id or not isinstance(stream, io.IOBase):
            return False
        try:
            stat = os.fstat(stream.fileno())
        except OSError:
            return False
        return self._journal_stream_id == (stat.st_dev, stat.st_ino)

    @staticmethod
    def _encode_journal(data: Mapping[str, Optional[Union[str, int]]]
                        ) -> bytes:
        msg = b""
        for key, value in data.items():
            if value is None:
                continue
            keyb = key.encode()
            valueb = str(value).encode()
            if b"\n" in valueb:
                msg += (keyb + b"\n" +
                        struct.pack("<Q", len(valueb)) + valueb + b"\n")
            else:
                msg += keyb + b"=" + valueb + b"\n"
        return msg

    def _try_emit_journal(self, record: logging.LogRecord) -> bool:
        if not self._journal_socket:
            # Try to connect to systemd journal socket
            if self._journal_socket_failed or not hasattr(socket, "AF_UNIX"):
                return False
            journal_socket = None
            try:
                journal_socket = socket.socket(
                    socket.AF_UNIX, socket.SOCK_DGRAM)
                journal_socket.connect("/run/systemd/journal/socket")
            except OSError as e:
                self._journal_socket_failed = True
                if journal_socket:
                    journal_socket.close()
                # Log after setting `_journal_socket_failed` to prevent loop!
                logger.error("Failed to connect to systemd journal: %s",
                             e, exc_info=True)
                return False
            self._journal_socket = journal_socket

        priority = {"DEBUG": 7,
                    "INFO": 6,
                    "WARNING": 4,
                    "ERROR": 3,
                    "CRITICAL": 2}.get(record.levelname, 4)
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%S.%%03dZ",
                                  time.gmtime(record.created)) % record.msecs
        data = {"PRIORITY": priority,
                "TID": cast(Optional[int], getattr(record, "tid", None)),
                "SYSLOG_IDENTIFIER": record.name,
                "SYSLOG_FACILITY": 1,
                "SYSLOG_PID": record.process,
                "SYSLOG_TIMESTAMP": timestamp,
                "CODE_FILE": record.pathname,
                "CODE_LINE": record.lineno,
                "CODE_FUNC": record.funcName,
                "MESSAGE": self._get_formatter("journal").format(record)}
        self._journal_socket.sendall(self._encode_journal(data))
        return True

    def emit(self, record: logging.LogRecord) -> None:
        try:
            stream = self._streams.get(threading.get_ident(), sys.stderr)
            if self._detect_journal(stream) and self._try_emit_journal(record):
                return
            msg = self._get_formatter("verbose").format(record)
            stream.write(msg + self.terminator)
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
    format_name = os.environ.get("RADICALE_LOG_FORMAT") or None
    sane_format_name = format_name if format_name in LOGGER_FORMATS else None
    handler = ThreadedStreamHandler(sane_format_name)
    logging.basicConfig(handlers=[handler])
    register_stream = handler.register_stream
    log_record_factory = IdentLogRecordFactory(logging.getLogRecordFactory())
    logging.setLogRecordFactory(log_record_factory)
    set_level(logging.INFO, True)
    if format_name != sane_format_name:
        logger.error("Invalid RADICALE_LOG_FORMAT: %r", format_name)


logger_display_backtrace_disabled: bool = False
logger_display_backtrace_enabled: bool = False


def set_level(level: Union[int, str], backtrace_on_debug: bool) -> None:
    """Set logging level for global logger."""
    global logger_display_backtrace_disabled
    global logger_display_backtrace_enabled
    if isinstance(level, str):
        level = getattr(logging, level.upper())
        assert isinstance(level, int)
    logger.setLevel(level)
    if level > logging.DEBUG:
        if logger_display_backtrace_disabled is False:
            logger.info("Logging of backtrace is disabled in this loglevel")
            logger_display_backtrace_disabled = True
        logger.addFilter(REMOVE_TRACEBACK_FILTER)
    else:
        if not backtrace_on_debug:
            if logger_display_backtrace_disabled is False:
                logger.debug("Logging of backtrace is disabled by option in this loglevel")
                logger_display_backtrace_disabled = True
            logger.addFilter(REMOVE_TRACEBACK_FILTER)
        else:
            if logger_display_backtrace_enabled is False:
                logger.debug("Logging of backtrace is enabled by option in this loglevel")
                logger_display_backtrace_enabled = True
            logger.removeFilter(REMOVE_TRACEBACK_FILTER)
