# This file is part of Radicale - CalDAV and CardDAV server
# Copyright © 2012-2017 Guillaume Ayoub
# Copyright © 2017-2022 Unrud <unrud@outlook.com>
# Copyright © 2024-2025 Peter Bieringer <pb@bieringer.de>
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

import logging
import os
import posixpath
from typing import Any, Callable, ClassVar, Iterable, List, Optional, Tuple

import defusedxml.ElementTree as DefusedET
import vobject

from radicale import storage, xmlutils
from radicale.tests import RESPONSES, BaseTest
from radicale.tests.helpers import get_file_content


class TestBaseRequests(BaseTest):
    """Tests with simple requests."""

    # Allow skipping sync-token tests, when not fully supported by the backend
    full_sync_token_support: ClassVar[bool] = True

    def setup_method(self) -> None:
        BaseTest.setup_method(self)
        rights_file_path = os.path.join(self.colpath, "rights")
        with open(rights_file_path, "w") as f:
            f.write("""\
[permit delete collection]
user: .*
collection: test-permit-delete
permissions: RrWwD

[forbid delete collection]
user: .*
collection: test-forbid-delete
permissions: RrWwd

[permit overwrite collection]
user: .*
collection: test-permit-overwrite
permissions: RrWwO

[forbid overwrite collection]
user: .*
collection: test-forbid-overwrite
permissions: RrWwo

[allow all]
user: .*
collection: .*
permissions: RrWw""")
        self.configure({"rights": {"file": rights_file_path,
                                   "type": "from_file"}})

    def test_root(self) -> None:
        """GET request at "/"."""
        for path in ["", "/", "//"]:
            _, headers, answer = self.request("GET", path, check=302)
            assert headers.get("Location") == "/.web"
            assert answer == "Redirected to /.web"

    def test_root_script_name(self) -> None:
        """GET request at "/" with SCRIPT_NAME."""
        for path in ["", "/", "//"]:
            _, headers, _ = self.request("GET", path, check=302,
                                         SCRIPT_NAME="/radicale")
            assert headers.get("Location") == "/radicale/.web"

    def test_root_broken_script_name(self) -> None:
        """GET request at "/" with SCRIPT_NAME ending with "/"."""
        for script_name, prefix in [
                ("/", ""), ("//", ""), ("/radicale/", "/radicale"),
                ("radicale", None), ("radicale//", None)]:
            _, headers, _ = self.request(
                "GET", "/", check=500 if prefix is None else 302,
                SCRIPT_NAME=script_name)
            assert (prefix is None or
                    headers.get("Location") == prefix + "/.web")

    def test_root_http_x_script_name(self) -> None:
        """GET request at "/" with HTTP_X_SCRIPT_NAME."""
        for path in ["", "/", "//"]:
            _, headers, _ = self.request("GET", path, check=302,
                                         HTTP_X_SCRIPT_NAME="/radicale")
            assert headers.get("Location") == "/radicale/.web"

    def test_root_broken_http_x_script_name(self) -> None:
        """GET request at "/" with HTTP_X_SCRIPT_NAME ending with "/"."""
        for script_name, prefix in [
                ("/", ""), ("//", ""), ("/radicale/", "/radicale"),
                ("radicale", None), ("radicale//", None)]:
            _, headers, _ = self.request(
                "GET", "/", check=400 if prefix is None else 302,
                HTTP_X_SCRIPT_NAME=script_name)
            assert (prefix is None or
                    headers.get("Location") == prefix + "/.web")

    def test_sanitized_path(self) -> None:
        """GET request with unsanitized paths."""
        for path, sane_path in [
                ("//.web", "/.web"), ("//.web/", "/.web/"),
                ("/.web//", "/.web/"), ("/.web/a//b", "/.web/a/b")]:
            _, headers, _ = self.request("GET", path, check=301)
            assert headers.get("Location") == sane_path
            _, headers, _ = self.request("GET", path, check=301,
                                         SCRIPT_NAME="/radicale")
            assert headers.get("Location") == "/radicale%s" % sane_path
            _, headers, _ = self.request("GET", path, check=301,
                                         HTTP_X_SCRIPT_NAME="/radicale")
            assert headers.get("Location") == "/radicale%s" % sane_path

    def test_add_event(self) -> None:
        """Add an event."""
        self.mkcalendar("/calendar.ics/")
        event = get_file_content("event1.ics")
        path = "/calendar.ics/event1.ics"
        self.put(path, event)
        _, headers, answer = self.request("GET", path, check=200)
        assert "ETag" in headers
        assert headers["Content-Type"] == "text/calendar; charset=utf-8"
        assert "VEVENT" in answer
        assert "Event" in answer
        assert "UID:event" in answer

    def test_add_event_without_uid(self) -> None:
        """Add an event without UID."""
        self.mkcalendar("/calendar.ics/")
        event = get_file_content("event1.ics").replace("UID:event1\n", "")
        assert "\nUID:" not in event
        path = "/calendar.ics/event.ics"
        self.put(path, event, check=400)

    def test_add_event_duplicate_uid(self) -> None:
        """Add an event with an existing UID."""
        self.mkcalendar("/calendar.ics/")
        event = get_file_content("event1.ics")
        self.put("/calendar.ics/event1.ics", event)
        status, answer = self.put(
            "/calendar.ics/event1-duplicate.ics", event, check=None)
        assert status in (403, 409)
        xml = DefusedET.fromstring(answer)
        assert xml.tag == xmlutils.make_clark("D:error")
        assert xml.find(xmlutils.make_clark("C:no-uid-conflict")) is not None

    def test_add_event_with_mixed_datetime_and_date(self) -> None:
        """Test event with DTSTART as DATE-TIME and EXDATE as DATE."""
        self.mkcalendar("/calendar.ics/")
        event = get_file_content("event_mixed_datetime_and_date.ics")
        self.put("/calendar.ics/event.ics", event)

    def test_add_event_with_exdate_without_rrule(self) -> None:
        """Test event with EXDATE but not having RRULE."""
        self.mkcalendar("/calendar.ics/")
        event = get_file_content("event_exdate_without_rrule.ics")
        self.put("/calendar.ics/event.ics", event)

    def test_add_todo(self) -> None:
        """Add a todo."""
        self.mkcalendar("/calendar.ics/")
        todo = get_file_content("todo1.ics")
        path = "/calendar.ics/todo1.ics"
        self.put(path, todo)
        _, headers, answer = self.request("GET", path, check=200)
        assert "ETag" in headers
        assert headers["Content-Type"] == "text/calendar; charset=utf-8"
        assert "VTODO" in answer
        assert "Todo" in answer
        assert "UID:todo" in answer

    def test_add_contact(self) -> None:
        """Add a contact."""
        self.create_addressbook("/contacts.vcf/")
        contact = get_file_content("contact1.vcf")
        path = "/contacts.vcf/contact.vcf"
        self.put(path, contact)
        _, headers, answer = self.request("GET", path, check=200)
        assert "ETag" in headers
        assert headers["Content-Type"] == "text/vcard; charset=utf-8"
        assert "VCARD" in answer
        assert "UID:contact1" in answer
        _, answer = self.get(path)
        assert "UID:contact1" in answer

    def test_add_contact_photo_with_data_uri(self) -> None:
        """Test workaround for broken PHOTO data from InfCloud"""
        self.create_addressbook("/contacts.vcf/")
        contact = get_file_content("contact_photo_with_data_uri.vcf")
        self.put("/contacts.vcf/contact.vcf", contact)

    def test_add_contact_without_uid(self) -> None:
        """Add a contact without UID."""
        self.create_addressbook("/contacts.vcf/")
        contact = get_file_content("contact1.vcf").replace("UID:contact1\n",
                                                           "")
        assert "\nUID" not in contact
        path = "/contacts.vcf/contact.vcf"
        self.put(path, contact, check=400)

    def test_update_event(self) -> None:
        """Update an event."""
        self.mkcalendar("/calendar.ics/")
        event = get_file_content("event1.ics")
        event_modified = get_file_content("event1_modified.ics")
        path = "/calendar.ics/event1.ics"
        self.put(path, event)
        self.put(path, event_modified, check=204)
        _, answer = self.get("/calendar.ics/")
        assert answer.count("BEGIN:VEVENT") == 1
        _, answer = self.get(path)
        assert "DTSTAMP:20130902T150159Z" in answer

    def test_update_event_no_etag_strict_preconditions_true(self) -> None:
        """Update an event without serving etag having strict_preconditions enabled (Precondition Failed)."""
        self.configure({"storage": {"strict_preconditions": True}})
        self.mkcalendar("/calendar.ics/")
        event = get_file_content("event1.ics")
        event_modified = get_file_content("event1_modified.ics")
        path = "/calendar.ics/event1.ics"
        self.put(path, event, check=201)
        self.put(path, event_modified, check=412)

    def test_update_event_with_etag_strict_preconditions_true(self) -> None:
        """Update an event with serving equal etag having strict_preconditions enabled (OK)."""
        self.configure({"storage": {"strict_preconditions": True}})
        self.configure({"logging": {"response_content_on_debug": True}})
        self.mkcalendar("/calendar.ics/")
        event = get_file_content("event1.ics")
        event_modified = get_file_content("event1_modified.ics")
        path = "/calendar.ics/event1.ics"
        self.put(path, event, check=201)
        # get etag
        _, responses = self.report("/calendar.ics/", """\
<?xml version="1.0" encoding="utf-8" ?>
<C:calendar-query xmlns:C="urn:ietf:params:xml:ns:caldav">
    <D:prop xmlns:D="DAV:">
        <D:getetag/>
    </D:prop>
</C:calendar-query>""")
        assert len(responses) == 1
        response = responses["/calendar.ics/event1.ics"]
        assert not isinstance(response, int)
        status, prop = response["D:getetag"]
        assert status == 200 and prop.text
        self.put(path, event_modified, check=204, http_if_match=prop.text)

    def test_update_event_with_etag_mismatch(self) -> None:
        """Update an event with serving mismatch etag (Precondition Failed)."""
        self.mkcalendar("/calendar.ics/")
        event = get_file_content("event1.ics")
        event_modified = get_file_content("event1_modified.ics")
        path = "/calendar.ics/event1.ics"
        self.put(path, event, check=201)
        self.put(path, event_modified, check=412, http_if_match="0000")

    def test_add_event_with_etag(self) -> None:
        """Add an event with serving etag (Precondition Failed)."""
        self.mkcalendar("/calendar.ics/")
        event = get_file_content("event1.ics")
        path = "/calendar.ics/event1.ics"
        self.put(path, event, check=412, http_if_match="0000")

    def test_update_event_uid_event(self) -> None:
        """Update an event with a different UID."""
        self.mkcalendar("/calendar.ics/")
        event1 = get_file_content("event1.ics")
        event2 = get_file_content("event2.ics")
        path = "/calendar.ics/event1.ics"
        self.put(path, event1)
        status, answer = self.put(path, event2, check=None)
        assert status in (403, 409)
        xml = DefusedET.fromstring(answer)
        assert xml.tag == xmlutils.make_clark("D:error")
        assert xml.find(xmlutils.make_clark("C:no-uid-conflict")) is not None

    def test_put_whole_calendar(self) -> None:
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

    def test_put_whole_calendar_without_uids(self) -> None:
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

    def test_put_whole_calendar_case_sensitive_uids(self) -> None:
        """Create a whole calendar with case-sensitive UIDs."""
        events = get_file_content("event_multiple_case_sensitive_uids.ics")
        self.put("/calendar.ics/", events)
        _, answer = self.get("/calendar.ics/")
        assert "\r\nUID:event\r\n" in answer and "\r\nUID:EVENT\r\n" in answer

    def test_put_whole_addressbook(self) -> None:
        """Create and overwrite a whole addressbook."""
        contacts = get_file_content("contact_multiple.vcf")
        self.put("/contacts.vcf/", contacts)
        _, answer = self.get("/contacts.vcf/")
        assert answer is not None
        assert "\r\nUID:contact1\r\n" in answer
        assert "\r\nUID:contact2\r\n" in answer

    def test_put_whole_addressbook_without_uids(self) -> None:
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

    def test_add_event_tz_dtend_only(self) -> None:
        """Add an event having TZ only on DTEND."""
        self.mkcalendar("/calendar.ics/")
        event = get_file_content("event_issue1847_1.ics")
        path = "/calendar.ics/event_issue1847_1.ics"
        self.put(path, event)
        _, headers, answer = self.request("GET", path, check=200)

    def test_add_event_tz_dtstart_only(self) -> None:
        """Add an event having TZ only on DTSTART."""
        self.mkcalendar("/calendar.ics/")
        event = get_file_content("event_issue1847_2.ics")
        path = "/calendar.ics/event_issue1847_2.ics"
        self.put(path, event)
        _, headers, answer = self.request("GET", path, check=200)

    def test_verify(self) -> None:
        """Verify the storage."""
        contacts = get_file_content("contact_multiple.vcf")
        self.put("/contacts.vcf/", contacts)
        events = get_file_content("event_multiple.ics")
        self.put("/calendar.ics/", events)
        s = storage.load(self.configuration)
        assert s.verify()

    def test_delete(self) -> None:
        """Delete an event."""
        self.mkcalendar("/calendar.ics/")
        event = get_file_content("event1.ics")
        path = "/calendar.ics/event1.ics"
        self.put(path, event)
        _, responses = self.delete(path)
        assert responses[path] == 200
        _, answer = self.get("/calendar.ics/")
        assert "VEVENT" not in answer

    def test_mkcalendar(self) -> None:
        """Make a calendar."""
        self.mkcalendar("/calendar.ics/")
        _, answer = self.get("/calendar.ics/")
        assert "BEGIN:VCALENDAR" in answer
        assert "END:VCALENDAR" in answer

    def test_mkcalendar_overwrite(self) -> None:
        """Try to overwrite an existing calendar."""
        self.mkcalendar("/calendar.ics/")
        status, answer = self.mkcalendar("/calendar.ics/", check=None)
        assert status in (403, 409)
        xml = DefusedET.fromstring(answer)
        assert xml.tag == xmlutils.make_clark("D:error")
        assert xml.find(xmlutils.make_clark(
            "D:resource-must-be-null")) is not None

    def test_mkcalendar_intermediate(self) -> None:
        """Try make a calendar in a unmapped collection."""
        self.mkcalendar("/unmapped/calendar.ics/", check=409)

    def test_mkcol(self) -> None:
        """Make a collection."""
        self.mkcol("/user/")

    def test_mkcol_overwrite(self) -> None:
        """Try to overwrite an existing collection."""
        self.mkcol("/user/")
        self.mkcol("/user/", check=405)

    def test_mkcol_intermediate(self) -> None:
        """Try make a collection in a unmapped collection."""
        self.mkcol("/unmapped/user/", check=409)

    def test_mkcol_make_calendar(self) -> None:
        """Make a calendar with additional props."""
        mkcol_make_calendar = get_file_content("mkcol_make_calendar.xml")
        self.mkcol("/calendar.ics/", mkcol_make_calendar)
        _, answer = self.get("/calendar.ics/")
        assert answer is not None
        assert "BEGIN:VCALENDAR" in answer
        assert "END:VCALENDAR" in answer
        # Read additional properties
        propfind = get_file_content("propfind_calendar_color.xml")
        _, responses = self.propfind("/calendar.ics/", propfind)
        response = responses["/calendar.ics/"]
        assert not isinstance(response, int) and len(response) == 1
        status, prop = response["ICAL:calendar-color"]
        assert status == 200 and prop.text == "#BADA55"

    def test_move(self) -> None:
        """Move a item."""
        self.mkcalendar("/calendar.ics/")
        event = get_file_content("event1.ics")
        path1 = "/calendar.ics/event1.ics"
        path2 = "/calendar.ics/event2.ics"
        self.put(path1, event)
        self.request("MOVE", path1, check=201,
                     HTTP_DESTINATION="http://127.0.0.1/"+path2)
        self.get(path1, check=404)
        self.get(path2)

    def test_move_between_collections(self) -> None:
        """Move a item."""
        self.mkcalendar("/calendar1.ics/")
        self.mkcalendar("/calendar2.ics/")
        event = get_file_content("event1.ics")
        path1 = "/calendar1.ics/event1.ics"
        path2 = "/calendar2.ics/event2.ics"
        self.put(path1, event)
        self.request("MOVE", path1, check=201,
                     HTTP_DESTINATION="http://127.0.0.1/"+path2)
        self.get(path1, check=404)
        self.get(path2)

    def test_move_between_collections_duplicate_uid(self) -> None:
        """Move a item to a collection which already contains the UID."""
        self.mkcalendar("/calendar1.ics/")
        self.mkcalendar("/calendar2.ics/")
        event = get_file_content("event1.ics")
        path1 = "/calendar1.ics/event1.ics"
        path2 = "/calendar2.ics/event2.ics"
        self.put(path1, event)
        self.put("/calendar2.ics/event1.ics", event)
        status, _, answer = self.request(
            "MOVE", path1, HTTP_DESTINATION="http://127.0.0.1/"+path2)
        assert status in (403, 409)
        xml = DefusedET.fromstring(answer)
        assert xml.tag == xmlutils.make_clark("D:error")
        assert xml.find(xmlutils.make_clark("C:no-uid-conflict")) is not None

    def test_move_between_collections_overwrite(self) -> None:
        """Move a item to a collection which already contains the item."""
        self.mkcalendar("/calendar1.ics/")
        self.mkcalendar("/calendar2.ics/")
        event = get_file_content("event1.ics")
        path1 = "/calendar1.ics/event1.ics"
        path2 = "/calendar2.ics/event1.ics"
        self.put(path1, event)
        self.put(path2, event)
        self.request("MOVE", path1, check=412,
                     HTTP_DESTINATION="http://127.0.0.1/"+path2)
        self.request("MOVE", path1, check=204, HTTP_OVERWRITE="T",
                     HTTP_DESTINATION="http://127.0.0.1/"+path2)

    def test_move_between_collections_overwrite_uid_conflict(self) -> None:
        """Move an item to a collection which already contains the item with
           a different UID."""
        self.mkcalendar("/calendar1.ics/")
        self.mkcalendar("/calendar2.ics/")
        event1 = get_file_content("event1.ics")
        event2 = get_file_content("event2.ics")
        path1 = "/calendar1.ics/event1.ics"
        path2 = "/calendar2.ics/event2.ics"
        self.put(path1, event1)
        self.put(path2, event2)
        status, _, answer = self.request(
            "MOVE", path1, HTTP_OVERWRITE="T",
            HTTP_DESTINATION="http://127.0.0.1/"+path2)
        assert status in (403, 409)
        xml = DefusedET.fromstring(answer)
        assert xml.tag == xmlutils.make_clark("D:error")
        assert xml.find(xmlutils.make_clark("C:no-uid-conflict")) is not None

    def test_head(self) -> None:
        _, headers, answer = self.request("HEAD", "/", check=302)
        assert int(headers.get("Content-Length", "0")) > 0 and not answer

    def test_options(self) -> None:
        _, headers, _ = self.request("OPTIONS", "/", check=200)
        assert "DAV" in headers

    def test_delete_collection(self) -> None:
        """Delete a collection."""
        self.mkcalendar("/calendar.ics/")
        event = get_file_content("event1.ics")
        self.put("/calendar.ics/event1.ics", event)
        _, responses = self.delete("/calendar.ics/")
        assert responses["/calendar.ics/"] == 200
        self.get("/calendar.ics/", check=404)

    def test_delete_collection_global_forbid(self) -> None:
        """Delete a collection (expect forbidden)."""
        self.configure({"rights": {"permit_delete_collection": False}})
        self.mkcalendar("/calendar.ics/")
        event = get_file_content("event1.ics")
        self.put("/calendar.ics/event1.ics", event)
        _, responses = self.delete("/calendar.ics/", check=401)
        self.get("/calendar.ics/", check=200)

    def test_delete_collection_global_forbid_explicit_permit(self) -> None:
        """Delete a collection with permitted path (expect permit)."""
        self.configure({"rights": {"permit_delete_collection": False}})
        self.mkcalendar("/test-permit-delete/")
        event = get_file_content("event1.ics")
        self.put("/test-permit-delete/event1.ics", event)
        _, responses = self.delete("/test-permit-delete/", check=200)
        self.get("/test-permit-delete/", check=404)

    def test_delete_collection_global_permit_explicit_forbid(self) -> None:
        """Delete a collection with permitted path (expect forbid)."""
        self.configure({"rights": {"permit_delete_collection": True}})
        self.mkcalendar("/test-forbid-delete/")
        event = get_file_content("event1.ics")
        self.put("/test-forbid-delete/event1.ics", event)
        _, responses = self.delete("/test-forbid-delete/", check=401)
        self.get("/test-forbid-delete/", check=200)

    def test_delete_root_collection(self) -> None:
        """Delete the root collection."""
        self.mkcalendar("/calendar.ics/")
        event = get_file_content("event1.ics")
        self.put("/event1.ics", event)
        self.put("/calendar.ics/event1.ics", event)
        _, responses = self.delete("/")
        assert len(responses) == 1 and responses["/"] == 200
        self.get("/calendar.ics/", check=404)
        self.get("/event1.ics", 404)

    def test_overwrite_collection_global_forbid(self) -> None:
        """Overwrite a collection (expect forbid)."""
        self.configure({"rights": {"permit_overwrite_collection": False}})
        event = get_file_content("event1.ics")
        self.put("/calender.ics/", event, check=401)

    def test_overwrite_collection_global_forbid_explict_permit(self) -> None:
        """Overwrite a collection with permitted path (expect permit)."""
        self.configure({"rights": {"permit_overwrite_collection": False}})
        event = get_file_content("event1.ics")
        self.put("/test-permit-overwrite/", event, check=201)

    def test_overwrite_collection_global_permit(self) -> None:
        """Overwrite a collection (expect permit)."""
        self.configure({"rights": {"permit_overwrite_collection": True}})
        event = get_file_content("event1.ics")
        self.put("/calender.ics/", event, check=201)

    def test_overwrite_collection_global_permit_explict_forbid(self) -> None:
        """Overwrite a collection with forbidden path (expect forbid)."""
        self.configure({"rights": {"permit_overwrite_collection": True}})
        event = get_file_content("event1.ics")
        self.put("/test-forbid-overwrite/", event, check=401)

    def test_propfind(self) -> None:
        calendar_path = "/calendar.ics/"
        self.mkcalendar("/calendar.ics/")
        event = get_file_content("event1.ics")
        event_path = posixpath.join(calendar_path, "event.ics")
        self.put(event_path, event)
        _, responses = self.propfind("/", HTTP_DEPTH="1")
        assert len(responses) == 2
        assert "/" in responses and calendar_path in responses
        _, responses = self.propfind(calendar_path, HTTP_DEPTH="1")
        assert len(responses) == 2
        assert calendar_path in responses and event_path in responses

    def test_propfind_propname(self) -> None:
        self.mkcalendar("/calendar.ics/")
        event = get_file_content("event1.ics")
        self.put("/calendar.ics/event.ics", event)
        propfind = get_file_content("propname.xml")
        _, responses = self.propfind("/calendar.ics/", propfind)
        response = responses["/calendar.ics/"]
        assert not isinstance(response, int)
        status, prop = response["D:sync-token"]
        assert status == 200 and not prop.text
        _, responses = self.propfind("/calendar.ics/event.ics", propfind)
        response = responses["/calendar.ics/event.ics"]
        assert not isinstance(response, int)
        status, prop = response["D:getetag"]
        assert status == 200 and not prop.text

    def test_propfind_allprop(self) -> None:
        self.mkcalendar("/calendar.ics/")
        event = get_file_content("event1.ics")
        self.put("/calendar.ics/event.ics", event)
        propfind = get_file_content("allprop.xml")
        _, responses = self.propfind("/calendar.ics/", propfind)
        response = responses["/calendar.ics/"]
        assert not isinstance(response, int)
        status, prop = response["D:sync-token"]
        assert status == 200 and prop.text
        _, responses = self.propfind("/calendar.ics/event.ics", propfind)
        response = responses["/calendar.ics/event.ics"]
        assert not isinstance(response, int)
        status, prop = response["D:getetag"]
        assert status == 200 and prop.text

    def test_propfind_nonexistent(self) -> None:
        """Read a property that does not exist."""
        self.mkcalendar("/calendar.ics/")
        propfind = get_file_content("propfind_calendar_color.xml")
        _, responses = self.propfind("/calendar.ics/", propfind)
        response = responses["/calendar.ics/"]
        assert not isinstance(response, int) and len(response) == 1
        status, prop = response["ICAL:calendar-color"]
        assert status == 404 and not prop.text

    def test_proppatch(self) -> None:
        """Set/Remove a property and read it back."""
        self.mkcalendar("/calendar.ics/")
        proppatch = get_file_content("proppatch_set_calendar_color.xml")
        _, responses = self.proppatch("/calendar.ics/", proppatch)
        response = responses["/calendar.ics/"]
        assert not isinstance(response, int) and len(response) == 1
        status, prop = response["ICAL:calendar-color"]
        assert status == 200 and not prop.text
        # Read property back
        propfind = get_file_content("propfind_calendar_color.xml")
        _, responses = self.propfind("/calendar.ics/", propfind)
        response = responses["/calendar.ics/"]
        assert not isinstance(response, int) and len(response) == 1
        status, prop = response["ICAL:calendar-color"]
        assert status == 200 and prop.text == "#BADA55"
        propfind = get_file_content("allprop.xml")
        _, responses = self.propfind("/calendar.ics/", propfind)
        response = responses["/calendar.ics/"]
        assert not isinstance(response, int)
        status, prop = response["ICAL:calendar-color"]
        assert status == 200 and prop.text == "#BADA55"
        # Remove property
        proppatch = get_file_content("proppatch_remove_calendar_color.xml")
        _, responses = self.proppatch("/calendar.ics/", proppatch)
        response = responses["/calendar.ics/"]
        assert not isinstance(response, int) and len(response) == 1
        status, prop = response["ICAL:calendar-color"]
        assert status == 200 and not prop.text
        # Read property back
        propfind = get_file_content("propfind_calendar_color.xml")
        _, responses = self.propfind("/calendar.ics/", propfind)
        response = responses["/calendar.ics/"]
        assert not isinstance(response, int) and len(response) == 1
        status, prop = response["ICAL:calendar-color"]
        assert status == 404

    def test_proppatch_multiple1(self) -> None:
        """Set/Remove a multiple properties and read them back."""
        self.mkcalendar("/calendar.ics/")
        propfind = get_file_content("propfind_multiple.xml")
        proppatch = get_file_content("proppatch_set_multiple1.xml")
        _, responses = self.proppatch("/calendar.ics/", proppatch)
        response = responses["/calendar.ics/"]
        assert not isinstance(response, int) and len(response) == 2
        status, prop = response["ICAL:calendar-color"]
        assert status == 200 and not prop.text
        status, prop = response["C:calendar-description"]
        assert status == 200 and not prop.text
        # Read properties back
        _, responses = self.propfind("/calendar.ics/", propfind)
        response = responses["/calendar.ics/"]
        assert not isinstance(response, int) and len(response) == 2
        status, prop = response["ICAL:calendar-color"]
        assert status == 200 and prop.text == "#BADA55"
        status, prop = response["C:calendar-description"]
        assert status == 200 and prop.text == "test"
        # Remove properties
        proppatch = get_file_content("proppatch_remove_multiple1.xml")
        _, responses = self.proppatch("/calendar.ics/", proppatch)
        response = responses["/calendar.ics/"]
        assert not isinstance(response, int) and len(response) == 2
        status, prop = response["ICAL:calendar-color"]
        assert status == 200 and not prop.text
        status, prop = response["C:calendar-description"]
        assert status == 200 and not prop.text
        # Read properties back
        _, responses = self.propfind("/calendar.ics/", propfind)
        response = responses["/calendar.ics/"]
        assert not isinstance(response, int) and len(response) == 2
        status, prop = response["ICAL:calendar-color"]
        assert status == 404
        status, prop = response["C:calendar-description"]
        assert status == 404

    def test_proppatch_multiple2(self) -> None:
        """Set/Remove a multiple properties and read them back."""
        self.mkcalendar("/calendar.ics/")
        propfind = get_file_content("propfind_multiple.xml")
        proppatch = get_file_content("proppatch_set_multiple2.xml")
        _, responses = self.proppatch("/calendar.ics/", proppatch)
        response = responses["/calendar.ics/"]
        assert not isinstance(response, int) and len(response) == 2
        status, prop = response["ICAL:calendar-color"]
        assert status == 200 and not prop.text
        status, prop = response["C:calendar-description"]
        assert status == 200 and not prop.text
        # Read properties back
        _, responses = self.propfind("/calendar.ics/", propfind)
        response = responses["/calendar.ics/"]
        assert not isinstance(response, int) and len(response) == 2
        assert len(response) == 2
        status, prop = response["ICAL:calendar-color"]
        assert status == 200 and prop.text == "#BADA55"
        status, prop = response["C:calendar-description"]
        assert status == 200 and prop.text == "test"
        # Remove properties
        proppatch = get_file_content("proppatch_remove_multiple2.xml")
        _, responses = self.proppatch("/calendar.ics/", proppatch)
        response = responses["/calendar.ics/"]
        assert not isinstance(response, int) and len(response) == 2
        status, prop = response["ICAL:calendar-color"]
        assert status == 200 and not prop.text
        status, prop = response["C:calendar-description"]
        assert status == 200 and not prop.text
        # Read properties back
        _, responses = self.propfind("/calendar.ics/", propfind)
        response = responses["/calendar.ics/"]
        assert not isinstance(response, int) and len(response) == 2
        status, prop = response["ICAL:calendar-color"]
        assert status == 404
        status, prop = response["C:calendar-description"]
        assert status == 404

    def test_proppatch_set_and_remove(self) -> None:
        """Set and remove multiple properties in single request."""
        self.mkcalendar("/calendar.ics/")
        propfind = get_file_content("propfind_multiple.xml")
        # Prepare
        proppatch = get_file_content("proppatch_set_multiple1.xml")
        self.proppatch("/calendar.ics/", proppatch)
        # Remove and set properties in single request
        proppatch = get_file_content("proppatch_set_and_remove.xml")
        _, responses = self.proppatch("/calendar.ics/", proppatch)
        response = responses["/calendar.ics/"]
        assert not isinstance(response, int) and len(response) == 2
        status, prop = response["ICAL:calendar-color"]
        assert status == 200 and not prop.text
        status, prop = response["C:calendar-description"]
        assert status == 200 and not prop.text
        # Read properties back
        _, responses = self.propfind("/calendar.ics/", propfind)
        response = responses["/calendar.ics/"]
        assert not isinstance(response, int) and len(response) == 2
        status, prop = response["ICAL:calendar-color"]
        assert status == 404
        status, prop = response["C:calendar-description"]
        assert status == 200 and prop.text == "test2"

    def test_put_whole_calendar_multiple_events_with_same_uid(self) -> None:
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
        response = responses["/calendar.ics/event2.ics"]
        assert not isinstance(response, int)
        status, prop = response["D:getetag"]
        assert status == 200 and prop.text
        _, answer = self.get("/calendar.ics/")
        assert answer.count("BEGIN:VEVENT") == 2

    def _test_filter(self, filters: Iterable[str], kind: str = "event",
                     test: Optional[str] = None, items: Iterable[int] = (1,)
                     ) -> List[str]:
        filter_template = "<C:filter>%s</C:filter>"
        create_collection_fn: Callable[[str], Any]
        if kind in ("event", "journal", "todo", "valarm"):
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
        status, _, = self.delete(path, check=None)
        assert status in (200, 404)
        create_collection_fn(path)
        logging.warning("Upload items %r", items)
        for i in items:
            logging.warning("Upload %d", i)
            filename = filename_template % (kind, i)
            event = get_file_content(filename)
            self.put(posixpath.join(path, filename), event)
        logging.warning("Upload items finished")
        filters_text = "".join(filter_template % f for f in filters)
        _, responses = self.report(path, """\
<?xml version="1.0" encoding="utf-8" ?>
<C:{1} xmlns:C="{0}">
    <D:prop xmlns:D="DAV:">
        <D:getetag/>
    </D:prop>
    {2}
</C:{1}>""".format(namespace, report, filters_text))
        assert responses is not None
        paths = []
        for path, props in responses.items():
            assert not isinstance(props, int) and len(props) == 1
            status, prop = props["D:getetag"]
            assert status == 200 and prop.text
            paths.append(path)
        return paths

    def test_addressbook_empty_filter(self) -> None:
        self._test_filter([""], kind="contact")

    def test_addressbook_prop_filter(self) -> None:
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

    def test_addressbook_prop_filter_any(self) -> None:
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

    def test_addressbook_prop_filter_all(self) -> None:
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

    def test_calendar_empty_filter(self) -> None:
        self._test_filter([""])

    def test_calendar_tag_filter(self) -> None:
        """Report request with tag-based filter on calendar."""
        assert "/calendar.ics/event1.ics" in self._test_filter(["""\
<C:comp-filter name="VCALENDAR"></C:comp-filter>"""])

    def test_item_tag_filter(self) -> None:
        """Report request with tag-based filter on an item."""
        assert "/calendar.ics/event1.ics" in self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
    <C:comp-filter name="VEVENT"></C:comp-filter>
