# This file is part of Radicale Server - Calendar Server
# Copyright © 2012-2017 Guillaume Ayoub
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

import base64
import os
import posixpath
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET
from functools import partial

import pytest

from radicale import Application, config

from . import BaseTest
from .helpers import get_file_content


class BaseRequestsMixIn:
    """Tests with simple requests."""

    def test_root(self):
        """GET request at "/"."""
        status, _, answer = self.request("GET", "/")
        assert status == 302
        assert answer == "Redirected to .web"

    def test_script_name(self):
        """GET request at "/" with SCRIPT_NAME."""
        status, _, answer = self.request("GET", "/", SCRIPT_NAME="/radicale")
        assert status == 302
        assert answer == "Redirected to .web"
        status, _, answer = self.request("GET", "", SCRIPT_NAME="/radicale")
        assert status == 302
        assert answer == "Redirected to radicale/.web"

    def test_add_event(self):
        """Add an event."""
        status, _, _ = self.request("MKCALENDAR", "/calendar.ics/")
        assert status == 201
        event = get_file_content("event1.ics")
        path = "/calendar.ics/event1.ics"
        status, _, _ = self.request("PUT", path, event)
        assert status == 201
        status, headers, answer = self.request("GET", path)
        assert status == 200
        assert "ETag" in headers
        assert headers["Content-Type"] == "text/calendar; charset=utf-8"
        assert "VEVENT" in answer
        assert "Event" in answer
        assert "UID:event" in answer

    def test_add_event_without_uid(self):
        """Add an event without UID."""
        status, _, _ = self.request("MKCALENDAR", "/calendar.ics/")
        assert status == 201
        event = get_file_content("event1.ics").replace("UID:event1\n", "")
        assert "\nUID:" not in event
        path = "/calendar.ics/event.ics"
        status, _, _ = self.request("PUT", path, event)
        assert status == 201
        status, _, answer = self.request("GET", path)
        assert status == 200
        uids = []
        for line in answer.split("\r\n"):
            if line.startswith("UID:"):
                uids.append(line[len("UID:"):])
        assert len(uids) == 1 and uids[0]
        # Overwrite the event with an event without UID and check that the UID
        # is still the same
        status, _, _ = self.request("PUT", path, event)
        assert status == 201
        status, _, answer = self.request("GET", path)
        assert status == 200
        assert "\r\nUID:%s\r\n" % uids[0] in answer

    def test_add_todo(self):
        """Add a todo."""
        status, _, _ = self.request("MKCALENDAR", "/calendar.ics/")
        assert status == 201
        todo = get_file_content("todo1.ics")
        path = "/calendar.ics/todo1.ics"
        status, _, _ = self.request("PUT", path, todo)
        assert status == 201
        status, headers, answer = self.request("GET", path)
        assert status == 200
        assert "ETag" in headers
        assert headers["Content-Type"] == "text/calendar; charset=utf-8"
        assert "VTODO" in answer
        assert "Todo" in answer
        assert "UID:todo" in answer

    def _create_addressbook(self, path):
        return self.request(
            "MKCOL", path, """\
<?xml version="1.0" encoding="UTF-8" ?>
<create xmlns="DAV:" xmlns:CR="urn:ietf:params:xml:ns:carddav">
  <set>
    <prop>
      <resourcetype>
        <collection />
        <CR:addressbook />
      </resourcetype>
    </prop>
  </set>
</create>""")

    def test_add_contact(self):
        """Add a contact."""
        status, _, _ = self._create_addressbook("/contacts.vcf/")
        assert status == 201
        contact = get_file_content("contact1.vcf")
        path = "/contacts.vcf/contact.vcf"
        status, _, _ = self.request("PUT", path, contact)
        assert status == 201
        status, headers, answer = self.request("GET", path)
        assert status == 200
        assert "ETag" in headers
        assert headers["Content-Type"] == "text/vcard; charset=utf-8"
        assert "VCARD" in answer
        assert "UID:contact1" in answer
        status, _, answer = self.request("GET", path)
        assert status == 200
        assert "UID:contact1" in answer

    def test_add_contact_without_uid(self):
        """Add a contact."""
        status, _, _ = self._create_addressbook("/contacts.vcf/")
        assert status == 201
        contact = get_file_content("contact1.vcf").replace("UID:contact1\n",
                                                           "")
        assert "\nUID" not in contact
        path = "/contacts.vcf/contact.vcf"
        status, _, _ = self.request("PUT", path, contact)
        assert status == 201
        status, _, answer = self.request("GET", path)
        assert status == 200
        uids = []
        for line in answer.split("\r\n"):
            if line.startswith("UID:"):
                uids.append(line[len("UID:"):])
        assert len(uids) == 1 and uids[0]
        # Overwrite the contact with an contact without UID and check that the
        # UID is still the same
        status, _, _ = self.request("PUT", path, contact)
        assert status == 201
        status, _, answer = self.request("GET", path)
        assert status == 200
        assert "\r\nUID:%s\r\n" % uids[0] in answer

    def test_update(self):
        """Update an event."""
        status, _, _ = self.request("MKCALENDAR", "/calendar.ics/")
        assert status == 201
        event = get_file_content("event1.ics")
        path = "/calendar.ics/event1.ics"
        status, _, _ = self.request("PUT", path, event)
        assert status == 201
        status, headers, answer = self.request("GET", path)
        assert "ETag" in headers
        assert status == 200
        assert "VEVENT" in answer
        assert "Event" in answer
        assert "UID:event" in answer
        assert "DTSTART;TZID=Europe/Paris:20130901T180000" in answer
        assert "DTEND;TZID=Europe/Paris:20130901T190000" in answer

        # Then we send another PUT request
        event = get_file_content("event1-prime.ics")
        status, _, _ = self.request("PUT", path, event)
        assert status == 201
        status, _, answer = self.request("GET", "/calendar.ics/")
        assert status == 200
        assert answer.count("BEGIN:VEVENT") == 1

        status, headers, answer = self.request("GET", path)
        assert status == 200
        assert "ETag" in headers
        assert "VEVENT" in answer
        assert "Event" in answer
        assert "UID:event" in answer
        assert "DTSTART;TZID=Europe/Paris:20130901T180000" not in answer
        assert "DTEND;TZID=Europe/Paris:20130901T190000" not in answer
        assert "DTSTART;TZID=Europe/Paris:20140901T180000" in answer
        assert "DTEND;TZID=Europe/Paris:20140901T210000" in answer

    def test_put_whole_calendar(self):
        """Create and overwrite a whole calendar."""
        status, _, _ = self.request(
            "PUT", "/calendar.ics/", "BEGIN:VCALENDAR\r\nEND:VCALENDAR")
        assert status == 201
        event1 = get_file_content("event1.ics")
        status, _, _ = self.request(
            "PUT", "/calendar.ics/test_event.ics", event1)
        assert status == 201
        # Overwrite
        events = get_file_content("event_multiple.ics")
        status, _, _ = self.request("PUT", "/calendar.ics/", events)
        assert status == 201
        status, _, _ = self.request("GET", "/calendar.ics/test_event.ics")
        assert status == 404
        status, _, answer = self.request("GET", "/calendar.ics/")
        assert status == 200
        assert "\r\nUID:event\r\n" in answer and "\r\nUID:todo\r\n" in answer
        assert "\r\nUID:event1\r\n" not in answer

    def test_put_whole_calendar_without_uids(self):
        """Create a whole calendar without UID."""
        event = get_file_content("event_multiple.ics")
        event = event.replace("UID:event\n", "").replace("UID:todo\n", "")
        assert "\nUID:" not in event
        status, _, _ = self.request("PUT", "/calendar.ics/", event)
        assert status == 201
        status, _, answer = self.request("GET", "/calendar.ics")
        assert status == 200
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
        status, _, _ = self.request("PUT", "/contacts.vcf/", contacts)
        assert status == 201
        status, _, answer = self.request("GET", "/contacts.vcf/")
        assert status == 200
        assert ("\r\nUID:contact1\r\n" in answer and
                "\r\nUID:contact2\r\n" in answer)

    def test_put_whole_addressbook_without_uids(self):
        """Create a whole addressbook without UID."""
        contacts = get_file_content("contact_multiple.vcf")
        contacts = contacts.replace("UID:contact1\n", "").replace(
            "UID:contact2\n", "")
        assert "\nUID:" not in contacts
        status, _, _ = self.request("PUT", "/contacts.vcf/", contacts)
        assert status == 201
        status, _, answer = self.request("GET", "/contacts.vcf")
        assert status == 200
        uids = []
        for line in answer.split("\r\n"):
            if line.startswith("UID:"):
                uids.append(line[len("UID:"):])
        assert len(uids) == 2
        for i, uid1 in enumerate(uids):
            assert uid1
            for uid2 in uids[i + 1:]:
                assert uid1 != uid2

    def test_delete(self):
        """Delete an event."""
        status, _, _ = self.request("MKCALENDAR", "/calendar.ics/")
        assert status == 201
        event = get_file_content("event1.ics")
        path = "/calendar.ics/event1.ics"
        status, _, _ = self.request("PUT", path, event)
        assert status == 201
        # Then we send a DELETE request
        status, _, answer = self.request("DELETE", path)
        assert status == 200
        assert "href>%s</" % path in answer
        status, _, answer = self.request("GET", "/calendar.ics/")
        assert status == 200
        assert "VEVENT" not in answer

    def test_mkcalendar(self):
        """Make a calendar."""
        status, _, _ = self.request("MKCALENDAR", "/calendar.ics/")
        assert status == 201
        status, _, answer = self.request("GET", "/calendar.ics/")
        assert status == 200
        assert "BEGIN:VCALENDAR" in answer
        assert "END:VCALENDAR" in answer

    def test_move(self):
        """Move a item."""
        status, _, _ = self.request("MKCALENDAR", "/calendar.ics/")
        assert status == 201
        event = get_file_content("event1.ics")
        path1 = "/calendar.ics/event1.ics"
        path2 = "/calendar.ics/event2.ics"
        status, _, _ = self.request("PUT", path1, event)
        assert status == 201
        status, _, _ = self.request(
            "MOVE", path1, HTTP_DESTINATION=path2, HTTP_HOST="")
        assert status == 201
        status, _, _ = self.request("GET", path1)
        assert status == 404
        status, _, _ = self.request("GET", path2)
        assert status == 200

    def test_move_between_colections(self):
        """Move a item."""
        status, _, _ = self.request("MKCALENDAR", "/calendar1.ics/")
        assert status == 201
        status, _, _ = self.request("MKCALENDAR", "/calendar2.ics/")
        assert status == 201
        event = get_file_content("event1.ics")
        path1 = "/calendar1.ics/event1.ics"
        path2 = "/calendar2.ics/event2.ics"
        status, _, _ = self.request("PUT", path1, event)
        assert status == 201
        status, _, _ = self.request(
            "MOVE", path1, HTTP_DESTINATION=path2, HTTP_HOST="")
        assert status == 201
        status, _, _ = self.request("GET", path1)
        assert status == 404
        status, _, _ = self.request("GET", path2)
        assert status == 200

    def test_head(self):
        status, _, _ = self.request("HEAD", "/")
        assert status == 302

    def test_options(self):
        status, headers, _ = self.request("OPTIONS", "/")
        assert status == 200
        assert "DAV" in headers

    def test_delete_collection(self):
        """Delete a collection."""
        status, _, _ = self.request("MKCALENDAR", "/calendar.ics/")
        assert status == 201
        event = get_file_content("event1.ics")
        self.request("PUT", "/calendar.ics/event1.ics", event)
        status, _, answer = self.request("DELETE", "/calendar.ics/")
        assert status == 200
        assert "href>/calendar.ics/</" in answer
        status, _, _ = self.request("GET", "/calendar.ics/")
        assert status == 404

    def test_delete_root_collection(self):
        """Delete the root collection."""
        status, _, _ = self.request("MKCALENDAR", "/calendar.ics/")
        assert status == 201
        event = get_file_content("event1.ics")
        status, _, _ = self.request("PUT", "/event1.ics", event)
        assert status == 201
        status, _, _ = self.request("PUT", "/calendar.ics/event1.ics", event)
        assert status == 201
        status, _, answer = self.request("DELETE", "/")
        assert status == 200
        assert "href>/</" in answer
        status, _, _ = self.request("GET", "/calendar.ics/")
        assert status == 404
        status, _, _ = self.request("GET", "/event1.ics")
        assert status == 404

    def test_propfind(self):
        calendar_path = "/calendar.ics/"
        status, _, _ = self.request("MKCALENDAR", calendar_path)
        assert status == 201
        event = get_file_content("event1.ics")
        event_path = posixpath.join(calendar_path, "event.ics")
        status, _, _ = self.request("PUT", event_path, event)
        assert status == 201
        status, _, answer = self.request("PROPFIND", "/", HTTP_DEPTH="1")
        assert status == 207
        assert "href>/</" in answer
        assert "href>%s</" % calendar_path in answer
        status, _, answer = self.request(
            "PROPFIND", calendar_path, HTTP_DEPTH="1")
        assert status == 207
        assert "href>%s</" % calendar_path in answer
        assert "href>%s</" % event_path in answer

    def test_propfind_propname(self):
        status, _, _ = self.request("MKCALENDAR", "/calendar.ics/")
        assert status == 201
        event = get_file_content("event1.ics")
        status, _, _ = self.request("PUT", "/calendar.ics/event.ics", event)
        assert status == 201
        propfind = get_file_content("propname.xml")
        status, _, answer = self.request(
            "PROPFIND", "/calendar.ics/", propfind)
        assert "<sync-token />" in answer
        status, _, answer = self.request(
            "PROPFIND", "/calendar.ics/event.ics", propfind)
        assert "<getetag />" in answer

    def test_propfind_allprop(self):
        status, _, _ = self.request("MKCALENDAR", "/calendar.ics/")
        assert status == 201
        event = get_file_content("event1.ics")
        status, _, _ = self.request("PUT", "/calendar.ics/event.ics", event)
        assert status == 201
        propfind = get_file_content("allprop.xml")
        status, _, answer = self.request(
            "PROPFIND", "/calendar.ics/", propfind)
        assert "<sync-token>" in answer
        status, _, answer = self.request(
            "PROPFIND", "/calendar.ics/event.ics", propfind)
        assert "<getetag>" in answer

    def test_proppatch(self):
        """Write a property and read it back."""
        status, _, _ = self.request("MKCALENDAR", "/calendar.ics/")
        assert status == 201
        proppatch = get_file_content("proppatch1.xml")
        status, _, answer = self.request(
            "PROPPATCH", "/calendar.ics/", proppatch)
        assert status == 207
        assert "calendar-color" in answer
        assert "200 OK</status" in answer
        # Read property back
        propfind = get_file_content("propfind1.xml")
        status, _, answer = self.request(
            "PROPFIND", "/calendar.ics/", propfind)
        assert status == 207
        assert "<ICAL:calendar-color>#BADA55</" in answer
        assert "200 OK</status" in answer
        propfind = get_file_content("allprop.xml")
        status, _, answer = self.request(
            "PROPFIND", "/calendar.ics/", propfind)
        assert "<ICAL:calendar-color>" in answer

    def test_put_whole_calendar_multiple_events_with_same_uid(self):
        """Add two events with the same UID."""
        status, _, _ = self.request(
            "PUT", "/calendar.ics/", get_file_content("event2.ics"))
        assert status == 201
        status, _, answer = self.request(
            "REPORT", "/calendar.ics/",
            """<?xml version="1.0" encoding="utf-8" ?>
               <C:calendar-query xmlns:C="urn:ietf:params:xml:ns:caldav">
                 <D:prop xmlns:D="DAV:"><D:getetag/></D:prop>
               </C:calendar-query>""")
        assert status == 207
        assert answer.count("<getetag>") == 1
        status, _, answer = self.request("GET", "/calendar.ics/")
        assert status == 200
        assert answer.count("BEGIN:VEVENT") == 2

    def _test_filter(self, filters, kind="event", test=None, items=(1,)):
        filter_template = "<C:filter>{}</C:filter>"
        if kind in ("event", "journal", "todo"):
            create_collection_fn = partial(self.request, "MKCALENDAR")
            path = "/calendar.ics/"
            filename_template = "{}{}.ics"
            namespace = "urn:ietf:params:xml:ns:caldav"
            report = "calendar-query"
        elif kind == "contact":
            create_collection_fn = self._create_addressbook
            if test:
                filter_template = '<C:filter test="{}">{{}}</C:filter>'.format(
                    test)
            path = "/contacts.vcf/"
            filename_template = "{}{}.vcf"
            namespace = "urn:ietf:params:xml:ns:carddav"
            report = "addressbook-query"
        else:
            raise ValueError("Unsupported kind: %r" % kind)
        status, _, _ = self.request("DELETE", path)
        assert status in (200, 404)
        status, _, _ = create_collection_fn(path)
        assert status == 201
        for i in items:
            filename = filename_template.format(kind, i)
            event = get_file_content(filename)
            status, _, _ = self.request(
                "PUT", posixpath.join(path, filename), event)
            assert status == 201
        filters_text = "".join(
            filter_template.format(filter_) for filter_ in filters)
        status, _, answer = self.request(
            "REPORT", path,
            """<?xml version="1.0" encoding="utf-8" ?>
               <C:{1} xmlns:C="{0}">
                 <D:prop xmlns:D="DAV:">
                   <D:getetag/>
                 </D:prop>
                 {2}
               </C:{1}>""".format(namespace, report, filters_text))
        assert status == 207
        return answer

    def test_addressbook_empty_filter(self):
        self._test_filter([""], kind="contact")

    def test_addressbook_prop_filter(self):
        assert "href>/contacts.vcf/contact1.vcf</" in self._test_filter(["""
            <C:prop-filter name="NICKNAME">
              <C:text-match collation="i;unicode-casemap"
                            match-type="contains"
              >es</C:text-match>
            </C:prop-filter>"""], "contact")
        assert "href>/contacts.vcf/contact1.vcf</" in self._test_filter(["""
            <C:prop-filter name="NICKNAME">
              <C:text-match collation="i;unicode-casemap"
              >es</C:text-match>
            </C:prop-filter>"""], "contact")
        assert "href>/contacts.vcf/contact1.vcf</" not in self._test_filter(["""
            <C:prop-filter name="NICKNAME">
              <C:text-match collation="i;unicode-casemap"
                            match-type="contains"
              >a</C:text-match>
            </C:prop-filter>"""], "contact")
        assert "href>/contacts.vcf/contact1.vcf</" in self._test_filter(["""
            <C:prop-filter name="NICKNAME">
              <C:text-match collation="i;unicode-casemap"
                            match-type="equals"
              >test</C:text-match>
            </C:prop-filter>"""], "contact")
        assert "href>/contacts.vcf/contact1.vcf</" not in self._test_filter(["""
            <C:prop-filter name="NICKNAME">
              <C:text-match collation="i;unicode-casemap"
                            match-type="equals"
              >tes</C:text-match>
            </C:prop-filter>"""], "contact")
        assert "href>/contacts.vcf/contact1.vcf</" not in self._test_filter(["""
            <C:prop-filter name="NICKNAME">
              <C:text-match collation="i;unicode-casemap"
                            match-type="equals"
              >est</C:text-match>
            </C:prop-filter>"""], "contact")
        assert "href>/contacts.vcf/contact1.vcf</" in self._test_filter(["""
            <C:prop-filter name="NICKNAME">
              <C:text-match collation="i;unicode-casemap"
                            match-type="starts-with"
              >tes</C:text-match>
            </C:prop-filter>"""], "contact")
        assert "href>/contacts.vcf/contact1.vcf</" not in self._test_filter(["""
            <C:prop-filter name="NICKNAME">
              <C:text-match collation="i;unicode-casemap"
                            match-type="starts-with"
              >est</C:text-match>
            </C:prop-filter>"""], "contact")
        assert "href>/contacts.vcf/contact1.vcf</" in self._test_filter(["""
            <C:prop-filter name="NICKNAME">
              <C:text-match collation="i;unicode-casemap"
                            match-type="ends-with"
              >est</C:text-match>
            </C:prop-filter>"""], "contact")
        assert "href>/contacts.vcf/contact1.vcf</" not in self._test_filter(["""
            <C:prop-filter name="NICKNAME">
              <C:text-match collation="i;unicode-casemap"
                            match-type="ends-with"
              >tes</C:text-match>
            </C:prop-filter>"""], "contact")

    def test_addressbook_prop_filter_any(self):
        assert "href>/contacts.vcf/contact1.vcf</" in self._test_filter(["""
            <C:prop-filter name="NICKNAME">
              <C:text-match collation="i;unicode-casemap"
              >test</C:text-match>
            </C:prop-filter>
            <C:prop-filter name="EMAIL">
              <C:text-match collation="i;unicode-casemap"
              >test</C:text-match>
            </C:prop-filter>"""], "contact", test="anyof")
        assert "href>/contacts.vcf/contact1.vcf</" not in self._test_filter(["""
            <C:prop-filter name="NICKNAME">
              <C:text-match collation="i;unicode-casemap"
              >a</C:text-match>
            </C:prop-filter>
            <C:prop-filter name="EMAIL">
              <C:text-match collation="i;unicode-casemap"
              >test</C:text-match>
            </C:prop-filter>"""], "contact", test="anyof")
        assert "href>/contacts.vcf/contact1.vcf</" in self._test_filter(["""
            <C:prop-filter name="NICKNAME">
              <C:text-match collation="i;unicode-casemap"
              >test</C:text-match>
            </C:prop-filter>
            <C:prop-filter name="EMAIL">
              <C:text-match collation="i;unicode-casemap"
              >test</C:text-match>
            </C:prop-filter>"""], "contact")

    def test_addressbook_prop_filter_all(self):
        assert "href>/contacts.vcf/contact1.vcf</" in self._test_filter(["""
            <C:prop-filter name="NICKNAME">
              <C:text-match collation="i;unicode-casemap"
              >tes</C:text-match>
            </C:prop-filter>
            <C:prop-filter name="NICKNAME">
              <C:text-match collation="i;unicode-casemap"
              >est</C:text-match>
            </C:prop-filter>"""], "contact", test="allof")
        assert "href>/contacts.vcf/contact1.vcf</" not in self._test_filter(["""
            <C:prop-filter name="NICKNAME">
              <C:text-match collation="i;unicode-casemap"
              >test</C:text-match>
            </C:prop-filter>
            <C:prop-filter name="EMAIL">
              <C:text-match collation="i;unicode-casemap"
              >test</C:text-match>
            </C:prop-filter>"""], "contact", test="allof")

    def test_calendar_empty_filter(self):
        self._test_filter([""])

    def test_calendar_tag_filter(self):
        """Report request with tag-based filter on calendar."""
        assert "href>/calendar.ics/event1.ics</" in self._test_filter(["""
            <C:comp-filter name="VCALENDAR"></C:comp-filter>"""])

    def test_item_tag_filter(self):
        """Report request with tag-based filter on an item."""
        assert "href>/calendar.ics/event1.ics</" in self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VEVENT"></C:comp-filter>
            </C:comp-filter>"""])
        assert "href>/calendar.ics/event1.ics</" not in self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VTODO"></C:comp-filter>
            </C:comp-filter>"""])

    def test_item_not_tag_filter(self):
        """Report request with tag-based is-not filter on an item."""
        assert "href>/calendar.ics/event1.ics</" not in self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VEVENT">
                <C:is-not-defined />
              </C:comp-filter>
            </C:comp-filter>"""])
        assert "href>/calendar.ics/event1.ics</" in self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VTODO">
                <C:is-not-defined />
              </C:comp-filter>
            </C:comp-filter>"""])

    def test_item_prop_filter(self):
        """Report request with prop-based filter on an item."""
        assert "href>/calendar.ics/event1.ics</" in self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VEVENT">
                <C:prop-filter name="SUMMARY"></C:prop-filter>
              </C:comp-filter>
            </C:comp-filter>"""])
        assert "href>/calendar.ics/event1.ics</" not in self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VEVENT">
                <C:prop-filter name="UNKNOWN"></C:prop-filter>
              </C:comp-filter>
            </C:comp-filter>"""])

    def test_item_not_prop_filter(self):
        """Report request with prop-based is-not filter on an item."""
        assert "href>/calendar.ics/event1.ics</" not in self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VEVENT">
                <C:prop-filter name="SUMMARY">
                  <C:is-not-defined />
                </C:prop-filter>
              </C:comp-filter>
            </C:comp-filter>"""])
        assert "href>/calendar.ics/event1.ics</" in self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VEVENT">
                <C:prop-filter name="UNKNOWN">
                  <C:is-not-defined />
                </C:prop-filter>
              </C:comp-filter>
            </C:comp-filter>"""])

    def test_mutiple_filters(self):
        """Report request with multiple filters on an item."""
        assert "href>/calendar.ics/event1.ics</" not in self._test_filter(["""
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
        assert "href>/calendar.ics/event1.ics</" in self._test_filter(["""
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
        assert "href>/calendar.ics/event1.ics</" in self._test_filter(["""
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
        assert "href>/calendar.ics/event1.ics</" in self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VEVENT">
                <C:prop-filter name="SUMMARY">
                  <C:text-match>event</C:text-match>
                </C:prop-filter>
              </C:comp-filter>
            </C:comp-filter>"""])
        assert "href>/calendar.ics/event1.ics</" not in self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VEVENT">
                <C:prop-filter name="UNKNOWN">
                  <C:text-match>event</C:text-match>
                </C:prop-filter>
              </C:comp-filter>
            </C:comp-filter>"""])
        assert "href>/calendar.ics/event1.ics</" not in self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VEVENT">
                <C:prop-filter name="SUMMARY">
                  <C:text-match>unknown</C:text-match>
                </C:prop-filter>
              </C:comp-filter>
            </C:comp-filter>"""])
        assert "href>/calendar.ics/event1.ics</" not in self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VEVENT">
                <C:prop-filter name="SUMMARY">
                  <C:text-match negate-condition="yes">event</C:text-match>
                </C:prop-filter>
              </C:comp-filter>
            </C:comp-filter>"""])

    def test_param_filter(self):
        """Report request with param-filter on calendar."""
        assert "href>/calendar.ics/event1.ics</" in self._test_filter(["""
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
        assert "href>/calendar.ics/event1.ics</" not in self._test_filter(["""
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
        assert "href>/calendar.ics/event1.ics</" not in self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VEVENT">
                <C:prop-filter name="ATTENDEE">
                  <C:param-filter name="PARTSTAT">
                    <C:is-not-defined />
                  </C:param-filter>
                </C:prop-filter>
              </C:comp-filter>
            </C:comp-filter>"""])
        assert "href>/calendar.ics/event1.ics</" in self._test_filter(["""
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
        answer = self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VEVENT">
                <C:time-range start="20130801T000000Z" end="20131001T000000Z"/>
              </C:comp-filter>
            </C:comp-filter>"""], "event", items=range(1, 6))
        assert "href>/calendar.ics/event1.ics</" in answer
        assert "href>/calendar.ics/event2.ics</" in answer
        assert "href>/calendar.ics/event3.ics</" in answer
        assert "href>/calendar.ics/event4.ics</" in answer
        assert "href>/calendar.ics/event5.ics</" in answer
        answer = self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VTODO">
                <C:time-range start="20130801T000000Z" end="20131001T000000Z"/>
              </C:comp-filter>
            </C:comp-filter>"""], "event", items=range(1, 6))
        assert "href>/calendar.ics/event1.ics</" not in answer
        answer = self._test_filter(["""
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
        assert "href>/calendar.ics/event1.ics</" not in answer
        assert "href>/calendar.ics/event2.ics</" not in answer
        assert "href>/calendar.ics/event3.ics</" not in answer
        assert "href>/calendar.ics/event4.ics</" not in answer
        assert "href>/calendar.ics/event5.ics</" not in answer
        answer = self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VEVENT">
                <C:time-range start="20130902T000000Z" end="20131001T000000Z"/>
              </C:comp-filter>
            </C:comp-filter>"""], items=range(1, 6))
        assert "href>/calendar.ics/event1.ics</" not in answer
        assert "href>/calendar.ics/event2.ics</" in answer
        assert "href>/calendar.ics/event3.ics</" in answer
        assert "href>/calendar.ics/event4.ics</" in answer
        assert "href>/calendar.ics/event5.ics</" in answer
        answer = self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VEVENT">
                <C:time-range start="20130903T000000Z" end="20130908T000000Z"/>
              </C:comp-filter>
            </C:comp-filter>"""], items=range(1, 6))
        assert "href>/calendar.ics/event1.ics</" not in answer
        assert "href>/calendar.ics/event2.ics</" not in answer
        assert "href>/calendar.ics/event3.ics</" in answer
        assert "href>/calendar.ics/event4.ics</" in answer
        assert "href>/calendar.ics/event5.ics</" in answer
        answer = self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VEVENT">
                <C:time-range start="20130903T000000Z" end="20130904T000000Z"/>
              </C:comp-filter>
            </C:comp-filter>"""], items=range(1, 6))
        assert "href>/calendar.ics/event1.ics</" not in answer
        assert "href>/calendar.ics/event2.ics</" not in answer
        assert "href>/calendar.ics/event3.ics</" in answer
        assert "href>/calendar.ics/event4.ics</" not in answer
        assert "href>/calendar.ics/event5.ics</" not in answer
        answer = self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VEVENT">
                <C:time-range start="20130805T000000Z" end="20130810T000000Z"/>
              </C:comp-filter>
            </C:comp-filter>"""], items=range(1, 6))
        assert "href>/calendar.ics/event1.ics</" not in answer
        assert "href>/calendar.ics/event2.ics</" not in answer
        assert "href>/calendar.ics/event3.ics</" not in answer
        assert "href>/calendar.ics/event4.ics</" not in answer
        assert "href>/calendar.ics/event5.ics</" not in answer
        # HACK: VObject doesn't match RECURRENCE-ID to recurrences, the
        # overwritten recurrence is still used for filtering.
        answer = self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VEVENT">
                <C:time-range start="20170601T063000Z" end="20170601T070000Z"/>
              </C:comp-filter>
            </C:comp-filter>"""], items=(6, 7, 8, 9))
        assert "href>/calendar.ics/event6.ics</" in answer
        assert "href>/calendar.ics/event7.ics</" in answer
        assert "href>/calendar.ics/event8.ics</" in answer
        assert "href>/calendar.ics/event9.ics</" in answer
        answer = self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VEVENT">
                <C:time-range start="20170701T060000Z"/>
              </C:comp-filter>
            </C:comp-filter>"""], items=(6, 7, 8, 9))
        assert "href>/calendar.ics/event6.ics</" in answer
        assert "href>/calendar.ics/event7.ics</" in answer
        assert "href>/calendar.ics/event8.ics</" in answer
        assert "href>/calendar.ics/event9.ics</" not in answer
        answer = self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VEVENT">
                <C:time-range start="20170702T070000Z" end="20170704T060000Z"/>
              </C:comp-filter>
            </C:comp-filter>"""], items=(6, 7, 8, 9))
        assert "href>/calendar.ics/event6.ics</" not in answer
        assert "href>/calendar.ics/event7.ics</" not in answer
        assert "href>/calendar.ics/event8.ics</" not in answer
        assert "href>/calendar.ics/event9.ics</" not in answer
        answer = self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VEVENT">
                <C:time-range start="20170602T075959Z" end="20170602T080000Z"/>
              </C:comp-filter>
            </C:comp-filter>"""], items=(9,))
        assert "href>/calendar.ics/event9.ics</" in answer
        answer = self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VEVENT">
                <C:time-range start="20170602T080000Z" end="20170603T083000Z"/>
              </C:comp-filter>
            </C:comp-filter>"""], items=(9,))
        assert "href>/calendar.ics/event9.ics</" not in answer

    def test_time_range_filter_events_rrule(self):
        """Report request with time-range filter on events with rrules."""
        answer = self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VEVENT">
                <C:time-range start="20130801T000000Z" end="20131001T000000Z"/>
              </C:comp-filter>
            </C:comp-filter>"""], "event", items=(1, 2))
        assert "href>/calendar.ics/event1.ics</" in answer
        assert "href>/calendar.ics/event2.ics</" in answer
        answer = self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VEVENT">
                <C:time-range start="20140801T000000Z" end="20141001T000000Z"/>
              </C:comp-filter>
            </C:comp-filter>"""], "event", items=(1, 2))
        assert "href>/calendar.ics/event1.ics</" not in answer
        assert "href>/calendar.ics/event2.ics</" in answer
        answer = self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VEVENT">
                <C:time-range start="20120801T000000Z" end="20121001T000000Z"/>
              </C:comp-filter>
            </C:comp-filter>"""], "event", items=(1, 2))
        assert "href>/calendar.ics/event1.ics</" not in answer
        assert "href>/calendar.ics/event2.ics</" not in answer
        answer = self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VEVENT">
                <C:time-range start="20130903T000000Z" end="20130907T000000Z"/>
              </C:comp-filter>
            </C:comp-filter>"""], "event", items=(1, 2))
        assert "href>/calendar.ics/event1.ics</" not in answer
        assert "href>/calendar.ics/event2.ics</" not in answer

    def test_time_range_filter_todos(self):
        """Report request with time-range filter on todos."""
        answer = self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VTODO">
                <C:time-range start="20130801T000000Z" end="20131001T000000Z"/>
              </C:comp-filter>
            </C:comp-filter>"""], "todo", items=range(1, 9))
        assert "href>/calendar.ics/todo1.ics</" in answer
        assert "href>/calendar.ics/todo2.ics</" in answer
        assert "href>/calendar.ics/todo3.ics</" in answer
        assert "href>/calendar.ics/todo4.ics</" in answer
        assert "href>/calendar.ics/todo5.ics</" in answer
        assert "href>/calendar.ics/todo6.ics</" in answer
        assert "href>/calendar.ics/todo7.ics</" in answer
        assert "href>/calendar.ics/todo8.ics</" in answer
        answer = self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VTODO">
                <C:time-range start="20130901T160000Z" end="20130901T183000Z"/>
              </C:comp-filter>
            </C:comp-filter>"""], "todo", items=range(1, 9))
        assert "href>/calendar.ics/todo1.ics</" not in answer
        assert "href>/calendar.ics/todo2.ics</" in answer
        assert "href>/calendar.ics/todo3.ics</" in answer
        assert "href>/calendar.ics/todo4.ics</" not in answer
        assert "href>/calendar.ics/todo5.ics</" not in answer
        assert "href>/calendar.ics/todo6.ics</" not in answer
        assert "href>/calendar.ics/todo7.ics</" in answer
        assert "href>/calendar.ics/todo8.ics</" in answer
        answer = self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VTODO">
                <C:time-range start="20130903T160000Z" end="20130901T183000Z"/>
              </C:comp-filter>
            </C:comp-filter>"""], "todo", items=range(1, 9))
        assert "href>/calendar.ics/todo2.ics</" not in answer
        answer = self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VTODO">
                <C:time-range start="20130903T160000Z" end="20130901T173000Z"/>
              </C:comp-filter>
            </C:comp-filter>"""], "todo", items=range(1, 9))
        assert "href>/calendar.ics/todo2.ics</" not in answer
        answer = self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VTODO">
                <C:time-range start="20130903T160000Z" end="20130903T173000Z"/>
              </C:comp-filter>
            </C:comp-filter>"""], "todo", items=range(1, 9))
        assert "href>/calendar.ics/todo3.ics</" not in answer
        answer = self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VTODO">
                <C:time-range start="20130903T160000Z" end="20130803T203000Z"/>
              </C:comp-filter>
            </C:comp-filter>"""], "todo", items=range(1, 9))
        assert "href>/calendar.ics/todo7.ics</" in answer

    def test_time_range_filter_todos_rrule(self):
        """Report request with time-range filter on todos with rrules."""
        answer = self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VTODO">
                <C:time-range start="20130801T000000Z" end="20131001T000000Z"/>
              </C:comp-filter>
            </C:comp-filter>"""], "todo", items=(1, 2, 9))
        assert "href>/calendar.ics/todo1.ics</" in answer
        assert "href>/calendar.ics/todo2.ics</" in answer
        assert "href>/calendar.ics/todo9.ics</" in answer
        answer = self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VTODO">
                <C:time-range start="20140801T000000Z" end="20141001T000000Z"/>
              </C:comp-filter>
            </C:comp-filter>"""], "todo", items=(1, 2, 9))
        assert "href>/calendar.ics/todo1.ics</" not in answer
        assert "href>/calendar.ics/todo2.ics</" in answer
        assert "href>/calendar.ics/todo9.ics</" in answer
        answer = self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VTODO">
                <C:time-range start="20140902T000000Z" end="20140903T000000Z"/>
              </C:comp-filter>
            </C:comp-filter>"""], "todo", items=(1, 2))
        assert "href>/calendar.ics/todo1.ics</" not in answer
        assert "href>/calendar.ics/todo2.ics</" in answer
        answer = self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VTODO">
                <C:time-range start="20140904T000000Z" end="20140914T000000Z"/>
              </C:comp-filter>
            </C:comp-filter>"""], "todo", items=(1, 2))
        assert "href>/calendar.ics/todo1.ics</" not in answer
        assert "href>/calendar.ics/todo2.ics</" not in answer
        answer = self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VTODO">
                <C:time-range start="20130902T000000Z" end="20130906T235959Z"/>
              </C:comp-filter>
            </C:comp-filter>"""], "todo", items=(9,))
        assert "href>/calendar.ics/todo9.ics</" not in answer

    def test_time_range_filter_journals(self):
        """Report request with time-range filter on journals."""
        answer = self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VJOURNAL">
                <C:time-range start="19991229T000000Z" end="20000202T000000Z"/>
              </C:comp-filter>
            </C:comp-filter>"""], "journal", items=(1, 2, 3))
        assert "href>/calendar.ics/journal1.ics</" not in answer
        assert "href>/calendar.ics/journal2.ics</" in answer
        assert "href>/calendar.ics/journal3.ics</" in answer
        answer = self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VJOURNAL">
                <C:time-range start="19991229T000000Z" end="20000202T000000Z"/>
              </C:comp-filter>
            </C:comp-filter>"""], "journal", items=(1, 2, 3))
        assert "href>/calendar.ics/journal1.ics</" not in answer
        assert "href>/calendar.ics/journal2.ics</" in answer
        assert "href>/calendar.ics/journal3.ics</" in answer
        answer = self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VJOURNAL">
                <C:time-range start="19981229T000000Z" end="19991012T000000Z"/>
              </C:comp-filter>
            </C:comp-filter>"""], "journal", items=(1, 2, 3))
        assert "href>/calendar.ics/journal1.ics</" not in answer
        assert "href>/calendar.ics/journal2.ics</" not in answer
        assert "href>/calendar.ics/journal3.ics</" not in answer
        answer = self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VJOURNAL">
                <C:time-range start="20131229T000000Z" end="21520202T000000Z"/>
              </C:comp-filter>
            </C:comp-filter>"""], "journal", items=(1, 2, 3))
        assert "href>/calendar.ics/journal1.ics</" not in answer
        assert "href>/calendar.ics/journal2.ics</" in answer
        assert "href>/calendar.ics/journal3.ics</" not in answer
        answer = self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VJOURNAL">
                <C:time-range start="20000101T000000Z" end="20000202T000000Z"/>
              </C:comp-filter>
            </C:comp-filter>"""], "journal", items=(1, 2, 3))
        assert "href>/calendar.ics/journal1.ics</" not in answer
        assert "href>/calendar.ics/journal2.ics</" in answer
        assert "href>/calendar.ics/journal3.ics</" in answer

    def test_time_range_filter_journals_rrule(self):
        """Report request with time-range filter on journals with rrules."""
        answer = self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VJOURNAL">
                <C:time-range start="19991229T000000Z" end="20000202T000000Z"/>
              </C:comp-filter>
            </C:comp-filter>"""], "journal", items=(1, 2))
        assert "href>/calendar.ics/journal1.ics</" not in answer
        assert "href>/calendar.ics/journal2.ics</" in answer
        answer = self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VJOURNAL">
                <C:time-range start="20051229T000000Z" end="20060202T000000Z"/>
              </C:comp-filter>
            </C:comp-filter>"""], "journal", items=(1, 2))
        assert "href>/calendar.ics/journal1.ics</" not in answer
        assert "href>/calendar.ics/journal2.ics</" in answer
        answer = self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VJOURNAL">
                <C:time-range start="20060102T000000Z" end="20060202T000000Z"/>
              </C:comp-filter>
            </C:comp-filter>"""], "journal", items=(1, 2))
        assert "href>/calendar.ics/journal1.ics</" not in answer
        assert "href>/calendar.ics/journal2.ics</" not in answer

    def test_report_item(self):
        """Test report request on an item"""
        calendar_path = "/calendar.ics/"
        status, _, _ = self.request("MKCALENDAR", calendar_path)
        assert status == 201
        event = get_file_content("event1.ics")
        event_path = posixpath.join(calendar_path, "event.ics")
        status, _, _ = self.request("PUT", event_path, event)
        assert status == 201
        status, _, answer = self.request(
            "REPORT", event_path,
            """<?xml version="1.0" encoding="utf-8" ?>
               <C:calendar-query xmlns:C="urn:ietf:params:xml:ns:caldav">
                 <D:prop xmlns:D="DAV:">
                   <D:getetag />
                 </D:prop>
               </C:calendar-query>""")
        assert status == 207
        assert "href>%s<" % event_path in answer

    def _report_sync_token(self, calendar_path, sync_token=None):
        sync_token_xml = (
            "<sync-token><![CDATA[%s]]></sync-token>" % sync_token
            if sync_token else "<sync-token />")
        status, _, answer = self.request(
            "REPORT", calendar_path,
            """<?xml version="1.0" encoding="utf-8" ?>
               <sync-collection xmlns="DAV:">
                 <prop>
                   <getetag />
                 </prop>
                 %s
               </sync-collection>""" % sync_token_xml)
        if sync_token and status == 409:
            return None, None
        assert status == 207
        xml = ET.fromstring(answer)
        sync_token = xml.find("{DAV:}sync-token").text.strip()
        assert sync_token
        return sync_token, xml

    def test_report_sync_collection_no_change(self):
        """Test sync-collection report without modifying the collection"""
        calendar_path = "/calendar.ics/"
        status, _, _ = self.request("MKCALENDAR", calendar_path)
        assert status == 201
        event = get_file_content("event1.ics")
        event_path = posixpath.join(calendar_path, "event.ics")
        status, _, _ = self.request("PUT", event_path, event)
        assert status == 201
        sync_token, xml = self._report_sync_token(calendar_path)
        assert xml.find("{DAV:}response") is not None
        new_sync_token, xml = self._report_sync_token(calendar_path,
                                                      sync_token)
        assert sync_token == new_sync_token
        assert xml.find("{DAV:}response") is None

    def test_report_sync_collection_add(self):
        """Test sync-collection report with an added item"""
        calendar_path = "/calendar.ics/"
        status, _, _ = self.request("MKCALENDAR", calendar_path)
        assert status == 201
        sync_token, xml = self._report_sync_token(calendar_path)
        event = get_file_content("event1.ics")
        event_path = posixpath.join(calendar_path, "event.ics")
        status, _, _ = self.request("PUT", event_path, event)
        assert status == 201
        sync_token, xml = self._report_sync_token(calendar_path, sync_token)
        if not sync_token:
            pytest.skip("storage backend does not support sync-token")
        assert xml.find("{DAV:}response") is not None
        assert xml.find("{DAV:}response/{DAV:}status") is None

    def test_report_sync_collection_delete(self):
        """Test sync-collection report with a deleted item"""
        calendar_path = "/calendar.ics/"
        status, _, _ = self.request("MKCALENDAR", calendar_path)
        assert status == 201
        event = get_file_content("event1.ics")
        event_path = posixpath.join(calendar_path, "event.ics")
        status, _, _ = self.request("PUT", event_path, event)
        assert status == 201
        sync_token, xml = self._report_sync_token(calendar_path)
        status, _, _ = self.request("DELETE", event_path)
        assert status == 200
        sync_token, xml = self._report_sync_token(calendar_path, sync_token)
        if not sync_token:
            pytest.skip("storage backend does not support sync-token")
        assert "404" in xml.find("{DAV:}response/{DAV:}status").text

    def test_report_sync_collection_create_delete(self):
        """Test sync-collection report with a created and deleted item"""
        calendar_path = "/calendar.ics/"
        status, _, _ = self.request("MKCALENDAR", calendar_path)
        assert status == 201
        sync_token, xml = self._report_sync_token(calendar_path)
        event = get_file_content("event1.ics")
        event_path = posixpath.join(calendar_path, "event.ics")
        status, _, _ = self.request("PUT", event_path, event)
        assert status == 201
        status, _, _ = self.request("DELETE", event_path)
        assert status == 200
        sync_token, xml = self._report_sync_token(calendar_path, sync_token)
        if not sync_token:
            pytest.skip("storage backend does not support sync-token")
        assert "404" in xml.find("{DAV:}response/{DAV:}status").text

    def test_report_sync_collection_modify_undo(self):
        """Test sync-collection report with a modified and changed back item"""
        calendar_path = "/calendar.ics/"
        status, _, _ = self.request("MKCALENDAR", calendar_path)
        assert status == 201
        event1 = get_file_content("event1.ics")
        event2 = get_file_content("event2.ics")
        event_path = posixpath.join(calendar_path, "event1.ics")
        status, _, _ = self.request("PUT", event_path, event1)
        assert status == 201
        sync_token, xml = self._report_sync_token(calendar_path)
        status, _, _ = self.request("PUT", event_path, event2)
        assert status == 201
        status, _, _ = self.request("PUT", event_path, event1)
        assert status == 201
        sync_token, xml = self._report_sync_token(calendar_path, sync_token)
        if not sync_token:
            pytest.skip("storage backend does not support sync-token")
        assert xml.find("{DAV:}response") is not None
        assert xml.find("{DAV:}response/{DAV:}status") is None

    def test_report_sync_collection_move(self):
        """Test sync-collection report a moved item"""
        calendar_path = "/calendar.ics/"
        status, _, _ = self.request("MKCALENDAR", calendar_path)
        assert status == 201
        event = get_file_content("event1.ics")
        event1_path = posixpath.join(calendar_path, "event1.ics")
        event2_path = posixpath.join(calendar_path, "event2.ics")
        status, _, _ = self.request("PUT", event1_path, event)
        assert status == 201
        sync_token, xml = self._report_sync_token(calendar_path)
        status, _, _ = self.request(
            "MOVE", event1_path, HTTP_DESTINATION=event2_path, HTTP_HOST="")
        assert status == 201
        sync_token, xml = self._report_sync_token(calendar_path, sync_token)
        if not sync_token:
            pytest.skip("storage backend does not support sync-token")
        for response in xml.findall("{DAV:}response"):
            if response.find("{DAV:}status") is None:
                assert response.find("{DAV:}href").text == event2_path
            else:
                assert "404" in response.find("{DAV:}status").text
                assert response.find("{DAV:}href").text == event1_path

    def test_report_sync_collection_move_undo(self):
        """Test sync-collection report with a moved and moved back item"""
        calendar_path = "/calendar.ics/"
        status, _, _ = self.request("MKCALENDAR", calendar_path)
        assert status == 201
        event = get_file_content("event1.ics")
        event1_path = posixpath.join(calendar_path, "event1.ics")
        event2_path = posixpath.join(calendar_path, "event2.ics")
        status, _, _ = self.request("PUT", event1_path, event)
        assert status == 201
        sync_token, xml = self._report_sync_token(calendar_path)
        status, _, _ = self.request(
            "MOVE", event1_path, HTTP_DESTINATION=event2_path, HTTP_HOST="")
        assert status == 201
        status, _, _ = self.request(
            "MOVE", event2_path, HTTP_DESTINATION=event1_path, HTTP_HOST="")
        assert status == 201
        sync_token, xml = self._report_sync_token(calendar_path, sync_token)
        if not sync_token:
            pytest.skip("storage backend does not support sync-token")
        created = deleted = 0
        for response in xml.findall("{DAV:}response"):
            if response.find("{DAV:}status") is None:
                assert response.find("{DAV:}href").text == event1_path
                created += 1
            else:
                assert "404" in response.find("{DAV:}status").text
                assert response.find("{DAV:}href").text == event2_path
                deleted += 1
        assert created == 1 and deleted == 1

    def test_report_sync_collection_invalid_sync_token(self):
        """Test sync-collection report with an invalid sync token"""
        calendar_path = "/calendar.ics/"
        status, _, _ = self.request("MKCALENDAR", calendar_path)
        assert status == 201
        sync_token, xml = self._report_sync_token(
            calendar_path, "http://radicale.org/ns/sync/INVALID")
        assert not sync_token

    def test_propfind_sync_token(self):
        """Retrieve the sync-token with a propfind request"""
        calendar_path = "/calendar.ics/"
        status, _, _ = self.request("MKCALENDAR", calendar_path)
        assert status == 201
        sync_token, xml = self._report_sync_token(calendar_path)
        event = get_file_content("event1.ics")
        event_path = posixpath.join(calendar_path, "event.ics")
        status, _, _ = self.request("PUT", event_path, event)
        assert status == 201
        new_sync_token, xml = self._report_sync_token(calendar_path,
                                                      sync_token)
        assert sync_token != new_sync_token

    def test_propfind_same_as_sync_collection_sync_token(self):
        """Compare sync-token property with sync-collection sync-token"""
        calendar_path = "/calendar.ics/"
        status, _, _ = self.request("MKCALENDAR", calendar_path)
        assert status == 201
        sync_token, xml = self._report_sync_token(calendar_path)
        new_sync_token, xml = self._report_sync_token(calendar_path,
                                                      sync_token)
        assert sync_token == new_sync_token

    def test_calendar_getcontenttype(self):
        """Test report request on an item"""
        status, _, _ = self.request("MKCALENDAR", "/test/")
        assert status == 201
        for component in ("event", "todo", "journal"):
            event = get_file_content("{}1.ics".format(component))
            status, _, _ = self.request("PUT", "/test/test.ics", event)
            assert status == 201
            status, _, answer = self.request(
                "REPORT", "/test/",
                """<?xml version="1.0" encoding="utf-8" ?>
                   <C:calendar-query xmlns:C="urn:ietf:params:xml:ns:caldav">
                     <D:prop xmlns:D="DAV:">
                       <D:getcontenttype />
                     </D:prop>
                   </C:calendar-query>""")
            assert status == 207
            assert ">text/calendar;charset=utf-8;component=V{}<".format(
                component.upper()) in answer

    def test_addressbook_getcontenttype(self):
        """Test report request on an item"""
        status, _, _ = self._create_addressbook("/test/")
        assert status == 201
        contact = get_file_content("contact1.vcf")
        status, _, _ = self.request("PUT", "/test/test.vcf", contact)
        assert status == 201
        status, _, answer = self.request(
            "REPORT", "/test/",
            """<?xml version="1.0" encoding="utf-8" ?>
               <C:calendar-query xmlns:C="urn:ietf:params:xml:ns:caldav">
                 <D:prop xmlns:D="DAV:">
                   <D:getcontenttype />
                 </D:prop>
               </C:calendar-query>""")
        assert status == 207
        assert ">text/vcard;charset=utf-8<" in answer

    def test_authorization(self):
        authorization = "Basic " + base64.b64encode(b"user:").decode()
        status, _, answer = self.request(
            "PROPFIND", "/",
            """<?xml version="1.0" encoding="utf-8"?>
               <propfind xmlns="DAV:">
                 <prop>
                   <current-user-principal />
                 </prop>
               </propfind>""",
            HTTP_AUTHORIZATION=authorization)
        assert status == 207
        assert "href>/user/<" in answer

    def test_authentication(self):
        """Test if server sends authentication request."""
        self.configuration["auth"]["type"] = "htpasswd"
        self.configuration["auth"]["htpasswd_filename"] = os.devnull
        self.configuration["auth"]["htpasswd_encryption"] = "plain"
        self.configuration["rights"]["type"] = "owner_only"
        self.application = Application(self.configuration, self.logger)
        status, headers, _ = self.request("MKCOL", "/user/")
        assert status in (401, 403)
        assert headers.get("WWW-Authenticate")

    def test_principal_collection_creation(self):
        """Verify existence of the principal collection."""
        status, _, _ = self.request("PROPFIND", "/user/", HTTP_AUTHORIZATION=(
            "Basic " + base64.b64encode(b"user:").decode()))
        assert status == 207

    def test_existence_of_root_collections(self):
        """Verify that the root collection always exists."""
        # Use PROPFIND because GET returns message
        status, _, _ = self.request("PROPFIND", "/")
        assert status == 207
        # it should still exist after deletion
        status, _, _ = self.request("DELETE", "/")
        assert status == 200
        status, _, _ = self.request("PROPFIND", "/")
        assert status == 207

    def test_custom_headers(self):
        if not self.configuration.has_section("headers"):
            self.configuration.add_section("headers")
        self.configuration.set("headers", "test", "123")
        # Test if header is set on success
        status, headers, _ = self.request("OPTIONS", "/")
        assert status == 200
        assert headers.get("test") == "123"
        # Test if header is set on failure
        status, headers, _ = self.request(
            "GET", "/.well-known/does not exist")
        assert status == 404
        assert headers.get("test") == "123"

    @pytest.mark.skipif(sys.version_info < (3, 6),
                        reason="Unsupported in Python < 3.6")
    def test_timezone_seconds(self):
        """Verify that timezones with minutes and seconds work."""
        status, _, _ = self.request("MKCALENDAR", "/calendar.ics/")
        assert status == 201
        event = get_file_content("event_timezone_seconds.ics")
        status, _, _ = self.request("PUT", "/calendar.ics/event.ics", event)
        assert status == 201

    def test_missing_uid(self):
        """Verify that missing UIDs are added in a stable manner."""
        status, _, _ = self.request("MKCALENDAR", "/calendar.ics/")
        assert status == 201
        event_without_uid = get_file_content("event1.ics").replace(
            "UID:event1\n", "")
        assert "UID" not in event_without_uid
        path = "/calendar.ics/event1.ics"
        status, _, _ = self.request("PUT", path, event_without_uid)
        assert status == 201
        status, _, answer = self.request("GET", path)
        assert status == 200
        uid = None
        for line in answer.split("\r\n"):
            if line.startswith("UID:"):
                uid = line[len("UID:"):]
        assert uid
        status, _, _ = self.request("PUT", path, event_without_uid)
        assert status == 201
        status, _, answer = self.request("GET", path)
        assert status == 200
        assert "UID:%s\r\n" % uid in answer


