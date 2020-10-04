# This file is part of Radicale Server - Calendar Server
# Copyright © 2012-2017 Guillaume Ayoub
# Copyright © 2017-2019 Unrud <unrud@outlook.com>
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
Radicale tests with simple requests.

"""

import os
import posixpath
import shutil
import sys
import tempfile
from typing import Any, ClassVar

import defusedxml.ElementTree as DefusedET
import pytest

import radicale.tests.custom.storage_simple_sync
from radicale import Application, config, storage, xmlutils
from radicale.tests import BaseTest
from radicale.tests.helpers import get_file_content


class BaseRequestsMixIn:
    """Tests with simple requests."""

    # Allow skipping sync-token tests, when not fully supported by the backend
    full_sync_token_support = True

    def test_root(self):
        """GET request at "/"."""
        _, answer = self.get("/", check=302)
        assert answer == "Redirected to .web"

    def test_script_name(self):
        """GET request at "/" with SCRIPT_NAME."""
        _, answer = self.get("/", check=302, SCRIPT_NAME="/radicale")
        assert answer == "Redirected to .web"
        _, answer = self.get("", check=302, SCRIPT_NAME="/radicale")
        assert answer == "Redirected to radicale/.web"

    def test_add_event(self):
        """Add an event."""
        self.mkcalendar("/calendar.ics/")
        event = get_file_content("event1.ics")
        path = "/calendar.ics/event1.ics"
        self.put(path, event)
        status, headers, answer = self.request("GET", path)
        assert status == 200
        assert "ETag" in headers
        assert headers["Content-Type"] == "text/calendar; charset=utf-8"
        assert "VEVENT" in answer
        assert "Event" in answer
        assert "UID:event" in answer

    def test_add_event_without_uid(self):
        """Add an event without UID."""
        self.mkcalendar("/calendar.ics/")
        event = get_file_content("event1.ics").replace("UID:event1\n", "")
        assert "\nUID:" not in event
        path = "/calendar.ics/event.ics"
        self.put(path, event, check=400)

    def test_add_event_duplicate_uid(self):
        """Add an event with an existing UID."""
        self.mkcalendar("/calendar.ics/")
        event = get_file_content("event1.ics")
        self.put("/calendar.ics/event1.ics", event)
        status, answer = self.put(
            "/calendar.ics/event1-duplicate.ics", event, check=False)
        assert status in (403, 409)
        xml = DefusedET.fromstring(answer)
        assert xml.tag == xmlutils.make_clark("D:error")
        assert xml.find(xmlutils.make_clark("C:no-uid-conflict")) is not None

    def test_add_todo(self):
        """Add a todo."""
        self.mkcalendar("/calendar.ics/")
        todo = get_file_content("todo1.ics")
        path = "/calendar.ics/todo1.ics"
        self.put(path, todo)
        status, headers, answer = self.request("GET", path)
        assert status == 200
        assert "ETag" in headers
        assert headers["Content-Type"] == "text/calendar; charset=utf-8"
        assert "VTODO" in answer
        assert "Todo" in answer
        assert "UID:todo" in answer

    def test_add_contact(self):
        """Add a contact."""
        self.create_addressbook("/contacts.vcf/")
        contact = get_file_content("contact1.vcf")
        path = "/contacts.vcf/contact.vcf"
        self.put(path, contact)
        status, headers, answer = self.request("GET", path)
        assert status == 200
        assert "ETag" in headers
        assert headers["Content-Type"] == "text/vcard; charset=utf-8"
        assert "VCARD" in answer
        assert "UID:contact1" in answer
        _, answer = self.get(path)
        assert "UID:contact1" in answer

    def test_add_contact_without_uid(self):
        """Add a contact without UID."""
        self.create_addressbook("/contacts.vcf/")
        contact = get_file_content("contact1.vcf").replace("UID:contact1\n",
                                                           "")
        assert "\nUID" not in contact
        path = "/contacts.vcf/contact.vcf"
        self.put(path, contact, check=400)

    def test_update_event(self):
        """Update an event."""
        self.mkcalendar("/calendar.ics/")
        event = get_file_content("event1.ics")
        event_modified = get_file_content("event1_modified.ics")
        path = "/calendar.ics/event1.ics"
        self.put(path, event)
        self.put(path, event_modified)
        _, answer = self.get("/calendar.ics/")
        assert answer.count("BEGIN:VEVENT") == 1
        _, answer = self.get(path)
        assert "DTSTAMP:20130902T150159Z" in answer

    def test_update_event_uid_event(self):
        """Update an event with a different UID."""
        self.mkcalendar("/calendar.ics/")
        event1 = get_file_content("event1.ics")
        event2 = get_file_content("event2.ics")
        path = "/calendar.ics/event1.ics"
        self.put(path, event1)
        status, answer = self.put(path, event2, check=False)
        assert status in (403, 409)
        xml = DefusedET.fromstring(answer)
        assert xml.tag == xmlutils.make_clark("D:error")
        assert xml.find(xmlutils.make_clark("C:no-uid-conflict")) is not None

    def test_put_whole_calendar(self):
        """Create and overwrite a whole calendar."""
        self.put("/calendar.ics/", "BEGIN:VCALENDAR\r\nEND:VCALENDAR")
        event1 = get_file_content("event1.ics")
        self.put("/calendar.ics/test_event.ics", event1)
        # Overwrite
        events = get_file_content("event_multiple.ics")
        self.put("/calendar.ics/", events)
        self.get("/calendar.ics/test_event.ics", check=404)
        _, answer = self.get("/calendar.ics/")
        assert "\r\nUID:event\r\n" in answer and "\r\nUID:todo\r\n" in answer
        assert "\r\nUID:event1\r\n" not in answer

    def test_put_whole_calendar_without_uids(self):
        """Create a whole calendar without UID."""
        event = get_file_content("event_multiple.ics")
        event = event.replace("UID:event\n", "").replace("UID:todo\n", "")
        assert "\nUID:" not in event
        self.put("/calendar.ics/", event)
        _, answer = self.get("/calendar.ics")
        uids = []
        for line in answer.split("\r\n"):
            if line.startswith("UID:"):
                uids.append(line[len("UID:"):])
        assert len(uids) == 2
        for i, uid1 in enumerate(uids):
            assert uid1
            for uid2 in uids[i + 1:]:
                assert uid1 != uid2

    def test_put_whole_addressbook(self):
        """Create and overwrite a whole addressbook."""
        contacts = get_file_content("contact_multiple.vcf")
        self.put("/contacts.vcf/", contacts)
        _, answer = self.get("/contacts.vcf/")
        assert ("\r\nUID:contact1\r\n" in answer and
                "\r\nUID:contact2\r\n" in answer)

    def test_put_whole_addressbook_without_uids(self):
        """Create a whole addressbook without UID."""
        contacts = get_file_content("contact_multiple.vcf")
        contacts = contacts.replace("UID:contact1\n", "").replace(
            "UID:contact2\n", "")
        assert "\nUID:" not in contacts
        self.put("/contacts.vcf/", contacts)
        _, answer = self.get("/contacts.vcf")
        uids = []
        for line in answer.split("\r\n"):
            if line.startswith("UID:"):
                uids.append(line[len("UID:"):])
        assert len(uids) == 2
        for i, uid1 in enumerate(uids):
            assert uid1
            for uid2 in uids[i + 1:]:
                assert uid1 != uid2

    def test_verify(self):
        """Verify the storage."""
        contacts = get_file_content("contact_multiple.vcf")
        self.put("/contacts.vcf/", contacts)
        events = get_file_content("event_multiple.ics")
        self.put("/calendar.ics/", events)
        s = storage.load(self.configuration)
        assert s.verify()

    def test_delete(self):
        """Delete an event."""
        self.mkcalendar("/calendar.ics/")
        event = get_file_content("event1.ics")
        path = "/calendar.ics/event1.ics"
        self.put(path, event)
        _, responses = self.delete(path)
        assert responses[path] == 200
        _, answer = self.get("/calendar.ics/")
        assert "VEVENT" not in answer

    def test_mkcalendar(self):
        """Make a calendar."""
        self.mkcalendar("/calendar.ics/")
        _, answer = self.get("/calendar.ics/")
        assert "BEGIN:VCALENDAR" in answer
        assert "END:VCALENDAR" in answer

    def test_mkcalendar_overwrite(self):
        """Try to overwrite an existing calendar."""
        self.mkcalendar("/calendar.ics/")
        status, answer = self.mkcalendar("/calendar.ics/", check=False)
        assert status in (403, 409)
        xml = DefusedET.fromstring(answer)
        assert xml.tag == xmlutils.make_clark("D:error")
        assert xml.find(xmlutils.make_clark(
            "D:resource-must-be-null")) is not None

    def test_mkcalendar_intermediate(self):
        """Try make a calendar in a unmapped collection."""
        status, _ = self.mkcalendar("/unmapped/calendar.ics/", check=False)
        assert status == 409

    def test_mkcol(self):
        """Make a collection."""
        self.mkcol("/user/")

    def test_mkcol_overwrite(self):
        """Try to overwrite an existing collection."""
        self.mkcol("/user/")
        status = self.mkcol("/user/", check=False)
        assert status == 405

    def test_mkcol_intermediate(self):
        """Try make a collection in a unmapped collection."""
        status = self.mkcol("/unmapped/user/", check=False)
        assert status == 409

    def test_mkcol_make_calendar(self):
        """Make a calendar with additional props."""
        mkcol_make_calendar = get_file_content("mkcol_make_calendar.xml")
        self.mkcol("/calendar.ics/", mkcol_make_calendar)
        _, answer = self.get("/calendar.ics/")
        assert "BEGIN:VCALENDAR" in answer
        assert "END:VCALENDAR" in answer
        # Read additional properties
        propfind = get_file_content("propfind_calendar_color.xml")
        _, responses = self.propfind("/calendar.ics/", propfind)
        assert len(responses["/calendar.ics/"]) == 1
        status, prop = responses["/calendar.ics/"]["ICAL:calendar-color"]
        assert status == 200 and prop.text == "#BADA55"

    def test_move(self):
        """Move a item."""
        self.mkcalendar("/calendar.ics/")
        event = get_file_content("event1.ics")
        path1 = "/calendar.ics/event1.ics"
        path2 = "/calendar.ics/event2.ics"
        self.put(path1, event)
        status, _, _ = self.request(
            "MOVE", path1, HTTP_DESTINATION=path2, HTTP_HOST="")
        assert status == 201
        self.get(path1, check=404)
        self.get(path2)

    def test_move_between_colections(self):
        """Move a item."""
        self.mkcalendar("/calendar1.ics/")
        self.mkcalendar("/calendar2.ics/")
        event = get_file_content("event1.ics")
        path1 = "/calendar1.ics/event1.ics"
        path2 = "/calendar2.ics/event2.ics"
        self.put(path1, event)
        status, _, _ = self.request(
            "MOVE", path1, HTTP_DESTINATION=path2, HTTP_HOST="")
        assert status == 201
        self.get(path1, check=404)
        self.get(path2)

    def test_move_between_colections_duplicate_uid(self):
        """Move a item to a collection which already contains the UID."""
        self.mkcalendar("/calendar1.ics/")
        self.mkcalendar("/calendar2.ics/")
        event = get_file_content("event1.ics")
        path1 = "/calendar1.ics/event1.ics"
        path2 = "/calendar2.ics/event2.ics"
        self.put(path1, event)
        self.put("/calendar2.ics/event1.ics", event)
        status, _, answer = self.request(
            "MOVE", path1, HTTP_DESTINATION=path2, HTTP_HOST="")
        assert status in (403, 409)
        xml = DefusedET.fromstring(answer)
        assert xml.tag == xmlutils.make_clark("D:error")
        assert xml.find(xmlutils.make_clark("C:no-uid-conflict")) is not None

    def test_move_between_colections_overwrite(self):
        """Move a item to a collection which already contains the item."""
        self.mkcalendar("/calendar1.ics/")
        self.mkcalendar("/calendar2.ics/")
        event = get_file_content("event1.ics")
        path1 = "/calendar1.ics/event1.ics"
        path2 = "/calendar2.ics/event1.ics"
        self.put(path1, event)
        self.put(path2, event)
        status, _, _ = self.request(
            "MOVE", path1, HTTP_DESTINATION=path2, HTTP_HOST="")
        assert status == 412
        status, _, _ = self.request("MOVE", path1, HTTP_DESTINATION=path2,
                                    HTTP_HOST="", HTTP_OVERWRITE="T")
        assert status == 204

    def test_move_between_colections_overwrite_uid_conflict(self):
        """Move a item to a collection which already contains the item with
           a different UID."""
        self.mkcalendar("/calendar1.ics/")
        self.mkcalendar("/calendar2.ics/")
        event1 = get_file_content("event1.ics")
        event2 = get_file_content("event2.ics")
        path1 = "/calendar1.ics/event1.ics"
        path2 = "/calendar2.ics/event2.ics"
        self.put(path1, event1)
        self.put(path2, event2)
        status, _, answer = self.request("MOVE", path1, HTTP_DESTINATION=path2,
                                         HTTP_HOST="", HTTP_OVERWRITE="T")
        assert status in (403, 409)
        xml = DefusedET.fromstring(answer)
        assert xml.tag == xmlutils.make_clark("D:error")
        assert xml.find(xmlutils.make_clark("C:no-uid-conflict")) is not None

    def test_head(self):
        status, _, _ = self.request("HEAD", "/")
        assert status == 302

    def test_options(self):
        status, headers, _ = self.request("OPTIONS", "/")
        assert status == 200
        assert "DAV" in headers

    def test_delete_collection(self):
        """Delete a collection."""
        self.mkcalendar("/calendar.ics/")
        event = get_file_content("event1.ics")
        self.put("/calendar.ics/event1.ics", event)
        _, responses = self.delete("/calendar.ics/")
        assert responses["/calendar.ics/"] == 200
        self.get("/calendar.ics/", check=404)

    def test_delete_root_collection(self):
        """Delete the root collection."""
        self.mkcalendar("/calendar.ics/")
        event = get_file_content("event1.ics")
        self.put("/event1.ics", event)
        self.put("/calendar.ics/event1.ics", event)
        _, responses = self.delete("/")
        assert len(responses) == 1 and responses["/"] == 200
        self.get("/calendar.ics/", check=404)
        self.get("/event1.ics", 404)

    def test_propfind(self):
        calendar_path = "/calendar.ics/"
        self.mkcalendar("/calendar.ics/")
        event = get_file_content("event1.ics")
        event_path = posixpath.join(calendar_path, "event.ics")
        self.put(event_path, event)
        _, responses = self.propfind("/", HTTP_DEPTH=1)
        assert len(responses) == 2
        assert "/" in responses and calendar_path in responses
        _, responses = self.propfind(calendar_path, HTTP_DEPTH=1)
        assert len(responses) == 2
        assert calendar_path in responses and event_path in responses

    def test_propfind_propname(self):
        self.mkcalendar("/calendar.ics/")
        event = get_file_content("event1.ics")
        self.put("/calendar.ics/event.ics", event)
        propfind = get_file_content("propname.xml")
        _, responses = self.propfind("/calendar.ics/", propfind)
        status, prop = responses["/calendar.ics/"]["D:sync-token"]
        assert status == 200 and not prop.text
        _, responses = self.propfind("/calendar.ics/event.ics", propfind)
        status, prop = responses["/calendar.ics/event.ics"]["D:getetag"]
        assert status == 200 and not prop.text

    def test_propfind_allprop(self):
        self.mkcalendar("/calendar.ics/")
        event = get_file_content("event1.ics")
        self.put("/calendar.ics/event.ics", event)
        propfind = get_file_content("allprop.xml")
        _, responses = self.propfind("/calendar.ics/", propfind)
        status, prop = responses["/calendar.ics/"]["D:sync-token"]
        assert status == 200 and prop.text
        _, responses = self.propfind("/calendar.ics/event.ics", propfind)
        status, prop = responses["/calendar.ics/event.ics"]["D:getetag"]
        assert status == 200 and prop.text

    def test_propfind_nonexistent(self):
        """Read a property that does not exist."""
        self.mkcalendar("/calendar.ics/")
        propfind = get_file_content("propfind_calendar_color.xml")
        _, responses = self.propfind("/calendar.ics/", propfind)
        assert len(responses["/calendar.ics/"]) == 1
        status, prop = responses["/calendar.ics/"]["ICAL:calendar-color"]
        assert status == 404 and not prop.text

    def test_proppatch(self):
        """Set/Remove a property and read it back."""
        self.mkcalendar("/calendar.ics/")
        proppatch = get_file_content("proppatch_set_calendar_color.xml")
        _, responses = self.proppatch("/calendar.ics/", proppatch)
        assert len(responses["/calendar.ics/"]) == 1
        status, prop = responses["/calendar.ics/"]["ICAL:calendar-color"]
        assert status == 200 and not prop.text
        # Read property back
        propfind = get_file_content("propfind_calendar_color.xml")
        _, responses = self.propfind("/calendar.ics/", propfind)
        assert len(responses["/calendar.ics/"]) == 1
        status, prop = responses["/calendar.ics/"]["ICAL:calendar-color"]
        assert status == 200 and prop.text == "#BADA55"
        propfind = get_file_content("allprop.xml")
        _, responses = self.propfind("/calendar.ics/", propfind)
        status, prop = responses["/calendar.ics/"]["ICAL:calendar-color"]
        assert status == 200 and prop.text == "#BADA55"
        # Remove property
        proppatch = get_file_content("proppatch_remove_calendar_color.xml")
        _, responses = self.proppatch("/calendar.ics/", proppatch)
        assert len(responses["/calendar.ics/"]) == 1
        status, prop = responses["/calendar.ics/"]["ICAL:calendar-color"]
        assert status == 200 and not prop.text
        # Read property back
        propfind = get_file_content("propfind_calendar_color.xml")
        _, responses = self.propfind("/calendar.ics/", propfind)
        assert len(responses["/calendar.ics/"]) == 1
        status, prop = responses["/calendar.ics/"]["ICAL:calendar-color"]
        assert status == 404

    def test_proppatch_multiple1(self):
        """Set/Remove a multiple properties and read them back."""
        self.mkcalendar("/calendar.ics/")
        propfind = get_file_content("propfind_multiple.xml")
        proppatch = get_file_content("proppatch_set_multiple1.xml")
        _, responses = self.proppatch("/calendar.ics/", proppatch)
        assert len(responses["/calendar.ics/"]) == 2
        status, prop = responses["/calendar.ics/"]["ICAL:calendar-color"]
        assert status == 200 and not prop.text
        status, prop = responses["/calendar.ics/"]["C:calendar-description"]
        assert status == 200 and not prop.text
        # Read properties back
        _, responses = self.propfind("/calendar.ics/", propfind)
        assert len(responses["/calendar.ics/"]) == 2
        status, prop = responses["/calendar.ics/"]["ICAL:calendar-color"]
        assert status == 200 and prop.text == "#BADA55"
        status, prop = responses["/calendar.ics/"]["C:calendar-description"]
        assert status == 200 and prop.text == "test"
        # Remove properties
        proppatch = get_file_content("proppatch_remove_multiple1.xml")
        _, responses = self.proppatch("/calendar.ics/", proppatch)
        assert len(responses["/calendar.ics/"]) == 2
        status, prop = responses["/calendar.ics/"]["ICAL:calendar-color"]
        assert status == 200 and not prop.text
        status, prop = responses["/calendar.ics/"]["C:calendar-description"]
        assert status == 200 and not prop.text
        # Read properties back
        _, responses = self.propfind("/calendar.ics/", propfind)
        assert len(responses["/calendar.ics/"]) == 2
        status, prop = responses["/calendar.ics/"]["ICAL:calendar-color"]
        assert status == 404
        status, prop = responses["/calendar.ics/"]["C:calendar-description"]
        assert status == 404

    def test_proppatch_multiple2(self):
        """Set/Remove a multiple properties and read them back."""
        self.mkcalendar("/calendar.ics/")
        propfind = get_file_content("propfind_multiple.xml")
        proppatch = get_file_content("proppatch_set_multiple2.xml")
        _, responses = self.proppatch("/calendar.ics/", proppatch)
        assert len(responses["/calendar.ics/"]) == 2
        status, prop = responses["/calendar.ics/"]["ICAL:calendar-color"]
        assert status == 200 and not prop.text
        status, prop = responses["/calendar.ics/"]["C:calendar-description"]
        assert status == 200 and not prop.text
        # Read properties back
        _, responses = self.propfind("/calendar.ics/", propfind)
        assert len(responses["/calendar.ics/"]) == 2
        status, prop = responses["/calendar.ics/"]["ICAL:calendar-color"]
        assert status == 200 and prop.text == "#BADA55"
        status, prop = responses["/calendar.ics/"]["C:calendar-description"]
        assert status == 200 and prop.text == "test"
        # Remove properties
        proppatch = get_file_content("proppatch_remove_multiple2.xml")
        _, responses = self.proppatch("/calendar.ics/", proppatch)
        assert len(responses["/calendar.ics/"]) == 2
        status, prop = responses["/calendar.ics/"]["ICAL:calendar-color"]
        assert status == 200 and not prop.text
        status, prop = responses["/calendar.ics/"]["C:calendar-description"]
        assert status == 200 and not prop.text
        # Read properties back
        _, responses = self.propfind("/calendar.ics/", propfind)
        assert len(responses["/calendar.ics/"]) == 2
        status, prop = responses["/calendar.ics/"]["ICAL:calendar-color"]
        assert status == 404
        status, prop = responses["/calendar.ics/"]["C:calendar-description"]
        assert status == 404

    def test_proppatch_set_and_remove(self):
        """Set and remove multiple properties in single request."""
        self.mkcalendar("/calendar.ics/")
        propfind = get_file_content("propfind_multiple.xml")
        # Prepare
        proppatch = get_file_content("proppatch_set_multiple1.xml")
        self.proppatch("/calendar.ics/", proppatch)
        # Remove and set properties in single request
        proppatch = get_file_content("proppatch_set_and_remove.xml")
        _, responses = self.proppatch("/calendar.ics/", proppatch)
        assert len(responses["/calendar.ics/"]) == 2
        status, prop = responses["/calendar.ics/"]["ICAL:calendar-color"]
        assert status == 200 and not prop.text
        status, prop = responses["/calendar.ics/"]["C:calendar-description"]
        assert status == 200 and not prop.text
        # Read properties back
        _, responses = self.propfind("/calendar.ics/", propfind)
        assert len(responses["/calendar.ics/"]) == 2
        status, prop = responses["/calendar.ics/"]["ICAL:calendar-color"]
        assert status == 404
        status, prop = responses["/calendar.ics/"]["C:calendar-description"]
        assert status == 200 and prop.text == "test2"

    def test_put_whole_calendar_multiple_events_with_same_uid(self):
        """Add two events with the same UID."""
        self.put("/calendar.ics/", get_file_content("event2.ics"))
        _, responses = self.report("/calendar.ics/", """\