</C:comp-filter>"""])
        assert "/calendar.ics/event1.ics" not in self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
    <C:comp-filter name="VTODO"></C:comp-filter>
</C:comp-filter>"""])

    def test_item_not_tag_filter(self) -> None:
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

    def test_item_prop_filter(self) -> None:
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

    def test_item_not_prop_filter(self) -> None:
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

    def test_mutiple_filters(self) -> None:
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

    def test_text_match_filter(self) -> None:
        """Report request with text-match filter on calendar."""
        assert "/calendar.ics/event1.ics" in self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
    <C:comp-filter name="VEVENT">
        <C:prop-filter name="SUMMARY">
            <C:text-match>event</C:text-match>
        </C:prop-filter>
    </C:comp-filter>
</C:comp-filter>"""])
        assert "/calendar.ics/event1.ics" in self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
    <C:comp-filter name="VEVENT">
        <C:prop-filter name="CATEGORIES">
            <C:text-match>some_category1</C:text-match>
        </C:prop-filter>
    </C:comp-filter>
</C:comp-filter>"""])
        assert "/calendar.ics/event1.ics" in self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
    <C:comp-filter name="VEVENT">
        <C:prop-filter name="CATEGORIES">
            <C:text-match collation="i;octet">some_category1</C:text-match>
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

    def test_param_filter(self) -> None:
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

    def test_time_range_filter_events(self) -> None:
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

    def test_time_range_filter_without_comp_filter(self) -> None:
        """Report request with time-range filter without comp-filter on events."""
        answer = self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
        <C:time-range start="20130801T000000Z" end="20131001T000000Z"/>
