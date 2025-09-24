# This file is part of Radicale - CalDAV and CardDAV server
# Copyright © 2012-2017 Guillaume Ayoub
# Copyright © 2017-2019 Unrud <unrud@outlook.com>
# Copyright © 2024 Pieter Hijma <pieterhijma@users.noreply.github.com>
# Copyright © 2025 David Greaves <david@dgreaves.com>
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
from typing import ClassVar, List, Optional
from xml.etree import ElementTree

from radicale.log import logger
from radicale.tests import BaseTest
from radicale.tests.helpers import get_file_content

ONLY_DATES = True
CONTAINS_TIMES = False


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

    def _req_without_expand(self,
                            expected_uid: str,
                            start: str,
                            end: str,
                            ) -> str:
        self.put("/calendar.ics/", get_file_content(f"{expected_uid}.ics"))
        return \
            f"""<?xml version="1.0" encoding="utf-8" ?>
            <C:calendar-query xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
                <D:prop>
                    <C:calendar-data>
                    </C:calendar-data>
                </D:prop>
                <C:filter>
                    <C:comp-filter name="VCALENDAR">
                        <C:comp-filter name="VEVENT">
                            <C:time-range start="{start}" end="{end}"/>
                        </C:comp-filter>
                    </C:comp-filter>
                </C:filter>
            </C:calendar-query>
            """

    def _req_with_expand(self,
                         expected_uid: str,
                         start: str,
                         end: str,
                         ) -> str:
        self.put("/calendar.ics/", get_file_content(f"{expected_uid}.ics"))
        return \
            f"""<?xml version="1.0" encoding="utf-8" ?>
            <C:calendar-query xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
                <D:prop>
                    <C:calendar-data>
                        <C:expand start="{start}" end="{end}"/>
                    </C:calendar-data>
                </D:prop>
                <C:filter>
                    <C:comp-filter name="VCALENDAR">
                        <C:comp-filter name="VEVENT">
                            <C:time-range start="{start}" end="{end}"/>
                        </C:comp-filter>
                    </C:comp-filter>
                </C:filter>
            </C:calendar-query>
            """

    def _test_expand(self,
                     expected_uid: str,
                     start: str,
                     end: str,
                     expected_recurrence_ids: List[str],
                     expected_start_times: List[str],
                     expected_end_times: List[str],
                     only_dates: bool,
                     nr_uids: int) -> None:
        _, responses = self.report("/calendar.ics/",
                                   self._req_without_expand(expected_uid, start, end))
        assert len(responses) == 1
        response_without_expand = responses[f'/calendar.ics/{expected_uid}.ics']
        assert isinstance(response_without_expand, dict)
        status, element = response_without_expand["C:calendar-data"]

        assert status == 200 and element.text

        assert "RRULE" in element.text
        if not only_dates:
            assert "BEGIN:VTIMEZONE" in element.text
        if nr_uids == 1:
            assert "RECURRENCE-ID" not in element.text

        uids: List[str] = []
        for line in element.text.split("\n"):
            if line.startswith("UID:"):
                uid = line[len("UID:"):]
                assert uid == expected_uid
                uids.append(uid)

        assert len(uids) == nr_uids

        _, responses = self.report("/calendar.ics/",
                                   self._req_with_expand(expected_uid, start, end))

        assert len(responses) == 1

        response_with_expand = responses[f'/calendar.ics/{expected_uid}.ics']
        assert isinstance(response_with_expand, dict)
        status, element = response_with_expand["C:calendar-data"]

        logger.debug("lbt: element is %s",
                     ElementTree.tostring(element, encoding='unicode'))
        assert status == 200 and element.text
        assert "RRULE" not in element.text
        assert "BEGIN:VTIMEZONE" not in element.text

        uids = []
        recurrence_ids = []
        for line in element.text.split("\n"):
            if line.startswith("UID:"):
                assert line == f"UID:{expected_uid}"
                uids.append(line)

            if line.startswith("RECURRENCE-ID:"):
                assert line in expected_recurrence_ids
                recurrence_ids.append(line)

            if line.startswith("DTSTART:"):
                assert line in expected_start_times

            if line.startswith("DTEND:"):
                assert line in expected_end_times

        assert len(uids) == len(expected_recurrence_ids)
        assert len(set(recurrence_ids)) == len(expected_recurrence_ids)

    def _test_expand_max(self,
                         expected_uid: str,
                         start: str,
                         end: str,
                         check: Optional[int] = None) -> None:
        _, responses = self.report("/calendar.ics/",
                                   self._req_without_expand(expected_uid, start, end))
        assert len(responses) == 1
        response_without_expand = responses[f'/calendar.ics/{expected_uid}.ics']
        assert isinstance(response_without_expand, dict)
        status, element = response_without_expand["C:calendar-data"]

        assert status == 200 and element.text

        assert "RRULE" in element.text

        status, _, _ = self.request(
            "REPORT", "/calendar.ics/",
            self._req_with_expand(expected_uid, start, end),
            check=check)

        assert status == 400

    def test_report_with_expand_property(self) -> None:
        """Test report with expand property"""
        self._test_expand(
            "event_daily_rrule",
            "20060103T000000Z",
            "20060105T000000Z",
            ["RECURRENCE-ID:20060103T170000Z", "RECURRENCE-ID:20060104T170000Z"],
            ["DTSTART:20060103T170000Z", "DTSTART:20060104T170000Z"],
            [],
            CONTAINS_TIMES,
            1
        )

    def test_report_with_expand_property_start_inside(self) -> None:
        """Test report with expand property start inside"""
        self._test_expand(
            "event_daily_rrule",
            "20060103T171500Z",
            "20060105T000000Z",
            ["RECURRENCE-ID:20060103T170000Z", "RECURRENCE-ID:20060104T170000Z"],
            ["DTSTART:20060103T170000Z", "DTSTART:20060104T170000Z"],
            [],
            CONTAINS_TIMES,
            1
        )

    def test_report_with_expand_property_just_inside(self) -> None:
        """Test report with expand property start and end inside event"""
        self._test_expand(
            "event_daily_rrule",
            "20060103T171500Z",
            "20060103T171501Z",
            ["RECURRENCE-ID:20060103T170000Z"],
            ["DTSTART:20060103T170000Z"],
            [],
            CONTAINS_TIMES,
            1
        )

    def test_report_with_expand_property_issue1812(self) -> None:
        """Test report with expand property for issue 1812"""
        self._test_expand(
            "event_issue1812",
            "20250127T183000Z",
            "20250127T183001Z",
            ["RECURRENCE-ID:20250127T180000Z"],
            ["DTSTART:20250127T180000Z"],
            ["DTEND:20250127T233000Z"],
            CONTAINS_TIMES,
            11
        )

    def test_report_with_expand_property_issue1812_DS(self) -> None:
        """Test report with expand property for issue 1812 - DS active"""
        self._test_expand(
            "event_issue1812",
            "20250627T183000Z",
            "20250627T183001Z",
            ["RECURRENCE-ID:20250627T170000Z"],
            ["DTSTART:20250627T170000Z"],
            ["DTEND:20250627T223000Z"],
            CONTAINS_TIMES,
            11
        )

    def test_report_with_expand_property_all_day_event(self) -> None:
        """Test report with expand property for all day events"""
        self._test_expand(
            "event_full_day_rrule",
            "20060103T000000Z",
            "20060105T000000Z",
            ["RECURRENCE-ID:20060103", "RECURRENCE-ID:20060104", "RECURRENCE-ID:20060105"],
            ["DTSTART:20060103", "DTSTART:20060104", "DTSTART:20060105"],
            ["DTEND:20060104", "DTEND:20060105", "DTEND:20060106"],
            ONLY_DATES,
            1
        )

    def test_report_with_expand_property_overridden(self) -> None:
        """Test report with expand property with overridden events"""
        self._test_expand(
            "event_daily_rrule_overridden",
            "20060103T000000Z",
            "20060105T000000Z",
            ["RECURRENCE-ID:20060103T170000Z", "RECURRENCE-ID:20060104T170000Z"],
            ["DTSTART:20060103T170000Z", "DTSTART:20060104T190000Z"],
            [],
            CONTAINS_TIMES,
            2
        )

    def test_report_with_expand_property_timezone(self):
        self._test_expand(
            "event_weekly_rrule",
            "20060320T000000Z",
            "20060414T000000Z",
            [
                "RECURRENCE-ID:20060321T200000Z",
                "RECURRENCE-ID:20060328T200000Z",
                "RECURRENCE-ID:20060404T190000Z",
                "RECURRENCE-ID:20060411T190000Z",
            ],
            [
                "DTSTART:20060321T200000Z",
                "DTSTART:20060328T200000Z",
                "DTSTART:20060404T190000Z",
                "DTSTART:20060411T190000Z",
            ],
            [],
            CONTAINS_TIMES,
            1
        )

    def test_report_with_expand_property_max_occur(self) -> None:
        """Test report with expand property too many vevents"""
        self.configure({"reporting": {"max_freebusy_occurrence": 100}})
        self._test_expand_max(
            "event_daily_rrule_forever",
            "20060103T000000Z",
            "20060501T000000Z",
            check=400
        )

    def test_report_with_max_occur(self) -> None:
        """Test report with too many vevents"""
        self.configure({"reporting": {"max_freebusy_occurrence": 10}})

        uid = "event_multiple_too_many"
        start = "20130901T000000Z"
        end = "20130902T000000Z"
        check = 400

        status, responses = self.report("/calendar.ics/",
                                        self._req_without_expand(uid, start, end),
                                        check=check)
        assert len(responses) == 0
        assert status == check

    def test_report_vcalendar_all_components(self) -> None:
        """Test calendar-query with comp-filter VCALENDAR, returns all components."""
        self.mkcalendar("/test/")
        self.put("/test/calendar.ics", get_file_content("event_daily_rrule.ics"))
        self.put("/test/todo.ics", get_file_content("todo1.ics"))

        request = """
        <C:calendar-query xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
            <D:prop>
                <C:calendar-data/>
            </D:prop>
            <C:filter>
                <C:comp-filter name="VCALENDAR"/>
            </C:filter>
        </C:calendar-query>
        """
        status, responses = self.report("/test", request)
        assert status == 207
        assert len(responses) == 2
        assert "/test/calendar.ics" in responses
        assert "/test/todo.ics" in responses

    def test_report_vevent_only(self) -> None:
        """Test calendar-query with comp-filter VEVENT, returns only VEVENT."""
        self.mkcalendar("/test/")
        self.put("/test/calendar.ics", get_file_content("event_daily_rrule.ics"))
        self.put("/test/todo.ics", get_file_content("todo1.ics"))

        start = "20060101T000000Z"
        end = "20060104T000000Z"

        request = f"""
        <C:calendar-query xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
            <D:prop>
                <C:calendar-data>
                    <C:expand start="{start}" end="{end}"/>
                </C:calendar-data>
            </D:prop>
            <C:filter>
                <C:comp-filter name="VCALENDAR">
                    <C:comp-filter name="VEVENT">
                        <C:time-range start="{start}" end="{end}"/>
                    </C:comp-filter>
                </C:comp-filter>
            </C:filter>
        </C:calendar-query>
        """
        status, responses = self.report("/test", request)
        assert status == 207
        assert len(responses) == 1
        assert "/test/calendar.ics" in responses
        vevent_response = responses["/test/calendar.ics"]
        assert type(vevent_response) is dict
        status, element = vevent_response["C:calendar-data"]
        assert status == 200 and element.text
        assert "BEGIN:VEVENT" in element.text
        assert "UID:" in element.text
        assert "BEGIN:VTODO" not in element.text

    def test_report_time_range_no_vevent(self) -> None:
        """Test calendar-query with time-range filter, no matching VEVENT."""
        self.mkcalendar("/test/")
        self.put("/test/calendar.ics/", get_file_content("event_daily_rrule.ics"))

        request = """
        <C:calendar-query xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
            <D:prop>
                <C:calendar-data>
                    <C:expand start="20000101T000000Z" end="20000105T000000Z"/>
                </C:calendar-data>
            </D:prop>
            <C:filter>
                <C:comp-filter name="VCALENDAR">
                    <C:comp-filter name="VEVENT">
                        <C:time-range start="20000101T000000Z" end="20000105T000000Z"/>
                    </C:comp-filter>
                </C:comp-filter>
            </C:filter>
        </C:calendar-query>
        """
        status, responses = self.report("/test", request)
        assert status == 207
        assert len(responses) == 0

    def test_report_time_range_one_vevent(self) -> None:
        """Test calendar-query with time-range filter, matches one VEVENT."""
        self.mkcalendar("/test/")
        self.put("/test/calendar1.ics/", get_file_content("event_daily_rrule.ics"))
        self.put("/test/calendar2.ics/", get_file_content("event1.ics"))

        start = "20060101T000000Z"
        end = "20060104T000000Z"

        request = f"""
        <C:calendar-query xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
            <D:prop>
                <C:calendar-data>
                    <C:expand start="{start}" end="{end}"/>
                </C:calendar-data>
            </D:prop>
            <C:filter>
                <C:comp-filter name="VCALENDAR">
                    <C:comp-filter name="VEVENT">
                        <C:time-range start="{start}" end="{end}"/>
                    </C:comp-filter>
                </C:comp-filter>
            </C:filter>
        </C:calendar-query>
        """
        status, responses = self.report("/test", request)
        assert status == 207
        assert len(responses) == 1
        response = responses["/test/calendar1.ics"]
        assert type(response) is dict
        status, element = response["C:calendar-data"]
        assert status == 200 and element.text
        assert "BEGIN:VEVENT" in element.text
        assert "RECURRENCE-ID:20060103T170000Z" in element.text
        assert "DTSTART:20060103T170000Z" in element.text

    def test_expand_report_for_recurring_and_non_recurring_events(self) -> None:
        """Test calendar-query with time-range filter, matches one VEVENT."""
        self.mkcalendar("/test/")
        self.put("/test/event.ics/", get_file_content("event_issue1812_2.ics"))
        self.put("/test/event2.ics/", get_file_content("event_issue1812_3.ics"))

        request = """
            <c:calendar-query xmlns:c="urn:ietf:params:xml:ns:caldav" xmlns:d="DAV:">
            <d:prop>
                <d:getetag/>
                <c:calendar-data>
                    <c:expand start="20250629T220000Z" end="20250803T220000Z"/>
                </c:calendar-data>
            </d:prop>
            <c:filter>
                <c:comp-filter name="VCALENDAR">
                    <c:comp-filter name="VEVENT">
                        <c:time-range start="20250629T220000Z" end="20250803T220000Z"/>
                    </c:comp-filter>
                </c:comp-filter>
            </c:filter>
            </c:calendar-query>
        """
        status, responses = self.report("/test", request)
        assert status == 207
        assert len(responses) == 2
        assert isinstance(responses, dict)
        assert "/test/event.ics" in responses
        assert "/test/event2.ics" in responses
        assert isinstance(responses["/test/event.ics"], dict)
        assert isinstance(responses["/test/event2.ics"], dict)

        assert "C:calendar-data" in responses["/test/event.ics"]
        status, event1_calendar_data = responses["/test/event.ics"]["C:calendar-data"]
        assert event1_calendar_data.text
        assert "UID:a07cfa8b-0ce6-4956-800d-c0bfe1f0730a" in event1_calendar_data.text
        assert "RECURRENCE-ID:20250716" in event1_calendar_data.text
        assert "RECURRENCE-ID:20250723" in event1_calendar_data.text
        assert "RECURRENCE-ID:20250730" in event1_calendar_data.text

        assert "C:calendar-data" in responses["/test/event2.ics"]
        status, event2_calendar_data = responses["/test/event2.ics"]["C:calendar-data"]
        assert event2_calendar_data.text
        assert "UID:c6be8b2c-3d72-453c-b698-4f25cdf1569e" in event2_calendar_data.text

    def test_report_getetag_expand_filter(self) -> None:
        """Test getetag with time-range filter and expand (example from #1880)."""
        self.mkcalendar("/test/")
        self.put("/test/event_issue1880_1.ics", get_file_content("event_issue1880_1.ics"))
        self.put("/test/event_issue1880_2.ics", get_file_content("event_issue1880_2.ics"))

        request = """
        <C:calendar-query xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
            <D:prop>
                <D:getetag>
				    <C:expand start="20250921T220000Z" end="20250928T220000Z"/>
                </D:getetag>
            </D:prop>
            <C:filter>
                <C:comp-filter name="VCALENDAR">
                    <C:comp-filter name="VEVENT">
                        <C:time-range start="20250921T220000Z" end="20250928T220000Z"/>
                    </C:comp-filter>
                </C:comp-filter>
            </C:filter>
        </C:calendar-query>
        """
        status, responses = self.report("/test", request)
        assert status == 207
        assert len(responses) == 2
        assert "D:getetag" in responses["/test/event_issue1880_1.ics"]
        assert "D:getetag" in responses["/test/event_issue1880_2.ics"]

    def test_report_getetag_expand_filter_positive1(self) -> None:
        """Test getetag with time-range filter and expand (not applicable), should return as matching filter range (example from #1812)."""
        self.mkcalendar("/test/")
        self.put("/test/event_issue1812_getetag.ics", get_file_content("event_issue1812_getetag.ics"))

        request = """
        <C:calendar-query xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
            <D:prop>
                <D:getetag>
                    <C:expand start="20250706T220000Z" end="20250713T220000Z" />
                </D:getetag>
            </D:prop>
            <C:filter>
                <C:comp-filter name="VCALENDAR">
                    <C:comp-filter name="VEVENT">
                        <C:time-range start="20250716T220000Z" end="20250717T220000Z" />
                    </C:comp-filter>
                </C:comp-filter>
            </C:filter>
        </C:calendar-query>
        """
        status, responses = self.report("/test", request)
        assert status == 207
        assert len(responses) == 1
        assert "D:getetag" in responses["/test/event_issue1812_getetag.ics"]

    def test_report_getetag_expand_filter_positive2(self) -> None:
        """Test getetag with time-range filter and expand, should return as matching filter range (example from #1812)."""
        self.mkcalendar("/test/")
        self.put("/test/event_issue1812.ics", get_file_content("event_issue1812.ics"))

        request = """
        <C:calendar-query xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
            <D:prop>
                <D:getetag>
                   <C:expand start="20250706T220000Z" end="20250730T220000Z" />
                </D:getetag>
            </D:prop>
            <C:filter>
                <C:comp-filter name="VCALENDAR">
                    <C:comp-filter name="VEVENT">
                        <C:time-range start="20250716T220000Z" end="20250723T220000Z" />
                    </C:comp-filter>
                </C:comp-filter>
            </C:filter>
        </C:calendar-query>
        """
        status, responses = self.report("/test", request)
        assert status == 207
        assert len(responses) == 1
        assert "D:getetag" in responses["/test/event_issue1812.ics"]

    def test_report_getetag_expand_filter_negative1(self) -> None:
        """Test getetag with time-range filter and expand, should not return anything (example from #1812)."""
        self.mkcalendar("/test/")
        self.put("/test/event_issue1812_getetag.ics", get_file_content("event_issue1812_getetag.ics"))

        request = """
        <C:calendar-query xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
            <D:prop>
                <D:getetag>
                    <C:expand start="20250706T220000Z" end="20250713T220000Z" />
                </D:getetag>
            </D:prop>
            <C:filter>
                <C:comp-filter name="VCALENDAR">
                    <C:comp-filter name="VEVENT">
                        <C:time-range start="20250706T220000Z" end="20250713T220000Z" />
                    </C:comp-filter>
                </C:comp-filter>
            </C:filter>
        </C:calendar-query>
        """
        status, responses = self.report("/test", request)
        assert status == 207
        assert len(responses) == 0

    def test_report_getetag_expand_filter_negative2(self) -> None:
        """Test getetag with time-range filter and expand, should not return anything (example from #1812)."""
        self.mkcalendar("/test/")
        self.put("/test/event_issue1812_getetag.ics", get_file_content("event_issue1812_getetag.ics"))

        request = """
        <C:calendar-query xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
            <D:prop>
                <D:getetag />
                <C:calendar-data>
                    <C:expand start="20240706T220000Z" end="20240713T220000Z" />
                </C:calendar-data>
            </D:prop>
            <C:filter>
                <C:comp-filter name="VCALENDAR">
                    <C:comp-filter name="VEVENT">
                        <C:time-range start="20250706T220000Z" end="20250713T220000Z" />
                    </C:comp-filter>
                </C:comp-filter>
            </C:filter>
        </C:calendar-query>
        """
        status, responses = self.report("/test", request)
        assert status == 207
        assert len(responses) == 0


    def test_report_getetag_expand_filter_negative3(self) -> None:
        """Test getetag with time-range filter and expand, should not return anything (example from #1812)."""
        self.mkcalendar("/test/")
        self.put("/test/event_issue1812_getetag.ics", get_file_content("event_issue1812_getetag.ics"))

        request = """
        <C:calendar-query xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
            <D:prop>
                <C:calendar-data>
                    <C:expand start="20240706T220000Z" end="20240713T220000Z" />
                </C:calendar-data>
            </D:prop>
            <C:filter>
                <C:comp-filter name="VCALENDAR">
                    <C:comp-filter name="VEVENT">
                        <C:time-range start="20250706T220000Z" end="20250713T220000Z" />
                    </C:comp-filter>
                </C:comp-filter>
            </C:filter>
        </C:calendar-query>
        """
        status, responses = self.report("/test", request)
        assert status == 207
        assert len(responses) == 0

    def test_report_getetag_expand_filter_negative4(self) -> None:
        """Test getetag with time-range filter and expand, nothing returned as filter is not matching (example from #1812)."""
        self.mkcalendar("/test/")
        self.put("/test/event_issue1812.ics", get_file_content("event_issue1812.ics"))

        request = """
        <C:calendar-query xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
            <D:prop>
                <D:getetag>
                   <C:expand start="20250706T220000Z" end="20250730T220000Z" />
                </D:getetag>
            </D:prop>
            <C:filter>
                <C:comp-filter name="VCALENDAR">
                    <C:comp-filter name="VEVENT">
                        <C:time-range start="20240716T220000Z" end="20240723T220000Z" />
                    </C:comp-filter>
                </C:comp-filter>
            </C:filter>
        </C:calendar-query>
        """
        status, responses = self.report("/test", request)
        assert status == 207
        assert len(responses) == 0