<?xml version="1.0" encoding="utf-8" ?>
<C:calendar-query xmlns:C="urn:ietf:params:xml:ns:caldav">
    <D:prop xmlns:D="DAV:">
        <D:getetag/>
    </D:prop>
</C:calendar-query>""")
        assert len(responses) == 1
        status, prop = responses["/calendar.ics/event2.ics"]["D:getetag"]
        assert status == 200 and prop.text
        _, answer = self.get("/calendar.ics/")
        assert answer.count("BEGIN:VEVENT") == 2

    def _test_filter(self, filters, kind="event", test=None, items=(1,)):
        filter_template = "<C:filter>%s</C:filter>"
        if kind in ("event", "journal", "todo"):
            create_collection_fn = self.mkcalendar
            path = "/calendar.ics/"
            filename_template = "%s%d.ics"
            namespace = "urn:ietf:params:xml:ns:caldav"
            report = "calendar-query"
        elif kind == "contact":
            create_collection_fn = self.create_addressbook
            if test:
                filter_template = '<C:filter test="%s">%%s</C:filter>' % test
            path = "/contacts.vcf/"
            filename_template = "%s%d.vcf"
            namespace = "urn:ietf:params:xml:ns:carddav"
            report = "addressbook-query"
        else:
            raise ValueError("Unsupported kind: %r" % kind)
        status, _, = self.delete(path, check=False)
        assert status in (200, 404)
        create_collection_fn(path)
        for i in items:
            filename = filename_template % (kind, i)
            event = get_file_content(filename)
            self.put(posixpath.join(path, filename), event)
        filters_text = "".join(filter_template % f for f in filters)
        _, responses = self.report(path, """\