</C:comp-filter>"""], "event", items=range(1, 6))
        assert "/calendar.ics/event1.ics" in answer
        assert "/calendar.ics/event2.ics" in answer
        assert "/calendar.ics/event3.ics" in answer
        assert "/calendar.ics/event4.ics" in answer
        assert "/calendar.ics/event5.ics" in answer
        answer = self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
        <C:time-range start="20130902T000000Z" end="20131001T000000Z"/>
</C:comp-filter>"""], items=range(1, 6))
        assert "/calendar.ics/event1.ics" not in answer
        assert "/calendar.ics/event2.ics" in answer
        assert "/calendar.ics/event3.ics" in answer
        assert "/calendar.ics/event4.ics" in answer
        assert "/calendar.ics/event5.ics" in answer
        answer = self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
        <C:time-range start="20130903T000000Z" end="20130908T000000Z"/>
</C:comp-filter>"""], items=range(1, 6))
        assert "/calendar.ics/event1.ics" not in answer
        assert "/calendar.ics/event2.ics" not in answer
        assert "/calendar.ics/event3.ics" in answer
        assert "/calendar.ics/event4.ics" in answer
        assert "/calendar.ics/event5.ics" in answer
        answer = self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
        <C:time-range start="20130903T000000Z" end="20130904T000000Z"/>
</C:comp-filter>"""], items=range(1, 6))
        assert "/calendar.ics/event1.ics" not in answer
        assert "/calendar.ics/event2.ics" not in answer
        assert "/calendar.ics/event3.ics" in answer
        assert "/calendar.ics/event4.ics" not in answer
        assert "/calendar.ics/event5.ics" not in answer
        answer = self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
        <C:time-range start="20130805T000000Z" end="20130810T000000Z"/>
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
        <C:time-range start="20170601T063000Z" end="20170601T070000Z"/>
