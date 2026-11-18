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

"""Outcome tests for request logging, profiling, and path checks."""

import cProfile
import datetime
import importlib
import logging
import os
import socket
import sys
import types
import wsgiref.util
from io import BytesIO

import radicale.app as app_module
from radicale import config as radicale_config
from radicale import pathutils
from radicale.log import logger
from radicale.tests import BaseTest

CALENDAR_MKCOL = """<?xml version="1.0" encoding="utf-8" ?>
<mkcol xmlns="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
  <set><prop><resourcetype><collection/><C:calendar/></resourcetype></prop></set>
</mkcol>"""

SUBSCRIBED_MKCOL = """<?xml version="1.0" encoding="utf-8" ?>
<mkcol xmlns="DAV:" xmlns:CS="http://calendarserver.org/ns/">
  <set><prop><resourcetype><collection/><CS:subscribed/></resourcetype></prop></set>
</mkcol>"""

PROPPATCH_NAME = """<?xml version="1.0" encoding="utf-8"?>
<D:propertyupdate xmlns:D="DAV:">
  <D:set><D:prop><D:displayname>%s</D:displayname></D:prop></D:set>
</D:propertyupdate>"""

PROPFIND_ONE = """<?xml version="1.0" encoding="utf-8"?>
<D:propfind xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav"
            xmlns:CS="http://calendarserver.org/ns/"
            xmlns:RADICALE="http://radicale.org/ns/">
  <D:prop>{0}</D:prop>
</D:propfind>"""

ACCESS_FORBIDDEN = "Access to the requested resource forbidden."
ACTION_REFUSED = "Action on the requested resource refused."
BAD_REQUEST = "Bad Request"
PRECONDITION = "Precondition failed."
NOT_FOUND = "The requested resource could not be found."
CONFLICT = "Conflict in the request."
METHOD_NOT_ALLOWED = "The method is not allowed on the requested resource."
TIMEOUT = "Connection timed out."
TOO_LARGE = "Request body too large."
REMOTE_DESTINATION = "Remote destination not supported."
INSUFFICIENT = "Insufficient Storage."
SERVER_ERROR = "A server error occurred.  Please contact the administrator."
LOGIN = "alice:secret"


def _event(uid="evt", summary="Event", start="20130901T160000Z",
           end="20130901T170000Z", extra=""):
    return (
        "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Test//EN\r\n"
        "BEGIN:VEVENT\r\nUID:%s\r\nDTSTAMP:20130101T000000Z\r\n"
        "DTSTART:%s\r\nDTEND:%s\r\nSUMMARY:%s\r\n%s"
        "END:VEVENT\r\nEND:VCALENDAR\r\n" % (uid, start, end, summary, extra))


def _vcard(uid="card", fn="Ada"):
    return (
        "BEGIN:VCARD\r\nVERSION:3.0\r\nUID:%s\r\nFN:%s\r\nEND:VCARD\r\n"
        % (uid, fn))


def _todo():
    return (
        "BEGIN:VTODO\r\nUID:todo-1\r\nDTSTAMP:20130101T000000Z\r\n"
        "SUMMARY:Task\r\nEND:VTODO\r\n")


def _set_rights(test, text, **extra):
    path = os.path.join(test.colpath, "rights")
    with open(path, "w") as handle:
        handle.write(text)
    config = {
        "auth": {"type": "none", "delay": "0"},
        "rights": {"type": "from_file", "file": path},
        "server": {"delay_on_error": "0"},
    }
    config.update(extra)
    test.configure(config)


def _grant(test):
    _set_rights(test, "[all]\nuser: .*\ncollection: .*\npermissions: RrWw\n")


class _Level:
    def __init__(self, level):
        self.level = level
        self.previous = None

    def __enter__(self):
        self.previous = logger.level
        logger.setLevel(self.level)
        return self

    def __exit__(self, *_args):
        logger.setLevel(self.previous)


class TimeoutStream:
    def read(self, size=-1):
        raise socket.timeout("timed out")


def _second_profiler_is_blocked():
    """True when a second ``cProfile`` cannot start while one is active."""
    holder = cProfile.Profile()
    holder.enable()
    try:
        nested = cProfile.Profile()
        try:
            nested.enable()
        except ValueError:
            return True
        nested.disable()
        return False
    finally:
        holder.disable()