<?xml version="1.0" encoding="utf-8" ?>
<C:{1} xmlns:C="{0}">
    <D:prop xmlns:D="DAV:">
        <D:getetag/>
    </D:prop>
    {2}
</C:{1}>""".format(namespace, report, filters_text))
        paths = []
        for path, props in responses.items():
            assert len(props) == 1
            status, prop = props["D:getetag"]
            assert status == 200 and prop.text
            paths.append(path)
        return paths

    def test_addressbook_empty_filter(self):
        self._test_filter([""], kind="contact")

    def test_addressbook_prop_filter(self):
        assert "/contacts.vcf/contact1.vcf" in self._test_filter(["""\
<C:prop-filter name="NICKNAME">
    <C:text-match collation="i;unicode-casemap" match-type="contains"
        >es</C:text-match>
</C:prop-filter>"""], "contact")
        assert "/contacts.vcf/contact1.vcf" in self._test_filter(["""\
<C:prop-filter name="NICKNAME">
    <C:text-match collation="i;unicode-casemap">es</C:text-match>
</C:prop-filter>"""], "contact")
        assert "/contacts.vcf/contact1.vcf" not in self._test_filter(["""\
<C:prop-filter name="NICKNAME">
    <C:text-match collation="i;unicode-casemap" match-type="contains"
        >a</C:text-match>
</C:prop-filter>"""], "contact")
        assert "/contacts.vcf/contact1.vcf" in self._test_filter(["""\
<C:prop-filter name="NICKNAME">
    <C:text-match collation="i;unicode-casemap" match-type="equals"
        >test</C:text-match>
</C:prop-filter>"""], "contact")
        assert "/contacts.vcf/contact1.vcf" not in self._test_filter(["""\
<C:prop-filter name="NICKNAME">
    <C:text-match collation="i;unicode-casemap" match-type="equals"
        >tes</C:text-match>
</C:prop-filter>"""], "contact")
        assert "/contacts.vcf/contact1.vcf" not in self._test_filter(["""\
