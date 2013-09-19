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
Tests for Radicale.

"""

import base64
import hashlib
import os
import shutil
import sys
import tempfile
from dulwich.repo import Repo
from io import BytesIO

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import radicale

os.environ["RADICALE_CONFIG"] = os.path.join(os.path.dirname(
    os.path.dirname(__file__)), "config")

from radicale import config
from radicale.auth import htpasswd
from radicale.storage import filesystem, database
from .helpers import get_file_content
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine


class BaseTest(object):
    """Base class for tests."""
    def request(self, method, path, data=None, **args):
        """Send a request."""
        self.application._status = None
        self.application._headers = None
        self.application._answer = None

        for key in args:
            args[key.upper()] = args[key]
        args["REQUEST_METHOD"] = method.upper()
        args["PATH_INFO"] = path
        if data:
            if sys.version_info[0] >= 3:
                data = data.encode("utf-8")
            args["wsgi.input"] = BytesIO(data)
            args["CONTENT_LENGTH"] = str(len(data))
        self.application._answer = self.application(args, self.start_response)

        return (
            int(self.application._status.split()[0]),
            dict(self.application._headers),
            self.application._answer[0].decode("utf-8")
            if self.application._answer else None)

    def start_response(self, status, headers):
        """Put the response values into the current application."""
        self.application._status = status
        self.application._headers = headers


class FileSystem(BaseTest):
    """Base class for filesystem tests."""
    storage_type = "filesystem"

    def setup(self):
        """Setup function for each test."""
        self.colpath = tempfile.mkdtemp()
        config.set("storage", "type", self.storage_type)
        filesystem.FOLDER = self.colpath
        filesystem.GIT_REPOSITORY = None
        self.application = radicale.Application()

    def teardown(self):
        """Teardown function for each test."""
        shutil.rmtree(self.colpath)


class MultiFileSystem(FileSystem):
    """Base class for multifilesystem tests."""
    storage_type = "multifilesystem"


class DataBaseSystem(BaseTest):
    """Base class for database tests"""
    def setup(self):
        config.set("storage", "type", "database")
        config.set("storage", "database_url", "sqlite://")
        database.Session = sessionmaker()
        database.Session.configure(bind=create_engine("sqlite://"))
        session = database.Session()
        # session.execute(get_file_content("schema.sql"))
        for st in get_file_content("schema.sql").split(";"):
            session.execute(st)
        session.commit()
        self.application = radicale.Application()


class GitFileSystem(FileSystem):
    """Base class for filesystem tests using Git"""
    def setup(self):
        super(GitFileSystem, self).setup()
        Repo.init(self.colpath)
        filesystem.GIT_REPOSITORY = Repo(self.colpath)


class GitMultiFileSystem(GitFileSystem, MultiFileSystem):
    """Base class for multifilesystem tests using Git"""


class HtpasswdAuthSystem(BaseTest):
    """Base class to test Radicale with Htpasswd authentication"""
    def setup(self):
        self.colpath = tempfile.mkdtemp()
        htpasswd_file_path = os.path.join(self.colpath, ".htpasswd")
        with open(htpasswd_file_path, "wb") as fd:
            fd.write(b"tmp:{SHA}" + base64.b64encode(
                hashlib.sha1(b"bepo").digest()))
        config.set("auth", "type", "htpasswd")
        self.userpass = base64.b64encode(b"tmp:bepo")
        self.application = radicale.Application()
        htpasswd.FILENAME = htpasswd_file_path
        htpasswd.ENCRYPTION = "sha1"

    def teardown(self):
        config.set("auth", "type", "None")
        radicale.auth.is_authenticated = lambda *_: True
