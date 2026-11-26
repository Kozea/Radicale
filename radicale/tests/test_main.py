# This file is part of Radicale - CalDAV and CardDAV server
# Copyright © 2026-2026 oliviasculley <olivia@sculley.dev>
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

"""Outcome tests for the ``python -m radicale`` entry point."""

import contextlib
import io
import logging
import signal
import socket
import sys

import pytest

import radicale.__main__ as main
from radicale import VERSION
from radicale import log as radicale_log


def _exit_signals():
    numbers = [signal.SIGTERM, signal.SIGINT]
    if sys.platform == "win32":
        numbers.append(signal.SIGBREAK)
    else:
        numbers.extend((signal.SIGHUP, signal.SIGQUIT))
    return numbers


@contextlib.contextmanager
def _closing_cli_socketpairs(monkeypatch):
    """Close the socketpair ``run`` opens after the replaced serve returns.

    The success path's signal handler has already closed one end. Closing
    that end again does not raise. The caller checks both ends.
    """
    opened = []
    real_socketpair = socket.socketpair

    def tracking_socketpair(*args, **kwargs):
        pair = real_socketpair(*args, **kwargs)
        opened.append(pair)
        return pair

    monkeypatch.setattr(socket, "socketpair", tracking_socketpair)
    try:
        yield opened
    finally:
        for left, right in opened:
            # close() is idempotent if the signal handler already closed one end.
            left.close()
            right.close()


def _run_cli(args):
    """Run ``radicale.__main__.run`` and return the process exit code.

    Signal handlers and ``sys.argv`` are restored. Logging is left to the
    caller's fixture so log text can be asserted first.
    """
    saved_handlers = {number: signal.getsignal(number) for number in _exit_signals()}
    saved_argv = sys.argv
    sys.argv = ["radicale", *args]
    try:
        try:
            main.run()
        except SystemExit as exc:
            return 0 if exc.code is None else exc.code
        return 0
    finally:
        sys.argv = saved_argv
        for number, handler in saved_handlers.items():
            signal.signal(number, handler)