<C:prop-filter name="NICKNAME">
    <C:text-match collation="i;unicode-casemap" match-type="equals"
        >est</C:text-match>
</C:prop-filter>"""], "contact")
        assert "/contacts.vcf/contact1.vcf" in self._test_filter(["""\
<C:prop-filter name="NICKNAME">
    <C:text-match collation="i;unicode-casemap" match-type="starts-with"
        >tes</C:text-match>
</C:prop-filter>"""], "contact")
        assert "/contacts.vcf/contact1.vcf" not in self._test_filter(["""\
<C:prop-filter name="NICKNAME">
    <C:text-match collation="i;unicode-casemap" match-type="starts-with"
        >est</C:text-match>
</C:prop-filter>"""], "contact")
        assert "/contacts.vcf/contact1.vcf" in self._test_filter(["""\
<C:prop-filter name="NICKNAME">
    <C:text-match collation="i;unicode-casemap" match-type="ends-with"
        >est</C:text-match>
</C:prop-filter>"""], "contact")
        assert "/contacts.vcf/contact1.vcf" not in self._test_filter(["""\
<C:prop-filter name="NICKNAME">
    <C:text-match collation="i;unicode-casemap" match-type="ends-with"
        >tes</C:text-match>
</C:prop-filter>"""], "contact")

    def test_addressbook_prop_filter_any(self):
        assert "/contacts.vcf/contact1.vcf" in self._test_filter(["""\
<C:prop-filter name="NICKNAME">
    <C:text-match collation="i;unicode-casemap">test</C:text-match>
</C:prop-filter>
<C:prop-filter name="EMAIL">
    <C:text-match collation="i;unicode-casemap">test</C:text-match>
</C:prop-filter>"""], "contact", test="anyof")
        assert "/contacts.vcf/contact1.vcf" not in self._test_filter(["""\
<C:prop-filter name="NICKNAME">
    <C:text-match collation="i;unicode-casemap">a</C:text-match>
</C:prop-filter>
<C:prop-filter name="EMAIL">
    <C:text-match collation="i;unicode-casemap">test</C:text-match>
</C:prop-filter>"""], "contact", test="anyof")
        assert "/contacts.vcf/contact1.vcf" in self._test_filter(["""\
<C:prop-filter name="NICKNAME">
    <C:text-match collation="i;unicode-casemap">test</C:text-match>
</C:prop-filter>
<C:prop-filter name="EMAIL">
    <C:text-match collation="i;unicode-casemap">test</C:text-match>
</C:prop-filter>"""], "contact")

    def test_addressbook_prop_filter_all(self):
        assert "/contacts.vcf/contact1.vcf" in self._test_filter(["""\
<C:prop-filter name="NICKNAME">
    <C:text-match collation="i;unicode-casemap">tes</C:text-match>
</C:prop-filter>
<C:prop-filter name="NICKNAME">
    <C:text-match collation="i;unicode-casemap">est</C:text-match>
</C:prop-filter>"""], "contact", test="allof")
        assert "/contacts.vcf/contact1.vcf" not in self._test_filter(["""\
<C:prop-filter name="NICKNAME">
    <C:text-match collation="i;unicode-casemap">test</C:text-match>
</C:prop-filter>
<C:prop-filter name="EMAIL">
    <C:text-match collation="i;unicode-casemap">test</C:text-match>
</C:prop-filter>"""], "contact", test="allof")

    def test_calendar_empty_filter(self):
        self._test_filter([""])

    def test_calendar_tag_filter(self):
        """Report request with tag-based filter on calendar."""
        assert "/calendar.ics/event1.ics" in self._test_filter(["""\
<C:comp-filter name="VCALENDAR"></C:comp-filter>"""])

    def test_item_tag_filter(self):
        """Report request with tag-based filter on an item."""
        assert "/calendar.ics/event1.ics" in self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
    <C:comp-filter name="VEVENT"></C:comp-filter>
</C:comp-filter>"""])
        assert "/calendar.ics/event1.ics" not in self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
    <C:comp-filter name="VTODO"></C:comp-filter>
</C:comp-filter>"""])

    def test_item_not_tag_filter(self):
        """Report request with tag-based is-not filter on an item."""
        assert "/calendar.ics/event1.ics" not in self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
    <C:comp-filter name="VEVENT">
        <C:is-not-defined />
    </C:comp-filter>
</C:comp-filter>"""])
        assert "/calendar.ics/event1.ics" in self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
    <C:comp-filter name="VTODO">
        <C:is-not-defined />
    </C:comp-filter>
</C:comp-filter>"""])

    def test_item_prop_filter(self):
        """Report request with prop-based filter on an item."""
        assert "/calendar.ics/event1.ics" in self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
    <C:comp-filter name="VEVENT">
        <C:prop-filter name="SUMMARY"></C:prop-filter>
    </C:comp-filter>
</C:comp-filter>"""])
        assert "/calendar.ics/event1.ics" not in self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
    <C:comp-filter name="VEVENT">
        <C:prop-filter name="UNKNOWN"></C:prop-filter>
    </C:comp-filter>
</C:comp-filter>"""])

    def test_item_not_prop_filter(self):
        """Report request with prop-based is-not filter on an item."""
        assert "/calendar.ics/event1.ics" not in self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
    <C:comp-filter name="VEVENT">
        <C:prop-filter name="SUMMARY">
            <C:is-not-defined />
        </C:prop-filter>
    </C:comp-filter>
</C:comp-filter>"""])
        assert "/calendar.ics/event1.ics" in self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
    <C:comp-filter name="VEVENT">
        <C:prop-filter name="UNKNOWN">
            <C:is-not-defined />
        </C:prop-filter>
    </C:comp-filter>
</C:comp-filter>"""])

    def test_mutiple_filters(self):
        """Report request with multiple filters on an item."""
        assert "/calendar.ics/event1.ics" not in self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
    <C:comp-filter name="VEVENT">
        <C:prop-filter name="SUMMARY">
            <C:is-not-defined />
        </C:prop-filter>
    </C:comp-filter>
</C:comp-filter>""", """
<C:comp-filter name="VCALENDAR">
    <C:comp-filter name="VEVENT">
        <C:prop-filter name="UNKNOWN">
            <C:is-not-defined />
        </C:prop-filter>
    </C:comp-filter>
</C:comp-filter>"""])
        assert "/calendar.ics/event1.ics" in self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
    <C:comp-filter name="VEVENT">
        <C:prop-filter name="SUMMARY"></C:prop-filter>
    </C:comp-filter>
</C:comp-filter>""", """
<C:comp-filter name="VCALENDAR">
    <C:comp-filter name="VEVENT">
        <C:prop-filter name="UNKNOWN">
            <C:is-not-defined />
        </C:prop-filter>
    </C:comp-filter>
</C:comp-filter>"""])
        assert "/calendar.ics/event1.ics" in self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
    <C:comp-filter name="VEVENT">
        <C:prop-filter name="SUMMARY"></C:prop-filter>
        <C:prop-filter name="UNKNOWN">
            <C:is-not-defined />
        </C:prop-filter>
    </C:comp-filter>
</C:comp-filter>"""])

    def test_text_match_filter(self):
        """Report request with text-match filter on calendar."""
        assert "/calendar.ics/event1.ics" in self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
    <C:comp-filter name="VEVENT">
        <C:prop-filter name="SUMMARY">
            <C:text-match>event</C:text-match>
        </C:prop-filter>
    </C:comp-filter>
</C:comp-filter>"""])
        assert "/calendar.ics/event1.ics" not in self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
    <C:comp-filter name="VEVENT">
        <C:prop-filter name="UNKNOWN">
            <C:text-match>event</C:text-match>
        </C:prop-filter>
    </C:comp-filter>
</C:comp-filter>"""])
        assert "/calendar.ics/event1.ics" not in self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
    <C:comp-filter name="VEVENT">
        <C:prop-filter name="SUMMARY">
            <C:text-match>unknown</C:text-match>
        </C:prop-filter>
    </C:comp-filter>
</C:comp-filter>"""])
        assert "/calendar.ics/event1.ics" not in self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
    <C:comp-filter name="VEVENT">
        <C:prop-filter name="SUMMARY">
            <C:text-match negate-condition="yes">event</C:text-match>
        </C:prop-filter>
    </C:comp-filter>
</C:comp-filter>"""])

    def test_param_filter(self):
        """Report request with param-filter on calendar."""
        assert "/calendar.ics/event1.ics" in self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
    <C:comp-filter name="VEVENT">
        <C:prop-filter name="ATTENDEE">
            <C:param-filter name="PARTSTAT">
                <C:text-match collation="i;ascii-casemap"
                    >ACCEPTED</C:text-match>
            </C:param-filter>
        </C:prop-filter>
    </C:comp-filter>
