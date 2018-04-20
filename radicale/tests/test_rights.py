# This file is part of Radicale Server - Calendar Server
# Copyright (C) 2017 Unrud <unrud@outlook.com>
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
Radicale tests with simple requests and rights.
"""

import base64
import os
import shutil
import tempfile

from radicale import Application, config

from .test_base import BaseTest


class TestBaseAuthRequests(BaseTest):
    """Tests basic requests with rights."""

    def setup(self):
        self.configuration = config.load()
        self.colpath = tempfile.mkdtemp()
        self.configuration["storage"]["filesystem_folder"] = self.colpath
        # Disable syncing to disk for better performance
        self.configuration["storage"]["filesystem_fsync"] = "False"
        # Required on Windows, doesn't matter on Unix
        self.configuration["storage"]["filesystem_close_lock_file"] = "True"

    def teardown(self):
        shutil.rmtree(self.colpath)

    def _test_rights(self, rights_type, user, path, mode, expected_status):
        assert mode in ("r", "w")
        assert user in ("", "tmp")
        htpasswd_file_path = os.path.join(self.colpath, ".htpasswd")
        with open(htpasswd_file_path, "w") as f:
            f.write("tmp:bepo\nother:bepo")
        self.configuration["rights"]["type"] = rights_type
        self.configuration["auth"]["type"] = "htpasswd"
        self.configuration["auth"]["htpasswd_filename"] = htpasswd_file_path
        self.configuration["auth"]["htpasswd_encryption"] = "plain"
        self.application = Application(self.configuration, self.logger)
        for u in ("tmp", "other"):
            status, _, _ = self.request(
                "PROPFIND", "/%s" % u, HTTP_AUTHORIZATION="Basic %s" %
                base64.b64encode(("%s:bepo" % u).encode()).decode())
            assert status == 207
        status, _, _ = self.request(
            "PROPFIND" if mode == "r" else "PROPPATCH", path,
            HTTP_AUTHORIZATION="Basic %s" % base64.b64encode(
                ("tmp:bepo").encode()).decode() if user else "")
        assert status == expected_status

    def test_owner_only(self):
        self._test_rights("owner_only", "", "/", "r", 401)
        self._test_rights("owner_only", "", "/", "w", 401)
        self._test_rights("owner_only", "", "/tmp", "r", 401)
        self._test_rights("owner_only", "", "/tmp", "w", 401)
        self._test_rights("owner_only", "tmp", "/", "r", 207)
        self._test_rights("owner_only", "tmp", "/", "w", 403)
        self._test_rights("owner_only", "tmp", "/tmp", "r", 207)
        self._test_rights("owner_only", "tmp", "/tmp", "w", 207)
        self._test_rights("owner_only", "tmp", "/other", "r", 403)
        self._test_rights("owner_only", "tmp", "/other", "w", 403)

    def test_owner_write(self):
        self._test_rights("owner_write", "", "/", "r", 401)
        self._test_rights("owner_write", "", "/", "w", 401)
        self._test_rights("owner_write", "", "/tmp", "r", 401)
        self._test_rights("owner_write", "", "/tmp", "w", 401)
        self._test_rights("owner_write", "tmp", "/", "r", 207)
        self._test_rights("owner_write", "tmp", "/", "w", 403)
        self._test_rights("owner_write", "tmp", "/tmp", "r", 207)
        self._test_rights("owner_write", "tmp", "/tmp", "w", 207)
        self._test_rights("owner_write", "tmp", "/other", "r", 207)
        self._test_rights("owner_write", "tmp", "/other", "w", 403)

    def test_authenticated(self):
        self._test_rights("authenticated", "", "/", "r", 401)
        self._test_rights("authenticated", "", "/", "w", 401)
        self._test_rights("authenticated", "", "/tmp", "r", 401)
        self._test_rights("authenticated", "", "/tmp", "w", 401)
        self._test_rights("authenticated", "tmp", "/", "r", 207)
        self._test_rights("authenticated", "tmp", "/", "w", 207)
        self._test_rights("authenticated", "tmp", "/tmp", "r", 207)
        self._test_rights("authenticated", "tmp", "/tmp", "w", 207)
        self._test_rights("authenticated", "tmp", "/other", "r", 207)
        self._test_rights("authenticated", "tmp", "/other", "w", 207)

    def test_none(self):
        self._test_rights("none", "", "/", "r", 207)
        self._test_rights("none", "", "/", "w", 207)
        self._test_rights("none", "", "/tmp", "r", 207)
        self._test_rights("none", "", "/tmp", "w", 207)
        self._test_rights("none", "tmp", "/", "r", 207)
        self._test_rights("none", "tmp", "/", "w", 207)
        self._test_rights("none", "tmp", "/tmp", "r", 207)
        self._test_rights("none", "tmp", "/tmp", "w", 207)
        self._test_rights("none", "tmp", "/other", "r", 207)
        self._test_rights("none", "tmp", "/other", "w", 207)

    def test_from_file(self):
        rights_file_path = os.path.join(self.colpath, "rights")
        with open(rights_file_path, "w") as f:
            f.write("""\
[owner]
user: .+
collection: %(login)s(/.*)?
permission: rw
[custom]
user: .*
collection: custom(/.*)?
permission: r""")
        self.configuration["rights"]["file"] = rights_file_path
        self._test_rights("from_file", "", "/other", "r", 401)
        self._test_rights("from_file", "tmp", "/other", "r", 403)
        self._test_rights("from_file", "", "/custom/sub", "r", 404)
        self._test_rights("from_file", "tmp", "/custom/sub", "r", 404)
        self._test_rights("from_file", "", "/custom/sub", "w", 401)
        self._test_rights("from_file", "tmp", "/custom/sub", "w", 403)

    def test_custom(self):
        """Custom rights management."""
        self._test_rights("tests.custom.rights", "", "/", "r", 401)
        self._test_rights("tests.custom.rights", "", "/tmp", "r", 207)