class TestMain:
    @pytest.fixture(autouse=True)
    def preserve_logging(self):
        root = logging.getLogger()
        saved = {
            "level": radicale_log.logger.level,
            "filters": list(radicale_log.logger.filters),
            "factory": logging.getLogRecordFactory(),
            "disabled": radicale_log.logger_display_backtrace_disabled,
            "enabled": radicale_log.logger_display_backtrace_enabled,
            "handlers": list(root.handlers),
            "root_level": root.level,
            "register_stream": radicale_log.register_stream,
        }
        yield
        logging.setLogRecordFactory(saved["factory"])
        radicale_log.register_stream = saved["register_stream"]
        radicale_log.logger.setLevel(saved["level"])
        for filt in list(radicale_log.logger.filters):
            radicale_log.logger.removeFilter(filt)
        for filt in saved["filters"]:
            radicale_log.logger.addFilter(filt)
        radicale_log.logger_display_backtrace_disabled = saved["disabled"]
        radicale_log.logger_display_backtrace_enabled = saved["enabled"]
        for handler in list(root.handlers):
            if handler not in saved["handlers"]:
                root.removeHandler(handler)
        root.setLevel(saved["root_level"])

    def test_version_exits_zero_and_prints_version(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = _run_cli(["--version"])
        assert code == 0
        assert stdout.getvalue().strip() == VERSION

    def test_unrecognized_argument_exits_with_message(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = _run_cli(["--not-a-radicale-option"])
        assert code == 2
        assert "unrecognized arguments: --not-a-radicale-option" in stderr.getvalue()

    def test_invalid_config_value_exits_with_critical_log(self, tmp_path, caplog):
        caplog.set_level(logging.INFO)
        config_path = tmp_path / "bad.conf"
        config_path.write_text("[auth]\ndelay = -5\n", encoding="utf-8")
        code = _run_cli(["-C", str(config_path), "--verify-storage"])
        assert code == 1
        assert "Invalid configuration:" in caplog.text
        assert "delay" in caplog.text

    def test_missing_config_file_exits(self, tmp_path, caplog):
        caplog.set_level(logging.INFO)
        missing = tmp_path / "missing.conf"
        code = _run_cli(["-C", str(missing), "--verify-storage"])
        assert code == 1
        assert "Invalid configuration:" in caplog.text
        assert "Failed to load" in caplog.text
        # the path is logged with %r: backslashes are doubled on Windows
        assert "Failed to load config file %r" % str(missing) in caplog.text

    def test_verify_storage_empty_folder_exits_zero(self, tmp_path, caplog):
        caplog.set_level(logging.INFO)
        code = _run_cli([
            "--verify-storage",
            "--storage-filesystem-folder", str(tmp_path),
        ])
        assert code == 0
        assert "Verifying storage" in caplog.text
        assert "Storage verification failed" not in caplog.text

    def test_verify_storage_broken_item_exits(self, tmp_path, caplog):
        caplog.set_level(logging.INFO)
        collection = tmp_path / "collection-root" / "calendar"
        collection.mkdir(parents=True)
        (collection / ".Radicale.props").write_text(
            '{"tag": "VCALENDAR"}\n', encoding="utf-8")
        (collection / "broken.ics").write_text(
            "this is not a calendar\n", encoding="utf-8")
        code = _run_cli([
            "--verify-storage",
            "--no-storage-skip-broken-item",
            "--storage-filesystem-folder", str(tmp_path),
        ])
        assert code == 1
        # "Failed to load item" is the RuntimeError from a disabled skip.
        # The default skip path exits 1 as well, but never logs that text.
        # "Storage verification failed" means that error was counted.
        assert "Failed to load item" in caplog.text
        assert "Storage verification failed" in caplog.text

    def test_verify_storage_on_a_file_reports_the_exception(self, tmp_path, caplog):
        caplog.set_level(logging.INFO)
        folder = tmp_path / "not-a-directory"
        folder.write_text("x", encoding="utf-8")
        code = _run_cli([
            "--verify-storage",
            "--storage-filesystem-folder", str(folder),
        ])
        assert code == 1
        assert "An exception occurred during storage verification:" in caplog.text

    def test_verify_item_missing_file_reports_the_exception(self, tmp_path, caplog):
        caplog.set_level(logging.INFO)
        missing = tmp_path / "absent.ics"
        code = _run_cli(["--verify-item", str(missing)])
        assert code == 1
        assert "An exception occurred during item verification:" in caplog.text
        assert "absent.ics" in caplog.text

    def test_debug_flag_and_config_file_verify_storage(self, tmp_path, caplog):
        caplog.set_level(logging.DEBUG)
        storage = tmp_path / "collections"
        storage.mkdir()
        config_path = tmp_path / "config"
        config_path.write_text(
            "[storage]\nfilesystem_folder = %s\n" % storage, encoding="utf-8")
        code = _run_cli(["-D", "-C", str(config_path), "--verify-storage"])
        assert code == 0
        assert "Verifying storage" in caplog.text
        assert "Storage location: %r" % str(storage) in caplog.text

    def test_logging_level_rejected_when_unknown(self, caplog):
        caplog.set_level(logging.INFO)
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = _run_cli(["--logging-level", "loud"])
        assert code == 1
        assert "Invalid configuration:" in caplog.text
        assert "loud" in caplog.text

    def test_backend_options_and_headers_reach_configuration(self, tmp_path, monkeypatch):
        seen = {}

        def fake_serve(configuration, shutdown_socket):
            seen["auth_type"] = configuration.get("auth", "type")
            seen["custom_flag"] = configuration.get("auth", "custom_flag")
            seen["beta"] = configuration.get("auth", "beta")
            seen["gamma"] = configuration.get("auth", "gamma")
            seen["header"] = configuration.get("headers", "X-Trace")
            seen["folder"] = configuration.get("storage", "filesystem_folder")
            handler = signal.getsignal(signal.SIGTERM)
            handler(signal.SIGTERM, None)
            shutdown_socket.settimeout(1)
            seen["shutdown"] = shutdown_socket.recv(16)
            return None

        monkeypatch.setattr(main.server, "serve", fake_serve)
        with _closing_cli_socketpairs(monkeypatch) as opened:
            code = _run_cli([
                "--storage-filesystem-folder", str(tmp_path),
                "--auth-type", "radicale.tests.custom.auth",
                "--auth-custom-flag=yes",
                "--auth-beta", "two",
                "--auth-gamma",
                "--headers-X-Trace", "abc",
            ])
        assert code == 0
        assert len(opened) == 1
        for end in opened[0]:
            assert end.fileno() == -1
        assert seen["auth_type"] == "radicale.tests.custom.auth"
        assert seen["custom_flag"] == "yes"
        assert seen["beta"] == "two"
        assert seen["gamma"] == ""
        assert seen["header"] == "abc"
        assert seen["folder"] == str(tmp_path)
        assert seen["shutdown"] == b""

    def test_server_startup_failure_exits(self, tmp_path, monkeypatch, caplog):
        caplog.set_level(logging.INFO)

        def fake_serve(configuration, shutdown_socket):
            raise RuntimeError("refused to bind")

        monkeypatch.setattr(main.server, "serve", fake_serve)
        with _closing_cli_socketpairs(monkeypatch) as opened:
            code = _run_cli([
                "--storage-filesystem-folder", str(tmp_path),
                "--auth-type", "none",
            ])
        assert code == 1
        assert len(opened) == 1
        for end in opened[0]:
            assert end.fileno() == -1
        assert "An exception occurred during server startup: refused to bind" in caplog.text
