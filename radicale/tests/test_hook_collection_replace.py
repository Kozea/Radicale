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

"""A whole-collection PUT reports replaced items by the stored href."""

import json
import os

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


class Hook:
    """Recording hook loaded as radicale.tests.test_hook_collection_replace."""

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


class TestWholeCollectionReplace(BaseTest):

    def setup_method(self):
        super().setup_method()
        _grant(self)
        Hook.events = []

    def _collection(self, path):
        with self.application._storage.acquire_lock("r", ""):
            return next(self.application._storage.discover(path))

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
        self.configure({"hook": {"type": "radicale.tests.test_hook_collection_replace"}})

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
