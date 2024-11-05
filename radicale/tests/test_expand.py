# This file is part of Radicale - CalDAV and CardDAV server
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
Radicale tests with expand requests.

"""

import os
import posixpath
from typing import Any, Callable, ClassVar, Iterable, List, Optional, Tuple

import defusedxml.ElementTree as DefusedET
import vobject

from radicale import storage, xmlutils
from radicale.tests import RESPONSES, BaseTest
from radicale.tests.helpers import get_file_content


class TestExpandRequests(BaseTest):
    """Tests with expand requests."""

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

    def test_report_with_expand_property(self) -> None:
        """Test report with expand property"""
        self.put("/calendar.ics/", get_file_content("event_daily_rrule.ics"))
        req_body_without_expand = \
            """<?xml version="1.0" encoding="utf-8" ?>
            <C:calendar-query xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
                <D:prop>
                    <C:calendar-data>
                    </C:calendar-data>
                </D:prop>
                <C:filter>
                    <C:comp-filter name="VCALENDAR">
                        <C:comp-filter name="VEVENT">
                            <C:time-range start="20060103T000000Z" end="20060105T000000Z"/>
                        </C:comp-filter>
                    </C:comp-filter>
                </C:filter>
            </C:calendar-query>
            """
        _, responses = self.report("/calendar.ics/", req_body_without_expand)
        assert len(responses) == 1

        response_without_expand = responses['/calendar.ics/event_daily_rrule.ics']
        assert not isinstance(response_without_expand, int)
        status, element = response_without_expand["C:calendar-data"]

        assert status == 200 and element.text

        assert "RRULE" in element.text
        assert "BEGIN:VTIMEZONE" in element.text
        assert "RECURRENCE-ID" not in element.text

        uids: List[str] = []
        for line in element.text.split("\n"):
            if line.startswith("UID:"):
                uid = line[len("UID:"):]
                assert uid == "event_daily_rrule"
                uids.append(uid)

        assert len(uids) == 1

        req_body_with_expand = \
            """<?xml version="1.0" encoding="utf-8" ?>
            <C:calendar-query xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
                <D:prop>
                    <C:calendar-data>
                        <C:expand start="20060103T000000Z" end="20060105T000000Z"/>
                    </C:calendar-data>
                </D:prop>
                <C:filter>
                    <C:comp-filter name="VCALENDAR">
                        <C:comp-filter name="VEVENT">
                            <C:time-range start="20060103T000000Z" end="20060105T000000Z"/>
                        </C:comp-filter>
                    </C:comp-filter>
                </C:filter>
            </C:calendar-query>
            """

        _, responses = self.report("/calendar.ics/", req_body_with_expand)

        assert len(responses) == 1

        response_with_expand = responses['/calendar.ics/event_daily_rrule.ics']
        assert not isinstance(response_with_expand, int)
        status, element = response_with_expand["C:calendar-data"]

        assert status == 200 and element.text
        assert "RRULE" not in element.text
        assert "BEGIN:VTIMEZONE" not in element.text

        uids = []
        recurrence_ids = []
        for line in element.text.split("\n"):
            if line.startswith("UID:"):
                assert line == "UID:event_daily_rrule"
                uids.append(line)

            if line.startswith("RECURRENCE-ID:"):
                assert line in ["RECURRENCE-ID:20060103T170000Z", "RECURRENCE-ID:20060104T170000Z"]
                recurrence_ids.append(line)

            if line.startswith("DTSTART:"):
                assert line in ["DTSTART:20060103T170000Z", "DTSTART:20060104T170000Z"]

        assert len(uids) == 2
        assert len(set(recurrence_ids)) == 2

    def test_report_with_expand_property_all_day_event(self) -> None:
        """Test report with expand property"""
        self.put("/calendar.ics/", get_file_content("event_full_day_rrule.ics"))
        req_body_without_expand = \
            """<?xml version="1.0" encoding="utf-8" ?>
            <C:calendar-query xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
                <D:prop>
                    <C:calendar-data>
                    </C:calendar-data>
                </D:prop>
                <C:filter>
                    <C:comp-filter name="VCALENDAR">
                        <C:comp-filter name="VEVENT">
                            <C:time-range start="20060103T000000Z" end="20060105T000000Z"/>
                        </C:comp-filter>
                    </C:comp-filter>
                </C:filter>
            </C:calendar-query>
            """
        _, responses = self.report("/calendar.ics/", req_body_without_expand)
        assert len(responses) == 1

        response_without_expand = responses['/calendar.ics/event_full_day_rrule.ics']
        assert not isinstance(response_without_expand, int)
        status, element = response_without_expand["C:calendar-data"]

        assert status == 200 and element.text

        assert "RRULE" in element.text
        assert "RECURRENCE-ID" not in element.text

        uids: List[str] = []
        for line in element.text.split("\n"):
            if line.startswith("UID:"):
                uid = line[len("UID:"):]
                assert uid == "event_full_day_rrule"
                uids.append(uid)

        assert len(uids) == 1

        req_body_with_expand = \
            """<?xml version="1.0" encoding="utf-8" ?>
            <C:calendar-query xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
                <D:prop>
                    <C:calendar-data>
                        <C:expand start="20060103T000000Z" end="20060105T000000Z"/>
                    </C:calendar-data>
                </D:prop>
                <C:filter>
                    <C:comp-filter name="VCALENDAR">
                        <C:comp-filter name="VEVENT">
                            <C:time-range start="20060103T000000Z" end="20060105T000000Z"/>
                        </C:comp-filter>
                    </C:comp-filter>
                </C:filter>
            </C:calendar-query>
            """

        _, responses = self.report("/calendar.ics/", req_body_with_expand)

        assert len(responses) == 1

        response_with_expand = responses['/calendar.ics/event_full_day_rrule.ics']
        assert not isinstance(response_with_expand, int)
        status, element = response_with_expand["C:calendar-data"]

        assert status == 200 and element.text
        assert "RRULE" not in element.text
        assert "BEGIN:VTIMEZONE" not in element.text

        uids = []
        recurrence_ids = []
        for line in element.text.split("\n"):
            if line.startswith("UID:"):
                assert line == "UID:event_full_day_rrule"
                uids.append(line)

            if line.startswith("RECURRENCE-ID:"):
                assert line in ["RECURRENCE-ID:20060103", "RECURRENCE-ID:20060104", "RECURRENCE-ID:20060105"]
                recurrence_ids.append(line)

            if line.startswith("DTSTART:"):
                assert line in ["DTSTART:20060103", "DTSTART:20060104", "DTSTART:20060105"]

            if line.startswith("DTEND:"):
                assert line in ["DTEND:20060104", "DTEND:20060105", "DTEND:20060106"]

        assert len(uids) == 3
        assert len(set(recurrence_ids)) == 3

    def test_report_with_expand_property_overridden(self) -> None:
        """Test report with expand property"""
        self.put("/calendar.ics/", get_file_content("event_daily_rrule_overridden.ics"))
        req_body_without_expand = \
            """<?xml version="1.0" encoding="utf-8" ?>
            <C:calendar-query xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
                <D:prop>
                    <C:calendar-data>
                    </C:calendar-data>
                </D:prop>
                <C:filter>
                    <C:comp-filter name="VCALENDAR">
                        <C:comp-filter name="VEVENT">
                            <C:time-range start="20060103T000000Z" end="20060105T000000Z"/>
                        </C:comp-filter>
                    </C:comp-filter>
                </C:filter>
            </C:calendar-query>
            """
        _, responses = self.report("/calendar.ics/", req_body_without_expand)
        assert len(responses) == 1

        response_without_expand = responses['/calendar.ics/event_daily_rrule_overridden.ics']
        assert not isinstance(response_without_expand, int)
        status, element = response_without_expand["C:calendar-data"]

        assert status == 200 and element.text

        assert "RRULE" in element.text
        assert "BEGIN:VTIMEZONE" in element.text

        uids: List[str] = []
        for line in element.text.split("\n"):
            if line.startswith("UID:"):
                uid = line[len("UID:"):]
                assert uid == "event_daily_rrule_overridden"
                uids.append(uid)

        assert len(uids) == 2

        req_body_with_expand = \
            """<?xml version="1.0" encoding="utf-8" ?>
            <C:calendar-query xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
                <D:prop>
                    <C:calendar-data>
                        <C:expand start="20060103T000000Z" end="20060105T000000Z"/>
                    </C:calendar-data>
                </D:prop>
                <C:filter>
                    <C:comp-filter name="VCALENDAR">
                        <C:comp-filter name="VEVENT">
                            <C:time-range start="20060103T000000Z" end="20060105T000000Z"/>
                        </C:comp-filter>
                    </C:comp-filter>
                </C:filter>
            </C:calendar-query>
            """

        _, responses = self.report("/calendar.ics/", req_body_with_expand)

        assert len(responses) == 1

        response_with_expand = responses['/calendar.ics/event_daily_rrule_overridden.ics']
        assert not isinstance(response_with_expand, int)
        status, element = response_with_expand["C:calendar-data"]

        assert status == 200 and element.text
        assert "RRULE" not in element.text
        assert "BEGIN:VTIMEZONE" not in element.text

        uids = []
        recurrence_ids = []
        for line in element.text.split("\n"):
            if line.startswith("UID:"):
                assert line == "UID:event_daily_rrule_overridden"
                uids.append(line)

            if line.startswith("RECURRENCE-ID:"):
                assert line in ["RECURRENCE-ID:20060103T170000Z", "RECURRENCE-ID:20060104T170000Z"]
                recurrence_ids.append(line)

            if line.startswith("DTSTART:"):
                assert line in ["DTSTART:20060103T170000Z", "DTSTART:20060104T190000Z"]

        assert len(uids) == 2
        assert len(set(recurrence_ids)) == 2
