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

import radicale
import shutil
import tempfile

from dulwich.repo import Repo
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from . import BaseTest
from .helpers import get_file_content


class BaseRequests(object):
    """Tests with simple requests."""
    storage_type = None

    def setup(self):
        radicale.config.set("storage", "type", self.storage_type)

    def test_root(self):
        """GET request at "/"."""
        status, headers, answer = self.request("GET", "/")
        assert status == 200
        assert "Radicale works!" in answer
        # Test the creation of the collection
        status, headers, answer = self.request("GET", "/calendar.ics/")
        assert "BEGIN:VCALENDAR" in answer
        #assert "VERSION:2.0" in answer
        assert "END:VCALENDAR" in answer
        #assert "PRODID:-//Radicale//NONSGML Radicale Server//EN" in answer

    def test_add_event(self):
        """Add an event."""
        self.request("GET", "/calendar.ics/")
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
        self.request("GET", "/calendar.ics/")
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
        self.request("GET", "/calendar.ics/")
        event = get_file_content("event.ics")
        path = "/calendar.ics/event.ics"
        status, headers, answer = self.request("PUT", path, event)
        # Then we send a DELETE request
        status, headers, answer = self.request("DELETE", path)
        assert status == 200
        assert "href>%s</" % path in answer
        status, headers, answer = self.request("GET", "/calendar.ics/")
        assert "VEVENT" not in answer


class TestFileSystem(BaseRequests, BaseTest):
    """Base class for filesystem tests."""
    storage_type = "filesystem"

    def setup(self):
        """Setup function for each test."""
        self.colpath = tempfile.mkdtemp()
        from radicale.storage import filesystem
        filesystem.FOLDER = self.colpath
        filesystem.GIT_REPOSITORY = None
        self.application = radicale.Application()

    def teardown(self):
        """Teardown function for each test."""
        shutil.rmtree(self.colpath)


class TestMultiFileSystem(TestFileSystem):
    """Base class for multifilesystem tests."""
    storage_type = "multifilesystem"


class TestDataBaseSystem(BaseRequests, BaseTest):
    """Base class for database tests"""
    storage_type = "database"

    def setup(self):
        super(TestDataBaseSystem, self).setup()
        radicale.config.set("storage", "database_url", "sqlite://")
        from radicale.storage import database
        database.Session = sessionmaker()
        database.Session.configure(bind=create_engine("sqlite://"))
        session = database.Session()
        for st in get_file_content("schema.sql").split(";"):
            session.execute(st)
        session.commit()
        self.application = radicale.Application()

    class TestGitFileSystem(TestFileSystem):
        """Base class for filesystem tests using Git"""
        def setup(self):
            super(TestGitFileSystem, self).setup()
            Repo.init(self.colpath)
            from radicale.storage import filesystem
            filesystem.GIT_REPOSITORY = Repo(self.colpath)


    class TestGitMultiFileSystem(TestGitFileSystem, TestMultiFileSystem):
        """Base class for multifilesystem tests using Git"""


class TestCustomStorageSystem(BaseRequests, BaseTest):
    """Base class for custom backend tests."""
    storage_type = "custom"

    def setup(self):
        """Setup function for each test."""
        super(TestCustomStorageSystem, self).setup()
        self.colpath = tempfile.mkdtemp()
        radicale.config.set(
            "storage", "custom_handler", "tests.custom.storage")
        from tests.custom import storage
        storage.FOLDER = self.colpath
        storage.GIT_REPOSITORY = None
        self.application = radicale.Application()

    def teardown(self):
        """Teardown function for each test."""
        shutil.rmtree(self.colpath)
