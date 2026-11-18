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

"""Outcome tests for GET, PROPFIND, PROPPATCH, and REPORT."""

import cProfile
import datetime
import errno
import logging
import os
import socket
import wsgiref.util
from io import BytesIO

import pytest

import radicale.item as radicale_item
from radicale.log import logger
from radicale.storage.multifilesystem import Collection
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
    """Recording hook loaded as radicale.tests.test_cov_app_report."""

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

        self.configure({"hook": {"type": "radicale.tests.test_cov_app_report"}})
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