</C:comp-filter>"""])
        assert "/calendar.ics/event1.ics" not in self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
    <C:comp-filter name="VEVENT">
        <C:prop-filter name="ATTENDEE">
            <C:param-filter name="PARTSTAT">
                <C:text-match collation="i;ascii-casemap"
                    >UNKNOWN</C:text-match>
            </C:param-filter>
        </C:prop-filter>
    </C:comp-filter>
</C:comp-filter>"""])
        assert "/calendar.ics/event1.ics" not in self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
    <C:comp-filter name="VEVENT">
        <C:prop-filter name="ATTENDEE">
            <C:param-filter name="PARTSTAT">
                <C:is-not-defined />
            </C:param-filter>
        </C:prop-filter>
    </C:comp-filter>
</C:comp-filter>"""])
        assert "/calendar.ics/event1.ics" in self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
    <C:comp-filter name="VEVENT">
        <C:prop-filter name="ATTENDEE">
            <C:param-filter name="UNKNOWN">
                <C:is-not-defined />
            </C:param-filter>
        </C:prop-filter>
    </C:comp-filter>
</C:comp-filter>"""])

    def test_time_range_filter_events(self):
        """Report request with time-range filter on events."""
        answer = self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
    <C:comp-filter name="VEVENT">
        <C:time-range start="20130801T000000Z" end="20131001T000000Z"/>
    </C:comp-filter>
</C:comp-filter>"""], "event", items=range(1, 6))
        assert "/calendar.ics/event1.ics" in answer
        assert "/calendar.ics/event2.ics" in answer
        assert "/calendar.ics/event3.ics" in answer
        assert "/calendar.ics/event4.ics" in answer
        assert "/calendar.ics/event5.ics" in answer
        answer = self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
    <C:comp-filter name="VTODO">
        <C:time-range start="20130801T000000Z" end="20131001T000000Z"/>
    </C:comp-filter>
</C:comp-filter>"""], "event", items=range(1, 6))
        assert "/calendar.ics/event1.ics" not in answer
        answer = self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
    <C:comp-filter name="VEVENT">
        <C:prop-filter name="ATTENDEE">
            <C:param-filter name="PARTSTAT">
                <C:is-not-defined />
            </C:param-filter>
        </C:prop-filter>
        <C:time-range start="20130801T000000Z" end="20131001T000000Z"/>
    </C:comp-filter>
</C:comp-filter>"""], items=range(1, 6))
        assert "/calendar.ics/event1.ics" not in answer
        assert "/calendar.ics/event2.ics" not in answer
        assert "/calendar.ics/event3.ics" not in answer
        assert "/calendar.ics/event4.ics" not in answer
        assert "/calendar.ics/event5.ics" not in answer
        answer = self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
    <C:comp-filter name="VEVENT">
        <C:time-range start="20130902T000000Z" end="20131001T000000Z"/>
    </C:comp-filter>
</C:comp-filter>"""], items=range(1, 6))
        assert "/calendar.ics/event1.ics" not in answer
        assert "/calendar.ics/event2.ics" in answer
        assert "/calendar.ics/event3.ics" in answer
        assert "/calendar.ics/event4.ics" in answer
        assert "/calendar.ics/event5.ics" in answer
        answer = self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
    <C:comp-filter name="VEVENT">
        <C:time-range start="20130903T000000Z" end="20130908T000000Z"/>
    </C:comp-filter>
</C:comp-filter>"""], items=range(1, 6))
        assert "/calendar.ics/event1.ics" not in answer
        assert "/calendar.ics/event2.ics" not in answer
        assert "/calendar.ics/event3.ics" in answer
        assert "/calendar.ics/event4.ics" in answer
        assert "/calendar.ics/event5.ics" in answer
        answer = self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
    <C:comp-filter name="VEVENT">
        <C:time-range start="20130903T000000Z" end="20130904T000000Z"/>
    </C:comp-filter>
</C:comp-filter>"""], items=range(1, 6))
        assert "/calendar.ics/event1.ics" not in answer
        assert "/calendar.ics/event2.ics" not in answer
        assert "/calendar.ics/event3.ics" in answer
        assert "/calendar.ics/event4.ics" not in answer
        assert "/calendar.ics/event5.ics" not in answer
        answer = self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
    <C:comp-filter name="VEVENT">
        <C:time-range start="20130805T000000Z" end="20130810T000000Z"/>
    </C:comp-filter>
</C:comp-filter>"""], items=range(1, 6))
        assert "/calendar.ics/event1.ics" not in answer
        assert "/calendar.ics/event2.ics" not in answer
        assert "/calendar.ics/event3.ics" not in answer
        assert "/calendar.ics/event4.ics" not in answer
        assert "/calendar.ics/event5.ics" not in answer
        # HACK: VObject doesn't match RECURRENCE-ID to recurrences, the
        # overwritten recurrence is still used for filtering.
        answer = self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
    <C:comp-filter name="VEVENT">
        <C:time-range start="20170601T063000Z" end="20170601T070000Z"/>
    </C:comp-filter>
</C:comp-filter>"""], items=(6, 7, 8, 9))
        assert "/calendar.ics/event6.ics" in answer
        assert "/calendar.ics/event7.ics" in answer
        assert "/calendar.ics/event8.ics" in answer
        assert "/calendar.ics/event9.ics" in answer
        answer = self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
    <C:comp-filter name="VEVENT">
        <C:time-range start="20170701T060000Z"/>
    </C:comp-filter>
</C:comp-filter>"""], items=(6, 7, 8, 9))
        assert "/calendar.ics/event6.ics" in answer
        assert "/calendar.ics/event7.ics" in answer
        assert "/calendar.ics/event8.ics" in answer
        assert "/calendar.ics/event9.ics" not in answer
        answer = self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
    <C:comp-filter name="VEVENT">
        <C:time-range start="20170702T070000Z" end="20170704T060000Z"/>
    </C:comp-filter>
</C:comp-filter>"""], items=(6, 7, 8, 9))
        assert "/calendar.ics/event6.ics" not in answer
        assert "/calendar.ics/event7.ics" not in answer
        assert "/calendar.ics/event8.ics" not in answer
        assert "/calendar.ics/event9.ics" not in answer
        answer = self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
    <C:comp-filter name="VEVENT">
        <C:time-range start="20170602T075959Z" end="20170602T080000Z"/>
    </C:comp-filter>
</C:comp-filter>"""], items=(9,))
        assert "/calendar.ics/event9.ics" in answer
        answer = self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
    <C:comp-filter name="VEVENT">
        <C:time-range start="20170602T080000Z" end="20170603T083000Z"/>
    </C:comp-filter>
</C:comp-filter>"""], items=(9,))
        assert "/calendar.ics/event9.ics" not in answer

    def test_time_range_filter_events_rrule(self):
        """Report request with time-range filter on events with rrules."""
        answer = self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
    <C:comp-filter name="VEVENT">
        <C:time-range start="20130801T000000Z" end="20131001T000000Z"/>
    </C:comp-filter>
</C:comp-filter>"""], "event", items=(1, 2))
        assert "/calendar.ics/event1.ics" in answer
        assert "/calendar.ics/event2.ics" in answer
        answer = self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
    <C:comp-filter name="VEVENT">
        <C:time-range start="20140801T000000Z" end="20141001T000000Z"/>
    </C:comp-filter>
</C:comp-filter>"""], "event", items=(1, 2))
        assert "/calendar.ics/event1.ics" not in answer
        assert "/calendar.ics/event2.ics" in answer
        answer = self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
    <C:comp-filter name="VEVENT">
        <C:time-range start="20120801T000000Z" end="20121001T000000Z"/>
    </C:comp-filter>
</C:comp-filter>"""], "event", items=(1, 2))
        assert "/calendar.ics/event1.ics" not in answer
        assert "/calendar.ics/event2.ics" not in answer
        answer = self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
    <C:comp-filter name="VEVENT">
        <C:time-range start="20130903T000000Z" end="20130907T000000Z"/>
    </C:comp-filter>
</C:comp-filter>"""], "event", items=(1, 2))
        assert "/calendar.ics/event1.ics" not in answer
        assert "/calendar.ics/event2.ics" not in answer

    def test_time_range_filter_todos(self):
        """Report request with time-range filter on todos."""
        answer = self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
    <C:comp-filter name="VTODO">
        <C:time-range start="20130801T000000Z" end="20131001T000000Z"/>
    </C:comp-filter>
</C:comp-filter>"""], "todo", items=range(1, 9))
        assert "/calendar.ics/todo1.ics" in answer
        assert "/calendar.ics/todo2.ics" in answer
        assert "/calendar.ics/todo3.ics" in answer
        assert "/calendar.ics/todo4.ics" in answer
        assert "/calendar.ics/todo5.ics" in answer
        assert "/calendar.ics/todo6.ics" in answer
        assert "/calendar.ics/todo7.ics" in answer
        assert "/calendar.ics/todo8.ics" in answer
        answer = self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
    <C:comp-filter name="VTODO">
        <C:time-range start="20130901T160000Z" end="20130901T183000Z"/>
    </C:comp-filter>
</C:comp-filter>"""], "todo", items=range(1, 9))
        assert "/calendar.ics/todo1.ics" not in answer
        assert "/calendar.ics/todo2.ics" in answer
        assert "/calendar.ics/todo3.ics" in answer
        assert "/calendar.ics/todo4.ics" not in answer
        assert "/calendar.ics/todo5.ics" not in answer
        assert "/calendar.ics/todo6.ics" not in answer
        assert "/calendar.ics/todo7.ics" in answer
        assert "/calendar.ics/todo8.ics" in answer
        answer = self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
    <C:comp-filter name="VTODO">
        <C:time-range start="20130903T160000Z" end="20130901T183000Z"/>
    </C:comp-filter>
