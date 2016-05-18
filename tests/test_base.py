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
        self.request(
            "PUT", "/calendar.ics/", "BEGIN:VCALENDAR\r\nEND:VCALENDAR")
        status, headers, answer = self.request("GET", "/calendar.ics/")
        assert "BEGIN:VCALENDAR" in answer
        assert "END:VCALENDAR" in answer

    def test_add_event(self):
        """Add an event."""
        self.request(
            "PUT", "/calendar.ics/", "BEGIN:VCALENDAR\r\nEND:VCALENDAR")
        event = get_file_content("event.ics")
        path = "/calendar.ics/event.ics"
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
        self.request(
            "PUT", "/calendar.ics/", "BEGIN:VCALENDAR\r\nEND:VCALENDAR")
        todo = get_file_content("todo.ics")
        path = "/calendar.ics/todo.ics"
        status, headers, answer = self.request("PUT", path, todo)
        assert status == 201
        status, headers, answer = self.request("GET", path)
        assert "ETag" in headers.keys()
        assert "VTODO" in answer
        assert "Todo" in answer
        assert "UID:todo" in answer

    def test_delete(self):
        """Delete an event."""
        self.request(
            "PUT", "/calendar.ics/", "BEGIN:VCALENDAR\r\nEND:VCALENDAR")
        event = get_file_content("event.ics")
        path = "/calendar.ics/event.ics"
        status, headers, answer = self.request("PUT", path, event)
        # Then we send a DELETE request
        status, headers, answer = self.request("DELETE", path)
        assert status == 200
        assert "href>%s</" % path in answer
        status, headers, answer = self.request("GET", "/calendar.ics/")
        assert "VEVENT" not in answer

    def _test_filter(self, filters):
        filters_text = "".join(
            "<C:filter>%s</C:filter>" % filter_ for filter_ in filters)
        self.request(
            "PUT", "/calendar.ics/", "BEGIN:VCALENDAR\r\nEND:VCALENDAR")
        event = get_file_content("event.ics")
        self.request("PUT", "/calendar.ics/event.ics", event)
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
        assert "href>/calendar.ics/event.ics</" in self._test_filter(["""
            <C:comp-filter name="VCALENDAR"></C:comp-filter>"""])

    def test_item_tag_filter(self):
        """Report request with tag-based filter on an item."""
        assert "href>/calendar.ics/event.ics</" in self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VEVENT"></C:comp-filter>
            </C:comp-filter>"""])
        assert "href>/calendar.ics/event.ics</" not in self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VTODO"></C:comp-filter>
            </C:comp-filter>"""])

    def test_item_not_tag_filter(self):
        """Report request with tag-based is-not filter on an item."""
        assert "href>/calendar.ics/event.ics</" not in self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VEVENT">
                <C:is-not-defined />
              </C:comp-filter>
            </C:comp-filter>"""])
        assert "href>/calendar.ics/event.ics</" in self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VTODO">
                <C:is-not-defined />
              </C:comp-filter>
            </C:comp-filter>"""])

    def test_item_prop_filter(self):
        """Report request with prop-based filter on an item."""
        assert "href>/calendar.ics/event.ics</" in self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VEVENT">
                <C:prop-filter name="SUMMARY"></C:prop-filter>
              </C:comp-filter>
            </C:comp-filter>"""])
        assert "href>/calendar.ics/event.ics</" not in self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VEVENT">
                <C:prop-filter name="UNKNOWN"></C:prop-filter>
              </C:comp-filter>
            </C:comp-filter>"""])

    def test_item_not_prop_filter(self):
        """Report request with prop-based is-not filter on an item."""
        assert "href>/calendar.ics/event.ics</" not in self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VEVENT">
                <C:prop-filter name="SUMMARY">
                  <C:is-not-defined />
                </C:prop-filter>
              </C:comp-filter>
            </C:comp-filter>"""])
        assert "href>/calendar.ics/event.ics</" in self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VEVENT">
                <C:prop-filter name="UNKNOWN">
                  <C:is-not-defined />
                </C:prop-filter>
              </C:comp-filter>
            </C:comp-filter>"""])

    def test_mutiple_filters(self):
        """Report request with multiple filters on an item."""
        assert "href>/calendar.ics/event.ics</" not in self._test_filter(["""
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
        assert "href>/calendar.ics/event.ics</" in self._test_filter(["""
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
        assert "href>/calendar.ics/event.ics</" in self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VEVENT">
                <C:prop-filter name="SUMMARY"></C:prop-filter>
                <C:prop-filter name="UNKNOWN">
                  <C:is-not-defined />
                </C:prop-filter>
              </C:comp-filter>
            </C:comp-filter>"""])

    def test_text_match_filter(self):
        """Report request with tag-based filter on calendar."""
        assert "href>/calendar.ics/event.ics</" in self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VEVENT">
                <C:prop-filter name="SUMMARY">
                  <C:text-match>event</C:text-match>
                </C:prop-filter>
              </C:comp-filter>
            </C:comp-filter>"""])
        assert "href>/calendar.ics/event.ics</" not in self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VEVENT">
                <C:prop-filter name="UNKNOWN">
                  <C:text-match>event</C:text-match>
                </C:prop-filter>
              </C:comp-filter>
            </C:comp-filter>"""])
        assert "href>/calendar.ics/event.ics</" not in self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VEVENT">
                <C:prop-filter name="SUMMARY">
                  <C:text-match>unknown</C:text-match>
                </C:prop-filter>
              </C:comp-filter>
            </C:comp-filter>"""])
        assert "href>/calendar.ics/event.ics</" not in self._test_filter(["""
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VEVENT">
                <C:prop-filter name="SUMMARY">
                  <C:text-match negate-condition="yes">event</C:text-match>
                </C:prop-filter>
              </C:comp-filter>
            </C:comp-filter>"""])


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
