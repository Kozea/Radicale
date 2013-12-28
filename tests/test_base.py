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

from .helpers import get_file_content
import radicale
import shutil
import tempfile
from dulwich.repo import Repo
from radicale import config
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from tests import BaseTest


class BaseRequests(object):
    """Tests with simple requests."""

    def test_root(self):
        """Test a GET request at "/"."""
        status, headers, answer = self.request("GET", "/")
        assert status == 200
        assert "Radicale works!" in answer
        # Test the creation of the collection
        status, headers, answer = self.request("GET", "/calendar.ics/")
        assert "BEGIN:VCALENDAR" in answer
        assert "VERSION:2.0" in answer
        assert "END:VCALENDAR" in answer
        assert "PRODID:-//Radicale//NONSGML Radicale Server//EN" in answer

    def test_add_event_todo(self):
        """Tests the add of an event and todo."""
        self.request("GET", "/calendar.ics/")
        #VEVENT test
        event = get_file_content("put.ics")
        path = "/calendar.ics/02805f81-4cc2-4d68-8d39-72768ffa02d9.ics"
        status, headers, answer = self.request("PUT", path, event)
        assert status == 201
        assert "ETag" in headers.keys()
        status, headers, answer = self.request("GET", path)
        assert status == 200
        assert "VEVENT" in answer
        assert b"Nouvel \xc3\xa9v\xc3\xa8nement".decode("utf-8") in answer
        assert "UID:02805f81-4cc2-4d68-8d39-72768ffa02d9" in answer
        # VTODO test
        todo = get_file_content("putvtodo.ics")
        path = "/calendar.ics/40f8cf9b-0e62-4624-89a2-24c5e68850f5.ics"
        status, headers, answer = self.request("PUT", path, todo)
        assert status == 201
        assert "ETag" in headers.keys()
        status, headers, answer = self.request("GET", path)
        assert "VTODO" in answer
        assert b"Nouvelle t\xc3\xa2che".decode("utf-8") in answer
        assert "UID:40f8cf9b-0e62-4624-89a2-24c5e68850f5" in answer

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
        assert "href>%s</" % path in answer
        status, headers, answer = self.request("GET", "/calendar.ics/")
        assert "VEVENT" not in answer


class TestFileSystem(BaseRequests, BaseTest):
    """Base class for filesystem tests."""
    storage_type = "filesystem"

    def setup(self):
        """Setup function for each test."""
        self.colpath = tempfile.mkdtemp()
        config.set("storage", "type", self.storage_type)
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
    def setup(self):
        config.set("storage", "type", "database")
        config.set("storage", "database_url", "sqlite://")
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
        self.colpath = tempfile.mkdtemp()
        config.set("storage", "type", self.storage_type)
        config.set("storage", "custom_handler", "tests.custom.storage")
        from tests.custom import storage
        storage.FOLDER = self.colpath
        storage.GIT_REPOSITORY = None
        self.application = radicale.Application()

    def teardown(self):
        """Teardown function for each test."""
        shutil.rmtree(self.colpath)