</C:comp-filter>"""], items=(6, 7, 8, 9))
        assert "/calendar.ics/event6.ics" in answer
        assert "/calendar.ics/event7.ics" in answer
        assert "/calendar.ics/event8.ics" in answer
        assert "/calendar.ics/event9.ics" in answer
        answer = self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
        <C:time-range start="20170701T060000Z"/>
</C:comp-filter>"""], items=(6, 7, 8, 9))
        assert "/calendar.ics/event6.ics" in answer
        assert "/calendar.ics/event7.ics" in answer
        assert "/calendar.ics/event8.ics" in answer
        assert "/calendar.ics/event9.ics" not in answer
        answer = self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
        <C:time-range start="20170702T070000Z" end="20170704T060000Z"/>
</C:comp-filter>"""], items=(6, 7, 8, 9))
        assert "/calendar.ics/event6.ics" not in answer
        assert "/calendar.ics/event7.ics" not in answer
        assert "/calendar.ics/event8.ics" not in answer
        assert "/calendar.ics/event9.ics" not in answer
        answer = self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
        <C:time-range start="20170602T075959Z" end="20170602T080000Z"/>
</C:comp-filter>"""], items=(9,))
        assert "/calendar.ics/event9.ics" in answer
        answer = self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
        <C:time-range start="20170602T080000Z" end="20170603T083000Z"/>
