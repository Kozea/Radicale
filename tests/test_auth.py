# -*- coding: utf-8 -*-
#
# This file is part of Radicale Server - Calendar Server
# Copyright © 2012-2013 Guillaume Ayoub
# Copyright © 2012-2013 Jean-Marc Martins
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
Radicale tests with simple requests and authentication.

"""

import base64
import hashlib
import os
import radicale
import tempfile
from radicale import config
from radicale.auth import htpasswd
from tests import BaseTest


class TestBaseAuthRequests(BaseTest):
    """
    Tests basic requests with auth.

    We should setup auth for each type before create Application object
    """

    def setup(self):
        self.userpass = "dG1wOmJlcG8="

    def teardown(self):
        config.set("auth", "type", "None")
        radicale.auth.is_authenticated = lambda *_: True

    def test_root(self):
        self.colpath = tempfile.mkdtemp()
        htpasswd_file_path = os.path.join(self.colpath, ".htpasswd")
        with open(htpasswd_file_path, "wb") as fd:
            fd.write(b"tmp:{SHA}" + base64.b64encode(
                hashlib.sha1(b"bepo").digest()))
        config.set("auth", "type", "htpasswd")

        htpasswd.FILENAME = htpasswd_file_path
        htpasswd.ENCRYPTION = "sha1"

        self.application = radicale.Application()

        status, headers, answer = self.request(
            "GET", "/", HTTP_AUTHORIZATION=self.userpass)
        assert status == 200
        assert "Radicale works!" in answer

    def test_custom(self):
        config.set("auth", "type", "custom")
        config.set("auth", "custom_handler", "tests.custom.auth")
        self.application = radicale.Application()
        status, headers, answer = self.request(
            "GET", "/", HTTP_AUTHORIZATION=self.userpass)
        assert status == 200
        assert "Radicale works!" in answer
