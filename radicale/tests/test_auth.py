# This file is part of Radicale Server - Calendar Server
# Copyright © 2012-2013 Guillaume Ayoub
# Copyright © 2012-2016 Jean-Marc Martins
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
import logging
import os
import shutil
import tempfile

from radicale import Application, config

from . import BaseTest


class TestBaseAuthRequests(BaseTest):
    """Tests basic requests with auth.

    We should setup auth for each type before creating the Application object.

    """
    def setup(self):
        self.colpath = tempfile.mkdtemp()

    def teardown(self):
        shutil.rmtree(self.colpath)

    def test_root(self):
        """Htpasswd authentication."""
        htpasswd_file_path = os.path.join(self.colpath, ".htpasswd")
        with open(htpasswd_file_path, "wb") as fd:
            fd.write(b"tmp:{SHA}" + base64.b64encode(
                hashlib.sha1(b"bepo").digest()))

        configuration = config.load()
        configuration.set("auth", "type", "htpasswd")
        configuration.set("auth", "htpasswd_filename", htpasswd_file_path)
        configuration.set("auth", "htpasswd_encryption", "sha1")

        self.application = Application(
            configuration, logging.getLogger("radicale_test"))

        status, headers, answer = self.request(
            "GET", "/", HTTP_AUTHORIZATION="dG1wOmJlcG8=")
        assert status == 200
        assert "Radicale works!" in answer

    def test_custom(self):
        """Custom authentication."""
        configuration = config.load()
        configuration.set("auth", "type", "tests.custom.auth")
        self.application = Application(
            configuration, logging.getLogger("radicale_test"))

        status, headers, answer = self.request("GET", "/")
        assert status == 200
        assert "Radicale works!" in answer