</C:comp-filter>"""], items=(9,))
        assert "/calendar.ics/event9.ics" not in answer

    def test_time_range_filter_events_rrule(self) -> None:
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

    def test_time_range_filter_todos(self) -> None:
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

    def test_time_range_filter_events_valarm(self) -> None:
        """Report request with time-range filter on events having absolute VALARM."""
        answer = self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
    <C:comp-filter name="VEVENT">
        <C:comp-filter name="VALARM">
            <C:time-range start="20151010T030000Z" end="20151010T040000Z"/>
        </C:comp-filter>
    </C:comp-filter>
</C:comp-filter>"""], "valarm", items=[1, 2])
        assert "/calendar.ics/valarm1.ics" not in answer
        assert "/calendar.ics/valarm2.ics" in answer  # absolute date
        answer = self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
    <C:comp-filter name="VEVENT">
        <C:comp-filter name="VALARM">
            <C:time-range start="20151010T010000Z" end="20151010T020000Z"/>
        </C:comp-filter>
    </C:comp-filter>
</C:comp-filter>"""], "valarm", items=[1, 2])
        assert "/calendar.ics/valarm1.ics" not in answer
        assert "/calendar.ics/valarm2.ics" not in answer
        answer = self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
    <C:comp-filter name="VEVENT">
        <C:comp-filter name="VALARM">
            <C:time-range start="20151010T080000Z" end="20151010T090000Z"/>
        </C:comp-filter>
    </C:comp-filter>
</C:comp-filter>"""], "valarm", items=[1, 2])
        assert "/calendar.ics/valarm1.ics" not in answer
        assert "/calendar.ics/valarm2.ics" not in answer
        answer = self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
    <C:comp-filter name="VEVENT">
        <C:comp-filter name="VALARM">
            <C:time-range start="20151010T053000Z" end="20151010T055000Z"/>
        </C:comp-filter>
    </C:comp-filter>
