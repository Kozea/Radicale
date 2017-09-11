# This file is part of Radicale Server - Calendar Server
# Copyright © 2012-2016 Jean-Marc Martins
# Copyright © 2012-2017 Guillaume Ayoub
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
import os
import shutil
import tempfile

import pytest

from radicale import Application, config

from .test_base import BaseTest


class TestBaseAuthRequests(BaseTest):
    """Tests basic requests with auth.

    We should setup auth for each type before creating the Application object.

    """
    def setup(self):
        self.configuration = config.load()
        self.colpath = tempfile.mkdtemp()
        self.configuration["storage"]["filesystem_folder"] = self.colpath
        # Disable syncing to disk for better performance
        self.configuration["storage"]["filesystem_fsync"] = "False"
        # Required on Windows, doesn't matter on Unix
        self.configuration["storage"]["filesystem_close_lock_file"] = "True"
        # Set incorrect authentication delay to a very low value
        self.configuration["auth"]["delay"] = "0.002"

    def teardown(self):
        shutil.rmtree(self.colpath)

    def _test_htpasswd(self, htpasswd_encryption, htpasswd_content,
                       test_matrix=None):
        """Test htpasswd authentication with user "tmp" and password "bepo"."""
        htpasswd_file_path = os.path.join(self.colpath, ".htpasswd")
        with open(htpasswd_file_path, "w") as f:
            f.write(htpasswd_content)
        self.configuration["auth"]["type"] = "htpasswd"
        self.configuration["auth"]["htpasswd_filename"] = htpasswd_file_path
        self.configuration["auth"]["htpasswd_encryption"] = htpasswd_encryption
        self.application = Application(self.configuration, self.logger)
        if test_matrix is None:
            test_matrix = (
                ("tmp", "bepo", 207), ("tmp", "tmp", 401), ("tmp", "", 401),
                ("unk", "unk", 401), ("unk", "", 401), ("", "", 401))
        for user, password, expected_status in test_matrix:
            status, _, answer = self.request(
                "PROPFIND", "/",
                HTTP_AUTHORIZATION="Basic %s" % base64.b64encode(
                    ("%s:%s" % (user, password)).encode()).decode())
            assert status == expected_status

    def test_htpasswd_plain(self):
        self._test_htpasswd("plain", "tmp:bepo")

    def test_htpasswd_plain_password_split(self):
        self._test_htpasswd("plain", "tmp:be:po", (
            ("tmp", "be:po", 207), ("tmp", "bepo", 401)))

    def test_htpasswd_sha1(self):
        self._test_htpasswd("sha1", "tmp:{SHA}UWRS3uSJJq2itZQEUyIH8rRajCM=")

    def test_htpasswd_ssha(self):
        self._test_htpasswd("ssha", "tmp:{SSHA}qbD1diw9RJKi0DnW4qO8WX9SE18W")

    def test_htpasswd_md5(self):
        try:
            import passlib  # noqa: F401
        except ImportError:
            pytest.skip("passlib is not installed")
        self._test_htpasswd("md5", "tmp:$apr1$BI7VKCZh$GKW4vq2hqDINMr8uv7lDY/")

    def test_htpasswd_crypt(self):
        try:
            import crypt  # noqa: F401
        except ImportError:
            pytest.skip("crypt is not installed")
        self._test_htpasswd("crypt", "tmp:dxUqxoThMs04k")

    def test_htpasswd_bcrypt(self):
        try:
            from passlib.hash import bcrypt
            from passlib.exc import MissingBackendError
        except ImportError:
            pytest.skip("passlib is not installed")
        try:
            bcrypt.encrypt("test-bcrypt-backend")
        except MissingBackendError:
            pytest.skip("bcrypt backend for passlib is not installed")
        self._test_htpasswd(
            "bcrypt",
            "tmp:$2y$05$oD7hbiQFQlvCM7zoalo/T.MssV3VNTRI3w5KDnj8NTUKJNWfVpvRq")

    def test_htpasswd_multi(self):
        self._test_htpasswd("plain", "ign:ign\ntmp:bepo")

    @pytest.mark.skipif(os.name == "nt", reason="leading and trailing "
                        "whitespaces not allowed in file names")
    def test_htpasswd_whitespace_preserved(self):
        self._test_htpasswd("plain", " tmp : bepo ",
                            ((" tmp ", " bepo ", 207),))

    def test_htpasswd_whitespace_not_trimmed(self):
        self._test_htpasswd("plain", " tmp : bepo ", (("tmp", "bepo", 401),))

    def test_htpasswd_comment(self):
        self._test_htpasswd("plain", "#comment\n #comment\n \ntmp:bepo\n\n")

    def test_remote_user(self):
        self.configuration["auth"]["type"] = "remote_user"
        self.application = Application(self.configuration, self.logger)
        status, _, answer = self.request(
            "PROPFIND", "/",
            """<?xml version="1.0" encoding="utf-8"?>
               <propfind xmlns="DAV:">
                 <prop>
                   <current-user-principal />
                 </prop>
               </propfind>""", REMOTE_USER="test")
        assert status == 207
        assert ">/test/<" in answer

    def test_http_x_remote_user(self):
        self.configuration["auth"]["type"] = "http_x_remote_user"
        self.application = Application(self.configuration, self.logger)
        status, _, answer = self.request(
            "PROPFIND", "/",
            """<?xml version="1.0" encoding="utf-8"?>
               <propfind xmlns="DAV:">
                 <prop>
                   <current-user-principal />
                 </prop>
               </propfind>""", HTTP_X_REMOTE_USER="test")
        assert status == 207
        assert ">/test/<" in answer

    def test_custom(self):
        """Custom authentication."""
        self.configuration["auth"]["type"] = "tests.custom.auth"
        self.application = Application(self.configuration, self.logger)
        status, _, answer = self.request(
            "PROPFIND", "/tmp", HTTP_AUTHORIZATION="Basic %s" %
            base64.b64encode(("tmp:").encode()).decode())
        assert status == 207
