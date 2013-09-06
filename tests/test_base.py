# -*- coding: utf-8 -*-
#
# This file is part of Radicale Server - Calendar Server
# Copyright © 2012-2013 Guillaume Ayoub
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

from . import (FileSystem, MultiFileSystem, DataBaseSystem,
               GitFileSystem, GitMultiFileSystem)
from .helpers import get_file_content
import sys


class BaseRequests(object):
    """Tests with simple requests."""

    def test_root(self):
        """Test a GET request at "/"."""
        status, headers, answer = self.request("GET", "/")
        assert status == 200
        assert "Radicale works!" in answer
        # Tests the creation of the collection
        status, headers, answer = self.request("GET", "/calendar.ics/")
        assert u"BEGIN:VCALENDAR" in answer
        assert u"VERSION:2.0" in answer
        assert u"END:VCALENDAR" in answer
        assert u"PRODID:-//Radicale//NONSGML Radicale Server//EN" in answer

    def test_add_event_todo(self):
        """Tests the add of an event and todo."""
        self.request("GET", "/calendar.ics/")
        #VEVENT test
        event = get_file_content("put.ics")
        path = "/calendar.ics/02805f81-4cc2-4d68-8d39-72768ffa02d9.ics"
        status, headers, answer = self.request("PUT", path, event)
        assert status == 201
        assert u"ETag" in headers.keys()
        status, headers, answer = self.request("GET", path)
        assert status == 200
        assert u"VEVENT" in answer
        assert u"Nouvel évènement" in answer
        assert u"UID:02805f81-4cc2-4d68-8d39-72768ffa02d9" in answer
        # VTODO test
        todo = get_file_content("putvtodo.ics")
        path = "/calendar.ics/40f8cf9b-0e62-4624-89a2-24c5e68850f5.ics"
        status, headers, answer = self.request("PUT", path, todo)
        assert status == 201
        assert u"ETag" in headers.keys()
        status, headers, answer = self.request("GET", path)
        assert u"VTODO" in answer
        assert u"Nouvelle tâche" in answer
        assert u"UID:40f8cf9b-0e62-4624-89a2-24c5e68850f5" in answer

    def test_delete(self):
        """Tests the deletion of an event"""
        self.request("GET", "/calendar.ics/")
        # Adds a VEVENT to be deleted
        event = get_file_content("put.ics")
        path = "/calendar.ics/02805f81-4cc2-4d68-8d39-72768ffa02d9.ics"
        status, headers, answer = self.request("PUT", path, event)
        # Then we send a DELETE request
        status, headers, answer = self.request("DELETE", path)
        assert status == 200
        assert u"<href>%s</href>" % path in answer
        status, headers, answer = self.request("GET", "/calendar.ics/")
        assert u"VEVENT" not in answer

# Generates Classes with different configs
cl_list = [FileSystem, MultiFileSystem, DataBaseSystem,
           GitFileSystem, GitMultiFileSystem]
for cl in cl_list:
    classname = "Test%s" % cl.__name__
    setattr(sys.modules[__name__],
            classname, type(classname, (BaseRequests, cl), {}))