</C:comp-filter>"""], "valarm", items=[1, 2])
        assert "/calendar.ics/valarm1.ics" in answer  # -15 min offset
        assert "/calendar.ics/valarm2.ics" not in answer

    def test_time_range_filter_todos_completed(self) -> None:
        answer = self._test_filter(["""\
<C:comp-filter name="VCALENDAR">
  <C:comp-filter name="VTODO">
    <C:prop-filter name="COMPLETED">
      <C:time-range start="20130918T000000Z" end="20130922T000000Z"/>
    </C:prop-filter>
  </C:comp-filter>
</C:comp-filter>"""], "todo", items=range(1, 9))
        assert "/calendar.ics/todo6.ics" in answer

    def test_time_range_filter_todos_rrule(self) -> None:
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

    def test_time_range_filter_journals(self) -> None:
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

    def test_time_range_filter_journals_rrule(self) -> None:
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

    def test_report_item(self) -> None:
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
        response = responses[event_path]
        assert isinstance(response, dict)
        status, prop = response["D:getetag"]
        assert status == 200 and prop.text

    def test_report_free_busy(self) -> None:
        """Test free busy report on a few items"""
        calendar_path = "/calendar.ics/"
        self.mkcalendar(calendar_path)
        for i in (1, 2, 10):
            filename = "event{}.ics".format(i)
            event = get_file_content(filename)
            self.put(posixpath.join(calendar_path, filename), event)
        code, responses = self.report(calendar_path, """\
