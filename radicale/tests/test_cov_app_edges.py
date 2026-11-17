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

"""Outcome tests for collection upload notifications and permission checks."""

import os

from radicale.app.base import Access
from radicale.tests import BaseTest


def _calendar(uid, summary):
    return (
        "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\n"
        "UID:%s\r\nSUMMARY:%s\r\n"
        "DTSTART:20130901T160000Z\r\nDTEND:20130901T170000Z\r\n"
        "END:VEVENT\r\nEND:VCALENDAR\r\n" % (uid, summary))


def _grant(test, permissions):
    path = os.path.join(test.colpath, "rights")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(
            "[all]\nuser: .*\ncollection: .*\npermissions: %s\n" % permissions)
    test.configure({
        "auth": {"type": "none", "delay": "0"},
        "rights": {"type": "from_file", "file": path},
        "hook": {"type": "radicale.tests.test_cov_app_edges"},
    })


class Hook:
    """Recording hook loaded as radicale.tests.test_cov_app_edges."""

    events: list = []

    def __init__(self, configuration):
        self.configuration = configuration

    @property
    def enabled(self):
        return True

    def notify(self, notification_item):
        Hook.events.append(notification_item)


class TestAppEdges(BaseTest):

    def setup_method(self):
        super().setup_method()
        Hook.events = []

    def test_collection_upload_notifies_each_new_event(self):
        """Uploading a calendar tells the hook about each event as new.

        One event and two events are the collection sizes. Replacing the
        calendar drops the previous summary. A read-only grant then rejects
        another upload and leaves the stored events in place.
        """
        _grant(self, "RrWw")
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

        _grant(self, "Rr")
        status, headers, answer = self.request(
            "PUT", "/team.ics/", _calendar("blocked", "Blocked"), check=None)
        assert status == 401 and answer
        assert "WWW-Authenticate" in headers
        kept = self.get("/team.ics/")[1]
        assert "SUMMARY:Next" in kept and "SUMMARY:Extra" in kept
        assert "SUMMARY:Blocked" not in kept

    def test_permission_check_rejects_letters_outside_the_item_set(self):
        """Only the item permission letters can be checked.

        Read and write are granted. A collection-level letter and an unknown
        letter are rejected. The empty string is not one of those letters, and
        it grants nothing. Read-only rights still answer a read check and
        refuse a write check.
        """
        _grant(self, "RrWw")
        access = Access(self.application._rights, "", set(), "/team.ics/")
        assert access.check("r") is True
        assert access.check("w") is True
        for letter in ("R", "x"):
            try:
                access.check(letter)
            except ValueError as exc:
                assert "Invalid permission argument" in str(exc)
            else:
                raise AssertionError(
                    "check(%r) returned without raising" % letter)
        # The empty string is a substring of every permission set, so it is
        # not rejected as unknown. It still grants nothing.
        assert access.check("") is False
        _grant(self, "R")
        read_only = Access(self.application._rights, "", set(), "/team.ics/")
        assert read_only.check("r") is True
        assert read_only.check("w") is False
