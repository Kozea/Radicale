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

"""Outcome tests for free/busy reports and collection property edges."""

import builtins
import datetime
import importlib
import logging
import os

import defusedxml.ElementTree as DefusedET
import pytest
import vobject

import radicale.app as app_module
import radicale.app.report as report_module
from radicale import pathutils, xmlutils
from radicale.app.base import Access
from radicale.app.propfind import xml_propfind_response
from radicale.app.proppatch import xml_proppatch
from radicale.item import Item
from radicale.storage.multifilesystem import Collection
from radicale.tests import BaseTest

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


class Hook:
    """Recording hook used by these tests."""

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


EXPAND = (
    "<?xml version='1.0' encoding='utf-8'?>"
    "<C:calendar-query xmlns:D='DAV:' xmlns:C='urn:ietf:params:xml:ns:caldav'>"
    "<D:prop><C:calendar-data><C:expand start='{start}' end='{end}'/>"
    "</C:calendar-data></D:prop>"
    "<C:filter><C:comp-filter name='VCALENDAR'>"
    "<C:comp-filter name='VEVENT'>"
    "<C:time-range start='{start}' end='{end}'/>"
    "</C:comp-filter></C:comp-filter></C:filter>"
    "</C:calendar-query>")


class _TextStatus:
    """STATUS value that is not a string until it is rendered."""

    def __str__(self):
        return " tentative "