<?xml version="1.0" encoding="utf-8" ?>
<C:free-busy-query xmlns:C="urn:ietf:params:xml:ns:caldav">
    <C:time-range start="20130901T140000Z" end="20130908T220000Z"/>
</C:free-busy-query>""", 200, is_xml=False)
        for response in responses.values():
            assert isinstance(response, vobject.base.Component)
        assert len(responses) == 1
        vcalendar = list(responses.values())[0]
        assert isinstance(vcalendar, vobject.base.Component)
        assert len(vcalendar.vfreebusy_list) == 3
        types = {}
        for vfb in vcalendar.vfreebusy_list:
            fbtype_val = vfb.fbtype.value
            if fbtype_val not in types:
                types[fbtype_val] = 0
            types[fbtype_val] += 1
        assert types == {'BUSY': 2, 'FREE': 1}

        # Test max_freebusy_occurrence limit
        self.configure({"reporting": {"max_freebusy_occurrence": 1}})
        code, responses = self.report(calendar_path, """\
<?xml version="1.0" encoding="utf-8" ?>
<C:free-busy-query xmlns:C="urn:ietf:params:xml:ns:caldav">
    <C:time-range start="20130901T140000Z" end="20130908T220000Z"/>
</C:free-busy-query>""", 400, is_xml=False)

    def _report_sync_token(
            self, calendar_path: str, sync_token: Optional[str] = None, **kwargs
            ) -> Tuple[str, RESPONSES]:
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
</sync-collection>""" % sync_token_xml, **kwargs)
        xml = DefusedET.fromstring(answer)
        if status in (403, 409):
            assert xml.tag == xmlutils.make_clark("D:error")
            assert sync_token and xml.find(
                xmlutils.make_clark("D:valid-sync-token")) is not None
            return "", {}
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

    def test_report_sync_collection_no_change(self) -> None:
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

    def test_report_sync_collection_add(self) -> None:
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

    def test_report_sync_collection_delete(self) -> None:
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

    def test_report_sync_collection_create_delete(self) -> None:
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

    def test_report_sync_collection_modify_undo(self) -> None:
        """Test sync-collection report with a modified and changed back item"""
        calendar_path = "/calendar.ics/"
        self.mkcalendar(calendar_path)
        event1 = get_file_content("event1.ics")
        event2 = get_file_content("event1_modified.ics")
        event_path = posixpath.join(calendar_path, "event.ics")
        self.put(event_path, event1)
        sync_token, responses = self._report_sync_token(calendar_path)
        assert len(responses) == 1 and responses[event_path] == 200
        self.put(event_path, event2, check=204)
        self.put(event_path, event1, check=204)
        sync_token, responses = self._report_sync_token(
            calendar_path, sync_token)
        if not self.full_sync_token_support and not sync_token:
            return
        assert len(responses) == 1 and responses[event_path] == 200

    def test_report_sync_collection_move(self) -> None:
        """Test sync-collection report a moved item"""
        calendar_path = "/calendar.ics/"
        self.mkcalendar(calendar_path)
        event = get_file_content("event1.ics")
        event1_path = posixpath.join(calendar_path, "event1.ics")
        event2_path = posixpath.join(calendar_path, "event2.ics")
        self.put(event1_path, event)
        sync_token, responses = self._report_sync_token(calendar_path)
        assert len(responses) == 1 and responses[event1_path] == 200
        self.request("MOVE", event1_path, check=201,
                     HTTP_DESTINATION="http://127.0.0.1/"+event2_path)
        sync_token, responses = self._report_sync_token(
            calendar_path, sync_token)
        if not self.full_sync_token_support and not sync_token:
            return
        assert len(responses) == 2 and (responses[event1_path] == 404 and
                                        responses[event2_path] == 200)

    def test_report_sync_collection_move_undo(self) -> None:
        """Test sync-collection report with a moved and moved back item"""
        calendar_path = "/calendar.ics/"
        self.mkcalendar(calendar_path)
        event = get_file_content("event1.ics")
        event1_path = posixpath.join(calendar_path, "event1.ics")
        event2_path = posixpath.join(calendar_path, "event2.ics")
        self.put(event1_path, event)
        sync_token, responses = self._report_sync_token(calendar_path)
        assert len(responses) == 1 and responses[event1_path] == 200
        self.request("MOVE", event1_path, check=201,
                     HTTP_DESTINATION="http://127.0.0.1/"+event2_path)
        self.request("MOVE", event2_path, check=201,
                     HTTP_DESTINATION="http://127.0.0.1/"+event1_path)
        sync_token, responses = self._report_sync_token(
            calendar_path, sync_token)
        if not self.full_sync_token_support and not sync_token:
            return
        assert len(responses) == 2 and (responses[event1_path] == 200 and
                                        responses[event2_path] == 404)

    def test_report_sync_collection_invalid_sync_token(self) -> None:
        """Test sync-collection report with an invalid sync token"""
        calendar_path = "/calendar.ics/"
        self.mkcalendar(calendar_path)
        sync_token, _ = self._report_sync_token(
            calendar_path, "http://radicale.org/ns/sync/INVALID")
        assert not sync_token

    def test_report_sync_collection_invalid_sync_token_with_user(self) -> None:
        """Test sync-collection report with an invalid sync token and user+host+useragent"""
        self.configure({"auth": {"type": "none"}})
        calendar_path = "/calendar.ics/"
        self.mkcalendar(calendar_path)
        sync_token, _ = self._report_sync_token(
            calendar_path, "http://radicale.org/ns/sync/INVALID", login="testuser:", remote_host="192.0.2.1", remote_useragent="Testclient/1.0")
        assert not sync_token

    def test_propfind_sync_token(self) -> None:
        """Retrieve the sync-token with a propfind request"""
        calendar_path = "/calendar.ics/"
        self.mkcalendar(calendar_path)
        propfind = get_file_content("allprop.xml")
        _, responses = self.propfind(calendar_path, propfind)
        response = responses[calendar_path]
        assert not isinstance(response, int)
        status, sync_token = response["D:sync-token"]
        assert status == 200 and sync_token.text
        event = get_file_content("event1.ics")
        event_path = posixpath.join(calendar_path, "event.ics")
        self.put(event_path, event)
        _, responses = self.propfind(calendar_path, propfind)
        response = responses[calendar_path]
        assert not isinstance(response, int)
        status, new_sync_token = response["D:sync-token"]
        assert status == 200 and new_sync_token.text
        assert sync_token.text != new_sync_token.text

    def test_propfind_same_as_sync_collection_sync_token(self) -> None:
        """Compare sync-token property with sync-collection sync-token"""
        calendar_path = "/calendar.ics/"
        self.mkcalendar(calendar_path)
        propfind = get_file_content("allprop.xml")
        _, responses = self.propfind(calendar_path, propfind)
        response = responses[calendar_path]
        assert not isinstance(response, int)
        status, sync_token = response["D:sync-token"]
        assert status == 200 and sync_token.text
        report_sync_token, _ = self._report_sync_token(calendar_path)
        assert sync_token.text == report_sync_token

    def test_calendar_getcontenttype(self) -> None:
        """Test report request on an item"""
        self.mkcalendar("/test/")
        for component in ("event", "todo", "journal"):
            event = get_file_content("%s1.ics" % component)
            status, _ = self.delete("/test/test.ics", check=None)
            assert status in (200, 404)
            self.put("/test/test.ics", event)
            _, responses = self.report("/test/", """\
<?xml version="1.0" encoding="utf-8" ?>
<C:calendar-query xmlns:C="urn:ietf:params:xml:ns:caldav">
    <D:prop xmlns:D="DAV:">
        <D:getcontenttype />
    </D:prop>
</C:calendar-query>""")
            assert len(responses) == 1
            response = responses["/test/test.ics"]
            assert not isinstance(response, int) and len(response) == 1
            status, prop = response["D:getcontenttype"]
            assert status == 200 and prop.text == (
                "text/calendar;charset=utf-8;component=V%s" %
                component.upper())

    def test_addressbook_getcontenttype(self) -> None:
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
        assert len(responses) == 1
        response = responses["/test/test.vcf"]
        assert not isinstance(response, int) and len(response) == 1
        status, prop = response["D:getcontenttype"]
        assert status == 200 and prop.text == "text/vcard;charset=utf-8"

    def test_authorization(self) -> None:
        self.configure({"auth": {"type": "none"}})
        _, responses = self.propfind("/", """\
<?xml version="1.0" encoding="utf-8"?>
<propfind xmlns="DAV:">
    <prop>
        <current-user-principal />
    </prop>
</propfind>""", login="user:")
        response = responses["/"]
        assert not isinstance(response, int) and len(response) == 1
        status, prop = response["D:current-user-principal"]
        assert status == 200 and len(prop) == 1
        element = prop.find(xmlutils.make_clark("D:href"))
        assert element is not None and element.text == "/user/"

    def test_authentication(self) -> None:
        """Test if server sends authentication request."""
        self.configure({"auth": {"type": "htpasswd",
                                 "htpasswd_filename": os.devnull,
                                 "htpasswd_encryption": "plain"},
                        "rights": {"type": "owner_only"}})
        status, headers, _ = self.request("MKCOL", "/user/")
        assert status in (401, 403)
        assert headers.get("WWW-Authenticate")

    def test_principal_collection_creation(self) -> None:
        """Verify existence of the principal collection."""
        self.configure({"auth": {"type": "none"}})
        self.propfind("/user/", login="user:")

    def test_authentication_current_user_principal_hack(self) -> None:
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

    def test_existence_of_root_collections(self) -> None:
        """Verify that the root collection always exists."""
        # Use PROPFIND because GET returns message
        self.propfind("/")
        # it should still exist after deletion
        self.delete("/")
        self.propfind("/")

    def test_well_known(self) -> None:
        for path in ["/.well-known/caldav", "/.well-known/carddav"]:
            for path in [path, "/foo" + path]:
                _, headers, _ = self.request("GET", path, check=301)
                assert headers.get("Location") == "/"

    def test_well_known_script_name(self) -> None:
        for path in ["/.well-known/caldav", "/.well-known/carddav"]:
            for path in [path, "/foo" + path]:
                _, headers, _ = self.request(
                    "GET", path, check=301,  SCRIPT_NAME="/radicale")
                assert headers.get("Location") == "/radicale/"

    def test_well_known_not_found(self) -> None:
        for path in ["/.well-known", "/.well-known/", "/.well-known/foo"]:
            for path in [path, "/foo" + path]:
                self.get(path, check=404)

    def test_custom_headers(self) -> None:
        self.configure({"headers": {"test": "123"}})
        # Test if header is set on success
        _, headers, _ = self.request("OPTIONS", "/", check=200)
        assert headers.get("test") == "123"
        # Test if header is set on failure
        _, headers, _ = self.request("GET", "/.well-known/foo", check=404)
        assert headers.get("test") == "123"

    def test_timezone_seconds(self) -> None:
        """Verify that timezones with minutes and seconds work."""
        self.mkcalendar("/calendar.ics/")
        event = get_file_content("event_timezone_seconds.ics")
        self.put("/calendar.ics/event.ics", event)
