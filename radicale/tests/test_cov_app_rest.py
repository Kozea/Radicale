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

"""Outcome tests for the HTTP app branches still left after the suite."""

import builtins
import csv
import datetime
import importlib
import json
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
from radicale.log import logger
from radicale.storage.multifilesystem import Collection
from radicale.tests import BaseTest
from radicale.tests.helpers import get_file_content
from radicale.tests.test_cov_app import (ACCESS_FORBIDDEN, BAD_REQUEST,
                                         PROPFIND_ONE, PROPPATCH_NAME,
                                         SUBSCRIBED_MKCOL, Hook, _event,
                                         _grant, _set_rights, _vcard)

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

    def test_whole_collection_put_notifies_new_and_replaced_items(self):
        """A collection upload reports new and replaced items by stored href.

        A normal UID is stored as ``uid`` plus the type suffix. A UID whose
        ``uid + suffix`` is not a safe filename is the boundary: the written
        name is the fallback, and a second upload of that same UID still
        reports the previous body. One request that keeps one UID and adds
        another distinguishes those two classes. An address book uses
        ``.vcf`` instead of ``.ics``.
        """
        self.configure({"hook": {"type": "radicale.tests.test_cov_app"}})

        def notified(path, body):
            Hook.events = []
            status, _, answer = self.request("PUT", path, body, check=None)
            assert status in (201, 204) and answer == ""
            return list(Hook.events)

        created = notified("/calendar.ics/", _event(summary="Original"))
        assert len(created) == 1
        assert created[0].old_content is None
        assert created[0].content == created[0].new_content
        assert "SUMMARY:Original" in created[0].content
        assert self._item_hrefs("/calendar.ics/") == ["evt.ics"]
        assert "SUMMARY:Original" in self.get("/calendar.ics/evt.ics")[1]

        replaced = notified("/calendar.ics/", _event(summary="Renamed"))
        assert len(replaced) == 1
        payload = json.loads(replaced[0].to_json())
        assert "SUMMARY:Original" in payload["old_content"]
        assert "SUMMARY:Renamed" not in payload["old_content"]
        assert payload["content"] == payload["new_content"]
        assert "SUMMARY:Renamed" in payload["content"]
        assert "SUMMARY:Original" not in payload["content"]
        assert self._item_hrefs("/calendar.ics/") == ["evt.ics"]
        assert "SUMMARY:Renamed" in self.get("/calendar.ics/evt.ics")[1]

        both = (
            "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Test//EN\r\n"
            "BEGIN:VEVENT\r\nUID:evt\r\nDTSTAMP:20130101T000000Z\r\n"
            "DTSTART:20130901T160000Z\r\nDTEND:20130901T170000Z\r\n"
            "SUMMARY:Kept\r\nEND:VEVENT\r\n"
            "BEGIN:VEVENT\r\nUID:extra\r\nDTSTAMP:20130101T000000Z\r\n"
            "DTSTART:20130902T160000Z\r\nDTEND:20130902T170000Z\r\n"
            "SUMMARY:Extra\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n")
        mixed = notified("/calendar.ics/", both)
        assert len(mixed) == 2
        by_uid = {}
        for event in mixed:
            body = json.loads(event.to_json())
            if "UID:extra" in body["new_content"]:
                by_uid["extra"] = body
            elif "UID:evt" in body["new_content"]:
                by_uid["evt"] = body
        assert set(by_uid) == {"evt", "extra"}
        assert "SUMMARY:Renamed" in by_uid["evt"]["old_content"]
        assert by_uid["evt"]["content"] == by_uid["evt"]["new_content"]
        assert "SUMMARY:Kept" in by_uid["evt"]["content"]
        assert "SUMMARY:Renamed" not in by_uid["evt"]["content"]
        assert by_uid["extra"]["old_content"] is None
        assert by_uid["extra"]["content"] == by_uid["extra"]["new_content"]
        assert "SUMMARY:Extra" in by_uid["extra"]["content"]
        assert self._item_hrefs("/calendar.ics/") == ["evt.ics", "extra.ics"]

        hidden = notified("/dotted.ics/", _event(uid=".hidden", summary="First"))
        assert len(hidden) == 1
        assert hidden[0].old_content is None
        assert hidden[0].content == hidden[0].new_content
        assert "SUMMARY:First" in hidden[0].content
        hidden_hrefs = self._item_hrefs("/dotted.ics/")
        assert len(hidden_hrefs) == 1
        assert hidden_hrefs[0] != ".hidden.ics"
        assert "SUMMARY:First" in self.get(
            "/dotted.ics/" + hidden_hrefs[0])[1]
        hidden_replaced = notified(
            "/dotted.ics/", _event(uid=".hidden", summary="Second"))
        assert len(hidden_replaced) == 1
        hidden_payload = json.loads(hidden_replaced[0].to_json())
        assert "SUMMARY:First" in hidden_payload["old_content"]
        assert hidden_payload["content"] == hidden_payload["new_content"]
        assert "SUMMARY:Second" in hidden_payload["content"]
        assert "SUMMARY:First" not in hidden_payload["content"]
        assert self._item_hrefs("/dotted.ics/") == hidden_hrefs
        assert "SUMMARY:Second" in self.get(
            "/dotted.ics/" + hidden_hrefs[0])[1]

        card = notified("/book/", _vcard(fn="Ada"))
        assert len(card) == 1
        assert card[0].old_content is None
        assert card[0].content == card[0].new_content
        assert "FN:Ada" in card[0].content
        assert self._item_hrefs("/book/") == ["card.vcf"]
        card_replaced = notified("/book/", _vcard(fn="Ada Lovelace"))
        assert len(card_replaced) == 1
        card_payload = json.loads(card_replaced[0].to_json())
        assert "FN:Ada\r\n" in card_payload["old_content"]
        assert "Lovelace" not in card_payload["old_content"]
        assert card_payload["content"] == card_payload["new_content"]
        assert "FN:Ada Lovelace" in card_payload["content"]
        assert self._item_hrefs("/book/") == ["card.vcf"]
        assert "FN:Ada Lovelace" in self.get("/book/card.vcf")[1]