</C:comp-filter>"""], "todo", items=range(1, 9))
        assert "/calendar.ics/todo2.ics" not in answer
        answer = self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
    <C:comp-filter name="VTODO">
        <C:time-range start="20130903T160000Z" end="20130901T173000Z"/>
    </C:comp-filter>
</C:comp-filter>"""], "todo", items=range(1, 9))
        assert "/calendar.ics/todo2.ics" not in answer
        answer = self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
    <C:comp-filter name="VTODO">
        <C:time-range start="20130903T160000Z" end="20130903T173000Z"/>
    </C:comp-filter>
</C:comp-filter>"""], "todo", items=range(1, 9))
        assert "/calendar.ics/todo3.ics" not in answer
        answer = self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
    <C:comp-filter name="VTODO">
        <C:time-range start="20130903T160000Z" end="20130803T203000Z"/>
    </C:comp-filter>
</C:comp-filter>"""], "todo", items=range(1, 9))
        assert "/calendar.ics/todo7.ics" in answer

    def test_time_range_filter_todos_rrule(self):
        """Report request with time-range filter on todos with rrules."""
        answer = self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
    <C:comp-filter name="VTODO">
        <C:time-range start="20130801T000000Z" end="20131001T000000Z"/>
    </C:comp-filter>
</C:comp-filter>"""], "todo", items=(1, 2, 9))
        assert "/calendar.ics/todo1.ics" in answer
        assert "/calendar.ics/todo2.ics" in answer
        assert "/calendar.ics/todo9.ics" in answer
        answer = self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
    <C:comp-filter name="VTODO">
        <C:time-range start="20140801T000000Z" end="20141001T000000Z"/>
    </C:comp-filter>
</C:comp-filter>"""], "todo", items=(1, 2, 9))
        assert "/calendar.ics/todo1.ics" not in answer
        assert "/calendar.ics/todo2.ics" in answer
        assert "/calendar.ics/todo9.ics" in answer
        answer = self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
    <C:comp-filter name="VTODO">
        <C:time-range start="20140902T000000Z" end="20140903T000000Z"/>
    </C:comp-filter>
</C:comp-filter>"""], "todo", items=(1, 2))
        assert "/calendar.ics/todo1.ics" not in answer
        assert "/calendar.ics/todo2.ics" in answer
        answer = self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
    <C:comp-filter name="VTODO">
        <C:time-range start="20140904T000000Z" end="20140914T000000Z"/>
    </C:comp-filter>
</C:comp-filter>"""], "todo", items=(1, 2))
        assert "/calendar.ics/todo1.ics" not in answer
        assert "/calendar.ics/todo2.ics" not in answer
        answer = self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
    <C:comp-filter name="VTODO">
        <C:time-range start="20130902T000000Z" end="20130906T235959Z"/>
    </C:comp-filter>
</C:comp-filter>"""], "todo", items=(9,))
        assert "/calendar.ics/todo9.ics" not in answer

    def test_time_range_filter_journals(self):
        """Report request with time-range filter on journals."""
        answer = self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
    <C:comp-filter name="VJOURNAL">
        <C:time-range start="19991229T000000Z" end="20000202T000000Z"/>
    </C:comp-filter>
</C:comp-filter>"""], "journal", items=(1, 2, 3))
        assert "/calendar.ics/journal1.ics" not in answer
        assert "/calendar.ics/journal2.ics" in answer
        assert "/calendar.ics/journal3.ics" in answer
        answer = self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
    <C:comp-filter name="VJOURNAL">
        <C:time-range start="19991229T000000Z" end="20000202T000000Z"/>
    </C:comp-filter>
</C:comp-filter>"""], "journal", items=(1, 2, 3))
        assert "/calendar.ics/journal1.ics" not in answer
        assert "/calendar.ics/journal2.ics" in answer
        assert "/calendar.ics/journal3.ics" in answer
        answer = self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
    <C:comp-filter name="VJOURNAL">
        <C:time-range start="19981229T000000Z" end="19991012T000000Z"/>
    </C:comp-filter>
</C:comp-filter>"""], "journal", items=(1, 2, 3))
        assert "/calendar.ics/journal1.ics" not in answer
        assert "/calendar.ics/journal2.ics" not in answer
        assert "/calendar.ics/journal3.ics" not in answer
        answer = self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
    <C:comp-filter name="VJOURNAL">
        <C:time-range start="20131229T000000Z" end="21520202T000000Z"/>
    </C:comp-filter>
</C:comp-filter>"""], "journal", items=(1, 2, 3))
        assert "/calendar.ics/journal1.ics" not in answer
        assert "/calendar.ics/journal2.ics" in answer
        assert "/calendar.ics/journal3.ics" not in answer
        answer = self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
    <C:comp-filter name="VJOURNAL">
        <C:time-range start="20000101T000000Z" end="20000202T000000Z"/>
    </C:comp-filter>
</C:comp-filter>"""], "journal", items=(1, 2, 3))
        assert "/calendar.ics/journal1.ics" not in answer
        assert "/calendar.ics/journal2.ics" in answer
        assert "/calendar.ics/journal3.ics" in answer

    def test_time_range_filter_journals_rrule(self):
        """Report request with time-range filter on journals with rrules."""
        answer = self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
    <C:comp-filter name="VJOURNAL">
        <C:time-range start="19991229T000000Z" end="20000202T000000Z"/>
    </C:comp-filter>
</C:comp-filter>"""], "journal", items=(1, 2))
        assert "/calendar.ics/journal1.ics" not in answer
        assert "/calendar.ics/journal2.ics" in answer
        answer = self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
    <C:comp-filter name="VJOURNAL">
        <C:time-range start="20051229T000000Z" end="20060202T000000Z"/>
    </C:comp-filter>
</C:comp-filter>"""], "journal", items=(1, 2))
        assert "/calendar.ics/journal1.ics" not in answer
        assert "/calendar.ics/journal2.ics" in answer
        answer = self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
    <C:comp-filter name="VJOURNAL">
        <C:time-range start="20060102T000000Z" end="20060202T000000Z"/>
    </C:comp-filter>
</C:comp-filter>"""], "journal", items=(1, 2))
        assert "/calendar.ics/journal1.ics" not in answer
        assert "/calendar.ics/journal2.ics" not in answer

    def test_report_item(self):
        """Test report request on an item"""
        calendar_path = "/calendar.ics/"
        self.mkcalendar(calendar_path)
        event = get_file_content("event1.ics")
        event_path = posixpath.join(calendar_path, "event.ics")
        self.put(event_path, event)
        _, responses = self.report(event_path, """\
<?xml version="1.0" encoding="utf-8" ?>
<C:calendar-query xmlns:C="urn:ietf:params:xml:ns:caldav">
    <D:prop xmlns:D="DAV:">
        <D:getetag />
    </D:prop>
</C:calendar-query>""")
        assert len(responses) == 1
        status, prop = responses[event_path]["D:getetag"]
        assert status == 200 and prop.text

    def _report_sync_token(self, calendar_path, sync_token=None):
        sync_token_xml = (
            "<sync-token><![CDATA[%s]]></sync-token>" % sync_token
            if sync_token else "<sync-token />")
        status, _, answer = self.request("REPORT", calendar_path, """\
<?xml version="1.0" encoding="utf-8" ?>
<sync-collection xmlns="DAV:">
    <prop>
        <getetag />
    </prop>
    %s
