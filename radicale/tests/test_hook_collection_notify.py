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

"""A whole-collection PUT tells the hook about each stored item."""

import cProfile
import os
import socket
import wsgiref.util
from io import BytesIO

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
    """Recording hook loaded as radicale.tests.test_hook_collection_notify."""

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


def _calendar(uid, summary):
    return (
        "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\n"
        "UID:%s\r\nSUMMARY:%s\r\n"
        "DTSTART:20130901T160000Z\r\nDTEND:20130901T170000Z\r\n"
        "END:VEVENT\r\nEND:VCALENDAR\r\n" % (uid, summary))


def _grant_level(test, permissions):
    path = os.path.join(test.colpath, "rights")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(
            "[all]\nuser: .*\ncollection: .*\npermissions: %s\n" % permissions)
    test.configure({
        "auth": {"type": "none", "delay": "0"},
        "rights": {"type": "from_file", "file": path},
        "hook": {"type": "radicale.tests.test_hook_collection_notify"},
    })


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

    def test_collection_put_notifies_the_hook_and_empty_body_adds_none(self):
        """A calendar upload reports the new event. An empty body adds none.

        One component is the inside case. An empty upload is the empty
        boundary and must not invent a notification.
        """
        self.configure({"hook": {"type": "radicale.tests.test_hook_collection_notify"}})
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


class TestCollectionUpload(BaseTest):

    def setup_method(self):
        super().setup_method()
        Hook.events = []

    def test_collection_upload_notifies_each_new_event(self):
        """Uploading a calendar tells the hook about each event as new.

        One event and two events are the collection sizes. Replacing the
        calendar drops the previous summary. A read-only grant then rejects
        another upload and leaves the stored events in place.
        """
        _grant_level(self, "RrWw")
        status, _, answer = self.request(
            "PUT", "/team.ics/", _calendar("kept", "Kept"), check=None)
        assert status == 201 and answer == ""
        assert "SUMMARY:Kept" in self.get("/team.ics/")[1]
        assert len(Hook.events) == 1
        created = Hook.events[0]
        assert created.type == "upsert"
        assert created.old_content is None
        assert created.new_content is not None
        assert "UID:kept" in created.new_content
        assert "SUMMARY:Kept" in created.new_content
        assert created.is_calendar_item is True

        Hook.events = []
        both = (
            "BEGIN:VCALENDAR\r\nVERSION:2.0\r\n"
            "BEGIN:VEVENT\r\nUID:next\r\nSUMMARY:Next\r\n"
            "DTSTART:20130901T160000Z\r\nDTEND:20130901T170000Z\r\n"
            "END:VEVENT\r\n"
            "BEGIN:VEVENT\r\nUID:extra\r\nSUMMARY:Extra\r\n"
            "DTSTART:20130902T160000Z\r\nDTEND:20130902T170000Z\r\n"
            "END:VEVENT\r\nEND:VCALENDAR\r\n")
        status, _, answer = self.request("PUT", "/team.ics/", both, check=None)
        assert status in (201, 204) and answer == ""
        stored = self.get("/team.ics/")[1]
        assert "SUMMARY:Next" in stored
        assert "SUMMARY:Extra" in stored
        assert "SUMMARY:Kept" not in stored
        assert len(Hook.events) == 2
        assert {event.type for event in Hook.events} == {"upsert"}
        uploaded = "\n".join(event.new_content for event in Hook.events)
        assert "UID:next" in uploaded and "UID:extra" in uploaded
        assert all(event.old_content is None for event in Hook.events)

        _grant_level(self, "Rr")
        status, headers, answer = self.request(
            "PUT", "/team.ics/", _calendar("blocked", "Blocked"), check=None)
        assert status == 401 and answer
        assert "WWW-Authenticate" in headers
        kept = self.get("/team.ics/")[1]
        assert "SUMMARY:Next" in kept and "SUMMARY:Extra" in kept
        assert "SUMMARY:Blocked" not in kept
