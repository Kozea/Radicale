# This file is part of Radicale Server - Calendar Server
# Copyright © 2012-2016 Guillaume Ayoub
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
import shutil
import tempfile

from radicale import Application, config

from . import BaseTest
from .helpers import get_file_content


class BaseRequests:
    """Tests with simple requests."""
    storage_type = None

    def setup(self):
        self.configuration = config.load()
        self.configuration.set("storage", "type", self.storage_type)
        self.logger = logging.getLogger("radicale_test")

    def test_root(self):
        """GET request at "/"."""
        status, headers, answer = self.request("GET", "/")
        assert status == 200
        assert "Radicale works!" in answer
        # Test the creation of the collection
        self.request("MKCOL", "/calendar.ics/")
        self.request(
            "PUT", "/calendar.ics/", "BEGIN:VCALENDAR\r\nEND:VCALENDAR")
        status, headers, answer = self.request("GET", "/calendar.ics/")
        assert "BEGIN:VCALENDAR" in answer
        assert "END:VCALENDAR" in answer

    def test_add_event(self):
        """Add an event."""
        self.request("MKCOL", "/calendar.ics/")
        self.request(
            "PUT", "/calendar.ics/", "BEGIN:VCALENDAR\r\nEND:VCALENDAR")
        event = get_file_content("event1.ics")
        path = "/calendar.ics/event1.ics"
        status, headers, answer = self.request("PUT", path, event)
        assert status == 201
        status, headers, answer = self.request("GET", path)
        assert "ETag" in headers.keys()
        assert status == 200
        assert "VEVENT" in answer
        assert "Event" in answer
        assert "UID:event" in answer

    def test_add_todo(self):
        """Add a todo."""
        self.request("MKCOL", "/calendar.ics/")
        self.request(
            "PUT", "/calendar.ics/", "BEGIN:VCALENDAR\r\nEND:VCALENDAR")
        todo = get_file_content("todo1.ics")
        path = "/calendar.ics/todo1.ics"
        status, headers, answer = self.request("PUT", path, todo)
        assert status == 201
        status, headers, answer = self.request("GET", path)
        assert "ETag" in headers.keys()
        assert "VTODO" in answer
        assert "Todo" in answer
        assert "UID:todo" in answer

    def test_delete(self):
        """Delete an event."""
        self.request("MKCOL", "/calendar.ics/")
        self.request(
            "PUT", "/calendar.ics/", "BEGIN:VCALENDAR\r\nEND:VCALENDAR")
        event = get_file_content("event1.ics")
        path = "/calendar.ics/event1.ics"
        status, headers, answer = self.request("PUT", path, event)
        # Then we send a DELETE request
        status, headers, answer = self.request("DELETE", path)
        assert status == 200
        assert "href>%s</" % path in answer
        status, headers, answer = self.request("GET", "/calendar.ics/")
        assert "VEVENT" not in answer

    def _test_filter(self, filters, kind="event", items=1):
        filters_text = "".join(
            "<C:filter>%s</C:filter>" % filter_ for filter_ in filters)
        self.request("MKCOL", "/calendar.ics/")
        self.request(
            "PUT", "/calendar.ics/", "BEGIN:VCALENDAR\r\nEND:VCALENDAR")
        for i in range(items):
            filename = "{}{}.ics".format(kind, i + 1)
            event = get_file_content(filename)
            self.request("PUT", "/calendar.ics/{}".format(filename), event)
        status, headers, answer = self.request(
            "REPORT", "/calendar.ics",
            """<?xml version="1.0" encoding="utf-8" ?>
               <C:calendar-query xmlns:C="urn:ietf:params:xml:ns:caldav">
                 <D:prop xmlns:D="DAV:">
                   <D:getetag/>
                 </D:prop>
                 %s
               </C:calendar-query>""" % filters_text)
        return answer

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
            </C:comp-filter>"""], "event", items=5)
        assert "href>/calendar.ics/event1.ics</" in answer
        assert "href>/calendar.ics/event2.ics</" in answer
        assert "href>/calendar.ics/event3.ics</" in answer
        assert "href>/calendar.ics/event4.ics</" in answer
        assert "href>/calendar.ics/event5.ics</" in answer
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
            </C:comp-filter>"""], items=5)
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
            </C:comp-filter>"""], items=5)
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
            </C:comp-filter>"""], items=5)
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
            </C:comp-filter>"""], items=5)
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
            </C:comp-filter>"""], items=5)
        assert "href>/calendar.ics/event1.ics</" not in answer
        assert "href>/calendar.ics/event2.ics</" not in answer
        assert "href>/calendar.ics/event3.ics</" not in answer
        assert "href>/calendar.ics/event4.ics</" not in answer
        assert "href>/calendar.ics/event5.ics</" not in answer

    def test_time_range_filter_events_rrule(self):
        """Report request with time-range filter on events with rrules."""
        answer = self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VEVENT">
                <C:time-range start="20130801T000000Z" end="20131001T000000Z"/>
              </C:comp-filter>
            </C:comp-filter>"""], "event", items=2)
        assert "href>/calendar.ics/event1.ics</" in answer
        assert "href>/calendar.ics/event2.ics</" in answer
        answer = self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VEVENT">
                <C:time-range start="20140801T000000Z" end="20141001T000000Z"/>
              </C:comp-filter>
            </C:comp-filter>"""], "event", items=2)
        assert "href>/calendar.ics/event1.ics</" not in answer
        assert "href>/calendar.ics/event2.ics</" in answer
        answer = self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VEVENT">
                <C:time-range start="20120801T000000Z" end="20121001T000000Z"/>
              </C:comp-filter>
            </C:comp-filter>"""], "event", items=2)
        assert "href>/calendar.ics/event1.ics</" not in answer
        assert "href>/calendar.ics/event2.ics</" not in answer
        answer = self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VEVENT">
                <C:time-range start="20130903T000000Z" end="20130907T000000Z"/>
              </C:comp-filter>
            </C:comp-filter>"""], "event", items=2)
        assert "href>/calendar.ics/event1.ics</" not in answer
        assert "href>/calendar.ics/event2.ics</" not in answer

    def test_time_range_filter_todos(self):
        """Report request with time-range filter on todos."""
        answer = self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VTODO">
                <C:time-range start="20130801T000000Z" end="20131001T000000Z"/>
              </C:comp-filter>
            </C:comp-filter>"""], "todo", items=8)
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
            </C:comp-filter>"""], "todo", items=8)
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
            </C:comp-filter>"""], "todo", items=8)
        assert "href>/calendar.ics/todo2.ics</" not in answer
        answer = self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VTODO">
                <C:time-range start="20130903T160000Z" end="20130901T173000Z"/>
              </C:comp-filter>
            </C:comp-filter>"""], "todo", items=8)
        assert "href>/calendar.ics/todo2.ics</" not in answer
        answer = self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VTODO">
                <C:time-range start="20130903T160000Z" end="20130903T173000Z"/>
              </C:comp-filter>
            </C:comp-filter>"""], "todo", items=8)
        assert "href>/calendar.ics/todo3.ics</" not in answer
        answer = self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VTODO">
                <C:time-range start="20130903T160000Z" end="20130803T203000Z"/>
              </C:comp-filter>
            </C:comp-filter>"""], "todo", items=8)
        assert "href>/calendar.ics/todo7.ics</" in answer

    def test_time_range_filter_todos_rrule(self):
        """Report request with time-range filter on todos with rrules."""
        answer = self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VTODO">
                <C:time-range start="20130801T000000Z" end="20131001T000000Z"/>
              </C:comp-filter>
            </C:comp-filter>"""], "todo", items=2)
        assert "href>/calendar.ics/todo1.ics</" in answer
        assert "href>/calendar.ics/todo2.ics</" in answer
        answer = self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VTODO">
                <C:time-range start="20140801T000000Z" end="20141001T000000Z"/>
              </C:comp-filter>
            </C:comp-filter>"""], "todo", items=2)
        assert "href>/calendar.ics/todo1.ics</" not in answer
        assert "href>/calendar.ics/todo2.ics</" in answer
        answer = self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VTODO">
                <C:time-range start="20140902T000000Z" end="20140903T000000Z"/>
              </C:comp-filter>
            </C:comp-filter>"""], "todo", items=2)
        assert "href>/calendar.ics/todo1.ics</" not in answer
        assert "href>/calendar.ics/todo2.ics</" in answer
        answer = self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VTODO">
                <C:time-range start="20140904T000000Z" end="20140914T000000Z"/>
              </C:comp-filter>
            </C:comp-filter>"""], "todo", items=2)
        assert "href>/calendar.ics/todo1.ics</" not in answer
        assert "href>/calendar.ics/todo2.ics</" not in answer

    def test_time_range_filter_journals(self):
        """Report request with time-range filter on journals."""
        answer = self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VJOURNAL">
                <C:time-range start="19991229T000000Z" end="20000202T000000Z"/>
              </C:comp-filter>
            </C:comp-filter>"""], "journal", items=3)
        assert "href>/calendar.ics/journal1.ics</" not in answer
        assert "href>/calendar.ics/journal2.ics</" in answer
        assert "href>/calendar.ics/journal3.ics</" in answer
        answer = self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VJOURNAL">
                <C:time-range start="19991229T000000Z" end="20000202T000000Z"/>
              </C:comp-filter>
            </C:comp-filter>"""], "journal", items=3)
        assert "href>/calendar.ics/journal1.ics</" not in answer
        assert "href>/calendar.ics/journal2.ics</" in answer
        assert "href>/calendar.ics/journal3.ics</" in answer
        answer = self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VJOURNAL">
                <C:time-range start="19981229T000000Z" end="19991012T000000Z"/>
              </C:comp-filter>
            </C:comp-filter>"""], "journal", items=3)
        assert "href>/calendar.ics/journal1.ics</" not in answer
        assert "href>/calendar.ics/journal2.ics</" not in answer
        assert "href>/calendar.ics/journal3.ics</" not in answer
        answer = self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VJOURNAL">
                <C:time-range start="20131229T000000Z" end="21520202T000000Z"/>
              </C:comp-filter>
            </C:comp-filter>"""], "journal", items=3)
        assert "href>/calendar.ics/journal1.ics</" not in answer
        assert "href>/calendar.ics/journal2.ics</" in answer
        assert "href>/calendar.ics/journal3.ics</" not in answer
        answer = self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VJOURNAL">
                <C:time-range start="20000101T000000Z" end="20000202T000000Z"/>
              </C:comp-filter>
            </C:comp-filter>"""], "journal", items=3)
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
            </C:comp-filter>"""], "journal", items=2)
        assert "href>/calendar.ics/journal1.ics</" not in answer
        assert "href>/calendar.ics/journal2.ics</" in answer
        answer = self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VJOURNAL">
                <C:time-range start="20051229T000000Z" end="20060202T000000Z"/>
              </C:comp-filter>
            </C:comp-filter>"""], "journal", items=2)
        assert "href>/calendar.ics/journal1.ics</" not in answer
        assert "href>/calendar.ics/journal2.ics</" in answer
        answer = self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VJOURNAL">
                <C:time-range start="20060102T000000Z" end="20060202T000000Z"/>
              </C:comp-filter>
            </C:comp-filter>"""], "journal", items=2)
        assert "href>/calendar.ics/journal1.ics</" not in answer
        assert "href>/calendar.ics/journal2.ics</" not in answer


class TestMultiFileSystem(BaseRequests, BaseTest):
    """Base class for filesystem tests."""
    storage_type = "multifilesystem"

    def setup(self):
        super().setup()
        self.colpath = tempfile.mkdtemp()
        self.configuration.set("storage", "filesystem_folder", self.colpath)
        self.application = Application(self.configuration, self.logger)

    def teardown(self):
        shutil.rmtree(self.colpath)


class TestCustomStorageSystem(BaseRequests, BaseTest):
    """Base class for custom backend tests."""
    storage_type = "tests.custom.storage"

    def setup(self):
        super().setup()
        self.colpath = tempfile.mkdtemp()
        self.configuration.set("storage", "filesystem_folder", self.colpath)
        self.configuration.set("storage", "test_folder", self.colpath)
        self.application = Application(self.configuration, self.logger)

    def teardown(self):
        shutil.rmtree(self.colpath)