</sync-collection>""" % sync_token_xml)
        xml = DefusedET.fromstring(answer)
        if status in (403, 409):
            assert xml.tag == xmlutils.make_clark("D:error")
            assert sync_token and xml.find(
                xmlutils.make_clark("D:valid-sync-token")) is not None
            return None, None
        assert status == 207
        assert xml.tag == xmlutils.make_clark("D:multistatus")
        sync_token = xml.find(xmlutils.make_clark("D:sync-token")).text.strip()
        assert sync_token
        responses = self.parse_responses(answer)
        for href, response in responses.items():
            if not isinstance(response, int):
                status, prop = response["D:getetag"]
                assert status == 200 and prop.text and len(response) == 1
                responses[href] = response = 200
            assert response in (200, 404)
        return sync_token, responses

    def test_report_sync_collection_no_change(self):
        """Test sync-collection report without modifying the collection"""
        calendar_path = "/calendar.ics/"
        self.mkcalendar(calendar_path)
        event = get_file_content("event1.ics")
        event_path = posixpath.join(calendar_path, "event.ics")
        self.put(event_path, event)
        sync_token, responses = self._report_sync_token(calendar_path)
        assert len(responses) == 1 and responses[event_path] == 200
        new_sync_token, responses = self._report_sync_token(
            calendar_path, sync_token)
        if not self.full_sync_token_support and not new_sync_token:
            return
        assert sync_token == new_sync_token and len(responses) == 0

    def test_report_sync_collection_add(self):
        """Test sync-collection report with an added item"""
        calendar_path = "/calendar.ics/"
        self.mkcalendar(calendar_path)
        sync_token, responses = self._report_sync_token(calendar_path)
        assert len(responses) == 0
        event = get_file_content("event1.ics")
        event_path = posixpath.join(calendar_path, "event.ics")
        self.put(event_path, event)
        sync_token, responses = self._report_sync_token(
            calendar_path, sync_token)
        if not self.full_sync_token_support and not sync_token:
            return
        assert len(responses) == 1 and responses[event_path] == 200

    def test_report_sync_collection_delete(self):
        """Test sync-collection report with a deleted item"""
        calendar_path = "/calendar.ics/"
        self.mkcalendar(calendar_path)
        event = get_file_content("event1.ics")
        event_path = posixpath.join(calendar_path, "event.ics")
        self.put(event_path, event)
        sync_token, responses = self._report_sync_token(calendar_path)
        assert len(responses) == 1 and responses[event_path] == 200
        self.delete(event_path)
        sync_token, responses = self._report_sync_token(
            calendar_path, sync_token)
        if not self.full_sync_token_support and not sync_token:
            return
        assert len(responses) == 1 and responses[event_path] == 404

    def test_report_sync_collection_create_delete(self):
        """Test sync-collection report with a created and deleted item"""
        calendar_path = "/calendar.ics/"
        self.mkcalendar(calendar_path)
        sync_token, responses = self._report_sync_token(calendar_path)
        assert len(responses) == 0
        event = get_file_content("event1.ics")
        event_path = posixpath.join(calendar_path, "event.ics")
        self.put(event_path, event)
        self.delete(event_path)
        sync_token, responses = self._report_sync_token(
            calendar_path, sync_token)
        if not self.full_sync_token_support and not sync_token:
            return
        assert len(responses) == 1 and responses[event_path] == 404

    def test_report_sync_collection_modify_undo(self):
        """Test sync-collection report with a modified and changed back item"""
        calendar_path = "/calendar.ics/"
        self.mkcalendar(calendar_path)
        event1 = get_file_content("event1.ics")
        event2 = get_file_content("event1_modified.ics")
        event_path = posixpath.join(calendar_path, "event.ics")
        self.put(event_path, event1)
        sync_token, responses = self._report_sync_token(calendar_path)
        assert len(responses) == 1 and responses[event_path] == 200
        self.put(event_path, event2)
        self.put(event_path, event1)
        sync_token, responses = self._report_sync_token(
            calendar_path, sync_token)
        if not self.full_sync_token_support and not sync_token:
            return
        assert len(responses) == 1 and responses[event_path] == 200

    def test_report_sync_collection_move(self):
        """Test sync-collection report a moved item"""
        calendar_path = "/calendar.ics/"
        self.mkcalendar(calendar_path)
        event = get_file_content("event1.ics")
        event1_path = posixpath.join(calendar_path, "event1.ics")
        event2_path = posixpath.join(calendar_path, "event2.ics")
        self.put(event1_path, event)
        sync_token, responses = self._report_sync_token(calendar_path)
        assert len(responses) == 1 and responses[event1_path] == 200
        status, _, _ = self.request(
            "MOVE", event1_path, HTTP_DESTINATION=event2_path, HTTP_HOST="")
        assert status == 201
        sync_token, responses = self._report_sync_token(
            calendar_path, sync_token)
        if not self.full_sync_token_support and not sync_token:
            return
        assert len(responses) == 2 and (responses[event1_path] == 404 and
                                        responses[event2_path] == 200)

    def test_report_sync_collection_move_undo(self):
        """Test sync-collection report with a moved and moved back item"""
        calendar_path = "/calendar.ics/"
        self.mkcalendar(calendar_path)
        event = get_file_content("event1.ics")
        event1_path = posixpath.join(calendar_path, "event1.ics")
        event2_path = posixpath.join(calendar_path, "event2.ics")
        self.put(event1_path, event)
        sync_token, responses = self._report_sync_token(calendar_path)
        assert len(responses) == 1 and responses[event1_path] == 200
        status, _, _ = self.request(
            "MOVE", event1_path, HTTP_DESTINATION=event2_path, HTTP_HOST="")
        assert status == 201
        status, _, _ = self.request(
            "MOVE", event2_path, HTTP_DESTINATION=event1_path, HTTP_HOST="")
        assert status == 201
        sync_token, responses = self._report_sync_token(
            calendar_path, sync_token)
        if not self.full_sync_token_support and not sync_token:
            return
        assert len(responses) == 2 and (responses[event1_path] == 200 and
                                        responses[event2_path] == 404)

    def test_report_sync_collection_invalid_sync_token(self):
        """Test sync-collection report with an invalid sync token"""
        calendar_path = "/calendar.ics/"
        self.mkcalendar(calendar_path)
        sync_token, _ = self._report_sync_token(
            calendar_path, "http://radicale.org/ns/sync/INVALID")
        assert not sync_token

    def test_propfind_sync_token(self):
        """Retrieve the sync-token with a propfind request"""
        calendar_path = "/calendar.ics/"
        self.mkcalendar(calendar_path)
        propfind = get_file_content("allprop.xml")
        _, responses = self.propfind(calendar_path, propfind)
        status, sync_token = responses[calendar_path]["D:sync-token"]
        assert status == 200 and sync_token.text
        event = get_file_content("event1.ics")
        event_path = posixpath.join(calendar_path, "event.ics")
        self.put(event_path, event)
        _, responses = self.propfind(calendar_path, propfind)
        status, new_sync_token = responses[calendar_path]["D:sync-token"]
        assert status == 200 and new_sync_token.text
        assert sync_token.text != new_sync_token.text

    def test_propfind_same_as_sync_collection_sync_token(self):
        """Compare sync-token property with sync-collection sync-token"""
        calendar_path = "/calendar.ics/"
        self.mkcalendar(calendar_path)
        propfind = get_file_content("allprop.xml")
        _, responses = self.propfind(calendar_path, propfind)
        status, sync_token = responses[calendar_path]["D:sync-token"]
        assert status == 200 and sync_token.text
        report_sync_token, _ = self._report_sync_token(calendar_path)
        assert sync_token.text == report_sync_token

    def test_calendar_getcontenttype(self):
        """Test report request on an item"""
        self.mkcalendar("/test/")
        for component in ("event", "todo", "journal"):
            event = get_file_content("%s1.ics" % component)
            status, _ = self.delete("/test/test.ics", check=False)
            assert status in (200, 404)
            self.put("/test/test.ics", event)
            _, responses = self.report("/test/", """\
<?xml version="1.0" encoding="utf-8" ?>
<C:calendar-query xmlns:C="urn:ietf:params:xml:ns:caldav">
    <D:prop xmlns:D="DAV:">
        <D:getcontenttype />
    </D:prop>
</C:calendar-query>""")
            assert len(responses) == 1 and len(
                responses["/test/test.ics"]) == 1
            status, prop = responses["/test/test.ics"]["D:getcontenttype"]
            assert status == 200 and prop.text == (
                "text/calendar;charset=utf-8;component=V%s" %
                component.upper())

    def test_addressbook_getcontenttype(self):
        """Test report request on an item"""
        self.create_addressbook("/test/")
        contact = get_file_content("contact1.vcf")
        self.put("/test/test.vcf", contact)
        _, responses = self.report("/test/", """\
<?xml version="1.0" encoding="utf-8" ?>
<C:calendar-query xmlns:C="urn:ietf:params:xml:ns:caldav">
    <D:prop xmlns:D="DAV:">
        <D:getcontenttype />
    </D:prop>
</C:calendar-query>""")
        assert len(responses) == 1 and len(responses["/test/test.vcf"]) == 1
        status, prop = responses["/test/test.vcf"]["D:getcontenttype"]
        assert status == 200 and prop.text == "text/vcard;charset=utf-8"

    def test_authorization(self):
        _, responses = self.propfind("/", """\
<?xml version="1.0" encoding="utf-8"?>
<propfind xmlns="DAV:">
    <prop>
        <current-user-principal />
    </prop>
