# This file is part of Radicale - CalDAV and CardDAV server
# Copyright © 2026 Peter Bieringer <pb@bieringer.de>
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

"""Outcome tests for logging conditions, levels, and the stream handler."""

import io
import logging
import os

import pytest

from radicale import log


class TestLog:
    @pytest.fixture(autouse=True)
    def preserve_logging(self):
        root = logging.getLogger()
        saved = {
            "level": log.logger.level,
            "filters": list(log.logger.filters),
            "factory": logging.getLogRecordFactory(),
            "disabled": log.logger_display_backtrace_disabled,
            "enabled": log.logger_display_backtrace_enabled,
            "handlers": list(root.handlers),
            "root_level": root.level,
            "register_stream": log.register_stream,
        }
        yield
        logging.setLogRecordFactory(saved["factory"])
        log.register_stream = saved["register_stream"]
        log.logger.setLevel(saved["level"])
        for filt in list(log.logger.filters):
            log.logger.removeFilter(filt)
        for filt in saved["filters"]:
            log.logger.addFilter(filt)
        log.logger_display_backtrace_disabled = saved["disabled"]
        log.logger_display_backtrace_enabled = saved["enabled"]
        for handler in list(root.handlers):
            if handler not in saved["handlers"]:
                root.removeHandler(handler)
        root.setLevel(saved["root_level"])

    @pytest.mark.parametrize(("condition", "value", "expected"), [
        ({}, {"login": "alice"}, False),
        ({"login": {"match": "equal", "value": "alice"}}, {"login": "alice"}, True),
        ({"login": {"match": "==", "value": "alice"}}, {"login": "bob"}, False),
        ({"login": {"match": "=", "value": "alice"}}, {"login": "alice"}, True),
        ({"path": {"match": "startswith", "value": "/cal"}}, {"path": "/cal/1"}, True),
        ({"path": {"match": "startswith", "value": "/cal"}}, {"path": "/other"}, False),
        ({"path": {"match": "endswith", "value": ".ics"}}, {"path": "/a.ics"}, True),
        ({"path": {"match": "endswith", "value": ".ics"}}, {"path": "/a.vcf"}, False),
        ({"useragent": {"match": "re", "value": r"Dav[0-9]+"}}, {"useragent": "Dav9"}, True),
        ({"useragent": {"match": "re", "value": r"^Other"}}, {"useragent": "Dav9"}, False),
        ({"status": {"match": "=", "value": "200"}}, {"status": 200}, True),
        ({"status": {"match": ">", "value": "400"}}, {"status": 200}, True),
        ({"status": {"match": ">", "value": "400"}}, {"status": 500}, False),
        ({"status": {"match": "<", "value": "400"}}, {"status": 500}, True),
        ({"status": {"match": "<", "value": "400"}}, {"status": 200}, False),
        ({"status": {"match": "<=", "value": "200"}}, {"status": 200}, True),
        # Comparisons are "configured value OP actual": 200 <= 100 is false.
        ({"status": {"match": "<=", "value": "200"}}, {"status": 100}, False),
        ({"status": {"match": ">=", "value": "200"}}, {"status": 200}, True),
        # 200 >= 500 is false, so the condition does not pass.
        ({"status": {"match": ">=", "value": "200"}}, {"status": 500}, False),
        ({"status": {"match": "!=", "value": "200"}}, {"status": 201}, True),
        ({"status": {"match": "<>", "value": "200"}}, {"status": 200}, False),
        ({"host": {"match": "=", "value": "192.0.2.10"}}, {"host": "192.0.2.10"}, True),
        ({"host": {"match": "!=", "value": "192.0.2.10"}}, {"host": "192.0.2.11"}, True),
        ({"host": {"match": "<>", "value": "192.0.2.10"}}, {"host": "192.0.2.10"}, False),
        ({"host": {"match": "included", "value": "192.0.2.0/24"}}, {"host": "192.0.2.10"}, True),
        ({"host": {"match": "incl", "value": "192.0.2.0/24"}}, {"host": "198.51.100.10"}, False),
        ({"host": {"match": "included", "value": "2001:db8::/32"}}, {"host": "2001:db8::5"}, True),
        ({"host": {"match": "included", "value": "192.0.2.0/24"}}, {"host": "2001:db8::5"}, False),
        ({"host": {"match": "included", "value": "192.0.2.0/24"}}, {"host": "unknown"}, False),
        ({"host": {"match": "excluded", "value": "192.0.2.0/24"}}, {"host": "198.51.100.10"}, True),
        ({"host": {"match": "excl", "value": "192.0.2.0/24"}}, {"host": "192.0.2.10"}, False),
        ({"host": {"match": "excluded", "value": "192.0.2.0/24"}}, {"host": "2001:db8::5"}, True),
        ({"host": {"match": "excluded", "value": "2001:db8::/32"}}, {"host": "2001:db8::5"}, False),
        ({"host": {"match": "excluded", "value": "192.0.2.0/24"}}, {"host": "unknown"}, True),
        ({"host": {"match": "startswith", "value": "192.0.2.0/24"}}, {"host": "192.0.2.10"}, True),
        (
            {
                "login": {"match": "equal", "value": "alice"},
                "status": {"match": "=", "value": "401"},
            },
            {"login": "alice", "status": 401},
            True,
        ),
        (
            {
                "login": {"match": "equal", "value": "alice"},
                "status": {"match": "=", "value": "401"},
            },
            {"login": "alice", "status": 200},
            False,
        ),
    ])
    def test_log_conditional(self, condition, value, expected):
        assert log.log_conditional("unit", condition, value) is expected

    def test_trace_filter_keeps_only_matching_trace_records(self, caplog):
        caplog.set_level(log.LOG_LEVEL_TRACE, logger="radicale")
        log.set_level("trace", True, "auth/")
        log.logger.trace("auth/visible")
        log.logger.trace("hidden-trace")
        log.logger.info("info-always")
        assert "auth/visible" in caplog.text
        assert "hidden-trace" not in caplog.text
        assert "info-always" in caplog.text
        assert any(isinstance(filt, log.PassTRACETOKENFilter) for filt in log.logger.filters)

    def test_set_level_info_disables_traceback_and_names_the_level(self, caplog):
        caplog.set_level(logging.INFO, logger="radicale")
        log.set_level("warning", True)
        assert log.logger.getEffectiveLevel() == logging.WARNING
        assert any(isinstance(filt, log.RemoveTracebackFilter) for filt in log.logger.filters)
        assert "Logging level set to: 'WARNING'" in caplog.text

    def test_set_level_debug_backtrace_switch(self, caplog):
        caplog.set_level(logging.DEBUG, logger="radicale")
        log.logger_display_backtrace_disabled = False
        log.logger_display_backtrace_enabled = False
        log.set_level(logging.DEBUG, False)
        assert any(isinstance(filt, log.RemoveTracebackFilter) for filt in log.logger.filters)
        assert "disabled by option" in caplog.text
        log.logger_display_backtrace_enabled = False
        log.set_level(logging.DEBUG, True)
        assert not any(isinstance(filt, log.RemoveTracebackFilter) for filt in log.logger.filters)
        assert "enabled by option" in caplog.text

    def test_remove_traceback_filter_clears_exc_info(self):
        record = logging.LogRecord("radicale", logging.ERROR, __file__, 1, "boom", (), (RuntimeError, RuntimeError("boom"), None))
        assert log.REMOVE_TRACEBACK_FILTER.filter(record) is True
        assert record.exc_info is None

    def test_pass_trace_filter_unit(self):
        filt = log.PassTRACETOKENFilter("auth/")
        trace = logging.LogRecord("radicale", log.LOG_LEVEL_TRACE, __file__, 1, "auth/ok", (), None)
        trace.levelno = log.LOG_LEVEL_TRACE
        assert filt.filter(trace) is True
        other = logging.LogRecord("radicale", log.LOG_LEVEL_TRACE, __file__, 1, "other", (), None)
        other.levelno = log.LOG_LEVEL_TRACE
        assert filt.filter(other) is False
        info = logging.LogRecord("radicale", logging.INFO, __file__, 1, "other", (), None)
        assert filt.filter(info) is True

    def test_ident_record_contains_pid(self):
        factory = log.IdentLogRecordFactory(logging.getLogRecordFactory())
        record = factory("radicale", logging.INFO, __file__, 1, "hello", (), None)
        assert record.ident.startswith(str(os.getpid()))
        assert record.tid is None or isinstance(record.tid, int)

    def test_threaded_handler_writes_registered_stream(self):
        handler = log.ThreadedStreamHandler("verbose")
        buf = io.StringIO()
        record = logging.LogRecord("radicale", logging.INFO, __file__, 1, "hello %s", ("world",), None)
        record.ident = "test-ident"
        with handler.register_stream(buf):
            handler.emit(record)
        text = buf.getvalue()
        assert "hello world" in text
        assert "INFO" in text
        assert "test-ident" in text
        assert text.endswith("\n")

    def test_encode_journal_escapes_multiline_and_skips_none(self):
        payload = log.ThreadedStreamHandler._encode_journal({
            "MESSAGE": "a\nb",
            "PRIORITY": 6,
            "EMPTY": None,
        })
        assert b"PRIORITY=6\n" in payload
        assert b"EMPTY" not in payload
        assert b"MESSAGE\n" in payload
        assert b"a\nb" in payload

    def test_journal_emit_reports_connect_result(self, tmp_path, caplog):
        caplog.set_level(logging.ERROR, logger="radicale")
        handler = log.ThreadedStreamHandler("journal")
        stream_path = tmp_path / "stderr"
        stream = stream_path.open("w+b")
        try:
            stat = os.fstat(stream.fileno())
            handler._journal_stream_id = (stat.st_dev, stat.st_ino)
            assert handler._detect_journal(stream) is True
            assert handler._detect_journal(io.StringIO()) is False
            record = logging.LogRecord("radicale", logging.ERROR, __file__, 1, "journal-me", (), None)
            record.ident = "1"
            sent = handler._try_emit_journal(record)
        finally:
            stream.close()
        if sent:
            assert handler._journal_socket is not None
        else:
            assert sent is False
            assert "Failed to connect to systemd journal" in caplog.text

    def test_setup_rejects_unknown_log_format(self, monkeypatch, caplog):
        caplog.set_level(logging.ERROR, logger="radicale")
        monkeypatch.setenv("RADICALE_LOG_FORMAT", "not-a-format")
        log.setup()
        assert "Invalid RADICALE_LOG_FORMAT: 'not-a-format'" in caplog.text

    def test_radicale_logger_custom_levels_emit(self, caplog):
        caplog.set_level(log.LOG_LEVEL_TRACE, logger="radicale")
        log.logger.setLevel(log.LOG_LEVEL_TRACE)
        log.logger.trace("trace-line")
        log.logger.notice("notice-line")
        log.logger.alert("alert-line")
        assert "trace-line" in caplog.text
        assert "notice-line" in caplog.text
        assert "alert-line" in caplog.text
