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

"""Outcome tests for radicale.app branches the rest of the suite misses."""

import ast
import cProfile
import csv
import datetime
import errno
import importlib
import json
import logging
import os
import socket
import sys
import types
import wsgiref.util
from io import BytesIO

import pytest

import radicale.app as app_module
import radicale.item as radicale_item
from radicale import config as radicale_config
from radicale import pathutils, xmlutils
from radicale.log import logger
from radicale.storage.multifilesystem import Collection
from radicale.tests import BaseTest
from radicale.tests.helpers import get_file_content

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
        outer = cProfile.Profile()
        outer.enable()
        try:
            caplog.clear()
            status, _, body = self.request("GET", "/calendar.ics/", check=None)
        finally:
            outer.disable()
        assert status == 200 and "BEGIN:VCALENDAR" in body
        assert "concurrent running profiling request" in "\n".join(caplog.messages)

        self.configure({
            "logging": {
                "profiling": "per_request_method",
                "profiling_per_request_method_interval": "1",
                "profiling_top_x_functions": "1",
            }})
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

    def test_post_sharing_prefix_and_other_paths(self):
        status, _, body = self.request("POST", "/.sharing", check=None)
        assert status == 404 and body == NOT_FOUND
        status, _, body = self.request("POST", "/.sharing/", check=None)
        assert status == 404 and body == NOT_FOUND
        status, _, body = self.request("POST", "/calendar.ics/", check=None)
        assert status == 405 and body == METHOD_NOT_ALLOWED

    def test_delete_permission_etag_and_hook_loop(self):
        self.mkcalendar("/calendar.ics/")
        self.put("/calendar.ics/event.ics", _event(summary="Keep"))
        status, _, body = self.request(
            "DELETE", "/calendar.ics/event.ics", HTTP_IF_MATCH='"nope"',
            check=None)
        assert status == 412 and body == PRECONDITION
        assert "Keep" in self.get("/calendar.ics/event.ics")[1]

        _set_rights(self, """\
[cal]
user: .*
collection: calendar\\.ics
permissions: W
[rest]
user: .*
collection: .*
permissions: R
""")
        status, _, body = self.request(
            "DELETE", "/calendar.ics/", login=LOGIN, check=None)
        assert status == 403 and body == ACCESS_FORBIDDEN
        _grant(self)
        assert "BEGIN:VCALENDAR" in self.get("/calendar.ics/")[1]

        self.configure({"hook": {"type": "radicale.tests.test_cov_app"}})
        self.mkcalendar("/empty.ics/")
        status, _, body = self.request("DELETE", "/empty.ics/", check=None)
        assert status == 200 and "multistatus" in body
        assert self.get("/empty.ics/", check=404)[0] == 404
        assert Hook.events == []

        self.mkcalendar("/full.ics/")
        self.put("/full.ics/event.ics", _event(uid="gone", summary="Gone"))
        Hook.events.clear()
        Hook.fail = True
        status, _, body = self.request("DELETE", "/full.ics/", check=None)
        assert status == 500 and body == SERVER_ERROR
        assert self.get("/full.ics/", check=404)[0] == 404
        assert [event.type for event in Hook.events] == ["delete"]

    def test_get_filenames_freebusy_and_limited_item(self, caplog):
        caplog.set_level(logging.DEBUG)
        self.mkcol("/sub.ics/", SUBSCRIBED_MKCOL)
        status, headers, body = self.request("GET", "/sub.ics/", check=None)
        assert status == 200
        assert "BEGIN:VCALENDAR" in body or body == "" or "VCALENDAR" in body
        disposition = headers.get("Content-Disposition", "")
        assert "sub.ics" in disposition
        assert disposition.endswith("sub.ics") or "sub.ics" in disposition

        self.mkcalendar("/calendar.ics/")
        self.put("/calendar.ics/event.ics", _event())
        self.proppatch("/calendar.ics/", PROPPATCH_NAME % "Caf\u00e9")
        self.configure({"encoding": {"request": "ascii"}})
        status, _, body = self.request("GET", "/calendar.ics/", check=None)
        assert status == 500 and body == SERVER_ERROR
        assert "Failed to encode filename" in "\n".join(caplog.messages)
        self.configure({"encoding": {"request": "utf-8"}})
        status, body = self.get("/calendar.ics/")
        assert status == 200 and "BEGIN:VCALENDAR" in body and "Caf\u00e9" in body

        self.proppatch("/calendar.ics/", PROPPATCH_NAME % "Name")
        self.configure({"encoding": {"request": "ascii"}})
        status, headers, body = self.request("GET", "/calendar.ics/", check=None)
        assert status == 200 and "BEGIN:VCALENDAR" in body
        assert "filename*=ascii''Name.ics" in headers.get("Content-Disposition", "")

        status, _, body = self.request(
            "GET", "/missing.ics/", QUERY_STRING="view=freebusy", check=None)
        assert status == 404 and body == NOT_FOUND
        self.create_addressbook("/book/")
        status, _, body = self.request(
            "GET", "/book/", QUERY_STRING="view=freebusy", login=LOGIN,
            check=None)
        assert status == 403 and body == ACCESS_FORBIDDEN

        _set_rights(self, """\
[item]
user: .*
collection: calendar\\.ics/event\\.ics
permissions: i
[rest]
user: .*
collection: .*
permissions: R
""")
        status, _, body = self.request(
            "GET", "/calendar.ics/event.ics", login=LOGIN, check=None)
        assert status == 403 and body == ACCESS_FORBIDDEN
        _grant(self)
        assert "UID:evt" in self.get("/calendar.ics/event.ics")[1]

    def test_freebusy_view_clips_status_and_all_day(self):
        self.mkcalendar("/calendar.ics/")
        self.put("/calendar.ics/span.ics", _event(
            uid="span", summary="Span",
            start="20130101T220000Z", end="20130102T030000Z"))
        self.put("/calendar.ics/inside.ics", _event(
            uid="inside", summary="Inside",
            start="20130102T100000Z", end="20130102T110000Z"))
        self.put("/calendar.ics/inner.ics", _event(
            uid="inner", summary="Inner",
            start="20130102T101500Z", end="20130102T103000Z"))
        self.put("/calendar.ics/zero.ics", _event(
            uid="zero", summary="Zero",
            start="20130102T120000Z", end="20130102T120000Z"))
        self.put("/calendar.ics/after.ics", _event(
            uid="after", summary="After",
            start="20130103T010000Z", end="20130103T020000Z"))
        self.put("/calendar.ics/tent.ics", _event(
            uid="tent", summary="Tent",
            start="20130102T140000Z", end="20130102T150000Z",
            extra="STATUS:TENTATIVE\r\n"))
        self.put("/calendar.ics/cancel.ics", _event(
            uid="cancel", summary="Cancel",
            start="20130102T160000Z", end="20130102T170000Z",
            extra="STATUS:CANCELLED\r\n"))
        self.put("/calendar.ics/clear.ics", _event(
            uid="clear", summary="Clear",
            start="20130102T180000Z", end="20130102T190000Z",
            extra="TRANSP:TRANSPARENT\r\n"))
        status, body = self.get(
            "/calendar.ics/",
            QUERY_STRING="view=freebusy&format=vfreebusy"
            "&start=20130102T000000Z&end=20130103T000000Z")
        assert status == 200 and "BEGIN:VFREEBUSY" in body
        assert "20130102T000000Z/20130102T030000Z" in body.replace("\r", "")
        assert "20130102T100000Z/20130102T110000Z" in body.replace("\r", "")
        assert "20130102T120000Z" not in body
        assert "20130103T010000Z" not in body
        assert "20130102T180000Z" not in body
        assert "BUSY-TENTATIVE" in body
        assert "FBTYPE=FREE" in body or "FREE" in body

        self.mkcalendar("/allday.ics/")
        self.put("/allday.ics/day.ics", (
            "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\n"
            "UID:allday\r\nDTSTART;VALUE=DATE:20130102\r\n"
            "DTEND;VALUE=DATE:20130103\r\nSUMMARY:Day\r\n"
            "END:VEVENT\r\nEND:VCALENDAR\r\n"))
        status, body = self.get(
            "/allday.ics/",
            QUERY_STRING="view=freebusy&format=vfreebusy"
            "&start=20130101T000000Z&end=20130104T000000Z")
        assert status == 200 and "BEGIN:VFREEBUSY" in body
        assert "FREEBUSY" in body

    def test_move_destinations_permissions_and_errno(self, monkeypatch):
        self.mkcalendar("/calendar.ics/")
        self.mkcalendar("/other.ics/")
        self.create_addressbook("/book/")
        self.put("/calendar.ics/event.ics", _event())
        status, _, body = self.request(
            "MOVE", "/calendar.ics/event.ics",
            HTTP_DESTINATION="http://127.0.0.1/cal*.ics/event.ics", check=None)
        assert status == 400 and body == BAD_REQUEST
        assert "UID:evt" in self.get("/calendar.ics/event.ics")[1]

        status, _, body = self.request(
            "MOVE", "/calendar.ics/event.ics",
            SCRIPT_NAME="/prefix",
            HTTP_DESTINATION="http://127.0.0.1/calendar.ics/moved.ics",
            login=LOGIN, check=None)
        assert status == 403 and body == ACCESS_FORBIDDEN
        assert "UID:evt" in self.get("/calendar.ics/event.ics")[1]

        status, _, body = self.request(
            "MOVE", "/calendar.ics/event.ics",
            HTTP_DESTINATION="http://127.0.0.1/calendar.ics/", check=None)
        assert status == 403 and body == ACTION_REFUSED
        assert "UID:evt" in self.get("/calendar.ics/event.ics")[1]

        status, _, body = self.request(
            "MOVE", "/calendar.ics/event.ics",
            HTTP_DESTINATION="http://127.0.0.1/missing.ics/event.ics",
            check=None)
        assert status == 409 and body == CONFLICT
        assert "UID:evt" in self.get("/calendar.ics/event.ics")[1]

        status, _, body = self.request(
            "MOVE", "/calendar.ics/event.ics",
            HTTP_DESTINATION="http://127.0.0.1/book/event.vcf", check=None)
        assert status == 403 and body == ACTION_REFUSED
        assert "UID:evt" in self.get("/calendar.ics/event.ics")[1]

        _set_rights(self, """\
[item]
user: .*
collection: calendar\\.ics/event\\.ics
permissions: W
[cal]
user: .*
collection: calendar\\.ics
permissions: R
[other]
user: .*
collection: other\\.ics.*
permissions: rw
[rest]
user: .*
collection: .*
permissions: R
""")
        status, _, body = self.request(
            "MOVE", "/calendar.ics/event.ics",
            HTTP_DESTINATION="http://127.0.0.1/other.ics/event.ics",
            login=LOGIN, check=None)
        assert status == 403 and body == ACCESS_FORBIDDEN
        _grant(self)
        assert "UID:evt" in self.get("/calendar.ics/event.ics")[1]

        def _fail_move(_item, _collection, _href):
            raise ValueError("failed [Errno %d]" % errno.EIO)

        monkeypatch.setattr(self.application._storage, "move", _fail_move)
        status, _, body = self.request(
            "MOVE", "/calendar.ics/event.ics",
            HTTP_DESTINATION="http://127.0.0.1/other.ics/event.ics",
            check=None)
        assert status == 500 and body == SERVER_ERROR
        assert "UID:evt" in self.get("/calendar.ics/event.ics")[1]

    @pytest.mark.parametrize("code,expect,text", [
        (errno.ENOSPC, 507, INSUFFICIENT),
        (errno.EACCES, 403, ACTION_REFUSED),
        (errno.EPERM, 403, ACTION_REFUSED),
        (errno.EIO, 500, SERVER_ERROR),
        (None, 400, BAD_REQUEST),
    ])
    def test_move_errno_classes(self, monkeypatch, code, expect, text):
        self.mkcalendar("/calendar.ics/")
        self.mkcalendar("/other.ics/")
        self.put("/calendar.ics/event.ics", _event())

        def _fail_move(_item, _collection, _href):
            if code is None:
                raise ValueError("move rejected")
            raise ValueError("failed [Errno %d]" % code)

        monkeypatch.setattr(self.application._storage, "move", _fail_move)
        status, _, body = self.request(
            "MOVE", "/calendar.ics/event.ics",
            HTTP_DESTINATION="http://127.0.0.1/other.ics/event.ics",
            check=None)
        assert status == expect and text in body
        assert "UID:evt" in self.get("/calendar.ics/event.ics")[1]
        assert self.get("/other.ics/event.ics", check=404)[0] == 404

    def test_put_tag_permissions_preconditions_and_timeout(self, caplog):
        caplog.set_level(logging.DEBUG)
        status, _, body = self.request("PUT", "/weird.ics/", _todo(), check=None)
        assert status == 500 and body == SERVER_ERROR
        assert "Can't determine collection tag" in "\n".join(caplog.messages)
        assert self.get("/weird.ics/", check=404)[0] == 404

        status, _, body = self.request(
            "PUT", "/subscribed.ics/", "",
            content_type="text/calendar", check=None)
        assert status == 201, body
        status, responses = self.propfind(
            "/subscribed.ics/", PROPFIND_ONE.format("<D:resourcetype/>"))
        kinds = responses["/subscribed.ics/"]["D:resourcetype"][1]
        assert any("subscribed" in child.tag for child in kinds.iter())

        self.mkcalendar("/calendar.ics/")
        self.put("/calendar.ics/event.ics", _event(summary="Original"))
        status, _, body = self.request(
            "PUT", "/calendar.ics/event.ics/child.ics", _event(uid="child"),
            check=None)
        assert status == 409 and body == CONFLICT
        assert "Original" in self.get("/calendar.ics/event.ics")[1]

        status, _, body = self.request(
            "PUT", "/calendar.ics/event.ics", _event(summary="Changed"),
            HTTP_IF_NONE_MATCH="*", check=None)
        assert status == 412 and body == PRECONDITION
        assert "Original" in self.get("/calendar.ics/event.ics")[1]
        status, _, body = self.request(
            "PUT", "/calendar.ics/fresh.ics", _event(uid="fresh", summary="Fresh"),
            HTTP_IF_NONE_MATCH="*", check=None)
        assert status == 201 and body == ""
        assert "Fresh" in self.get("/calendar.ics/fresh.ics")[1]

        _set_rights(self, """\
[root]
user: .*
collection: ^$
permissions: w
[child]
user: .*
collection: nocol\\.ics
permissions: R
[rest]
user: .*
collection: .*
permissions: R
""")
        caplog.set_level(logging.WARNING)
        status, _, body = self.request(
            "PUT", "/nocol.ics/", _event(uid="whole"), login=LOGIN, check=None)
        assert status == 403 and body == ACCESS_FORBIDDEN
        assert "Not a collection" in "\n".join(caplog.messages)
        _grant(self)
        assert self.get("/nocol.ics/", check=404)[0] == 404

        self.mkcalendar("/locked.ics/")
        self.put("/locked.ics/event.ics", _event(uid="locked", summary="Locked"))
        _set_rights(self, """\
[item]
user: .*
collection: locked\\.ics/event\\.ics
permissions: W
[cal]
user: .*
collection: locked\\.ics
permissions: R
[rest]
user: .*
collection: .*
permissions: R
""")
        status, _, body = self.request(
            "PUT", "/locked.ics/event.ics",
            _event(uid="locked", summary="Nope"), login=LOGIN, check=None)
        assert status == 403 and body == ACCESS_FORBIDDEN
        _grant(self)
        assert "Locked" in self.get("/locked.ics/event.ics")[1]

        status, headers, body = self._call(
            "PUT", "/calendar.ics/late.ics", data=TimeoutStream(),
            content_length=8, content_type="text/calendar")
        assert status == 408 and body == TIMEOUT

        caplog.clear()
        self.configure({"logging": {"bad_put_request_content": "True"}})
        status, _, body = self.request(
            "PUT", "/calendar.ics/bad.ics", "this is not a calendar", check=None)
        assert status == 400 and body == BAD_REQUEST
        assert "this is not a calendar" in "\n".join(caplog.messages)
        caplog.clear()
        with _Level(logging.ERROR):
            status, _, body = self.request(
                "PUT", "/calendar.ics/bad.ics", "hidden calendar text", check=None)
        assert status == 400 and body == BAD_REQUEST
        assert "hidden calendar text" not in "\n".join(caplog.messages)
        self.configure({"logging": {"bad_put_request_content": "False"}})
        caplog.set_level(logging.DEBUG, logger="radicale")
        caplog.clear()
        with _Level(logging.DEBUG):
            status, _, body = self.request(
                "PUT", "/calendar.ics/bad.ics", "suppressed calendar text",
                check=None)
        assert status == 400 and body == BAD_REQUEST
        messages = "\n".join(caplog.messages)
        assert ("Bad PUT request content: suppressed by config/option "
                "[logging] bad_put_request_content") in messages
        assert "Bad PUT request content of" not in messages
        assert self.get("/calendar.ics/bad.ics", check=404)[0] == 404

    def test_put_prepare_failures_size_and_create_error(self, monkeypatch, caplog):
        caplog.set_level(logging.DEBUG)

        def broken(self):
            raise RuntimeError("serialize failed for test")

        monkeypatch.setattr(radicale_item.Item, "serialize", broken)
        status, _, body = self.request(
            "PUT", "/calendar.ics/", _event(summary="BoomCal"), check=None)
        assert status == 400 and body == BAD_REQUEST
        assert "content below" in "\n".join(caplog.messages)
        assert "serialize failed for test" in "\n".join(caplog.messages)
        assert "content suppressed in this loglevel" not in "\n".join(caplog.messages)
        assert self.get("/calendar.ics/", check=404)[0] == 404

        caplog.clear()
        with _Level(logging.WARNING):
            status, _, body = self.request(
                "PUT", "/book/", _vcard(fn="BoomCard"), check=None)
        assert status == 400 and body == BAD_REQUEST
        assert "content suppressed in this loglevel" in "\n".join(caplog.messages)
        assert "content below" not in "\n".join(caplog.messages)
        assert self.get("/book/", check=404)[0] == 404
        monkeypatch.undo()

        self.configure({"server": {"max_resource_size": "1", "delay_on_error": "0"}})
        status, _, body = self.request("PUT", "/book/", _vcard(), check=None)
        assert status == 412 and body == PRECONDITION
        assert self.get("/book/", check=404)[0] == 404
        self.configure({"server": {"max_resource_size": "10000000",
                                   "delay_on_error": "0"}})
        status, _, body = self.request("PUT", "/book/", _vcard(fn="Ada"), check=None)
        assert status == 201, body
        assert "FN:Ada" in self.get("/book/")[1]

        def fail_create(*_args, **_kwargs):
            raise ValueError("cannot create collection")

        monkeypatch.setattr(self.application._storage, "create_collection", fail_create)
        status, _, body = self.request(
            "PUT", "/another.ics/", _event(uid="another"), check=None)
        assert status == 400 and body == BAD_REQUEST
        assert self.get("/another.ics/", check=404)[0] == 404

    def test_collection_put_notifies_the_hook_and_empty_body_adds_none(self):
        """A calendar upload reports the new event. An empty body adds none.

        One component is the inside case. An empty upload is the empty
        boundary and must not invent a notification.
        """
        self.configure({"hook": {"type": "radicale.tests.test_cov_app"}})
        status, _, body = self.request("PUT", "/calendar.ics/", _event(), check=None)
        assert status == 201 and body == ""
        assert "UID:evt" in self.get("/calendar.ics/")[1]
        assert len(Hook.events) == 1
        created = Hook.events[0]
        assert created.type == "upsert"
        assert created.old_content is None
        assert created.new_content is not None and "UID:evt" in created.new_content
        status, _, body = self.request("PUT", "/empty-book/", "", check=None)
        assert status in (201, 204)
        assert len(Hook.events) == 1

    def test_propfind_timeouts_leaf_and_freebusy_rights(self):
        status, _, body = self._call(
            "PROPFIND", "/calendar.ics/", data=TimeoutStream(), content_length=8)
        assert status == 408 and body == TIMEOUT
        status, _, body = self._call(
            "PROPFIND", "/calendar.ics/", data=b"<not xml", content_length=8)
        assert status == 400 and body == BAD_REQUEST

        self.mkcalendar("/calendar.ics/")
        props = "".join((
            "<D:getetag/>", "<D:getlastmodified/>", "<D:displayname/>",
            "<D:getcontenttype/>", "<CS:getctag/>", "<D:sync-token/>",
            "<RADICALE:displayname/>"))
        status, responses = self.propfind("/", PROPFIND_ONE.format(props))
        assert status == 207
        root = responses["/"]
        for name in ("D:getetag", "D:getlastmodified", "D:displayname",
                     "D:getcontenttype", "CS:getctag", "D:sync-token",
                     "RADICALE:displayname"):
            assert root[name][0] == 404
        status, responses = self.propfind(
            "/calendar.ics/", PROPFIND_ONE.format(props))
        leaf = responses["/calendar.ics/"]
        assert leaf["D:getetag"][0] == 200
        assert leaf["D:getlastmodified"][0] == 200
        assert leaf["D:displayname"][0] == 200
        assert leaf["D:displayname"][1].text == "calendar.ics"
        assert leaf["CS:getctag"][0] == 200
        assert leaf["D:sync-token"][0] == 200

        self.mkcol("/sub.ics/", SUBSCRIBED_MKCOL)
        status, responses = self.propfind(
            "/sub.ics/", PROPFIND_ONE.format("<D:resourcetype/>"))
        element = responses["/sub.ics/"]["D:resourcetype"][1]
        assert "subscribed" in "".join(element.itertext()) or any(
            "subscribed" in child.tag for child in element.iter())

        _set_rights(self, "[all]\nuser: .*\ncollection: .*\npermissions: f\n")
        status, _, body = self.request(
            "PROPFIND", "/calendar.ics/",
            PROPFIND_ONE.format("<D:current-user-privilege-set/>"),
            HTTP_DEPTH="0", login="alice:secret", check=None)
        assert status == 207 and "read-free-busy" in body
        assert "write-content" not in body
        status, _, body = self.request(
            "PROPFIND", "/calendar.ics/",
            PROPFIND_ONE.format("<D:current-user-privilege-set/>"),
            HTTP_DEPTH="1", login="alice:secret", check=None)
        assert status == 403 and body == ACCESS_FORBIDDEN

        _set_rights(self, "[all]\nuser: .*\ncollection: .*\npermissions: fw\n")
        status, _, body = self.request(
            "PROPFIND", "/calendar.ics/",
            PROPFIND_ONE.format("<D:current-user-privilege-set/>"),
            HTTP_DEPTH="0", login="alice:secret", check=None)
        assert status == 207 and "read-free-busy" in body
        assert "write-content" in body

        _set_rights(self, "[all]\nuser: .*\ncollection: .*\npermissions: f\n")
        status, _, body = self.request(
            "PROPFIND", "/", PROPFIND_ONE.format("<D:displayname/>"),
            HTTP_DEPTH="0", login="alice:secret", check=None)
        assert status == 403 and body == ACCESS_FORBIDDEN
        _set_rights(self, "[all]\nuser: .*\ncollection: .*\npermissions: Rf\n")
        status, _, body = self.request(
            "PROPFIND", "/", PROPFIND_ONE.format("<D:displayname/>"),
            HTTP_DEPTH="0", login="alice:secret", check=None)
        assert status == 207 and "response" not in body

        _grant(self)
        self.create_addressbook("/book/")
        _set_rights(self, "[all]\nuser: .*\ncollection: .*\npermissions: R\n")
        status, _, body = self.request(
            "PROPFIND", "/book/", PROPFIND_ONE.format("<D:displayname/>"),
            HTTP_DEPTH="0", login=LOGIN, check=None)
        assert status == 403 and body == ACCESS_FORBIDDEN

        _set_rights(self, "[all]\nuser: .*\ncollection: .*\npermissions: f\n")
        status, _, body = self.request(
            "PROPFIND", "/book/", PROPFIND_ONE.format("<D:displayname/>"),
            HTTP_DEPTH="0", login="alice:secret", check=None)
        assert status == 403 and body == ACCESS_FORBIDDEN

    def test_proppatch_blocks_and_errno(self, monkeypatch, caplog):
        self.mkcalendar("/calendar.ics/")
        self.proppatch("/calendar.ics/", PROPPATCH_NAME % "Original")
        self.put("/calendar.ics/event.ics", _event())
        _set_rights(self, "[all]\nuser: .*\ncollection: .*\npermissions: rwl\n")
        status, _, body = self.request(
            "PROPPATCH", "/calendar.ics/", PROPPATCH_NAME % "Blocked",
            login=LOGIN, check=None)
        assert status == 403 and body == ACCESS_FORBIDDEN
        _grant(self)
        _, responses = self.propfind(
            "/calendar.ics/", PROPFIND_ONE.format("<D:displayname/>"))
        assert responses["/calendar.ics/"]["D:displayname"][1].text == "Original"

        _set_rights(self, "[all]\nuser: .*\ncollection: .*\npermissions: R\n")
        status, _, body = self.request(
            "PROPPATCH", "/calendar.ics/", PROPPATCH_NAME % "Nope",
            login=LOGIN, check=None)
        assert status == 403 and body == ACCESS_FORBIDDEN

        _set_rights(self, """\
[cal]
user: .*
collection: calendar\\.ics
permissions: W
[rest]
user: .*
collection: .*
permissions: R
""")
        status, _, body = self.request(
            "PROPPATCH", "/calendar.ics/", PROPPATCH_NAME % "Nope",
            login=LOGIN, check=None)
        assert status == 403 and body == ACCESS_FORBIDDEN

        _grant(self)
        status, _, body = self.request(
            "PROPPATCH", "/calendar.ics/event.ics", PROPPATCH_NAME % "Item",
            check=None)
        assert status == 403 and body == ACTION_REFUSED
        status, _, body = self.request(
            "PROPPATCH", "/missing.ics/", PROPPATCH_NAME % "Missing", check=None)
        assert status == 404 and body == NOT_FOUND

        def fail_meta(_self, _props):
            raise ValueError("failed [Errno %d]" % errno.ENOSPC)

        monkeypatch.setattr(Collection, "set_meta", fail_meta)
        status, _, body = self.request(
            "PROPPATCH", "/calendar.ics/", PROPPATCH_NAME % "Disk", check=None)
        assert status == 507 and INSUFFICIENT in body
        monkeypatch.undo()
        _, responses = self.propfind(
            "/calendar.ics/", PROPFIND_ONE.format("<D:displayname/>"))
        assert responses["/calendar.ics/"]["D:displayname"][1].text == "Original"

        self.configure({"hook": {"type": "radicale.tests.test_cov_app"}})
        Hook.fail = True
        status, _, body = self.request(
            "PROPPATCH", "/calendar.ics/", PROPPATCH_NAME % "Hooked", check=None)
        assert status == 500 and body == SERVER_ERROR
        _, responses = self.propfind(
            "/calendar.ics/", PROPFIND_ONE.format("<D:displayname/>"))
        assert responses["/calendar.ics/"]["D:displayname"][1].text == "Hooked"

    @pytest.mark.parametrize("code,expect,text", [
        (errno.EACCES, 403, ACTION_REFUSED),
        (errno.EPERM, 403, ACTION_REFUSED),
        (errno.EIO, 500, SERVER_ERROR),
        (None, 400, BAD_REQUEST),
    ])
    def test_proppatch_errno_classes(self, monkeypatch, code, expect, text):
        self.mkcalendar("/calendar.ics/")

        def fail_meta(_self, _props):
            if code is None:
                raise ValueError("properties are not acceptable")
            raise ValueError("failed [Errno %d]" % code)

        monkeypatch.setattr(Collection, "set_meta", fail_meta)
        status, _, body = self.request(
            "PROPPATCH", "/calendar.ics/", PROPPATCH_NAME % "Name", check=None)
        assert status == expect and text in body
        monkeypatch.undo()
        _, responses = self.propfind(
            "/calendar.ics/", PROPFIND_ONE.format("<D:displayname/>"))
        stored = responses["/calendar.ics/"]["D:displayname"]
        assert stored[0] == 200 and stored[1].text != "Name"

    def test_report_edges_filters_and_expand(self, monkeypatch, caplog):
        self.mkcalendar("/calendar.ics/")
        self.put("/calendar.ics/event.ics", _event(summary="Event"))
        status, _, body = self.request("REPORT", "/calendar.ics/", "", check=None)
        assert status == 207 and "multistatus" in body and "response" not in body

        self.create_addressbook("/book/")
        self.put("/book/card.vcf", _vcard())
        query = (
            "<?xml version='1.0' encoding='utf-8'?>"
            "<C:free-busy-query xmlns:C='urn:ietf:params:xml:ns:caldav'>"
            "<C:time-range start='20130101T000000Z' end='20130102T000000Z'/>"
            "</C:free-busy-query>")
        status, _, body = self.request("REPORT", "/book/", query, check=None)
        assert status == 403 and "supported-report" in body

        status, _, body = self._call(
            "REPORT", "/calendar.ics/", data=b"<not xml", content_length=8)
        assert status == 400 and body == BAD_REQUEST
        status, _, body = self._call(
            "REPORT", "/calendar.ics/", data=TimeoutStream(), content_length=8)
        assert status == 408 and body == TIMEOUT

        outside = (
            "<?xml version='1.0' encoding='utf-8'?>"
            "<C:calendar-multiget xmlns:D='DAV:' "
            "xmlns:C='urn:ietf:params:xml:ns:caldav'>"
            "<D:prop><D:getetag/></D:prop>"
            "<D:href>/prefix/calendar.ics/event.ics</D:href>"
            "<D:href>/elsewhere/event.ics</D:href>"
            "<D:href>/prefix/calendar.ics/a/b.ics</D:href>"
            "</C:calendar-multiget>")
        status, _, body = self.request(
            "REPORT", "/calendar.ics/", outside, SCRIPT_NAME="/prefix", check=None)
        assert status == 207
        assert "event.ics" in body
        assert "elsewhere" not in body
        assert "a/b.ics" in body or "a%2Fb.ics" in body or ">404<" in body
        assert body.count("404") >= 1

        empty_and_one = (
            "<?xml version='1.0' encoding='utf-8'?>"
            "<C:calendar-query xmlns:D='DAV:' xmlns:C='urn:ietf:params:xml:ns:caldav'>"
            "<D:prop><D:getetag/></D:prop>"
            "<C:filter/>"
            "<C:filter><C:comp-filter name='VCALENDAR'>"
            "<C:comp-filter name='VEVENT'><C:prop-filter name='SUMMARY'/>"
            "</C:comp-filter></C:comp-filter></C:filter>"
            "</C:calendar-query>")
        status, _, body = self.request(
            "REPORT", "/calendar.ics/", empty_and_one, check=None)
        assert status == 207 and "getetag" in body

        two_children = (
            "<?xml version='1.0' encoding='utf-8'?>"
            "<C:calendar-query xmlns:C='urn:ietf:params:xml:ns:caldav'>"
            "<D:prop xmlns:D='DAV:'><D:getetag/></D:prop>"
            "<C:filter><C:comp-filter name='VCALENDAR'/>"
            "<C:comp-filter name='VCALENDAR'/></C:filter>"
            "</C:calendar-query>")
        status, _, body = self.request(
            "REPORT", "/calendar.ics/", two_children, check=None)
        assert status == 400 and body == BAD_REQUEST

        unexpected = (
            "<?xml version='1.0' encoding='utf-8'?>"
            "<C:calendar-query xmlns:C='urn:ietf:params:xml:ns:caldav'>"
            "<D:prop xmlns:D='DAV:'><D:getetag/></D:prop>"
            "<C:filter><C:time-range start='20130101T000000Z' "
            "end='20140101T000000Z'/></C:filter></C:calendar-query>")
        status, _, body = self.request(
            "REPORT", "/calendar.ics/", unexpected, check=None)
        assert status == 400 and body == BAD_REQUEST

        def _ab_query(test_name, props):
            inner = "".join(
                "<CR:prop-filter name='%s'/>" % name for name in props)
            return (
                "<?xml version='1.0' encoding='utf-8'?>"
                "<CR:addressbook-query xmlns:D='DAV:' "
                "xmlns:CR='urn:ietf:params:xml:ns:carddav'>"
                "<D:prop><D:getetag/></D:prop>"
                "<CR:filter test='%s'>%s</CR:filter>"
                "</CR:addressbook-query>" % (test_name, inner))

        status, _, body = self.request(
            "REPORT", "/book/", _ab_query("anyof", ["FN"]), check=None)
        assert status == 207 and "card.vcf" in body
        status, _, body = self.request(
            "REPORT", "/book/", _ab_query("allof", ["FN", "X-NOPE"]), check=None)
        assert status == 207 and "card.vcf" not in body
        status, _, body = self.request(
            "REPORT", "/book/", _ab_query("noneof", ["FN"]), check=None)
        assert status == 400 and body == BAD_REQUEST
        status, _, body = self.request(
            "REPORT", "/book/",
            "<?xml version='1.0' encoding='utf-8'?>"
            "<CR:addressbook-query xmlns:D='DAV:' "
            "xmlns:CR='urn:ietf:params:xml:ns:carddav'>"
            "<D:prop><D:getetag/></D:prop>"
            "<CR:filter><CR:address-data/></CR:filter>"
            "</CR:addressbook-query>", check=None)
        assert status == 400 and body == BAD_REQUEST

        unknown = (
            "<?xml version='1.0' encoding='utf-8'?>"
            "<C:calendar-query xmlns:D='DAV:' xmlns:C='urn:ietf:params:xml:ns:caldav'>"
            "<D:prop><D:getetag/><D:unknown-prop/></D:prop>"
            "<C:filter><C:comp-filter name='VCALENDAR'>"
            "<C:comp-filter name='VEVENT'/></C:comp-filter></C:filter>"
            "</C:calendar-query>")
        status, _, body = self.request("REPORT", "/calendar.ics/", unknown, check=None)
        assert status == 207 and "unknown-prop" in body
        assert ">404<" in body or "404" in body

        self.put("/calendar.ics/daily.ics", (
            "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nUID:daily\r\n"
            "DTSTART:20130101T100000Z\r\nDTEND:20130101T110000Z\r\n"
            "RRULE:FREQ=DAILY;COUNT=3\r\nEXDATE:20130102T100000Z\r\n"
            "SUMMARY:Daily\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"))
        expand = (
            "<?xml version='1.0' encoding='utf-8'?>"
            "<C:calendar-query xmlns:D='DAV:' xmlns:C='urn:ietf:params:xml:ns:caldav'>"
            "<D:prop><C:calendar-data><C:expand start='{start}' end='{end}'/>"
            "</C:calendar-data><D:getetag/></D:prop>"
            "<C:filter><C:comp-filter name='VCALENDAR'>"
            "<C:comp-filter name='VEVENT'/></C:comp-filter></C:filter>"
            "</C:calendar-query>")
        status, _, body = self.request(
            "REPORT", "/calendar.ics/",
            expand.format(start="20130101T000000Z", end="20130104T000000Z"),
            check=None)
        assert status == 207
        assert body.upper().count("BEGIN:VEVENT") == 2
        assert "20130102T100000Z" not in body
        assert "getetag" in body

        missing_expand = expand.replace(
            "<C:expand start='{start}' end='{end}'/>", "<C:expand/>")
        status, _, body = self.request(
            "REPORT", "/calendar.ics/", missing_expand, check=None)
        assert status == 403 and "expand" in body

        self.put("/calendar.ics/zero.ics", (
            "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nUID:dur0\r\n"
            "DTSTART:20130201T100000Z\r\nDURATION:PT0S\r\n"
            "RRULE:FREQ=DAILY;COUNT=2\r\nSUMMARY:Zero\r\n"
            "END:VEVENT\r\nEND:VCALENDAR\r\n"))
        caplog.set_level(logging.WARNING)
        with _Level(logging.INFO):
            status, _, body = self.request(
                "REPORT", "/calendar.ics/",
                expand.format(start="20130201T000000Z", end="20130203T000000Z"),
                check=None)
        assert status == 207 and "dur0" in body
        assert "Invalid DURATION" in "\n".join(caplog.messages)

        nomaster = (
            "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nUID:nomaster\r\n"
            "RECURRENCE-ID:20130401T100000Z\r\nDTSTART:20130401T100000Z\r\n"
            "DTEND:20130401T110000Z\r\nSUMMARY:Only\r\nEND:VEVENT\r\n"
            "END:VCALENDAR\r\n")
        status, _, body = self.request("PUT", "/nomaster.ics/", nomaster, check=None)
        if status == 201:
            status, _, body = self.request(
                "REPORT", "/nomaster.ics/",
                expand.format(start="20130401T000000Z", end="20130403T000000Z"),
                check=None)
            assert status == 400 and body == BAD_REQUEST

        self.put("/calendar.ics/span.ics", _event(
            uid="span", summary="Span",
            start="20000101T000000Z", end="20300101T000000Z"))

        def explode(*_args, **_kwargs):
            raise ValueError("filter exploded")

        monkeypatch.setattr(
            "radicale.app.report.radicale_filter.comp_match", explode)
        caplog.clear()
        status, _, body = self.request(
            "GET", "/calendar.ics/",
            QUERY_STRING="view=freebusy&format=vfreebusy"
            "&start=20130102T000000Z&end=20130103T000000Z", check=None)
        assert status == 400 and body == BAD_REQUEST
        assert "Failed to free-busy filter" in "\n".join(caplog.messages)

        def explode_runtime(*_args, **_kwargs):
            raise RuntimeError("filter exploded")

        monkeypatch.setattr(
            "radicale.app.report.radicale_filter.comp_match", explode_runtime)
        caplog.clear()
        status, _, body = self.request(
            "GET", "/calendar.ics/",
            QUERY_STRING="view=freebusy&format=vfreebusy"
            "&start=20130102T000000Z&end=20130103T000000Z", check=None)
        assert status == 500 and body == SERVER_ERROR
        assert "Failed to free-busy filter" in "\n".join(caplog.messages)

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

    def test_prepare_logs_and_calendar_metadata(self, monkeypatch, caplog):
        caplog.set_level(logging.DEBUG)

        def broken_serialize(self):
            raise RuntimeError("serialize failed for calendar")

        monkeypatch.setattr(radicale_item.Item, "serialize", broken_serialize)
        with _Level(logging.WARNING):
            status, _, body = self.request(
                "PUT", "/calendar.ics/", _event(summary="Cal"), check=None)
        assert status == 400 and body == BAD_REQUEST
        logged = "\n".join(caplog.messages)
        assert "content suppressed in this loglevel" in logged
        assert "content below" not in logged
        assert self.get("/calendar.ics/", check=404)[0] == 404
        monkeypatch.undo()

        def broken_range(self):
            raise RuntimeError("time range failed after serialize")

        monkeypatch.setattr(
            radicale_item.Item, "time_range", property(broken_range))
        caplog.clear()
        status, _, body = self.request(
            "PUT", "/book/", _vcard(fn="Ada Lovelace"), check=None)
        assert status == 400 and body == BAD_REQUEST
        logged = "\n".join(caplog.messages)
        assert "content below" in logged
        assert "FN:Ada Lovelace" in logged
        assert self.get("/book/", check=404)[0] == 404
        monkeypatch.undo()

        named = _event(uid="named", summary="Named").replace(
            "BEGIN:VCALENDAR\r\n",
            "BEGIN:VCALENDAR\r\nX-WR-CALNAME:Hello\r\nX-WR-CALDESC:Desc\r\n",
            1)
        status, _, body = self.request("PUT", "/named.ics/", named, check=None)
        assert status == 201 and body == ""
        status, _, answer = self.request(
            "PROPFIND", "/named.ics/",
            PROPFIND_ONE.format(
                "<D:displayname/><C:calendar-description/>"),
            HTTP_DEPTH="0", check=None)
        assert status == 207 and "Hello" in answer and "Desc" in answer

        blank = _event(uid="blank", summary="Blank").replace(
            "BEGIN:VCALENDAR\r\n",
            "BEGIN:VCALENDAR\r\nX-WR-CALNAME:\r\nX-WR-CALDESC:\r\n",
            1)
        status, _, body = self.request("PUT", "/blank.ics/", blank, check=None)
        assert status == 201 and body == ""
        status, _, answer = self.request(
            "PROPFIND", "/blank.ics/",
            PROPFIND_ONE.format("<D:displayname/>"),
            HTTP_DEPTH="0", check=None)
        assert status == 207 and "blank.ics" in answer
        assert ">Hello<" not in answer

    def test_move_explicit_port_and_principal_props(self):
        self.mkcalendar("/calendar.ics/")
        self.put("/calendar.ics/event.ics", _event(summary="Moved"))
        self.mkcalendar("/other.ics/")
        status, _, body = self.request(
            "MOVE", "/calendar.ics/event.ics",
            HTTP_DESTINATION="http://127.0.0.1:80/other.ics/event.ics",
            check=None)
        assert status in (201, 204), body
        assert "Moved" in self.get("/other.ics/event.ics")[1]
        self.put("/calendar.ics/again.ics", _event(uid="again", summary="Again"))
        status, _, body = self.request(
            "MOVE", "/calendar.ics/again.ics",
            HTTP_DESTINATION="http://127.0.0.1:81/other.ics/again.ics",
            check=None)
        assert status == 502 and body == REMOTE_DESTINATION
        assert "Again" in self.get("/calendar.ics/again.ics")[1]

        status, _, body = self.request(
            "PROPFIND", "/",
            PROPFIND_ONE.format("<D:getetag/><D:getlastmodified/>"),
            HTTP_DEPTH="0", check=None)
        assert status == 207 and "404" in body

        self.put("/calendar.ics/todo.ics", (
            "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VTODO\r\n"
            "UID:todo-1\r\nDTSTAMP:20130101T000000Z\r\nSUMMARY:Task\r\n"
            "END:VTODO\r\nEND:VCALENDAR\r\n"))
        self.put("/calendar.ics/odd.ics", _event(
            uid="odd", summary="Odd",
            start="20130601T100000Z", end="20130601T110000Z",
            extra="STATUS:NEEDS-ACTION\r\n"))
        status, body = self.get(
            "/calendar.ics/",
            QUERY_STRING="view=freebusy&format=vevent"
            "&start=20130601T000000Z&end=20130602T000000Z")
        assert status == 200 and "SUMMARY:Busy" in body
        assert "todo-1" not in body and "Task" not in body

    def test_report_unsupported_and_second_filter(self, monkeypatch):
        self.mkcalendar("/calendar.ics/")
        self.put("/calendar.ics/event.ics", _event(summary="Shown"))
        self.create_addressbook("/book/")
        status, _, body = self.request(
            "REPORT", "/calendar.ics/",
            "<?xml version='1.0' encoding='utf-8'?>"
            "<D:expand-property xmlns:D='DAV:'/>", check=None)
        assert status == 207 and "multistatus" in body
        assert "expand-property" not in body

        multiget = (
            "<?xml version='1.0' encoding='utf-8'?>"
            "<C:calendar-multiget xmlns:D='DAV:' "
            "xmlns:C='urn:ietf:params:xml:ns:caldav'>"
            "<D:prop><D:getetag/></D:prop>"
            "<D:href>/book/card.vcf</D:href>"
            "</C:calendar-multiget>")
        status, _, body = self.request("REPORT", "/book/", multiget, check=None)
        assert status == 403 and "supported-report" in body

        status, _, body = self.request(
            "REPORT", "/",
            "<?xml version='1.0' encoding='utf-8'?>"
            "<D:sync-collection xmlns:D='DAV:'>"
            "<D:sync-token/>"
            "</D:sync-collection>", check=None)
        assert status == 403 and "supported-report" in body

        status, _, body = self.request(
            "REPORT", "/calendar.ics/",
            "<?xml version='1.0' encoding='utf-8'?>"
            "<CR:addressbook-query xmlns:D='DAV:' "
            "xmlns:CR='urn:ietf:params:xml:ns:carddav'>"
            "<D:prop><D:getetag/></D:prop>"
            "<CR:filter test='anyof'><CR:prop-filter name='FN'/></CR:filter>"
            "</CR:addressbook-query>", check=None)
        assert status == 400 and body == BAD_REQUEST

        self.put("/calendar.ics/span.ics", _event(
            uid="span", summary="Span",
            start="20000101T000000Z", end="20300101T000000Z"))

        def hide(*_args, **_kwargs):
            return False

        monkeypatch.setattr(
            "radicale.app.report.radicale_filter.comp_match", hide)
        status, body = self.get(
            "/calendar.ics/",
            QUERY_STRING="view=freebusy&format=vevent"
            "&start=20130601T000000Z&end=20130602T000000Z")
        assert status == 200 and "SUMMARY:Busy" not in body
        monkeypatch.undo()

        def keep(*_args, **_kwargs):
            return True

        monkeypatch.setattr(
            "radicale.app.report.radicale_filter.comp_match", keep)
        status, body = self.get(
            "/calendar.ics/",
            QUERY_STRING="view=freebusy&format=vevent"
            "&start=20130601T000000Z&end=20130602T000000Z")
        assert status == 200 and "SUMMARY:Busy" in body

    def test_report_query_shapes_expand_and_filter(self, monkeypatch, caplog):
        self.mkcalendar("/calendar.ics/")
        self.put("/calendar.ics/kept.ics", _event(
            uid="kept", summary="InsideDay",
            start="20130601T100000Z", end="20130601T110000Z"))
        self.put("/calendar.ics/span.ics", _event(
            uid="span", summary="SpanWide",
            start="20000101T000000Z", end="20300101T000000Z"))
        window = (
            "<?xml version='1.0' encoding='utf-8'?>"
            "<C:calendar-query xmlns:D='DAV:' "
            "xmlns:C='urn:ietf:params:xml:ns:caldav'>"
            "<D:prop><D:getetag/></D:prop>"
            "<C:filter><C:comp-filter name='VCALENDAR'>"
            "<C:comp-filter name='VEVENT'>"
            "<C:time-range start='20130601T000000Z' end='20130602T000000Z'/>"
            "</C:comp-filter></C:comp-filter></C:filter>"
            "</C:calendar-query>")
        bare = (
            "<?xml version='1.0' encoding='utf-8'?>"
            "<C:calendar-query xmlns:C='urn:ietf:params:xml:ns:caldav'>"
            "<C:filter><C:comp-filter name='VCALENDAR'>"
            "<C:comp-filter name='VEVENT'/></C:comp-filter></C:filter>"
            "</C:calendar-query>")
        status, _, body = self.request(
            "REPORT", "/calendar.ics/", bare, check=None)
        assert status == 207 and "multistatus" in body
        assert "kept.ics" not in body and "span.ics" not in body
        status, _, body = self.request(
            "REPORT", "/calendar.ics/", window, check=None)
        assert status == 207 and "kept.ics" in body and "span.ics" in body

        def hide(*_args, **_kwargs):
            return False

        monkeypatch.setattr(
            "radicale.app.report.radicale_filter.comp_match", hide)
        status, _, body = self.request(
            "REPORT", "/calendar.ics/", window, check=None)
        assert status == 207 and "kept.ics" in body and "span.ics" not in body
        monkeypatch.undo()

        def keep(*_args, **_kwargs):
            return True

        monkeypatch.setattr(
            "radicale.app.report.radicale_filter.comp_match", keep)
        status, _, body = self.request(
            "REPORT", "/calendar.ics/", window, check=None)
        assert status == 207 and "kept.ics" in body and "span.ics" in body
        monkeypatch.undo()

        def explode(*_args, **_kwargs):
            raise RuntimeError("report filter exploded")

        monkeypatch.setattr(
            "radicale.app.report.radicale_filter.comp_match", explode)
        status, _, body = self.request(
            "REPORT", "/calendar.ics/", window, check=None)
        assert status == 500 and body == SERVER_ERROR
        monkeypatch.undo()

        def explode_value(*_args, **_kwargs):
            raise ValueError("report filter rejected")

        monkeypatch.setattr(
            "radicale.app.report.radicale_filter.comp_match", explode_value)
        status, _, body = self.request(
            "REPORT", "/calendar.ics/", window, check=None)
        assert status == 400 and body == BAD_REQUEST
        monkeypatch.undo()
        assert "InsideDay" in self.get("/calendar.ics/kept.ics")[1]

        self.put("/calendar.ics/allday.ics", (
            "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\n"
            "UID:allday\r\nDTSTART;VALUE=DATE:20130101\r\n"
            "DTEND;VALUE=DATE:20130102\r\n"
            "RRULE:FREQ=DAILY;COUNT=2\r\nSUMMARY:AllDay\r\n"
            "END:VEVENT\r\nEND:VCALENDAR\r\n"))
        self.put("/calendar.ics/open.ics", (
            "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\n"
            "UID:open\r\nDTSTART:20130101T100000Z\r\n"
            "RRULE:FREQ=DAILY;COUNT=2\r\nSUMMARY:OpenEnded\r\n"
            "END:VEVENT\r\nEND:VCALENDAR\r\n"))
        expand = (
            "<?xml version='1.0' encoding='utf-8'?>"
            "<C:calendar-query xmlns:D='DAV:' "
            "xmlns:C='urn:ietf:params:xml:ns:caldav'>"
            "<D:prop><C:calendar-data><C:expand start='{start}' end='{end}'/>"
            "</C:calendar-data></D:prop>"
            "<C:filter><C:comp-filter name='VCALENDAR'>"
            "<C:comp-filter name='VEVENT'/></C:comp-filter></C:filter>"
            "</C:calendar-query>")
        status, _, body = self.request(
            "REPORT", "/calendar.ics/",
            expand.format(start="20130101T000000Z", end="20130105T000000Z"),
            check=None)
        assert status == 207 and "AllDay" in body and "OpenEnded" in body
        assert body.upper().count("BEGIN:VEVENT") >= 2

        self.put("/calendar.ics/hour.ics", (
            "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\n"
            "UID:hour\r\nDTSTART:20130201T100000Z\r\nDURATION:PT1H\r\n"
            "RRULE:FREQ=DAILY;COUNT=1\r\nSUMMARY:Hour\r\n"
            "END:VEVENT\r\nEND:VCALENDAR\r\n"))

        class _BadDuration:
            days = 0
            seconds = 0

            def total_seconds(self):
                raise TypeError("bad duration")

            def __abs__(self):
                return self

        original_filtered = Collection.get_filtered

        def filtered_with_bad_duration(collection, filters):
            for item, flag in original_filtered(collection, filters):
                vevent = getattr(item.vobject_item, "vevent", None)
                if vevent is not None and vevent.uid.value == "hour":
                    vevent.duration.value = _BadDuration()
                yield item, flag

        monkeypatch.setattr(Collection, "get_filtered", filtered_with_bad_duration)
        caplog.set_level(logging.WARNING)
        status, _, body = self.request(
            "REPORT", "/calendar.ics/",
            expand.format(start="20130201T000000Z", end="20130202T000000Z"),
            check=None)
        assert status == 207 and "Hour" in body
        assert "Failed to parse DURATION" in "\n".join(caplog.messages)
        monkeypatch.undo()
        status, _, body = self.request(
            "REPORT", "/calendar.ics/",
            expand.format(start="20130201T000000Z", end="20130202T000000Z"),
            check=None)
        assert status == 207 and "Hour" in body
        assert "PT1H" in body

    def test_propfind_omits_child_without_read_or_freebusy(self):
        self.mkcol("/holder/")
        self.mkcol("/holder/open/")
        self.mkcol("/holder/sealed/")
        _set_rights(self, (
            "[sealed]\nuser: .*\ncollection: holder/sealed\npermissions: d\n"
            "[open]\nuser: .*\ncollection: holder/open\npermissions: R\n"
            "[rest]\nuser: .*\ncollection: .*\npermissions: RrWw\n"))
        status, _, body = self.request(
            "PROPFIND", "/holder/",
            PROPFIND_ONE.format("<D:resourcetype/>"),
            HTTP_DEPTH="1", login=LOGIN, check=None)
        assert status == 207 and "/holder/open/" in body
        assert "/holder/sealed/" not in body
        status, _, body = self.request(
            "PROPFIND", "/holder/sealed/",
            PROPFIND_ONE.format("<D:resourcetype/>"),
            HTTP_DEPTH="0", login=LOGIN, check=None)
        assert status == 403 and body == ACCESS_FORBIDDEN
        status, _, body = self.request(
            "PROPFIND", "/holder/open/",
            PROPFIND_ONE.format("<D:resourcetype/>"),
            HTTP_DEPTH="0", login=LOGIN, check=None)
        assert status == 207 and "/holder/open/" in body

        self.mkcol("/subscribed.ics/", SUBSCRIBED_MKCOL)
        self.mkcalendar("/calendar.ics/")
        status, _, body = self.request(
            "PROPFIND", "/subscribed.ics/",
            PROPFIND_ONE.format("<D:supported-report-set/>"),
            HTTP_DEPTH="0", login=LOGIN, check=None)
        assert status == 207 and "expand-property" in body
        assert "calendar-query" not in body
        assert "addressbook-query" not in body
        status, _, body = self.request(
            "PROPFIND", "/calendar.ics/",
            PROPFIND_ONE.format("<D:supported-report-set/>"),
            HTTP_DEPTH="0", login=LOGIN, check=None)
        assert status == 207 and "calendar-query" in body

    def test_expand_skips_bad_values_and_duplicate_master(self, monkeypatch, caplog):
        self.mkcalendar("/calendar.ics/")
        self.put("/calendar.ics/plain.ics", _event(
            uid="plain", summary="Plain",
            start="20130301T100000Z", end="20130301T110000Z"))
        self.put("/calendar.ics/bad.ics", (
            "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\n"
            "UID:bad\r\nDTSTAMP:20130101T000000Z\r\n"
            "DTSTART:20130301T120000Z\r\nSUMMARY:BadStart\r\n"
            "END:VEVENT\r\nEND:VCALENDAR\r\n"))
        self.put("/calendar.ics/odd.ics", _event(
            uid="odd", summary="Odd",
            start="20130301T130000Z", end="20130301T140000Z"))
        self.put("/calendar.ics/bare.ics", (
            "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\n"
            "UID:bare\r\nDTSTAMP:20130101T000000Z\r\n"
            "DTSTART:20130304T100000Z\r\nDTEND:20130304T110000Z\r\n"
            "EXDATE:20130304T100000Z\r\nSUMMARY:BareEx\r\n"
            "END:VEVENT\r\nEND:VCALENDAR\r\n"))
        self.put("/calendar.ics/twin.ics", _event(
            uid="twin", summary="Twin",
            start="20130301T150000Z", end="20130301T160000Z"))
        self.put("/calendar.ics/dateend.ics", (
            "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\n"
            "UID:dateend\r\nDTSTAMP:20130101T000000Z\r\n"
            "DTSTART:20130305T100000Z\r\nDTEND:20130305T110000Z\r\n"
            "RRULE:FREQ=DAILY;COUNT=1\r\nSUMMARY:DateEnd\r\n"
            "END:VEVENT\r\nEND:VCALENDAR\r\n"))
        expand = (
            "<?xml version='1.0' encoding='utf-8'?>"
            "<C:calendar-query xmlns:D='DAV:' "
            "xmlns:C='urn:ietf:params:xml:ns:caldav'>"
            "<D:prop><C:calendar-data><C:expand start='20130301T000000Z' "
            "end='20130310T000000Z'/></C:calendar-data></D:prop>"
            "<C:filter><C:comp-filter name='VCALENDAR'>"
            "<C:comp-filter name='VEVENT'>"
            "<C:time-range start='20130301T000000Z' end='20130310T000000Z'/>"
            "</C:comp-filter></C:comp-filter></C:filter>"
            "</C:calendar-query>")
        original_filtered = Collection.get_filtered
        original_serialize = radicale_item.Item.serialize

        def filtering(mutator):
            def wrapped(collection, filters):
                for item, flag in original_filtered(collection, filters):
                    vevent = getattr(item.vobject_item, "vevent", None)
                    if vevent is not None:
                        mutator(vevent)
                    yield item, flag
            return wrapped

        def serialize_then(adjust):
            def wrapped(item, *args, **kwargs):
                text = original_serialize(item, *args, **kwargs)
                vevent = getattr(item.vobject_item, "vevent", None)
                if vevent is not None:
                    adjust(vevent)
                return text
            return wrapped

        def bad_string(vevent):
            if vevent.uid.value == "bad":
                vevent.dtstart.value = "not-a-date"

        monkeypatch.setattr(
            radicale_item.Item, "serialize", serialize_then(bad_string))
        caplog.set_level(logging.WARNING)
        status, _, body = self.request(
            "REPORT", "/calendar.ics/", expand, check=None)
        assert status == 207 and "Plain" in body and "BadStart" not in body
        assert "Invalid DTSTART format" in "\n".join(caplog.messages)
        monkeypatch.undo()

        def valid_string(vevent):
            if vevent.uid.value == "bad":
                vevent.dtstart.value = "20120101T120000Z"

        monkeypatch.setattr(
            radicale_item.Item, "serialize", serialize_then(valid_string))
        caplog.clear()
        status, _, body = self.request(
            "REPORT", "/calendar.ics/", expand, check=None)
        assert status == 207 and "Plain" in body and "BadStart" not in body
        assert "Invalid DTSTART format" not in "\n".join(caplog.messages)
        monkeypatch.undo()

        def serialize_odd(item, *args, **kwargs):
            text = original_serialize(item, *args, **kwargs)
            vevent = getattr(item.vobject_item, "vevent", None)
            if vevent is not None and vevent.uid.value == "odd":
                vevent.dtstart.value = 5
                del vevent.dtend
            return text

        monkeypatch.setattr(radicale_item.Item, "serialize", serialize_odd)
        status, _, body = self.request(
            "REPORT", "/calendar.ics/", expand, check=None)
        assert status == 207 and "Plain" in body and "Odd" not in body
        monkeypatch.undo()
        status, _, body = self.request(
            "REPORT", "/calendar.ics/", expand, check=None)
        assert status == 207 and "Odd" in body

        def bare_exdate(vevent):
            if vevent.uid.value != "bare":
                return
            vevent.exdate.value = vevent.exdate.value[0]
            vevent.dtstart.value = datetime.datetime(
                2012, 1, 1, 10, tzinfo=datetime.timezone.utc)
            vevent.dtend.value = datetime.datetime(
                2012, 1, 1, 11, tzinfo=datetime.timezone.utc)

        monkeypatch.setattr(Collection, "get_filtered", filtering(bare_exdate))
        status, _, body = self.request(
            "REPORT", "/calendar.ics/", expand, check=None)
        assert status == 207 and "Plain" in body and "BareEx" not in body
        monkeypatch.undo()

        def second_master(collection, filters):
            for item, flag in original_filtered(collection, filters):
                vevent = getattr(item.vobject_item, "vevent", None)
                if vevent is not None and vevent.uid.value == "twin":
                    extra = vevent.duplicate(vevent)
                    extra.summary.value = "SecondMaster"
                    item.vobject_item.add(extra)
                yield item, flag

        monkeypatch.setattr(Collection, "get_filtered", second_master)
        status, _, body = self.request(
            "REPORT", "/calendar.ics/", expand, check=None)
        assert status == 400 and body == BAD_REQUEST
        monkeypatch.undo()
        status, _, body = self.request(
            "REPORT", "/calendar.ics/", expand, check=None)
        assert status == 207 and "Twin" in body and "SecondMaster" not in body

        import vobject

        original_rules = vobject.icalendar.RecurringComponent.getrruleset

        def rules_then_date(component, *args, **kwargs):
            rules = original_rules(component, *args, **kwargs)
            if getattr(getattr(component, "uid", None), "value", None) == "dateend":
                component.dtend.value = datetime.date(2013, 3, 5)
            return rules

        monkeypatch.setattr(
            vobject.icalendar.RecurringComponent, "getrruleset", rules_then_date)
        status, _, body = self.request(
            "REPORT", "/calendar.ics/", expand, check=None)
        assert status == 207 and "DateEnd" in body
        monkeypatch.undo()

        self.mkcalendar("/repeat.ics/")
        self.put("/repeat.ics/cached.ics", (
            "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\n"
            "UID:cached\r\nDTSTAMP:20130101T000000Z\r\n"
            "DTSTART:20130301T100000Z\r\nDTEND:20130301T110000Z\r\n"
            "RRULE:FREQ=DAILY;COUNT=3\r\nSUMMARY:Cached\r\n"
            "END:VEVENT\r\nEND:VCALENDAR\r\n"))

        class _Ex(datetime.datetime):
            pass

        def subclass_exdate(vevent):
            if vevent.uid.value != "cached":
                return
            stamp = _Ex(2013, 3, 2, 10, 0, tzinfo=datetime.timezone.utc)
            vevent.add("exdate").value = [stamp]

        monkeypatch.setattr(
            Collection, "get_filtered", filtering(subclass_exdate))
        status, _, body = self.request(
            "REPORT", "/repeat.ics/", expand, check=None)
        assert status == 207 and "Cached" in body
        assert body.upper().count("BEGIN:VEVENT") == 2
        monkeypatch.undo()
        status, _, body = self.request(
            "REPORT", "/repeat.ics/", expand, check=None)
        assert status == 207 and body.upper().count("BEGIN:VEVENT") == 3

    def test_put_tagged_parent_skips_collection_warning(self, caplog):
        self.mkcalendar("/cal.ics/")
        self.application._storage.create_collection(
            "/cal.ics/inner/", props={"tag": "VCALENDAR"})
        self.application._storage.create_collection(
            "/cal.ics/open/", props={"tag": "VCALENDAR"})
        _set_rights(self, (
            "[inner]\nuser: .*\ncollection: cal\\.ics/inner\npermissions: W\n"
            "[open]\nuser: .*\ncollection: cal\\.ics/open\npermissions: w\n"
            "[parent]\nuser: .*\ncollection: cal\\.ics\npermissions: R\n"
            "[rest]\nuser: .*\ncollection: .*\npermissions: RrWw\n"))
        caplog.set_level(logging.WARNING)
        status, _, body = self.request(
            "PUT", "/cal.ics/inner/",
            _event(uid="nested", summary="Nested"),
            content_type="text/calendar", login=LOGIN, check=None)
        assert status == 403 and body == ACCESS_FORBIDDEN
        assert "Not a collection" not in "\n".join(caplog.messages)
        _grant(self)
        status, text = self.get("/cal.ics/inner/")
        assert status == 200 and "Nested" not in text
        _set_rights(self, (
            "[open]\nuser: .*\ncollection: cal\\.ics/open\npermissions: w\n"
            "[parent]\nuser: .*\ncollection: cal\\.ics\npermissions: R\n"
            "[rest]\nuser: .*\ncollection: .*\npermissions: RrWw\n"))
        status, _, body = self.request(
            "PUT", "/cal.ics/open/",
            _event(uid="opened", summary="Opened"),
            content_type="text/calendar", check=None)
        assert status == 201 and body == ""
        _grant(self)
        assert "Opened" in self.get("/cal.ics/open/")[1]