</propfind>""", login="user:")
        assert len(responses["/"]) == 1
        status, prop = responses["/"]["D:current-user-principal"]
        assert status == 200 and len(prop) == 1
        assert prop.find(xmlutils.make_clark("D:href")).text == "/user/"

    def test_authentication(self):
        """Test if server sends authentication request."""
        self.configuration.update({
            "auth": {"type": "htpasswd",
                     "htpasswd_filename": os.devnull,
                     "htpasswd_encryption": "plain"},
            "rights": {"type": "owner_only"}}, "test")
        self.application = Application(self.configuration)
        status, headers, _ = self.request("MKCOL", "/user/")
        assert status in (401, 403)
        assert headers.get("WWW-Authenticate")

    def test_principal_collection_creation(self):
        """Verify existence of the principal collection."""
        self.propfind("/user/", login="user:")

    def test_authentication_current_user_principal_workaround(self):
        """Test if server sends authentication request when accessing
           current-user-principal prop (workaround for DAVx5)."""
        status, headers, _ = self.request("PROPFIND", "/", """\
<?xml version="1.0" encoding="utf-8"?>
<propfind xmlns="DAV:">
    <prop>
        <current-user-principal />
    </prop>
</propfind>""")
        assert status in (401, 403)
        assert headers.get("WWW-Authenticate")

    def test_existence_of_root_collections(self):
        """Verify that the root collection always exists."""
        # Use PROPFIND because GET returns message
        self.propfind("/")
        # it should still exist after deletion
        self.delete("/")
        self.propfind("/")

    def test_custom_headers(self):
        self.configuration.update({"headers": {"test": "123"}}, "test")
        self.application = Application(self.configuration)
        # Test if header is set on success
        status, headers, _ = self.request("OPTIONS", "/")
        assert status == 200
        assert headers.get("test") == "123"
        # Test if header is set on failure
        status, headers, _ = self.request("GET", "/.well-known/does not exist")
        assert status == 404
        assert headers.get("test") == "123"

    @pytest.mark.skipif(sys.version_info < (3, 6),
                        reason="Unsupported in Python < 3.6")
    def test_timezone_seconds(self):
        """Verify that timezones with minutes and seconds work."""
        self.mkcalendar("/calendar.ics/")
        event = get_file_content("event_timezone_seconds.ics")
        self.put("/calendar.ics/event.ics", event)


class BaseFileSystemTest(BaseTest):
    """Base class for filesystem backend tests."""

    storage_type: ClassVar[Any]

    def setup(self):
        self.configuration = config.load()
        self.colpath = tempfile.mkdtemp()
        # Allow access to anything for tests
        rights_file_path = os.path.join(self.colpath, "rights")
        with open(rights_file_path, "w") as f:
            f.write("""\
[allow all]
user: .*
collection: .*
permissions: RrWw""")
        self.configuration.update({
            "storage": {"type": self.storage_type,
                        "filesystem_folder": self.colpath,
                        # Disable syncing to disk for better performance
                        "_filesystem_fsync": "False"},
            "rights": {"file": rights_file_path,
                       "type": "from_file"}}, "test", privileged=True)
        self.application = Application(self.configuration)

    def teardown(self):
        shutil.rmtree(self.colpath)


class TestMultiFileSystem(BaseFileSystemTest, BaseRequestsMixIn):
    """Test BaseRequests on multifilesystem."""
    storage_type = "multifilesystem"

    def test_folder_creation(self):
        """Verify that the folder is created."""
        folder = os.path.join(self.colpath, "subfolder")
        self.configuration.update(
            {"storage": {"filesystem_folder": folder}}, "test")
        self.application = Application(self.configuration)
        assert os.path.isdir(folder)

    def test_fsync(self):
        """Create a directory and file with syncing enabled."""
        self.configuration.update({"storage": {"_filesystem_fsync": "True"}},
                                  "test", privileged=True)
        self.application = Application(self.configuration)
        self.mkcalendar("/calendar.ics/")

    def test_hook(self):
        """Run hook."""
        self.configuration.update({"storage": {
            "hook": ("mkdir %s" % os.path.join(
                "collection-root", "created_by_hook"))}}, "test")
        self.application = Application(self.configuration)
        self.mkcalendar("/calendar.ics/")
        self.propfind("/created_by_hook/")

    def test_hook_read_access(self):
        """Verify that hook is not run for read accesses."""
        self.configuration.update({"storage": {
            "hook": ("mkdir %s" % os.path.join(
                "collection-root", "created_by_hook"))}}, "test")
        self.application = Application(self.configuration)
        self.propfind("/")
        self.propfind("/created_by_hook/", check=404)

    @pytest.mark.skipif(not shutil.which("flock"),
                        reason="flock command not found")
    def test_hook_storage_locked(self):
        """Verify that the storage is locked when the hook runs."""
        self.configuration.update({"storage": {"hook": (
            "flock -n .Radicale.lock || exit 0; exit 1")}}, "test")
        self.application = Application(self.configuration)
        self.mkcalendar("/calendar.ics/")

    def test_hook_principal_collection_creation(self):
        """Verify that the hooks runs when a new user is created."""
        self.configuration.update({"storage": {
            "hook": ("mkdir %s" % os.path.join(
                "collection-root", "created_by_hook"))}}, "test")
        self.application = Application(self.configuration)
        self.propfind("/", login="user:")
        self.propfind("/created_by_hook/")

    def test_hook_fail(self):
        """Verify that a request fails if the hook fails."""
        self.configuration.update({"storage": {"hook": "exit 1"}}, "test")
        self.application = Application(self.configuration)
        self.mkcalendar("/calendar.ics/", check=500)

    def test_item_cache_rebuild(self):
        """Delete the item cache and verify that it is rebuild."""
        self.mkcalendar("/calendar.ics/")
        event = get_file_content("event1.ics")
        path = "/calendar.ics/event1.ics"
        self.put(path, event)
        _, answer1 = self.get(path)
        cache_folder = os.path.join(self.colpath, "collection-root",
                                    "calendar.ics", ".Radicale.cache", "item")
        assert os.path.exists(os.path.join(cache_folder, "event1.ics"))
        shutil.rmtree(cache_folder)
        _, answer2 = self.get(path)
        assert answer1 == answer2
        assert os.path.exists(os.path.join(cache_folder, "event1.ics"))

    @pytest.mark.skipif(os.name not in ("nt", "posix"),
                        reason="Only supported on 'nt' and 'posix'")
    def test_put_whole_calendar_uids_used_as_file_names(self):
        """Test if UIDs are used as file names."""
        BaseRequestsMixIn.test_put_whole_calendar(self)
        for uid in ("todo", "event"):
            _, answer = self.get("/calendar.ics/%s.ics" % uid)
            assert "\r\nUID:%s\r\n" % uid in answer

    @pytest.mark.skipif(os.name not in ("nt", "posix"),
                        reason="Only supported on 'nt' and 'posix'")
    def test_put_whole_calendar_random_uids_used_as_file_names(self):
        """Test if UIDs are used as file names."""
        BaseRequestsMixIn.test_put_whole_calendar_without_uids(self)
        _, answer = self.get("/calendar.ics")
        uids = []
        for line in answer.split("\r\n"):
            if line.startswith("UID:"):
                uids.append(line[len("UID:"):])
        for uid in uids:
            _, answer = self.get("/calendar.ics/%s.ics" % uid)
            assert "\r\nUID:%s\r\n" % uid in answer

    @pytest.mark.skipif(os.name not in ("nt", "posix"),
                        reason="Only supported on 'nt' and 'posix'")
    def test_put_whole_addressbook_uids_used_as_file_names(self):
        """Test if UIDs are used as file names."""
        BaseRequestsMixIn.test_put_whole_addressbook(self)
        for uid in ("contact1", "contact2"):
            _, answer = self.get("/contacts.vcf/%s.vcf" % uid)
            assert "\r\nUID:%s\r\n" % uid in answer

    @pytest.mark.skipif(os.name not in ("nt", "posix"),
                        reason="Only supported on 'nt' and 'posix'")
    def test_put_whole_addressbook_random_uids_used_as_file_names(self):
        """Test if UIDs are used as file names."""
        BaseRequestsMixIn.test_put_whole_addressbook_without_uids(self)
        _, answer = self.get("/contacts.vcf")
        uids = []
        for line in answer.split("\r\n"):
            if line.startswith("UID:"):
                uids.append(line[len("UID:"):])
        for uid in uids:
            _, answer = self.get("/contacts.vcf/%s.vcf" % uid)
            assert "\r\nUID:%s\r\n" % uid in answer


class TestCustomStorageSystem(BaseFileSystemTest):
    """Test custom backend loading."""
    storage_type = "radicale.tests.custom.storage_simple_sync"
    full_sync_token_support = False
    test_root = BaseRequestsMixIn.test_root
    _report_sync_token = BaseRequestsMixIn._report_sync_token
    # include tests related to sync token
    s = None
    for s in dir(BaseRequestsMixIn):
        if s.startswith("test_") and ("_sync_" in s or s.endswith("_sync")):
            locals()[s] = getattr(BaseRequestsMixIn, s)
    del s


class TestCustomStorageSystemCallable(BaseFileSystemTest):
    """Test custom backend loading with ``callable``."""
    storage_type = radicale.tests.custom.storage_simple_sync.Storage
    test_add_event = BaseRequestsMixIn.test_add_event
