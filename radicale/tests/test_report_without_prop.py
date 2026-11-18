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

"""A calendar-query with no DAV:prop still lists each match."""

import os

from radicale.tests import BaseTest

EVENT = (
    "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Test//EN\r\n"
    "BEGIN:VEVENT\r\nUID:kept\r\nDTSTAMP:20130101T000000Z\r\n"
    "DTSTART:20130601T100000Z\r\nDTEND:20130601T110000Z\r\n"
    "SUMMARY:InsideDay\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n")

BARE = (
    "<?xml version='1.0' encoding='utf-8'?>"
    "<C:calendar-query xmlns:C='urn:ietf:params:xml:ns:caldav'>"
    "<C:filter><C:comp-filter name='VCALENDAR'>"
    "<C:comp-filter name='VEVENT'/></C:comp-filter></C:filter>"
    "</C:calendar-query>")


class TestReportWithoutProp(BaseTest):

    def setup_method(self):
        super().setup_method()
        path = os.path.join(self.colpath, "rights")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("[all]\nuser: .*\ncollection: .*\npermissions: RrWw\n")
        self.configure({
            "auth": {"type": "none", "delay": "0"},
            "rights": {"type": "from_file", "file": path},
            "server": {"delay_on_error": "0"},
        })

    def test_match_is_listed_when_prop_is_absent(self):
        self.mkcalendar("/calendar.ics/")
        self.put("/calendar.ics/kept.ics", EVENT)
        status, _, body = self.request(
            "REPORT", "/calendar.ics/", BARE, check=None)
        assert status == 207
        assert "multistatus" in body
        assert "kept.ics" in body
        assert "response" in body