def _release_method_profilers(application):
    """Drop method profilers before the interpreter shuts down.

    They are stored on the Application class. Finalizing them at process
    exit killed the 32-bit job with signal 11 after the suite had passed.
    """
    application._profiling_per_request_method = False
    profilers = application.profiler_per_request_method
    for profiler in list(profilers.values()):
        try:
            profiler.disable()
        except ValueError:
            pass
    profilers.clear()
    application.profiler_per_request_method_counter.clear()


class Hook:
    """Recording hook loaded as radicale.tests.test_cov_app."""

    events: list = []
    fail = False

    def __init__(self, configuration):
        self.configuration = configuration

    @property
    def enabled(self):
        return True

    def notify(self, notification_item):
        Hook.events.append(notification_item)
        if Hook.fail:
            raise RuntimeError("hook failed")


class TestCovApp(BaseTest):

    def setup_method(self):
        super().setup_method()
        _grant(self)
        Hook.events = []
        Hook.fail = False

    def _call(self, method, path, data=b"", content_length=None,
              content_type=None, **kwargs):
        environ = {key.upper(): value for key, value in kwargs.items()}
        wsgiref.util.setup_testing_defaults(environ)
        environ["REQUEST_METHOD"] = method
        environ["PATH_INFO"] = path
        if hasattr(data, "read"):
            environ["wsgi.input"] = data
        else:
            if isinstance(data, str):
                data = data.encode()
            environ["wsgi.input"] = BytesIO(data)
            if content_length is None:
                content_length = len(data)
        if content_length is not None:
            environ["CONTENT_LENGTH"] = str(content_length)
        if content_type:
            environ["CONTENT_TYPE"] = content_type
        status = {}

        def start_response(status_line, headers):
            status["code"] = int(status_line.split()[0])
            status["headers"] = dict(headers)

        answers = list(self.application(environ, start_response))
        body = answers[0].decode() if answers else ""
        return status["code"], status.get("headers", {}), body

    def test_temp_directory_writable_serves_root(self):
        previous = os.environ.get("TEMP")
        os.environ["TEMP"] = self.colpath
        try:
            _grant(self)
            status, _, body = self.request("GET", "/", check=None)
        finally:
            if previous is None:
                os.environ.pop("TEMP", None)
            else:
                os.environ["TEMP"] = previous
        assert status == 302
        assert body == "Redirected to /.web"

    def test_storage_without_unicode_forces_validation(self, monkeypatch):
        monkeypatch.setattr(pathutils, "path_supports_unicode", lambda _path: False)
        cases = (
            ("minimal", "minimal", "no-unicode", "no-unicode"),
            ("strict", "minimal", "strict", "no-unicode"),
            ("minimal", "strict", "no-unicode", "strict"),
            ("strict", "strict", "strict", "strict"),
        )
        for index, (user_mode, path_mode, user_forced, path_forced) in enumerate(cases):
            _set_rights(
                self, "[all]\nuser: .*\ncollection: .*\npermissions: RrWw\n",
                server={"validate_user_value": user_mode,
                        "validate_path_value": path_mode,
                        "delay_on_error": "0"})
            assert self.application._validate_user_value == user_forced
            assert self.application._validate_path_value == path_forced
            ascii_status, _, ascii_body = self.request(
                "MKCALENDAR", "/c%d.ics/" % index, check=None)
            assert ascii_status == 201, ascii_body
            latin = "/c%d\u00e9.ics/" % index
            wide = "/c%d\u0100.ics/" % index
            latin_status, _, latin_body = self.request(
                "MKCALENDAR", latin, check=None)
            wide_status, _, wide_body = self.request(
                "MKCALENDAR", wide, check=None)
            if path_forced == "strict":
                assert latin_status == 400 and latin_body == BAD_REQUEST
                assert wide_status == 400 and wide_body == BAD_REQUEST
            else:
                assert latin_status == 201, latin_body
                assert wide_status == 400 and wide_body == BAD_REQUEST
                status, body = self.get(latin)
                assert status == 200 and "BEGIN:VCALENDAR" in body

    def test_path_character_classes_and_boundaries(self):
        _set_rights(
            self, "[all]\nuser: .*\ncollection: .*\npermissions: RrWw\n",
            server={"validate_path_value": "none", "delay_on_error": "0"})
        self.application._storage._supports_trailing_whitespace = False
        self.application._storage._supports_problematic_chars = False
        status, _, body = self.request("MKCALENDAR", "/trail ", check=None)
        assert status == 400 and body == BAD_REQUEST
        status, _, body = self.request("MKCALENDAR", "/star*.ics/", check=None)
        assert status == 400 and body == BAD_REQUEST
        status, _, body = self.request("MKCALENDAR", "/plain.ics/", check=None)
        assert status == 201 and "BEGIN:VCALENDAR" in self.get("/plain.ics/")[1]
        # VFAT rejects the name at rename time. Only claim the allow outcome
        # where a probe shows the filesystem keeps the character.
        if pathutils.path_supports_trailing_whitespace(self.colpath):
            self.application._storage._supports_trailing_whitespace = True
            status, _, body = self.request("MKCALENDAR", "/kept ", check=None)
            assert status == 201, body
            assert "BEGIN:VCALENDAR" in self.get("/kept ")[1]
        if pathutils.path_supports_problematic_chars(self.colpath):
            self.application._storage._supports_problematic_chars = True
            status, _, body = self.request(
                "MKCALENDAR", "/star2*.ics/", check=None)
            assert status == 201, body
            assert "BEGIN:VCALENDAR" in self.get("/star2*.ics/")[1]
        with _Level(logging.INFO):
            status, _, body = self.request(
                "MKCALENDAR", "/a\u200bb.ics/", check=None)
        assert status == 400 and body == BAD_REQUEST

        _set_rights(
            self, "[all]\nuser: .*\ncollection: .*\npermissions: RrWw\n",
            server={"validate_path_value": "unicode-none", "delay_on_error": "0"})
        self.application._validate_path_value = "no-unicode"
        self.application._storage._supports_trailing_whitespace = True
        status, _, body = self.request("MKCALENDAR", "/\u00ff.ics/", check=None)
        assert status == 201, body
        status, _, body = self.request("MKCALENDAR", "/\u0100.ics/", check=None)
        assert status == 400 and body == BAD_REQUEST

        _set_rights(
            self, "[all]\nuser: .*\ncollection: .*\npermissions: RrWw\n",
            server={"validate_path_value": "unicode-letter",
                    "delay_on_error": "0"})
        with _Level(logging.INFO):
            status, _, body = self.request("MKCALENDAR", "/bang!.ics/", check=None)
            assert status == 400 and body == BAD_REQUEST
            status, _, body = self.request(
                "MKCALENDAR", "/lettr\u00e9.ics/", check=None)
            assert status == 201, body
            status, _, body = self.request("MKCALENDAR", "/digit1.ics/", check=None)
            assert status == 201, body

    def test_two_at_signs_reject_login_one_at_sign_is_inside(self):
        status, _, body = self.request(
            "GET", "/", login="a@b@c:secret", check=None)
        assert status == 401 and ACCESS_FORBIDDEN in body
        status, _, body = self.request(
            "MKCALENDAR", "/a@b/cal.ics/", login="a@b:secret", check=None)
        assert status == 201, body
        assert "BEGIN:VCALENDAR" in self.get("/a@b/cal.ics/")[1]

    def test_put_on_root_reads_parent_permissions_of_root(self):
        status, _, body = self.request("PUT", "/", _event(), check=None)
        assert status == 201 and body == ""
        status, _, answer = self.request(
            "PROPFIND", "/", PROPFIND_ONE.format("<D:getetag/>"),
            HTTP_DEPTH="1", check=None)
        assert status == 207 and "evt" in answer

    def test_cookie_and_remote_host_are_logged_with_the_response(self, caplog):
        self.configure({"logging": {"request_header_on_debug": "True"}})
        caplog.set_level(logging.DEBUG)
        status, _, body = self.request(
            "GET", "/", HTTP_COOKIE="session=secret-cookie",
            REMOTE_HOST="client.example", REMOTE_ADDR="203.0.113.9",
            check=None)
        assert status == 302 and body == "Redirected to /.web"
        text = "\n".join(caplog.messages)
        assert "**masked**" in text
        assert "secret-cookie" not in text
        assert "'client.example'" in text

    def test_reverse_proxy_prefix_warning_depends_on_auth(self, caplog):
        self.configure({
            "auth": {"type": "remote_user", "delay": "0"},
            "web": {"type": "internal"},
            "server": {"script_name": "/radicale", "delay_on_error": "0"},
        })
        caplog.set_level(logging.DEBUG)
        status, headers, body = self.request(
            "GET", "/", HTTP_X_FORWARDED_FOR="203.0.113.5",
            REMOTE_USER="alice", check=None)
        assert status == 302
        assert body == "Redirected to /radicale/.web"
        assert headers["Location"] == "/radicale/.web"
        assert "may cause authentication issues" in "\n".join(caplog.messages)

        caplog.clear()
        _grant(self)
        self.configure({
            "web": {"type": "internal"},
            "server": {"script_name": "/radicale", "delay_on_error": "0"},
        })
        status, _, body = self.request(
            "GET", "/calendar.ics/", HTTP_X_FORWARDED_FOR="203.0.113.5",
            check=None)
        assert status == 404 and body == NOT_FOUND
        assert "may cause authentication issues" not in "\n".join(caplog.messages)

    def test_unknown_method_is_rejected(self):
        status, _, body = self.request("FOO", "/calendar.ics/", check=None)
        assert status == 405 and body == METHOD_NOT_ALLOWED

    def test_profiling_modes_and_concurrent_profiler(self, caplog, monkeypatch):
        caplog.set_level(logging.DEBUG)
        saved = radicale_config.PROFILING
        radicale_config.PROFILING = ()
        try:
            self.application = app_module.Application(self.configuration)
        finally:
            radicale_config.PROFILING = saved
        status, _, body = self.request("GET", "/", check=None)
        assert status == 302 and body == "Redirected to /.web"
        assert "profiling:" not in "\n".join(caplog.messages)

        caplog.clear()
        self.configure({
            "logging": {
                "profiling": "per_request",
                "profiling_per_request_min_duration": "0",
                "profiling_per_request_header": "True",
                "profiling_per_request_xml": "True",
                "profiling_top_x_functions": "1",
            }})
        self.mkcalendar("/calendar.ics/")
        caplog.clear()
        status, _, body = self.request("GET", "/", check=None)
        assert status == 302 and body == "Redirected to /.web"
        text = "\n".join(caplog.messages)
        assert "**Profiling statistics BEGIN**" in text
        assert "Profiling request header BEGIN" in text
        assert "Profiling request content (XML) BEGIN" not in text

        caplog.clear()
        status, _, answer = self.request(
            "PROPFIND", "/calendar.ics/",
            PROPFIND_ONE.format("<D:displayname/>"), HTTP_DEPTH="0",
            check=None)
        assert status == 207 and "multistatus" in answer
        text = "\n".join(caplog.messages)
        assert "Profiling request content (XML) BEGIN" in text
        assert "<D:displayname" in text or "displayname" in text

        self.configure({
            "logging": {
                "profiling": "per_request",
                "profiling_per_request_min_duration": "0",
                "profiling_per_request_header": "False",
                "profiling_per_request_xml": "True",
            }})
        caplog.clear()
        status, _, answer = self.request(
            "PROPFIND", "/calendar.ics/",
            PROPFIND_ONE.format("<D:displayname/>"), HTTP_DEPTH="0",
            check=None)
        assert status == 207 and "displayname" in answer
        text = "\n".join(caplog.messages)
        assert "**Profiling statistics BEGIN**" in text
        assert "Profiling request header BEGIN" not in text
        assert "Profiling request content (XML) BEGIN" in text

        self.configure({
            "logging": {
                "profiling": "per_request",
                "profiling_per_request_min_duration": "0",
                "profiling_per_request_header": "True",
                "profiling_per_request_xml": "False",
            }})
        caplog.clear()
        status, _, body = self.request("GET", "/calendar.ics/", check=None)
        assert status == 200 and "BEGIN:VCALENDAR" in body
        text = "\n".join(caplog.messages)
        assert "**Profiling statistics BEGIN**" in text
        assert "Profiling request header BEGIN" in text
        assert "Profiling request content (XML) BEGIN" not in text

        self.configure({
            "logging": {
                "profiling": "per_request",
                "profiling_per_request_min_duration": "99999",
                "profiling_per_request_header": "False",
                "profiling_per_request_xml": "False",
            }})
        caplog.clear()
        status, _, body = self.request("GET", "/calendar.ics/", check=None)
        assert status == 200 and "BEGIN:VCALENDAR" in body
        text = "\n".join(caplog.messages)
        assert "suppressed because duration below minimum" in text
        assert "**Profiling statistics BEGIN**" not in text

        self.configure({
            "logging": {
                "profiling": "per_request",
                "profiling_per_request_min_duration": "0",
            }})
        # CPython 3.12+ refuses a second cProfile while one is active, which
        # is the concurrent-request path. Earlier versions allow it and log
        # the statistics instead. Each interpreter has one outcome.
        blocked = _second_profiler_is_blocked()
        outer = cProfile.Profile()
        outer.enable()
        try:
            caplog.clear()
            status, _, body = self.request("GET", "/calendar.ics/", check=None)
        finally:
            outer.disable()
        assert status == 200 and "BEGIN:VCALENDAR" in body
        text = "\n".join(caplog.messages)
        if blocked:
            assert "concurrent running profiling request" in text
            assert "**Profiling statistics BEGIN**" not in text
        else:
            assert "**Profiling statistics BEGIN**" in text
            assert "concurrent running profiling request" not in text

        self.configure({
            "logging": {
                "profiling": "per_request_method",
                "profiling_per_request_method_interval": "1",
                "profiling_top_x_functions": "1",
            }})
        try:
            self.application.profiler_per_request_method_logtime = (
                datetime.datetime.now() - datetime.timedelta(seconds=30))
            caplog.clear()
            status, _, body = self.request("GET", "/calendar.ics/", check=None)
            assert status == 200 and "BEGIN:VCALENDAR" in body
            self.application._profiler_per_request_method(False)
            self.application._profiler_per_request_method(True)
            self.application.__del__()
            text = "\n".join(caplog.messages)
            assert "Profiling data per request method GET" in text
            assert "no request seen so far" in text
            assert "**Profiling statistics BEGIN**" in text

            outer = cProfile.Profile()
            outer.enable()
            try:
                caplog.clear()
                status, headers, body = self.request(
                    "OPTIONS", "/calendar.ics/", check=None)
            finally:
                outer.disable()
            assert status == 200 and body == ""
            assert headers.get("DAV")
        finally:
            _release_method_profilers(self.application)

    def test_random_auth_and_response_delays(self, caplog):
        saved = os.environ.pop("PYTEST_VERSION", None)
        try:
            _set_rights(
                self, "[only]\nuser: .*\ncollection: allowed\npermissions: R\n")
            self.configure({"auth": {"type": "denyall", "delay": "0.001"}})
            caplog.set_level(logging.DEBUG)
            status, headers, body = self.request(
                "GET", "/allowed/", login="nobody:nope", check=None)
            assert status == 401 and ACCESS_FORBIDDEN in body
            assert "WWW-Authenticate" in headers
            assert "sleeping random" in "\n".join(caplog.messages)
            caplog.clear()
            status, _, body = self.request("GET", "/allowed/", check=None)
            assert status == 404 and body == NOT_FOUND
            assert "Response random delay" not in "\n".join(caplog.messages)
            caplog.clear()
            status, _, body = self.request("GET", "/secret/", check=None)
            assert status == 401 and ACCESS_FORBIDDEN in body
            assert "Response random delay" in "\n".join(caplog.messages)
            caplog.clear()
            with _Level(logging.ERROR):
                status, _, body = self.request("GET", "/secret/", check=None)
            assert status == 401 and ACCESS_FORBIDDEN in body
            assert "Response random delay" not in "\n".join(caplog.messages)
        finally:
            if saved is not None:
                os.environ["PYTEST_VERSION"] = saved

    def test_non_xml_and_xml_log_matrix(self, caplog):
        self.mkcalendar("/calendar.ics/")
        self.put("/calendar.ics/event.ics", _event())
        caplog.set_level(logging.DEBUG)
        skipped = '{"method": {"match": "equal", "value": "PUT"}}'
        matched = '{"method": {"match": "equal", "value": "GET"}}'
        self.configure({"logging": {
            "response_content_on_debug": "False",
            "response_header_on_debug": "False",
            "request_content_on_debug": "False",
            "response_content_on_notice_condition": "{}",
            "response_header_on_notice_condition": "{}",
            "request_content_on_notice_condition": "{}",
        }})
        status, body = self.get("/calendar.ics/event.ics")
        assert status == 200 and "UID:evt" in body
        text = "\n".join(caplog.messages)
        assert "suppressed by config/option [logging] response_content_on_debug" in text

        self.configure({"logging": {
            "response_content_on_debug": "False",
            "response_content_on_notice_condition": skipped,
            "request_content_on_debug": "False",
            "request_content_on_notice_condition": skipped,
            "response_header_on_debug": "False",
            "response_header_on_notice_condition": skipped,
        }})
        caplog.clear()
        status, _, answer = self.request(
            "PROPFIND", "/calendar.ics/",
            PROPFIND_ONE.format("<D:displayname/>"), HTTP_DEPTH="0", check=None)
        assert status == 207 and "calendar.ics" in answer
        text = "\n".join(caplog.messages)
        assert "Request content (XML, log condition skipped): suppressed" in text
        assert "Response content (XML, log condition skipped): suppressed" in text

        self.configure({"logging": {
            "response_content_on_debug": "True",
            "response_header_on_debug": "True",
        }})
        caplog.clear()
        with _Level(logging.INFO):
            status, body = self.get("/calendar.ics/event.ics")
        assert status == 200 and "UID:evt" in body
        assert "Response content (nonXML)" not in "\n".join(caplog.messages)

        self.configure({"logging": {
            "response_content_on_debug": "False",
            "response_content_on_notice_condition": matched,
            "response_header_on_debug": "False",
            "response_header_on_notice_condition": matched,
        }})
        caplog.clear()
        with _Level(logging.ERROR):
            status, body = self.get("/calendar.ics/event.ics")
        assert status == 200 and "UID:evt" in body
        assert "log condition passed" not in "\n".join(caplog.messages)

    def test_permission_error_and_generic_storage_error(self, monkeypatch, caplog):
        caplog.set_level(logging.DEBUG)

        def _lock_permission(*_args, **_kwargs):
            raise PermissionError("storage locked down")

        monkeypatch.setattr(self.application._storage, "acquire_lock", _lock_permission)
        status, _, body = self.request("GET", "/calendar.ics/", check=None)
        assert status == 500 and body == SERVER_ERROR
        assert "PermissionError: storage locked down" in "\n".join(caplog.messages)

        def _lock_runtime(*_args, **_kwargs):
            raise RuntimeError("storage exploded")

        monkeypatch.setattr(self.application._storage, "acquire_lock", _lock_runtime)
        caplog.clear()
        status, _, body = self.request("GET", "/calendar.ics/", check=None)
        assert status == 500 and body == SERVER_ERROR
        assert "Exception: storage exploded" in "\n".join(caplog.messages)

    def test_token_and_user_denial_messages(self, caplog):
        _set_rights(self, "[cal]\nuser: .*\ncollection: calendar\\.ics\npermissions: RrWw\n")
        caplog.set_level(logging.DEBUG)
        status, _, body = self.request("GET", "/.token/secret", check=None)
        assert status == 403 and body == ACCESS_FORBIDDEN
        assert "Access to '/.token/secret' denied" in "\n".join(caplog.messages)
        assert "anonymous user" not in "\n".join(caplog.messages)
        caplog.clear()
        status, _, body = self.request(
            "GET", "/secret/", login="alice:secret", check=None)
        assert status == 403 and body == ACCESS_FORBIDDEN
        assert "denied for 'alice'" in "\n".join(caplog.messages)

    def test_from_auth_groups_attribute_error_still_succeeds(self, monkeypatch, caplog):
        caplog.set_level(logging.DEBUG)
        real_get = self.application.configuration.get

        def fake_get(section, option, *args, **kwargs):
            if section == "group" and option == "type":
                return "from_auth"
            if section == "auth" and option == "type":
                return "ldap"
            return real_get(section, option, *args, **kwargs)

        class BadGroups:
            def __iter__(self):
                raise AttributeError("groups have no join")

        def fake_login(_login, _password, _context):
            return ("alice", BadGroups(), "ldap")

        monkeypatch.setattr(self.application.configuration, "get", fake_get)
        monkeypatch.setattr(self.application._auth, "login", fake_login)
        status, _, body = self.request("GET", "/", login="alice:secret", check=None)
        assert status == 302 and body == "Redirected to /.web"
        assert "Exception:" not in "\n".join(caplog.messages)

        def good_login(_login, _password, _context):
            return ("alice", {"staff"}, "ldap")

        monkeypatch.setattr(self.application._auth, "login", good_login)
        caplog.clear()
        status, _, body = self.request("GET", "/", login="alice:secret", check=None)
        assert status == 302 and body == "Redirected to /.web"
        assert "staff" in "\n".join(caplog.messages)

        def other_auth(section, option, *args, **kwargs):
            if section == "group" and option == "type":
                return "from_auth"
            if section == "auth" and option == "type":
                return "htpasswd"
            return real_get(section, option, *args, **kwargs)

        monkeypatch.setattr(self.application.configuration, "get", other_auth)
        caplog.clear()
        status, _, body = self.request("GET", "/", login="alice:secret", check=None)
        assert status == 302 and body == "Redirected to /.web"
        assert "Groups received" not in "\n".join(caplog.messages)

    def test_zstd_import_error_still_serves(self):
        saved_compression = sys.modules.get("compression")
        saved_zstd = sys.modules.get("compression.zstd")
        sys.modules["compression"] = types.ModuleType("compression")
        sys.modules["compression.zstd"] = None
        try:
            importlib.reload(app_module)
            assert app_module.zstd is None
            source = open(app_module.__file__, encoding="utf-8").read()
            probed = {}
            exec(compile(source, app_module.__file__, "exec"), probed)
            assert probed["zstd"] is None
            self.application = app_module.Application(self.configuration)
            status, _, body = self.request("GET", "/", check=None)
            assert status == 302 and body == "Redirected to /.web"
        finally:
            if saved_compression is None:
                sys.modules.pop("compression", None)
            else:
                sys.modules["compression"] = saved_compression
            if saved_zstd is None:
                sys.modules.pop("compression.zstd", None)
            else:
                sys.modules["compression.zstd"] = saved_zstd
            importlib.reload(app_module)

    def test_log_guards_when_the_level_is_above_the_message(self, caplog):
        self.mkcalendar("/calendar.ics/")
        self.put("/calendar.ics/event.ics", _event(summary="Kept"))
        skipped = '{"method": {"match": "equal", "value": "PUT"}}'
        matched = '{"method": {"match": "equal", "value": "GET"}}'
        prop_matched = '{"method": {"match": "equal", "value": "PROPFIND"}}'
        propfind = PROPFIND_ONE.format("<D:displayname/>")

        self.configure({"logging": {"request_header_on_debug": "True"}})
        caplog.set_level(logging.DEBUG)
        caplog.clear()
        with _Level(logging.INFO):
            status, _, body = self.request("GET", "/", check=None)
        assert status == 302 and body == "Redirected to /.web"
        assert "Request header:\n" not in "\n".join(caplog.messages)

        self.configure({"logging": {
            "request_header_on_debug": "False",
            "request_header_on_notice_condition": matched,
        }})
        caplog.clear()
        with _Level(logging.ERROR):
            status, _, body = self.request("GET", "/", check=None)
        assert status == 302 and body == "Redirected to /.web"
        assert "Request header (log condition passed)" not in "\n".join(caplog.messages)

        self.configure({"logging": {
            "request_header_on_debug": "False",
            "request_header_on_notice_condition": "{}",
            "response_content_on_debug": "False",
            "response_content_on_notice_condition": skipped,
        }})
        caplog.clear()
        with _Level(logging.INFO):
            status, body = self.get("/calendar.ics/event.ics")
        assert status == 200 and "Kept" in body
        assert "log condition passed" not in "\n".join(caplog.messages)

        self.configure({"logging": {"request_content_on_debug": "True"}})
        caplog.clear()
        with _Level(logging.INFO):
            status, _, answer = self.request(
                "PROPFIND", "/calendar.ics/", propfind, HTTP_DEPTH="0", check=None)
        assert status == 207 and "calendar.ics" in answer
        assert "Request content (XML):" not in "\n".join(caplog.messages)

        self.configure({"logging": {
            "request_header_on_notice_condition": "{}",
            "request_content_on_debug": "False",
            "request_content_on_notice_condition": prop_matched,
        }})
        caplog.clear()
        with _Level(logging.ERROR):
            status, _, answer = self.request(
                "PROPFIND", "/calendar.ics/", propfind, HTTP_DEPTH="0", check=None)
        assert status == 207 and "calendar.ics" in answer
        assert "Request content (XML, log condition passed)" not in "\n".join(caplog.messages)

        self.configure({"logging": {
            "request_content_on_debug": "False",
            "request_content_on_notice_condition": skipped,
        }})
        caplog.clear()
        with _Level(logging.INFO):
            status, _, answer = self.request(
                "PROPFIND", "/calendar.ics/", propfind, HTTP_DEPTH="0", check=None)
        assert status == 207 and "calendar.ics" in answer
        assert "log condition skipped" not in "\n".join(caplog.messages)

        self.configure({"logging": {"response_content_on_debug": "True"}})
        caplog.clear()
        with _Level(logging.INFO):
            status, _, answer = self.request(
                "PROPFIND", "/calendar.ics/", propfind, HTTP_DEPTH="0", check=None)
        assert status == 207 and "calendar.ics" in answer
        assert "Response content (XML):" not in "\n".join(caplog.messages)

        self.configure({"logging": {
            "request_header_on_notice_condition": "{}",
            "request_content_on_notice_condition": "{}",
            "response_content_on_debug": "False",
            "response_content_on_notice_condition": prop_matched,
        }})
        caplog.clear()
        with _Level(logging.ERROR):
            status, _, answer = self.request(
                "PROPFIND", "/calendar.ics/", propfind, HTTP_DEPTH="0", check=None)
        assert status == 207 and "calendar.ics" in answer
        assert "Response content (XML, log condition passed)" not in "\n".join(caplog.messages)

        self.configure({"logging": {
            "response_content_on_debug": "False",
            "response_content_on_notice_condition": skipped,
        }})
        caplog.clear()
        with _Level(logging.INFO):
            status, _, answer = self.request(
                "PROPFIND", "/calendar.ics/", propfind, HTTP_DEPTH="0", check=None)
        assert status == 207 and "calendar.ics" in answer
        assert "log condition skipped" not in "\n".join(caplog.messages)

        saved = os.environ.get("PYTEST_VERSION")
        try:
            os.environ["PYTEST_VERSION"] = "1"
            self.configure({"auth": {"type": "denyall", "delay": "0.001"}})
            caplog.clear()
            with _Level(logging.ERROR):
                status, _, body = self.request(
                    "GET", "/", login="nobody:nope", check=None)
            assert status == 401 and ACCESS_FORBIDDEN in body
            assert "sleeping fixed" not in "\n".join(caplog.messages)
            os.environ.pop("PYTEST_VERSION", None)
            caplog.clear()
            with _Level(logging.ERROR):
                status, _, body = self.request(
                    "GET", "/", login="nobody:nope", check=None)
            assert status == 401 and ACCESS_FORBIDDEN in body
            assert "sleeping random" not in "\n".join(caplog.messages)
        finally:
            if saved is None:
                os.environ.pop("PYTEST_VERSION", None)
            else:
                os.environ["PYTEST_VERSION"] = saved

    def test_content_length_principal_and_groups(self, monkeypatch, caplog):
        event = _event(summary="Sized")
        exact = len(event.encode())
        self.configure({
            "server": {"_internal_server": "True",
                       "max_content_length": str(exact * 2),
                       "delay_on_error": "0"},
        })
        status, _, body = self.request(
            "PUT", "/calendar.ics/", event, check=None)
        assert status == 201 and body == ""
        assert "Sized" in self.get("/calendar.ics/")[1]
        self.configure({
            "server": {"_internal_server": "True",
                       "max_content_length": str(exact - 1),
                       "delay_on_error": "0"},
        })
        status, _, body = self.request(
            "PUT", "/over.ics/", event, check=None)
        assert status == 413 and body == TOO_LARGE
        assert self.get("/over.ics/", check=404)[0] == 404

        _set_rights(self, "[only]\nuser: alice\ncollection: secret\npermissions: R\n")
        caplog.set_level(logging.WARNING)
        status, _, body = self.request(
            "GET", "/secret/", login=LOGIN, check=None)
        assert status == 404 and body == NOT_FOUND
        assert "denied by rights backend" in "\n".join(caplog.messages)

        _grant(self)
        self.configure({
            "auth": {"type": "none", "delay": "0"},
            "storage": {"predefined_collections":
                        '{"cal.ics/": {"tag": "VCALENDAR"}}'},
            "server": {"delay_on_error": "0"},
        })
        real = self.application._storage.create_collection

        def skip_principal(href, *args, **kwargs):
            if href.strip("/") == "alice":
                return None, None, None
            return real(href, *args, **kwargs)

        monkeypatch.setattr(
            self.application._storage, "create_collection", skip_principal)
        caplog.clear()
        status, _, body = self.request("GET", "/", login=LOGIN, check=None)
        assert status == 302 and body == "Redirected to /.web"
        assert self.get("/alice/cal.ics/", login=LOGIN, check=404)[0] == 404
        monkeypatch.undo()

        def fail_principal(href, *args, **kwargs):
            if href.strip("/") == "cara":
                raise ValueError("principal rejected")
            if href.strip("/") == "dave":
                raise OSError("principal disk")
            if "cal.ics" in href.strip("/"):
                raise ValueError("predefined rejected")
            return real(href, *args, **kwargs)

        monkeypatch.setattr(
            self.application._storage, "create_collection", fail_principal)
        status, _, body = self.request(
            "GET", "/", login="cara:secret", check=None)
        assert status == 500 and body == SERVER_ERROR
        status, _, body = self.request(
            "GET", "/", login="dave:secret", check=None)
        assert status == 500 and body == SERVER_ERROR
        caplog.clear()
        status, _, body = self.request(
            "GET", "/", login="erin:secret", check=None)
        assert status == 302 and body == "Redirected to /.web"
        assert "Failed to create predefined collection" in "\n".join(caplog.messages)
        assert self.get("/erin/cal.ics/", login="erin:secret", check=404)[0] == 404