class BaseFileSystemTest(BaseTest):
    """Base class for filesystem backend tests."""
    storage_type = None

    def setup(self):
        self.configuration = config.load()
        self.configuration["storage"]["type"] = self.storage_type
        self.colpath = tempfile.mkdtemp()
        self.configuration["storage"]["filesystem_folder"] = self.colpath
        # Disable syncing to disk for better performance
        self.configuration["storage"]["filesystem_fsync"] = "False"
        # Required on Windows, doesn't matter on Unix
        self.configuration["storage"]["filesystem_close_lock_file"] = "True"
        self.application = Application(self.configuration, self.logger)

    def teardown(self):
        shutil.rmtree(self.colpath)


class TestMultiFileSystem(BaseFileSystemTest, BaseRequestsMixIn):
    """Test BaseRequests on multifilesystem."""
    storage_type = "multifilesystem"

    def test_fsync(self):
        """Create a directory and file with syncing enabled."""
        self.configuration["storage"]["filesystem_fsync"] = "True"
        status, _, _ = self.request("MKCALENDAR", "/calendar.ics/")
        assert status == 201

    def test_hook(self):
        """Run hook."""
        self.configuration["storage"]["hook"] = (
            "mkdir %s" % os.path.join("collection-root", "created_by_hook"))
        status, _, _ = self.request("MKCALENDAR", "/calendar.ics/")
        assert status == 201
        status, _, _ = self.request("PROPFIND", "/created_by_hook/")
        assert status == 207

    def test_hook_read_access(self):
        """Verify that hook is not run for read accesses."""
        self.configuration["storage"]["hook"] = (
            "mkdir %s" % os.path.join("collection-root", "created_by_hook"))
        status, _, _ = self.request("PROPFIND", "/")
        assert status == 207
        status, _, _ = self.request("PROPFIND", "/created_by_hook/")
        assert status == 404

    @pytest.mark.skipif(os.system("type flock") != 0,
                        reason="flock command not found")
    def test_hook_storage_locked(self):
        """Verify that the storage is locked when the hook runs."""
        self.configuration["storage"]["hook"] = (
            "flock -n .Radicale.lock || exit 0; exit 1")
        status, _, _ = self.request("MKCALENDAR", "/calendar.ics/")
        assert status == 201

    def test_hook_principal_collection_creation(self):
        """Verify that the hooks runs when a new user is created."""
        self.configuration["storage"]["hook"] = (
            "mkdir %s" % os.path.join("collection-root", "created_by_hook"))
        status, _, _ = self.request("PROPFIND", "/", HTTP_AUTHORIZATION=(
            "Basic " + base64.b64encode(b"user:").decode()))
        assert status == 207
        status, _, _ = self.request("PROPFIND", "/created_by_hook/")
        assert status == 207

    def test_hook_fail(self):
        """Verify that a request fails if the hook fails."""
        self.configuration["storage"]["hook"] = "exit 1"
        status, _, _ = self.request("MKCALENDAR", "/calendar.ics/")
        assert status != 201

    def test_item_cache_rebuild(self):
        """Delete the item cache and verify that it is rebuild."""
        status, _, _ = self.request("MKCALENDAR", "/calendar.ics/")
        assert status == 201
        event = get_file_content("event1.ics")
        path = "/calendar.ics/event1.ics"
        status, _, _ = self.request("PUT", path, event)
        assert status == 201
        status, _, answer1 = self.request("GET", path)
        assert status == 200
        cache_folder = os.path.join(self.colpath, "collection-root",
                                    "calendar.ics", ".Radicale.cache", "item")
        assert os.path.exists(os.path.join(cache_folder, "event1.ics"))
        shutil.rmtree(cache_folder)
        status, _, answer2 = self.request("GET", path)
        assert status == 200
        assert answer1 == answer2
        assert os.path.exists(os.path.join(cache_folder, "event1.ics"))


class TestCustomStorageSystem(BaseFileSystemTest):
    """Test custom backend loading."""
    storage_type = "tests.custom.storage"

    def test_root(self):
        """A simple test to verify that the custom backend works."""
        BaseRequestsMixIn.test_root(self)