class TestCovAppRest(BaseTest):

    def setup_method(self):
        super().setup_method()
        _grant(self)
        Hook.events = []
        Hook.fail = False

    def _collection(self, path):
        with self.application._storage.acquire_lock("r", ""):
            return next(self.application._storage.discover(path))

    def test_date_bounds_become_utc_midnights(self):
        # A date is not a datetime; a zoned datetime already is.
        start = datetime.date(2013, 1, 2)
        end = datetime.date(2013, 1, 3)
        text = report_module.render_freebusy(
            [(start, end, "BUSY")],
            datetime.date(2013, 1, 1),
            datetime.date(2013, 1, 4))
        flat = text.replace("\r\n", "").replace("\n", "")
        assert "20130102T000000Z/20130103T000000Z" in flat
        aware = datetime.datetime(2013, 1, 2, 15, tzinfo=datetime.timezone.utc)
        later = aware + datetime.timedelta(hours=1)
        text = report_module.render_freebusy(
            [(aware, later, "BUSY")],
            datetime.datetime(2013, 1, 2, tzinfo=datetime.timezone.utc),
            datetime.datetime(2013, 1, 3, tzinfo=datetime.timezone.utc))
        flat = text.replace("\r\n", "").replace("\n", "")
        assert "20130102T150000Z/20130102T160000Z" in flat
        converted = report_module._to_utc(datetime.date(2013, 1, 2))
        assert converted == datetime.datetime(
            2013, 1, 2, tzinfo=vobject.icalendar.utc)
        assert report_module._to_utc(aware) == aware

    def test_non_string_status_still_selects_a_freebusy_type(self):
        self.mkcalendar("/calendar.ics/")
        self.put("/calendar.ics/tent.ics", _event(
            uid="tent", summary="Tent",
            start="20130601T100000Z", end="20130601T110000Z",
            extra="STATUS:CONFIRMED\r\n"))
        self.put("/calendar.ics/cancel.ics", _event(
            uid="cancel", summary="Cancel",
            start="20130601T120000Z", end="20130601T130000Z",
            extra="STATUS:CANCELLED\r\n"))
        original = Collection.get_filtered

        def with_odd_status(collection, filters):
            for item, flag in original(collection, filters):
                if item.uid == "tent":
                    item.vobject_item.vevent.status.value = _TextStatus()
                yield item, flag

        Collection.get_filtered = with_odd_status
        try:
            status, body = self.get(
                "/calendar.ics/",
                QUERY_STRING="view=freebusy&format=vfreebusy"
                "&start=20130601T000000Z&end=20130602T000000Z")
        finally:
            Collection.get_filtered = original
        assert status == 200
        assert "BUSY-TENTATIVE" in body
        assert "FBTYPE=FREE" in body or "\nFREE" in body or "FREE" in body
        assert "SUMMARY:Tent" not in body

    def test_freebusy_drops_non_events_and_periods_without_a_type(self):
        self.mkcalendar("/calendar.ics/")
        self.put("/calendar.ics/task.ics", (
            "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VTODO\r\n"
            "UID:task\r\nDTSTART:20130601T100000Z\r\n"
            "DUE:20130601T110000Z\r\nSUMMARY:Task\r\n"
            "END:VTODO\r\nEND:VCALENDAR\r\n"))
        self.put("/calendar.ics/event.ics", _event(
            summary="Shown",
            start="20130601T100000Z", end="20130601T110000Z"))
        original = Collection.get_filtered

        def everything(collection, filters):
            for item in collection.get_all():
                yield item, True

        Collection.get_filtered = everything
        try:
            status, body = self.get(
                "/calendar.ics/",
                QUERY_STRING="view=freebusy&format=vfreebusy"
                "&start=20130601T000000Z&end=20130602T000000Z")
        finally:
            Collection.get_filtered = original
        assert status == 200 and "BEGIN:VFREEBUSY" in body
        assert "Task" not in body
        assert "20130601T100000Z/20130601T110000Z" in body.replace("\r", "")

        def visit_without_component(
                vobject_item, child_name, range_fn, infinity_fn,
                component_fn=None, max_occurrences=0):
            start = datetime.datetime(
                2013, 6, 1, 10, tzinfo=datetime.timezone.utc)
            end = datetime.datetime(
                2013, 6, 1, 11, tzinfo=datetime.timezone.utc)
            assert range_fn(start, end, False) is False

        original_visit = report_module.radicale_filter.visit_time_ranges
        report_module.radicale_filter.visit_time_ranges = visit_without_component
        try:
            status, body = self.get(
                "/calendar.ics/",
                QUERY_STRING="view=freebusy&format=vfreebusy"
                "&start=20130601T000000Z&end=20130602T000000Z")
        finally:
            report_module.radicale_filter.visit_time_ranges = original_visit
        assert status == 200 and "BEGIN:VFREEBUSY" in body
        assert "FREEBUSY:" not in body and "FREEBUSY;" not in body

        def visit_then_clear(
                vobject_item, child_name, range_fn, infinity_fn,
                component_fn=None, max_occurrences=0):
            child = vobject_item.vevent
            assert component_fn(child) is True
            child.add("transp").value = "TRANSPARENT"
            start = datetime.datetime(
                2013, 6, 1, 10, tzinfo=datetime.timezone.utc)
            end = datetime.datetime(
                2013, 6, 1, 11, tzinfo=datetime.timezone.utc)
            assert range_fn(start, end, False) is False

        report_module.radicale_filter.visit_time_ranges = visit_then_clear
        try:
            status, body = self.get(
                "/calendar.ics/",
                QUERY_STRING="view=freebusy&format=vfreebusy"
                "&start=20130601T000000Z&end=20130602T000000Z")
        finally:
            report_module.radicale_filter.visit_time_ranges = original_visit
        assert status == 200 and "BEGIN:VFREEBUSY" in body
        assert "FREEBUSY:" not in body and "FREEBUSY;" not in body
        assert "Shown" in self.get("/calendar.ics/event.ics")[1]

    def test_unknown_freebusy_format_and_empty_report_body(self):
        self.mkcalendar("/calendar.ics/")
        self.put("/calendar.ics/event.ics", _event(summary="Kept"))
        import radicale.app.get as get_module
        previous = get_module.sharing.FREEBUSY_VIEW_FORMATS
        get_module.sharing.FREEBUSY_VIEW_FORMATS = ("vfreebusy", "vevent", "other")
        try:
            status, _, body = self.request(
                "GET", "/calendar.ics/",
                QUERY_STRING="view=freebusy&format=other"
                "&start=20130601T000000Z&end=20130602T000000Z",
                check=None)
            kept = self.request(
                "GET", "/calendar.ics/",
                QUERY_STRING="view=freebusy&format=vfreebusy"
                "&start=20130601T000000Z&end=20130602T000000Z",
                check=None)
        finally:
            get_module.sharing.FREEBUSY_VIEW_FORMATS = previous
        assert status == 400 and body == BAD_REQUEST
        assert kept[0] == 200 and "BEGIN:VFREEBUSY" in kept[2]
        assert "Kept" not in kept[2]
        collection = self._collection("/calendar.ics/")
        code, answer = report_module.free_busy_report(
            "", "/calendar.ics/", None, collection, "utf-8", lambda: None, 0)
        assert code == 207
        assert answer.tag == xmlutils.make_clark("D:multistatus")
        assert len(list(answer)) == 0
        with pytest.raises(ValueError, match="unsupported free-busy format: ''"):
            report_module.freebusy_collection_text(
                collection,
                datetime.datetime(2013, 6, 1, tzinfo=datetime.timezone.utc),
                datetime.datetime(2013, 6, 2, tzinfo=datetime.timezone.utc),
                0, lambda: None, output="")

    def test_expand_skips_bad_starts_and_manual_exdates(self, monkeypatch, caplog):
        self.mkcalendar("/calendar.ics/")
        self.put("/calendar.ics/daily.ics", (
            "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nUID:daily\r\n"
            "DTSTART:20130101T100000Z\r\nDTEND:20130101T110000Z\r\n"
            "RRULE:FREQ=DAILY;COUNT=2\r\nEXDATE:20130102T100000Z\r\n"
            "SUMMARY:Daily\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"))
        self.put("/calendar.ics/plain.ics", _event(
            uid="plain", summary="Plain",
            start="20130301T100000Z", end="20130301T110000Z"))
        self.put("/calendar.ics/odd.ics", _event(
            uid="odd", summary="Odd",
            start="20130401T100000Z", end="20130401T110000Z"))
        original = Collection.get_filtered
        real_rules = vobject.icalendar.RecurringComponent.getrruleset

        def adjusted(collection, filters):
            for item, flag in original(collection, filters):
                vevent = item.vobject_item.vevent
                if item.uid == "daily":
                    class _Exdate:
                        value = datetime.datetime(
                            2013, 1, 2, 10, tzinfo=datetime.timezone.utc)

                    vevent.exdate = _Exdate()
                elif item.uid == "plain":
                    del vevent.dtend
                    vevent.dtstart.value = "BADDATE"
                elif item.uid == "odd":
                    del vevent.dtend
                    vevent.dtstart.value = datetime.time(10, 0)
                yield item, flag

        def rules_ignoring_exdate(self, addRDate=False):
            uid = getattr(getattr(self, "uid", None), "value", None)
            if uid == "daily":
                class _Rules:
                    def between(self, start, end, inc=True, count=0):
                        return [
                            datetime.datetime(
                                2013, 1, 1, 10, tzinfo=datetime.timezone.utc),
                            datetime.datetime(
                                2013, 1, 2, 10, tzinfo=datetime.timezone.utc),
                        ]
                return _Rules()
            return real_rules(self, addRDate=addRDate)

        monkeypatch.setattr(Collection, "get_filtered", adjusted)
        monkeypatch.setattr(
            vobject.icalendar.RecurringComponent, "getrruleset",
            rules_ignoring_exdate)
        caplog.set_level(logging.WARNING)
        status, _, body = self.request(
            "REPORT", "/calendar.ics/",
            EXPAND.format(start="20130101T000000Z", end="20130501T000000Z"),
            check=None)
        assert status == 207
        flat = body.replace("\r", "")
        assert "20130101T100000Z" in flat
        assert "20130102T100000Z" not in flat
        assert "SUMMARY:Plain" not in body and "SUMMARY:Odd" not in body
        logged = "\n".join(caplog.messages)
        assert "Invalid DTSTART format" in logged
        assert "Unexpected DTSTART/DTEND type" in logged
        assert "Daily" in self.get("/calendar.ics/daily.ics")[1]

    def test_two_master_events_in_one_resource_are_rejected(self, caplog):
        self.mkcalendar("/calendar.ics/")
        self.put("/calendar.ics/single.ics", _event(summary="Single"))
        doubled = Item(
            collection_path="calendar.ics", href="double.ics", uid="double",
            component_name="VEVENT", name="VCALENDAR",
            time_range=(0, 2 ** 31),
            text=(
                "BEGIN:VCALENDAR\r\nVERSION:2.0\r\n"
                "BEGIN:VEVENT\r\nUID:double\r\nDTSTAMP:20130101T000000Z\r\n"
                "DTSTART:20130501T100000Z\r\nDTEND:20130501T110000Z\r\n"
                "SUMMARY:First\r\nEND:VEVENT\r\n"
                "BEGIN:VEVENT\r\nUID:double\r\nDTSTAMP:20130101T000000Z\r\n"
                "DTSTART:20130502T100000Z\r\nDTEND:20130502T110000Z\r\n"
                "SUMMARY:Second\r\nEND:VEVENT\r\n"
                "END:VCALENDAR\r\n"))
        original = Collection.get_filtered

        def with_two_masters(collection, filters):
            yield from original(collection, filters)
            if collection.path == "calendar.ics":
                yield doubled, True

        Collection.get_filtered = with_two_masters
        caplog.set_level(logging.WARNING)
        try:
            status, _, body = self.request(
                "REPORT", "/calendar.ics/",
                EXPAND.format(start="20130501T000000Z", end="20130504T000000Z"),
                check=None)
        finally:
            Collection.get_filtered = original
        assert status == 400 and body == BAD_REQUEST
        assert "more than one vevent" in "\n".join(caplog.messages)
        assert "Single" in self.get("/calendar.ics/single.ics")[1]

    def test_date_property_on_a_timed_event_is_stored_as_utc(self):
        calendar = vobject.iCalendar()
        vevent = calendar.add("vevent")
        vevent.add("dtend").value = datetime.date(2013, 1, 3)
        report_module._convert_timezone(vevent, "dtend", "DTEND", False)
        assert vevent.dtend.value.tzinfo is datetime.timezone.utc
        assert vevent.dtend.value == datetime.datetime(
            2013, 1, 3, tzinfo=datetime.timezone.utc)
        all_day = vobject.iCalendar().add("vevent")
        all_day.add("dtend").value = datetime.date(2013, 1, 3)
        report_module._convert_timezone(all_day, "dtend", "DTEND", True)
        assert all_day.dtend.value.tzinfo is None
        zoned = vobject.iCalendar().add("vevent")
        zoned.add("dtend").value = datetime.datetime(
            2013, 1, 3, 12, tzinfo=datetime.timezone.utc)
        report_module._convert_timezone(zoned, "dtend", "DTEND", False)
        assert zoned.dtend.value.tzinfo is datetime.timezone.utc

    def test_subscribed_collection_rejects_a_calendar_filter(self, caplog):
        self.mkcol("/sub.ics/", SUBSCRIBED_MKCOL)
        planted = Item(
            collection_path="sub.ics", href="event.ics", uid="sub",
            component_name="VEVENT", name="VCALENDAR",
            time_range=(0, 2 ** 31), text=_event(summary="Subscribed"))
        original = Collection.get_filtered

        def with_filter(collection, filters):
            if collection.tag != "VSUBSCRIBED":
                yield from original(collection, filters)
                return
            children = [child for element in filters for child in element]
            if children:
                yield planted, False

        Collection.get_filtered = with_filter
        query = (
            "<?xml version='1.0' encoding='utf-8'?>"
            "<C:calendar-query xmlns:D='DAV:' "
            "xmlns:C='urn:ietf:params:xml:ns:caldav'>"
            "<D:prop><D:getetag/></D:prop>"
            "<C:filter><C:comp-filter name='VCALENDAR'>"
            "<C:comp-filter name='VEVENT'/></C:comp-filter></C:filter>"
            "</C:calendar-query>")
        empty = (
            "<?xml version='1.0' encoding='utf-8'?>"
            "<C:calendar-query xmlns:C='urn:ietf:params:xml:ns:caldav'>"
            "<C:filter/>"
            "</C:calendar-query>")
        caplog.set_level(logging.WARNING)
        try:
            status, _, body = self.request(
                "REPORT", "/sub.ics/", query, check=None)
            assert status == 400 and body == BAD_REQUEST
            assert "Unsupported filter" in "\n".join(caplog.messages)
            caplog.clear()
            status, _, body = self.request(
                "REPORT", "/sub.ics/", empty, check=None)
        finally:
            Collection.get_filtered = original
        assert status == 207 and "Subscribed" not in body
        assert "Unsupported filter" not in "\n".join(caplog.messages)

    def test_propfind_rejects_mixed_modes_and_a_missing_share_key(self):
        self.mkcalendar("/calendar.ics/")
        item = self._collection("/calendar.ics/")
        with pytest.raises(ValueError, match="Only use one of props"):
            xml_propfind_response(
                self.application, "", "/calendar.ics/", item, ["D:displayname"],
                "", "utf-8", 1000, propname=True, allprop=True)
        element = xml_propfind_response(
            self.application, "", "/calendar.ics/", item, [],
            "", "utf-8", 1000, propname=True, allprop=False)
        assert "displayname" in DefusedET.tostring(element, encoding="unicode")
        uri = pathutils.unstrip_path(item.path, True)
        skipped = {
            "PathMapped": uri,
            "PathOrToken": "/skipped/",
            "Conversion": "",
            "Permissions": "r",
            "Properties": {"D:displayname": "Skipped"},
            "User": "user",
            "Actions": None,
        }
        kept = dict(skipped)
        kept["PathOrToken"] = "/kept/"
        kept["Properties"] = {"D:displayname": "Kept"}
        element = xml_propfind_response(
            self.application, "", "/calendar.ics/", item,
            [xmlutils.make_clark("RADICALE:displayname")],
            "user", "utf-8", 1000, shares={None: skipped, "/kept/": kept},
            conversion="")
        text = DefusedET.tostring(element, encoding="unicode")
        assert "Kept" in text and "Skipped" not in text

    def test_invalid_permission_and_missing_proppatch_collection(self):
        _set_rights(self, "[all]\nuser: .*\ncollection: .*\npermissions: W\n")
        access = Access(self.application._rights, "alice", set(), "/calendar.ics/")
        with pytest.raises(ValueError, match="Invalid permission argument: 'x'"):
            access.check("x")
        assert access.check("r") is False
        assert access.check("w") is True
        _grant(self)
        self.mkcalendar("/calendar.ics/")
        access = Access(self.application._rights, "alice", set(), "/calendar.ics/")
        assert access.check("r") is True
        assert access.check("w") is True
        xml = DefusedET.fromstring(
            PROPPATCH_NAME % "Nowhere")
        with pytest.raises(NameError):
            xml_proppatch("", "/calendar.ics/", xml, None, None, False, None)
        # Overlay with no sharing backend: the property is acknowledged and
        # nothing is stored. An empty Properties map and a missing map are
        # the two empty cases; neither one is written to the collection.
        empty_share = {
            "ShareType": "token",
            "PathMapped": "/calendar.ics/",
            "PathOrToken": "/tok/",
            "User": "alice",
            "Properties": {},
        }
        missing_props = dict(empty_share)
        missing_props["Properties"] = None
        missing_props["PathOrToken"] = "/bare/"
        for share, token, value in (
                (empty_share, "/tok/", "OverlayOnly"),
                (missing_props, "/bare/", "Z"),
        ):
            overlay = DefusedET.fromstring(PROPPATCH_NAME % value)
            answer = xml_proppatch(
                "", "/calendar.ics/", overlay, None, share, True, None)
            text = DefusedET.tostring(answer, encoding="unicode")
            assert token in text and "/calendar.ics/" not in text
            assert "displayname" in text and "HTTP/1.1 200 OK" in text
            assert value not in text
        status, _, body = self.request(
            "PROPPATCH", "/calendar.ics/", PROPPATCH_NAME % "RestName",
            check=None)
        assert status == 207 and "displayname" in body
        found = self.request(
            "PROPFIND", "/calendar.ics/",
            PROPFIND_ONE.format("<D:displayname/>"),
            HTTP_DEPTH="0", check=None)[2]
        assert "RestName" in found and "Nowhere" not in found
        assert "OverlayOnly" not in found and ">Z<" not in found

    def test_freebusy_requires_a_calendar_collection(self):
        self.mkcalendar("/calendar.ics/")
        self.create_addressbook("/contacts.vcf/")
        self.put("/calendar.ics/event.ics", _event(summary="Busy"))
        _set_rights(self, "[all]\nuser: .*\ncollection: .*\npermissions: f\n")
        calendar = self._collection("/calendar.ics/")
        book = self._collection("/contacts.vcf/")
        with self.application._storage.acquire_lock("r", ""):
            event = next(self.application._storage.discover(
                "/calendar.ics/event.ics"))
        free = Access(self.application._rights, "alice", set(), "/calendar.ics/")
        assert free.allows_freebusy() is True
        assert free.allows_freebusy(calendar) is True
        assert free.allows_freebusy(book) is False
        assert free.allows_freebusy(event) is False
        _set_rights(self, "[all]\nuser: .*\ncollection: .*\npermissions: w\n")
        write_only = Access(
            self.application._rights, "alice", set(), "/calendar.ics/")
        assert write_only.allows_freebusy() is False
        assert write_only.allows_freebusy(calendar) is False
        _set_rights(self, "[all]\nuser: .*\ncollection: .*\npermissions: r\n")
        read = Access(self.application._rights, "alice", set(), "/calendar.ics/")
        assert read.allows_freebusy(calendar) is True
        assert read.allows_freebusy(book) is False
        assert read.allows_freebusy(event) is False

    def test_missing_zstd_still_redirects_the_root(self):
        real_import = builtins.__import__

        def guarded(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "compression" and fromlist and "zstd" in fromlist:
                raise ImportError("zstd unavailable")
            return real_import(name, globals, locals, fromlist, level)

        builtins.__import__ = guarded
        try:
            importlib.reload(app_module)
            assert app_module.zstd is None
            self.application = app_module.Application(self.configuration)
            status, _, body = self.request("GET", "/", check=None)
            assert status == 302 and body == "Redirected to /.web"
        finally:
            builtins.__import__ = real_import
            importlib.reload(app_module)
            self.application = app_module.Application(self.configuration)
        status, headers, raw = self.request_raw(
            "GET", "/", HTTP_ACCEPT_ENCODING="zstd", check=None)
        assert status == 302
        if app_module.zstd is None:
            # Python before 3.14 has no compression.zstd. The redirect stays plain.
            assert headers.get("Content-Encoding") is None
            assert raw == b"Redirected to /.web"
        else:
            import compression.zstd as zstd_mod
            assert headers.get("Content-Encoding") == "zstd"
            assert zstd_mod.ZstdDecompressor().decompress(raw).decode() == (
                "Redirected to /.web")

    def test_nested_collection_without_item_write_is_refused(self, caplog):
        self.mkcalendar("/cal.ics/")
        props = {"tag": "VCALENDAR"}
        with self.application._storage.acquire_lock("w", ""):
            self.application._storage.create_collection(
                "/cal.ics/inner/", props=props)
        self.put("/cal.ics/inner/event.ics", _event(summary="Stay"))
        _set_rights(self, """\
[child]
user: .*
collection: cal\\.ics/inner
permissions: R
[parent]
user: .*
collection: cal\\.ics
permissions: w
[rest]
user: .*
collection: .*
permissions: R
""")
        caplog.set_level(logging.WARNING)
        status, _, body = self.request(
            "PUT", "/cal.ics/inner/", _event(uid="new", summary="Replace"),
            login="alice:secret", check=None)
        assert status == 403 and body == ACCESS_FORBIDDEN
        assert "Not a collection" not in "\n".join(caplog.messages)
        _grant(self)
        assert "Stay" in self.get("/cal.ics/inner/event.ics")[1]
        assert self.get("/cal.ics/inner/new.ics", check=404)[0] == 404

    def _item_hrefs(self, path):
        return sorted(self._collection(path)._list())