class TestCovAppSharing(BaseTest):
    """Sharing paths exercised through the real handlers."""

    def setup_method(self):
        super().setup_method()
        self.htpasswd = os.path.join(self.colpath, ".htpasswd")
        with open(self.htpasswd, "w") as handle:
            handle.write("owner:ownerpw\nuser:userpw\n")
        _grant(self)
        self._enable_sharing()

    def _enable_sharing(self, rights_type="owner_only", rights_text=None):
        if rights_text:
            path = os.path.join(self.colpath, "rights")
            with open(path, "w") as handle:
                handle.write(rights_text)
            rights = {"type": "from_file", "file": path}
        else:
            rights = {"type": rights_type}
        self.configure({
            "auth": {"type": "htpasswd", "htpasswd_filename": self.htpasswd,
                     "htpasswd_encryption": "plain", "delay": "0"},
            "rights": rights,
            "sharing": {
                "type": "csv",
                "collection_by_map": "True",
                "collection_by_token": "True",
                "permit_create_map": "True",
                "permit_create_token": "True",
                "permit_properties_overlay": "False",
                "enforce_properties_overlay": "True",
            },
            "server": {"delay_on_error": "0"},
        })

    def _api(self, kind, action, payload, login, check=200):
        status, _, body = self.request(
            "POST", "/.sharing/v1/%s/%s" % (kind, action),
            json.dumps(payload), login=login,
            content_type="application/json", HTTP_ACCEPT="application/json",
            check=None)
        assert status == check, body
        return body

    def _map(self, mapped, token, user="user", permissions="r",
             owner_login="owner:ownerpw", user_login="user:userpw",
             properties=None, conversion=None):
        payload = {
            "User": user,
            "PathMapped": mapped,
            "PathOrToken": token,
            "Permissions": permissions,
            "Enabled": True,
            "Hidden": False,
        }
        if properties:
            payload["Properties"] = properties
        if conversion:
            payload["Conversion"] = conversion
        body = self._api("map", "create", payload, owner_login)
        assert "success" in body
        self._api("map", "enable", {"PathOrToken": token}, owner_login)
        self._api("map", "enable", {"PathOrToken": token}, user_login)
        self._api("map", "unhide", {"PathOrToken": token}, user_login)
        return token

    def _retarget(self, old_token, new_token):
        path = os.path.join(self.colpath, "collection-db", "sharing.csv")
        text = open(path, encoding="utf-8").read()
        assert old_token in text
        text = text.replace(old_token, new_token)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        self.configure({})

    def _rewrite_row(self, token, permissions=None, properties=None,
                     path_mapped=None):
        path = os.path.join(self.colpath, "collection-db", "sharing.csv")
        with open(path, encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle, delimiter=";")
            fieldnames = reader.fieldnames
            rows = list(reader)
        found = False
        for row in rows:
            if row["PathOrToken"] != token:
                continue
            found = True
            if permissions is not None:
                row["Permissions"] = permissions
            if path_mapped is not None:
                row["PathMapped"] = path_mapped
            if properties is not None:
                current = ast.literal_eval(row["Properties"]) if row["Properties"] else {}
                current.update(properties)
                row["Properties"] = repr(current)
        assert found, token
        with open(path, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle, fieldnames=fieldnames, delimiter=";")
            writer.writeheader()
            writer.writerows(rows)
        self.configure({})

    def test_user_format_group_boundaries(self):
        self.mkcalendar("/owner/cal.ics/", login="owner:ownerpw")
        base = {
            "PathMapped": "/owner/cal.ics/",
            "PathOrToken": "/user/shared/",
            "Permissions": "r",
        }
        self.configure({"server": {"validate_user_value": "strict",
                                   "delay_on_error": "0"}})
        body = self._api("map", "create", dict(base, User=":bad name"),
                         "owner:ownerpw", check=400)
        assert "Invalid value for User" in body
        body = self._api(
            "map", "create",
            dict(base, User=":g1", PathOrToken="/{user}/g1/"),
            "owner:ownerpw")
        assert "success" in body
        assert "Invalid value for User" not in body
        body = self._api("map", "create", dict(base, User="alice:"),
                         "owner:ownerpw", check=400)
        assert "Invalid value for User" in body

        self.configure({"server": {"validate_user_value": "minimal",
                                   "delay_on_error": "0"}})
        with _Level(logging.INFO):
            body = self._api("map", "create", dict(base, User=":bad*"),
                             "owner:ownerpw", check=400)
            assert "Invalid value for User" in body
            self.mkcalendar("/owner/cal2.ics/", login="owner:ownerpw")
            body = self._api(
                "map", "create",
                dict(base, User=":g1,g2", PathMapped="/owner/cal2.ics/",
                     PathOrToken="/{user}/g1g2/"),
                "owner:ownerpw")
            assert "success" in body
            assert "Invalid value for User" not in body

    def test_overlap_skip_preserves_owner_rights(self, caplog):
        self.mkcalendar("/owner/cal.ics/", login="owner:ownerpw")
        self.put("/owner/cal.ics/event.ics", _event(summary="Owned"),
                 login="owner:ownerpw")
        self._map("/owner/cal.ics/", "/owner/alias/", user="owner",
                  permissions="w", user_login="owner:ownerpw")
        self._retarget("/owner/alias/", "/owner/cal.ics/")
        caplog.set_level(logging.TRACE)
        with _Level(logging.TRACE):
            status, body = self.get("/owner/cal.ics/", login="owner:ownerpw")
        assert status == 200 and "Owned" in body
        assert "skip overlap mapping" in "\n".join(caplog.messages)
        caplog.clear()
        with _Level(logging.INFO):
            status, body = self.get("/owner/cal.ics/", login="owner:ownerpw")
        assert status == 200 and "Owned" in body
        assert "skip overlap mapping" not in "\n".join(caplog.messages)
        caplog.clear()
        with _Level(logging.INFO):
            status, _, answer = self.request(
                "PROPFIND", "/owner/cal.ics/",
                PROPFIND_ONE.format("<D:displayname/>"),
                HTTP_DEPTH="0", login="owner:ownerpw", check=None)
        assert status == 207 and "cal.ics" in answer
        assert "skip overlap mapping" not in "\n".join(caplog.messages)
        caplog.clear()
        with _Level(logging.TRACE):
            status, _, body = self.request(
                "PUT", "/owner/cal.ics/event.ics", _event(summary="Traced"),
                login="owner:ownerpw", check=None)
        assert status in (201, 204), body
        assert "Traced" in self.get("/owner/cal.ics/event.ics",
                                    login="owner:ownerpw")[1]
        assert "skip overlap mapping" in "\n".join(caplog.messages)
        caplog.clear()
        with _Level(logging.INFO):
            status, _, body = self.request(
                "PUT", "/owner/cal.ics/event.ics", _event(summary="Updated"),
                login="owner:ownerpw", check=None)
        assert status in (201, 204), body
        assert "skip overlap mapping" not in "\n".join(caplog.messages)
        assert "Updated" in self.get("/owner/cal.ics/event.ics",
                                     login="owner:ownerpw")[1]
        caplog.clear()
        with _Level(logging.TRACE):
            status, _, body = self.request(
                "PROPPATCH", "/owner/cal.ics/", PROPPATCH_NAME % "TracedName",
                login="owner:ownerpw", check=None)
        assert status == 207 and "displayname" in body
        assert "skip overlap mapping" in "\n".join(caplog.messages)
        caplog.clear()
        with _Level(logging.INFO):
            status, _, body = self.request(
                "PROPPATCH", "/owner/cal.ics/", PROPPATCH_NAME % "OwnerName",
                login="owner:ownerpw", check=None)
        assert status == 207 and "displayname" in body
        assert "skip overlap mapping" not in "\n".join(caplog.messages)
        assert "Updated" in self.get("/owner/cal.ics/event.ics",
                                     login="owner:ownerpw")[1]
        report = (
            "<?xml version='1.0' encoding='utf-8'?>"
            "<C:calendar-query xmlns:D='DAV:' "
            "xmlns:C='urn:ietf:params:xml:ns:caldav'>"
            "<D:prop><D:getetag/></D:prop></C:calendar-query>")
        caplog.clear()
        with _Level(logging.TRACE):
            status, _, body = self.request(
                "REPORT", "/owner/cal.ics/", report,
                login="owner:ownerpw", check=None)
        assert status == 207 and "event.ics" in body
        assert "skip overlap mapping" in "\n".join(caplog.messages)
        caplog.clear()
        with _Level(logging.INFO):
            status, _, body = self.request(
                "REPORT", "/owner/cal.ics/", report,
                login="owner:ownerpw", check=None)
        assert status == 207 and "event.ics" in body
        assert "skip overlap mapping" not in "\n".join(caplog.messages)
        self.mkcalendar("/owner/other.ics/", login="owner:ownerpw")
        self.put("/owner/cal.ics/stay.ics", _event(uid="stay", summary="Stay"),
                 login="owner:ownerpw")
        caplog.clear()
        with _Level(logging.TRACE):
            status, _, body = self.request(
                "MOVE", "/owner/cal.ics/stay.ics",
                HTTP_DESTINATION="http://127.0.0.1/owner/other.ics/stay.ics",
                login="owner:ownerpw", check=None)
        assert status in (201, 204), body
        assert "Stay" in self.get("/owner/other.ics/stay.ics",
                                  login="owner:ownerpw")[1]
        assert "skip overlap mapping" in "\n".join(caplog.messages)
        caplog.clear()
        with _Level(logging.INFO):
            status, _, body = self.request(
                "MOVE", "/owner/cal.ics/event.ics",
                HTTP_DESTINATION="http://127.0.0.1/owner/other.ics/event.ics",
                login="owner:ownerpw", check=None)
        assert status in (201, 204), body
        assert "skip overlap mapping" not in "\n".join(caplog.messages)
        assert "Updated" in self.get(
            "/owner/other.ics/event.ics", login="owner:ownerpw")[1]

    def test_share_propfind_principal_overlay_and_depth(self):
        self.mkcalendar("/owner/cal.ics/", login="owner:ownerpw")
        self.put("/owner/cal.ics/event.ics", _event(summary="Shared"),
                 login="owner:ownerpw")
        self._map("/owner/cal.ics/", "/user/shared/", permissions="r",
                  properties={"D:displayname": "Overlay"})
        status, _, body = self.request(
            "PROPFIND", "/user/shared/",
            PROPFIND_ONE.format(
                "<D:displayname/><RADICALE:displayname/>"
                "<D:current-user-principal/>"),
            HTTP_DEPTH="0", login="user:userpw", check=None)
        assert status == 207
        assert "Overlay" in body
        assert "/user/" in body
        status, _, body = self.request(
            "PROPFIND", "/user/",
            PROPFIND_ONE.format("<D:resourcetype/>"),
            HTTP_DEPTH="1", login="user:userpw", check=None)
        assert status == 207 and "/user/shared/" in body

        self._map("/owner/", "/user/owner-home/", permissions="Rr")
        status, _, body = self.request(
            "PROPFIND", "/user/owner-home/",
            PROPFIND_ONE.format("<D:principal-URL/>"),
            HTTP_DEPTH="0", login="user:userpw", check=None)
        assert status == 207
        assert "/user/owner-home/" in body

    def test_proppatch_share_overlay_matrix(self, monkeypatch):
        self.mkcalendar("/owner/cal.ics/", login="owner:ownerpw")
        token = self._map("/owner/cal.ics/", "/user/shared/", permissions="rP")
        with _Level(logging.INFO):
            status, _, body = self.request(
                "PROPPATCH", token, PROPPATCH_NAME % "FromShare",
                login="user:userpw", check=None)
        assert status == 207 and "displayname" in body
        owner = self.request(
            "PROPFIND", "/owner/cal.ics/",
            PROPFIND_ONE.format("<D:displayname/>"),
            HTTP_DEPTH="0", login="owner:ownerpw", check=None)[2]
        assert "FromShare" not in owner
        shared = self.request(
            "PROPFIND", token, PROPFIND_ONE.format("<D:displayname/>"),
            HTTP_DEPTH="0", login="user:userpw", check=None)[2]
        assert "FromShare" in shared

        self.mkcalendar("/owner/blocked.ics/", login="owner:ownerpw")
        self._map("/owner/blocked.ics/", "/user/blocked-e/", permissions="rPe")
        status, _, body = self.request(
            "PROPPATCH", "/user/blocked-e/", PROPPATCH_NAME % "NoE",
            login="user:userpw", check=None)
        assert status == 403 and body == ACCESS_FORBIDDEN
        assert "NoE" not in self.request(
            "PROPFIND", "/user/blocked-e/",
            PROPFIND_ONE.format("<D:displayname/>"),
            HTTP_DEPTH="0", login="user:userpw", check=None)[2]

        self.mkcalendar("/owner/cal2.ics/", login="owner:ownerpw")
        self._enable_sharing(rights_text=(
            "[cal]\nuser: owner\ncollection: owner/cal2\\.ics\npermissions: re\n"
            "[all]\nuser: .*\ncollection: .*\npermissions: RrWw\n"))
        self._map("/owner/cal2.ics/", "/user/rights-e/", permissions="rP")
        status, _, body = self.request(
            "PROPPATCH", "/user/rights-e/", PROPPATCH_NAME % "RightsE",
            login="user:userpw", check=None)
        assert status == 403 and body == ACCESS_FORBIDDEN

        self._enable_sharing(rights_text=(
            "[cal]\nuser: owner\ncollection: owner/cal3\\.ics\npermissions: rwp\n"
            "[all]\nuser: .*\ncollection: .*\npermissions: RrWw\n"))
        self.mkcalendar("/owner/cal3.ics/", login="owner:ownerpw")
        self._map("/owner/cal3.ics/", "/user/rights-p/", permissions="rw")
        status, _, body = self.request(
            "PROPPATCH", "/user/rights-p/", PROPPATCH_NAME % "RightsP",
            login="user:userpw", check=None)
        assert status == 403 and ACCESS_FORBIDDEN in body
        assert "RightsP" not in self.get("/owner/cal3.ics/", login="owner:ownerpw")[1]

        def fail_update(**_kwargs):
            raise ValueError("failed [Errno %d]" % errno.EIO)

        self._enable_sharing()
        self.mkcalendar("/owner/cal4.ics/", login="owner:ownerpw")
        self._map("/owner/cal4.ics/", "/user/errno/", permissions="rP")
        monkeypatch.setattr(
            self.application._sharing, "sharing_collection_update", fail_update)
        status, _, body = self.request(
            "PROPPATCH", "/user/errno/", PROPPATCH_NAME % "Disk",
            login="user:userpw", check=None)
        assert status == 500 and body == SERVER_ERROR

    def test_bday_share_skips_contacts_without_birthday(self):
        self.create_addressbook("/owner/book/", login="owner:ownerpw")
        self.put("/owner/book/plain.vcf", get_file_content("contact1.vcf"),
                 login="owner:ownerpw")
        self.put("/owner/book/bday.vcf",
                 get_file_content("contact2-with-bday.vcf"),
                 login="owner:ownerpw")
        self._map("/owner/book/", "/user/birthdays/", permissions="r",
                  conversion="bday")
        status, _, body = self.request(
            "PROPFIND", "/user/birthdays/",
            PROPFIND_ONE.format("<D:getetag/><D:displayname/>"),
            HTTP_DEPTH="1", login="user:userpw", check=None)
        assert status == 207
        assert "bday.ics" in body
        assert "plain" not in body
        status, _, body = self.request(
            "GET", "/user/birthdays/plain.ics", login="user:userpw", check=None)
        assert status == 404 and body == NOT_FOUND
        status, body = self.get(
            "/user/birthdays/bday.ics", login="user:userpw")
        assert status == 200 and "VEVENT" in body

    def test_delete_through_share_with_encoded_prefix(self):
        self.mkcalendar("/owner/cal.ics/", login="owner:ownerpw")
        self.put("/owner/cal.ics/event.ics", _event(summary="Gone"),
                 login="owner:ownerpw")
        self._map("/owner/cal.ics/", "/user/shared/", permissions="rw")
        with _Level(logging.INFO):
            status, _, body = self.request(
                "DELETE", "/user/shared/event.ics",
                SCRIPT_NAME="/a:b", login="user:userpw", check=None)
        assert status == 200 and "multistatus" in body
        assert self.get("/owner/cal.ics/event.ics",
                        login="owner:ownerpw", check=404)[0] == 404

    def test_read_only_share_cannot_write_owner_still_can(self):
        self.mkcalendar("/owner/cal.ics/", login="owner:ownerpw")
        self.put("/owner/cal.ics/event.ics", _event(summary="Stay"),
                 login="owner:ownerpw")
        self._map("/owner/cal.ics/", "/user/shared/", permissions="r")
        status, _, body = self.request(
            "PUT", "/user/shared/event.ics", _event(summary="Hijack"),
            login="user:userpw", check=None)
        assert status == 403 and body == ACCESS_FORBIDDEN
        assert "Stay" in self.get("/owner/cal.ics/event.ics",
                                  login="owner:ownerpw")[1]
        status, _, body = self.request(
            "DELETE", "/user/shared/", login="user:userpw", check=None)
        assert status == 403 and body == ACCESS_FORBIDDEN
        assert "BEGIN:VCALENDAR" in self.get(
            "/owner/cal.ics/", login="owner:ownerpw")[1]

    def test_depth_filters_and_overlay_write_edges(self, monkeypatch, caplog):
        self.mkcalendar("/owner/cal.ics/", login="owner:ownerpw")
        self.put("/owner/cal.ics/event.ics", _event(summary="Listed"),
                 login="owner:ownerpw")
        self._map("/owner/cal.ics/", "/user/shared/", permissions="r")
        self.mkcalendar("/owner/hidden.ics/", login="owner:ownerpw")
        self._map("/owner/hidden.ics/", "/user/hidden/", permissions="w")
        self.mkcalendar("/owner/same.ics/", login="owner:ownerpw")
        self._map("/owner/same.ics/", "/owner/alias/", user="owner",
                  permissions="r", user_login="owner:ownerpw")

        status, _, body = self.request(
            "PROPFIND", "/owner/",
            PROPFIND_ONE.format("<D:resourcetype/>"),
            HTTP_DEPTH="1", login="owner:ownerpw", check=None)
        assert status == 207 and "/owner/cal.ics/" in body
        assert "/user/shared/" not in body
        assert "/owner/alias/" not in body

        with _Level(logging.INFO):
            status, _, body = self.request(
                "PROPFIND", "/user/",
                PROPFIND_ONE.format("<D:resourcetype/>"),
                HTTP_DEPTH="1", login="user:userpw", check=None)
        assert status == 207 and "/user/shared/" in body
        assert "/user/hidden/" not in body

        self._enable_sharing(rights_text=(
            "[cal]\nuser: owner\ncollection: owner/locked\\.ics\npermissions: rwl\n"
            "[all]\nuser: .*\ncollection: .*\npermissions: RrWw\n"))
        self.mkcalendar("/owner/locked.ics/", login="owner:ownerpw")
        self._map("/owner/locked.ics/", "/user/locked/", permissions="rP")
        status, _, body = self.request(
            "PROPPATCH", "/user/locked/", PROPPATCH_NAME % "LockedName",
            login="user:userpw", check=None)
        assert status == 403 and body == ACCESS_FORBIDDEN
        owner = self.request(
            "PROPFIND", "/owner/locked.ics/",
            PROPFIND_ONE.format("<D:displayname/>"),
            HTTP_DEPTH="0", login="owner:ownerpw", check=None)[2]
        assert "LockedName" not in owner

        self._enable_sharing(rights_text=(
            "[cal]\nuser: owner\ncollection: owner/native\\.ics\npermissions: rwe\n"
            "[all]\nuser: .*\ncollection: .*\npermissions: RrWw\n"))
        self.mkcalendar("/owner/native.ics/", login="owner:ownerpw")
        self._map("/owner/native.ics/", "/user/native/", permissions="rw")
        caplog.set_level(logging.INFO)
        status, _, body = self.request(
            "PROPPATCH", "/user/native/", PROPPATCH_NAME % "NativeName",
            login="user:userpw", check=None)
        assert status == 207 and "displayname" in body
        assert "disabled by rights permission 'e'" in "\n".join(caplog.messages)
        owner = self.request(
            "PROPFIND", "/owner/native.ics/",
            PROPFIND_ONE.format("<D:displayname/>"),
            HTTP_DEPTH="0", login="owner:ownerpw", check=None)[2]
        assert "NativeName" in owner

        def fail_update(**_kwargs):
            raise ValueError("failed [Errno %d]" % errno.EACCES)

        self._enable_sharing()
        self.mkcalendar("/owner/errno.ics/", login="owner:ownerpw")
        self._map("/owner/errno.ics/", "/user/errno/", permissions="rP")
        monkeypatch.setattr(
            self.application._sharing, "sharing_collection_update", fail_update)
        status, _, body = self.request(
            "PROPPATCH", "/user/errno/", PROPPATCH_NAME % "Denied",
            login="user:userpw", check=None)
        assert status == 403 and body == ACTION_REFUSED
        shared = self.request(
            "PROPFIND", "/user/errno/",
            PROPFIND_ONE.format("<D:displayname/>"),
            HTTP_DEPTH="0", login="user:userpw", check=None)[2]
        assert "Denied" not in shared

        monkeypatch.undo()
        self._enable_sharing()
        self.mkcalendar("/owner/empty.ics/", login="owner:ownerpw")
        self._map("/owner/empty.ics/", "/user/empty/", permissions="rP")
        status, _, body = self.request(
            "PROPPATCH", "/user/empty/", "", login="user:userpw", check=None)
        assert status == 207 and "multistatus" in body
        assert "Denied" not in self.request(
            "PROPFIND", "/user/empty/",
            PROPFIND_ONE.format("<D:displayname/>"),
            HTTP_DEPTH="0", login="user:userpw", check=None)[2]

    def test_depth_prefix_item_share_and_privilege_edges(self):
        self._enable_sharing(rights_text=(
            "[all]\nuser: .*\ncollection: .*\npermissions: RrWw\n"))
        self.mkcalendar("/owner/cal.ics/", login="owner:ownerpw")
        self.put("/owner/cal.ics/event.ics", _event(summary="SharedItem"),
                 login="owner:ownerpw")
        self.mkcalendar("/owner/same.ics/", login="owner:ownerpw")
        self._map("/owner/same.ics/", "/owner/alias/", user="owner",
                  permissions="r", user_login="owner:ownerpw")
        self.mkcalendar("/user/mine.ics/", login="user:userpw")
        self.put("/user/mine.ics/local.ics", _event(summary="Local"),
                 login="user:userpw")
        self._map("/owner/cal.ics/", "/user/item/", permissions="r")
        path = os.path.join(self.colpath, "collection-db", "sharing.csv")
        text = open(path, encoding="utf-8").read()
        assert "/owner/cal.ics/" in text
        text = text.replace("/owner/cal.ics/", "/owner/cal.ics/event.ics", 1)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        self.configure({})

        with _Level(logging.INFO):
            status, _, body = self.request(
                "PROPFIND", "/owner/",
                PROPFIND_ONE.format("<D:resourcetype/>"),
                HTTP_DEPTH="1", login="owner:ownerpw", check=None)
        assert status == 207 and "/owner/same.ics/" in body
        assert "/owner/alias/" not in body
        with _Level(logging.INFO):
            status, _, body = self.request(
                "PROPFIND", "/user/",
                PROPFIND_ONE.format("<D:resourcetype/>"),
                HTTP_DEPTH="1", login="user:userpw", check=None)
        assert status == 207 and "/user/item/" in body
        assert "/user/mine.ics/" in body
        with _Level(logging.INFO):
            status, _, body = self.request(
                "PROPFIND", "/user/mine.ics/",
                PROPFIND_ONE.format("<D:resourcetype/>"),
                HTTP_DEPTH="1", login="user:userpw", check=None)
        assert status == 207 and "local.ics" in body
        assert "/user/item/" not in body

        self._enable_sharing()
        self.mkcalendar("/owner/listed.ics/", login="owner:ownerpw")
        self.put("/owner/listed.ics/event.ics", _event(summary="Listed"),
                 login="owner:ownerpw")
        self._map("/owner/listed.ics/", "/user/fresh/", permissions="r")
        path = os.path.join(self.colpath, "collection-db", "sharing.csv")
        text = open(path, encoding="utf-8").read()
        assert "/user/fresh/" in text
        text = text.replace("/user/fresh/", "/user/mine.ics/")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        self.configure({})
        with _Level(logging.INFO):
            status, _, body = self.request(
                "PROPFIND", "/user/",
                PROPFIND_ONE.format("<D:resourcetype/>"),
                HTTP_DEPTH="1", login="user:userpw", check=None)
        assert status == 207 and body.count("/user/mine.ics/") == 1
        assert "Listed" not in body

        self.mkcalendar("/owner/multi.ics/", login="owner:ownerpw")
        self.put("/owner/multi.ics/event.ics", _event(summary="Multi"),
                 login="owner:ownerpw")
        self._map("/owner/multi.ics/", "/user/shared/", permissions="r")
        multiget = (
            "<?xml version='1.0' encoding='utf-8'?>"
            "<C:calendar-multiget xmlns:D='DAV:' "
            "xmlns:C='urn:ietf:params:xml:ns:caldav'>"
            "<D:prop><D:getetag/></D:prop>"
            "<D:href>/user/shared/event.ics</D:href>"
            "<D:href>/user/shared/a/b.ics</D:href>"
            "<D:href>/user/other.ics</D:href>"
            "</C:calendar-multiget>")
        with _Level(logging.INFO):
            status, _, body = self.request(
                "REPORT", "/user/shared/", multiget,
                login="user:userpw", check=None)
        assert status == 207 and "event.ics" in body
        assert body.count("404") >= 1
        empty = multiget.replace(
            "<D:href>/user/shared/event.ics</D:href>"
            "<D:href>/user/shared/a/b.ics</D:href>"
            "<D:href>/user/other.ics</D:href>", "")
        status, _, body = self.request(
            "REPORT", "/user/shared/", empty,
            login="user:userpw", check=None)
        assert status == 207 and "event.ics" not in body

    def test_privilege_set_and_bday_reports(self):
        self.mkcalendar("/owner/cal.ics/", login="owner:ownerpw")
        self.mkcalendar("/owner/locked.ics/", login="owner:ownerpw")
        self._map("/owner/cal.ics/", "/user/props/", permissions="rP")
        self._map("/owner/locked.ics/", "/user/locked/", permissions="rPl")
        props = (
            "<D:current-user-privilege-set/>"
            "<D:supported-report-set/>")
        with _Level(logging.INFO):
            status, _, body = self.request(
                "PROPFIND", "/user/props/",
                PROPFIND_ONE.format(props),
                HTTP_DEPTH="0", login="user:userpw", check=None)
        assert status == 207 and "write-properties" in body
        assert "free-busy-query" in body
        with _Level(logging.INFO):
            status, _, body = self.request(
                "PROPFIND", "/user/locked/",
                PROPFIND_ONE.format(props),
                HTTP_DEPTH="0", login="user:userpw", check=None)
        assert status == 207 and "write-properties" not in body
        assert "read" in body

        self.create_addressbook("/owner/book/", login="owner:ownerpw")
        self.put("/owner/book/bday.vcf",
                 get_file_content("contact2-with-bday.vcf"),
                 login="owner:ownerpw")
        self._map("/owner/book/", "/user/birthdays/", permissions="r",
                  conversion="bday")
        with _Level(logging.INFO):
            status, _, body = self.request(
                "PROPFIND", "/user/birthdays/",
                PROPFIND_ONE.format(
                    "<D:supported-report-set/><D:getcontentlength/>"),
                HTTP_DEPTH="0", login="user:userpw", check=None)
        assert status == 207
        assert "calendar-query" in body
        assert "free-busy-query" not in body
        assert "addressbook-query" not in body
        assert "getcontentlength" in body
        with _Level(logging.INFO):
            status, _, body = self.request(
                "PROPFIND", "/user/birthdays/",
                PROPFIND_ONE.format(
                    "<D:getcontentlength/><RADICALE:getcontentcount/>"),
                HTTP_DEPTH="1", login="user:userpw", check=None)
        assert status == 207 and "getcontentlength" in body
        assert "getcontentcount" in body and ">0<" not in body
        query = (
            "<?xml version='1.0' encoding='utf-8'?>"
            "<C:calendar-query xmlns:D='DAV:' "
            "xmlns:C='urn:ietf:params:xml:ns:caldav'>"
            "<D:prop><C:calendar-data/></D:prop>"
            "<C:filter><C:comp-filter name='VCALENDAR'>"
            "<C:comp-filter name='VEVENT'/></C:comp-filter></C:filter>"
            "</C:calendar-query>")
        with _Level(logging.INFO):
            status, _, body = self.request(
                "REPORT", "/user/birthdays/", query,
                login="user:userpw", check=None)
        assert status == 207 and "BEGIN:VEVENT" in body.upper()

        self.mkcalendar("/owner/ro.ics/", login="owner:ownerpw")
        self.mkcalendar("/owner/rw.ics/", login="owner:ownerpw")
        self._enable_sharing(rights_text=(
            "[ro]\nuser: owner\ncollection: owner/ro\\.ics\npermissions: r\n"
            "[all]\nuser: .*\ncollection: .*\npermissions: RrWw\n"))
        self._map("/owner/ro.ics/", "/user/ro/", permissions="rw")
        self._map("/owner/rw.ics/", "/user/rw/", permissions="rw",
                  properties={"C:calendar-description": "SharedDesc",
                              "D:displayname": "SharedName"})
        priv = PROPFIND_ONE.format("<D:current-user-privilege-set/>")
        status, _, body = self.request(
            "PROPFIND", "/user/ro/", priv,
            HTTP_DEPTH="0", login="user:userpw", check=None)
        assert status == 207 and "read" in body and "write-content" not in body
        status, _, body = self.request(
            "PROPFIND", "/user/rw/", priv,
            HTTP_DEPTH="0", login="user:userpw", check=None)
        assert status == 207 and "write-content" in body
        with _Level(logging.INFO):
            status, _, body = self.request(
                "PROPFIND", "/user/rw/",
                PROPFIND_ONE.format(
                    "<D:displayname/><C:calendar-description/>"),
                HTTP_DEPTH="0", login="user:userpw", check=None)
        assert status == 207 and "SharedName" in body and "SharedDesc" in body

    def test_null_overlay_bday_write_and_unconverted_item(self):
        self.mkcalendar("/owner/shown.ics/", login="owner:ownerpw")
        description = (
            "<?xml version='1.0' encoding='utf-8'?>"
            "<D:propertyupdate xmlns:D='DAV:' "
            "xmlns:C='urn:ietf:params:xml:ns:caldav'>"
            "<D:set><D:prop><C:calendar-description>NativeDesc"
            "</C:calendar-description></D:prop></D:set>"
            "</D:propertyupdate>")
        self.request(
            "PROPPATCH", "/owner/shown.ics/", description,
            login="owner:ownerpw")
        self._map(
            "/owner/shown.ics/", "/user/shown/", permissions="r",
            properties={"D:displayname": "OverlayName",
                        "C:calendar-description": "Sentinel"})
        self._rewrite_row(
            "/user/shown/",
            properties={"C:calendar-description": None})
        with _Level(logging.INFO):
            status, _, body = self.request(
                "PROPFIND", "/user/shown/",
                PROPFIND_ONE.format(
                    "<RADICALE:displayname/><C:calendar-description/>"),
                HTTP_DEPTH="0", login="user:userpw", check=None)
        assert status == 207 and "OverlayName" in body and "NativeDesc" in body
        assert "Sentinel" not in body

        self.create_addressbook("/owner/people/", login="owner:ownerpw")
        self.put("/owner/people/nobday.vcf", _vcard(uid="nobday", fn="NoDay"),
                 login="owner:ownerpw")
        self.put("/owner/people/bday.vcf",
                 get_file_content("contact2-with-bday.vcf"),
                 login="owner:ownerpw")
        self._map("/owner/people/", "/user/birthdays/", permissions="r",
                  conversion="bday")
        self._rewrite_row("/user/birthdays/", permissions="rw")
        status, _, body = self.request(
            "PROPFIND", "/user/birthdays/",
            PROPFIND_ONE.format("<D:current-user-privilege-set/>"),
            HTTP_DEPTH="0", login="user:userpw", check=None)
        assert status == 207 and "read" in body
        assert "write-content" not in body

        self._map("/owner/", "/user/principal/", permissions="Rr")
        status, responses = self.propfind(
            "/user/",
            PROPFIND_ONE.format("<D:principal-URL/>"),
            HTTP_DEPTH="1", login="user:userpw")
        principal = responses["/user/principal/"]["D:principal-URL"]
        assert principal[0] == 200
        href = principal[1].find(xmlutils.make_clark("D:href"))
        assert href is not None and href.text == "/user/"
        assert "/user/principal//user/" not in "".join(
            principal[1].itertext())

        self.create_addressbook("/owner/nonebook/", login="owner:ownerpw")
        self.create_addressbook("/owner/somebook/", login="owner:ownerpw")
        self.put("/owner/nonebook/nobday.vcf",
                 _vcard(uid="nobday-item", fn="NoDayItem"),
                 login="owner:ownerpw")
        self.put("/owner/somebook/bday.vcf",
                 get_file_content("contact2-with-bday.vcf"),
                 login="owner:ownerpw")
        self._map("/owner/nonebook/", "/user/nobday/", permissions="r",
                  conversion="bday")
        self._map("/owner/somebook/", "/user/yesbday/", permissions="r",
                  conversion="bday")
        self._rewrite_row(
            "/user/nobday/", path_mapped="/owner/nonebook/nobday.vcf")
        self._rewrite_row(
            "/user/yesbday/", path_mapped="/owner/somebook/bday.vcf")
        self._enable_sharing(rights_text=(
            "[all]\nuser: .*\ncollection: .*\npermissions: RrWw\n"))
        status, responses = self.propfind(
            "/user/",
            PROPFIND_ONE.format("<D:getetag/><D:getcontentlength/>"),
            HTTP_DEPTH="1", login="user:userpw")
        missing = responses["/user/nobday/"]
        assert missing["D:getetag"][0] == 404
        assert missing["D:getcontentlength"][0] == 404
        present = responses["/user/yesbday/"]
        assert present["D:getetag"][0] == 200
        assert present["D:getcontentlength"][0] == 200
        assert present["D:getcontentlength"][1].text not in (None, "", "0")
