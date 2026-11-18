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

"""Outcome tests for DELETE, MOVE, and PUT."""

import cProfile
import errno
import logging
import os
import socket
import wsgiref.util
from io import BytesIO

import pytest

import radicale.item as radicale_item
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


class Hook:
    """Recording hook loaded as radicale.tests.test_cov_app_write."""

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

        self.configure({"hook": {"type": "radicale.tests.test_cov_app_write"}})
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