class TestCovAppRestSharing(BaseTest):

    def setup_method(self):
        super().setup_method()
        self.htpasswd = os.path.join(self.colpath, ".htpasswd")
        with open(self.htpasswd, "w", encoding="utf-8") as handle:
            handle.write("owner:ownerpw\nuser:userpw\n")
        _grant(self)
        self._enable_sharing()

    def _enable_sharing(self, rights_text=None):
        if rights_text:
            path = os.path.join(self.colpath, "rights")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(rights_text)
            rights = {"type": "from_file", "file": path}
        else:
            rights = {"type": "owner_only"}
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
             properties=None, conversion=None, owner_login="owner:ownerpw",
             user_login="user:userpw"):
        payload = {
            "User": user,
            "PathMapped": mapped,
            "PathOrToken": token,
            "Permissions": permissions,
            "Enabled": True,
            "Hidden": False,
        }
        if properties is not None:
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

    def _rewrite(self, token, **fields):
        path = os.path.join(self.colpath, "collection-db", "sharing.csv")
        with open(path, encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle, delimiter=";")
            rows = list(reader)
            fieldnames = reader.fieldnames
        found = False
        for row in rows:
            if row["PathOrToken"] != token:
                continue
            found = True
            for key, value in fields.items():
                row[key] = value
        assert found, token
        with open(path, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle, fieldnames=fieldnames, delimiter=";")
            writer.writeheader()
            writer.writerows(rows)
        self.configure({})

    def test_freebusy_filename_without_an_ics_suffix(self):
        self.mkcalendar("/owner/cal.ics/", login="owner:ownerpw")
        self.mkcalendar("/owner/other.ics/", login="owner:ownerpw")
        self.put("/owner/cal.ics/event.ics", _event(summary="Busy"),
                 login="owner:ownerpw")
        self.put("/owner/other.ics/event.ics", _event(summary="Busy"),
                 login="owner:ownerpw")
        self._map("/owner/cal.ics/", "/user/blank/", permissions="r",
                  properties={"D:displayname": ""})
        self._map("/owner/other.ics/", "/user/cased/", permissions="r",
                  properties={"D:displayname": "FILE.ICS"})
        status, headers, body = self.request(
            "GET", "/user/blank/",
            QUERY_STRING="view=freebusy&format=vfreebusy"
            "&start=20130601T000000Z&end=20130602T000000Z",
            login="user:userpw", check=None)
        assert status == 200 and "BEGIN:VFREEBUSY" in body
        assert "SUMMARY:Busy" not in body
        assert "-freebusy.ics" in headers.get("Content-Disposition", "")
        assert "FILE" not in headers.get("Content-Disposition", "")
        status, headers, body = self.request(
            "GET", "/user/cased/",
            QUERY_STRING="view=freebusy&format=vfreebusy"
            "&start=20130601T000000Z&end=20130602T000000Z",
            login="user:userpw", check=None)
        assert status == 200 and "BEGIN:VFREEBUSY" in body
        disposition = headers.get("Content-Disposition", "")
        assert "FILE-freebusy.ics" in disposition
        assert "FILE.ICS" not in disposition

    def test_share_propfind_when_debug_logging_is_off(self, caplog):
        self.mkcalendar("/owner/cal.ics/", login="owner:ownerpw")
        self.put("/owner/cal.ics/event.ics", _event(summary="Shared"),
                 login="owner:ownerpw")
        self._map("/owner/cal.ics/", "/user/shared/", permissions="r",
                  properties={"D:displayname": "Overlay",
                              "ICAL:calendar-color": "#112233"})
        caplog.set_level(logging.DEBUG)
        previous = logger.level
        logger.setLevel(logging.WARNING)
        try:
            status, _, body = self.request(
                "PROPFIND", "/user/shared/",
                PROPFIND_ONE.format(
                    "<RADICALE:displayname/><D:displayname/>"
                    "<ICAL:calendar-color "
                    "xmlns:ICAL='http://apple.com/ns/ical/'/>"),
                HTTP_DEPTH="0", login="user:userpw", check=None)
            assert status == 207
            assert "Overlay" in body and "#112233" in body
            assert "replace from share properties" not in "\n".join(caplog.messages)
            status, _, body = self.request(
                "PROPFIND", "/user/",
                PROPFIND_ONE.format("<D:resourcetype/>"),
                HTTP_DEPTH="1", login="user:userpw", check=None)
        finally:
            logger.setLevel(previous)
        assert status == 207 and "/user/shared/" in body
        assert "add mapping" not in "\n".join(caplog.messages)

    def test_bday_counts_principal_suffix_and_failed_conversion(self, caplog):
        self.create_addressbook("/owner/book/", login="owner:ownerpw")
        self.create_addressbook("/owner/empty/", login="owner:ownerpw")
        self.put("/owner/book/plain.vcf", get_file_content("contact1.vcf"),
                 login="owner:ownerpw")
        self.put("/owner/book/bday.vcf",
                 get_file_content("contact2-with-bday.vcf"),
                 login="owner:ownerpw")
        self._map("/owner/book/", "/user/birthdays/", permissions="r",
                  conversion="bday")
        self._map("/owner/empty/", "/user/empty-bday/", permissions="r",
                  conversion="bday")
        self._map("/owner/", "/user/home/", permissions="Rr")
        caplog.set_level(logging.DEBUG)
        previous = logger.level
        logger.setLevel(logging.WARNING)
        try:
            status, _, body = self.request(
                "PROPFIND", "/user/birthdays/",
                PROPFIND_ONE.format("<RADICALE:getcontentcount/>"),
                HTTP_DEPTH="0", login="user:userpw", check=None)
            empty = self.request(
                "PROPFIND", "/user/empty-bday/",
                PROPFIND_ONE.format("<RADICALE:getcontentcount/>"),
                HTTP_DEPTH="0", login="user:userpw", check=None)
            native = self.request(
                "PROPFIND", "/owner/book/",
                PROPFIND_ONE.format("<RADICALE:getcontentcount/>"),
                HTTP_DEPTH="0", login="owner:ownerpw", check=None)
        finally:
            logger.setLevel(previous)
        assert status == 207
        counted = self.parse_responses(body)["/user/birthdays/"]
        assert counted["RADICALE:getcontentcount"] == (
            200, counted["RADICALE:getcontentcount"][1])
        assert counted["RADICALE:getcontentcount"][1].text == "1"
        assert self.parse_responses(empty[2])["/user/empty-bday/"][
            "RADICALE:getcontentcount"][1].text == "0"
        assert self.parse_responses(native[2])["/owner/book/"][
            "RADICALE:getcontentcount"][1].text == "2"
        assert "getcontentcount: start bday" not in "\n".join(caplog.messages)

        real = Item.convert_vcf_to_ics

        def fail_after_admit(item, ShareActions=None):
            converted = real(item, ShareActions=ShareActions)
            if getattr(item, "uid", None) != "contact2-with-bday":
                return converted
            if fail_after_admit.admitted:
                return None
            fail_after_admit.admitted = True
            return converted

        fail_after_admit.admitted = False
        Item.convert_vcf_to_ics = fail_after_admit
        try:
            status, _, body = self.request(
                "PROPFIND", "/user/birthdays/",
                PROPFIND_ONE.format("<D:getetag/><D:getcontentlength/>"),
                HTTP_DEPTH="1", login="user:userpw", check=None)
        finally:
            Item.convert_vcf_to_ics = real
        assert status == 207
        responses = self.parse_responses(body)
        matched = [value for key, value in responses.items()
                   if key.endswith("/bday.ics")]
        assert matched
        props = matched[0]
        assert not isinstance(props, int)
        assert props["D:getetag"][0] == 404
        assert props["D:getcontentlength"][0] == 404

        self._retarget("/user/birthdays/", "/user/birthdays.vcf")
        self._rewrite(
            "/user/home/", PathOrToken="/user/home.vcf", Conversion="bday")
        status, _, body = self.request(
            "PROPFIND", "/user/",
            PROPFIND_ONE.format("<D:resourcetype/>"),
            HTTP_DEPTH="1", login="user:userpw", check=None)
        assert status == 207
        assert "/user/birthdays.ics" in body
        assert "birthdays.vcf" not in body
        status, _, body = self.request(
            "PROPFIND", "/user/home.vcf",
            PROPFIND_ONE.format("<D:principal-URL/>"),
            HTTP_DEPTH="0", login="user:userpw", check=None)
        assert status == 207
        assert "/user/home.ics" in body
        assert "home.vcf" not in body

    def test_subscribed_report_set_omits_calendar_reports(self):
        self.mkcol("/owner/sub.ics/", SUBSCRIBED_MKCOL, login="owner:ownerpw")
        self.mkcalendar("/owner/cal.ics/", login="owner:ownerpw")
        status, _, body = self.request(
            "PROPFIND", "/owner/sub.ics/",
            PROPFIND_ONE.format("<D:supported-report-set/>"),
            HTTP_DEPTH="0", login="owner:ownerpw", check=None)
        assert status == 207
        assert "sync-collection" in body
        assert "calendar-query" not in body
        assert "addressbook-query" not in body
        status, _, body = self.request(
            "PROPFIND", "/owner/cal.ics/",
            PROPFIND_ONE.format("<D:supported-report-set/>"),
            HTTP_DEPTH="0", login="owner:ownerpw", check=None)
        assert status == 207 and "calendar-query" in body
        assert "free-busy-query" in body

    def test_bday_report_keeps_foreign_hrefs_and_converts_contacts(self):
        self.create_addressbook("/owner/book/", login="owner:ownerpw")
        self.put("/owner/book/plain.vcf", get_file_content("contact1.vcf"),
                 login="owner:ownerpw")
        self.put("/owner/book/bday.vcf",
                 get_file_content("contact2-with-bday.vcf"),
                 login="owner:ownerpw")
        self._map("/owner/book/", "/user/birthdays/", permissions="r",
                  conversion="bday")
        query = (
            "<?xml version='1.0' encoding='utf-8'?>"
            "<C:calendar-query xmlns:D='DAV:' "
            "xmlns:C='urn:ietf:params:xml:ns:caldav'>"
            "<D:prop><C:calendar-data/></D:prop>"
            "<C:filter><C:comp-filter name='VCALENDAR'>"
            "<C:comp-filter name='VEVENT'/></C:comp-filter></C:filter>"
            "</C:calendar-query>")
        status, _, body = self.request(
            "REPORT", "/user/birthdays/", query, login="user:userpw",
            check=None)
        assert status == 207
        assert "bday.ics" in body and "VEVENT" in body
        assert "plain" not in body
        assert ".vcf" not in body
        multiget = (
            "<?xml version='1.0' encoding='utf-8'?>"
            "<C:calendar-multiget xmlns:D='DAV:' "
            "xmlns:C='urn:ietf:params:xml:ns:caldav'>"
            "<D:prop><D:getetag/></D:prop>"
            "<D:href>/elsewhere/person.vcf</D:href>"
            "</C:calendar-multiget>")
        status, _, body = self.request(
            "REPORT", "/user/birthdays/", multiget, login="user:userpw",
            check=None)
        assert status == 207
        assert "elsewhere/person.ics" in body
        assert "elsewhere/person.vcf" not in body
        assert "owner/book" not in body
        assert ">404<" in body or "404" in body

    def test_duplicate_share_targets_are_listed_once_without_debug(self, caplog):
        self.mkcalendar("/owner/cal.ics/", login="owner:ownerpw")
        self.put("/owner/cal.ics/event.ics", _event(summary="Once"),
                 login="owner:ownerpw")
        self.mkcalendar("/user/solo.ics/", login="user:userpw")
        self._map("/owner/cal.ics/", "/user/fresh/", permissions="r")
        self._retarget("/user/fresh/", "/user/solo.ics/")
        self._map("/owner/cal.ics/", "/owner/twin/", user="owner",
                  permissions="r", user_login="owner:ownerpw")
        caplog.set_level(logging.DEBUG)
        previous = logger.level
        logger.setLevel(logging.WARNING)
        try:
            status, _, body = self.request(
                "PROPFIND", "/user/",
                PROPFIND_ONE.format("<D:resourcetype/>"),
                HTTP_DEPTH="1", login="user:userpw", check=None)
            assert status == 207
            assert body.count("/user/solo.ics/") == 1
            owner = self.request(
                "PROPFIND", "/owner/",
                PROPFIND_ONE.format("<D:resourcetype/>"),
                HTTP_DEPTH="1", login="owner:ownerpw", check=None)
        finally:
            logger.setLevel(previous)
        assert owner[0] == 207
        assert "/owner/cal.ics/" in owner[2]
        assert "/owner/twin/" not in owner[2]
        logged = "\n".join(caplog.messages)
        assert "skipped (source existing)" not in logged
        assert "backmapped already existing" not in logged

    def test_share_color_absent_from_overlay_stays_on_the_collection(self):
        color = """<?xml version="1.0" encoding="utf-8"?>
            <D:propertyupdate xmlns:D="DAV:">
              <D:set><D:prop>
                <I:calendar-color xmlns:I="http://apple.com/ns/ical/">#abcdef</I:calendar-color>
              </D:prop></D:set>
            </D:propertyupdate>"""
        self.mkcalendar("/owner/cal.ics/", login="owner:ownerpw")
        self.mkcalendar("/owner/other.ics/", login="owner:ownerpw")
        self.request("PROPPATCH", "/owner/cal.ics/", color,
                     login="owner:ownerpw", check=None)
        self.request("PROPPATCH", "/owner/other.ics/", color,
                     login="owner:ownerpw", check=None)
        self._map("/owner/cal.ics/", "/user/colored/", permissions="r",
                  properties={"ICAL:calendar-color": "#111111"})
        self._map("/owner/other.ics/", "/user/blank-color/", permissions="r",
                  properties={"ICAL:calendar-color": None})
        prop = (
            "<ICAL:calendar-color xmlns:ICAL='http://apple.com/ns/ical/'/>")
        colored = self.request(
            "PROPFIND", "/user/colored/", PROPFIND_ONE.format(prop),
            HTTP_DEPTH="0", login="user:userpw", check=None)[2]
        assert "#111111" in colored and "#abcdef" not in colored
        blank = self.request(
            "PROPFIND", "/user/blank-color/", PROPFIND_ONE.format(prop),
            HTTP_DEPTH="0", login="user:userpw", check=None)[2]
        assert "#111111" not in blank
        assert "#abcdef" in blank or ">404<" in blank or "404" in blank
