# This file is part of Radicale Server - Calendar Server
# Copyright © 2018-2019 Unrud <unrud@outlook.com>
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
Test web plugin.

"""

import shutil
import tempfile

from radicale import Application, config

from .test_base import BaseTest


class TestBaseWebRequests(BaseTest):
    """Test web plugin."""

    def setup(self):
        self.configuration = config.load()
        self.colpath = tempfile.mkdtemp()
        self.configuration.update({
            "storage": {"filesystem_folder": self.colpath},
            # Disable syncing to disk for better performance
            "internal": {"filesystem_fsync": "False"}}, "test")
        self.application = Application(self.configuration)

    def teardown(self):
        shutil.rmtree(self.colpath)

    def test_internal(self):
        status, headers, _ = self.request("GET", "/.web")
        assert status == 302
        assert headers.get("Location") == ".web/"
        status, _, answer = self.request("GET", "/.web/")
        assert status == 200
        assert answer

    def test_none(self):
        self.configuration.update({"web": {"type": "none"}}, "test")
        self.application = Application(self.configuration)
        status, _, answer = self.request("GET", "/.web")
        assert status == 200
        assert answer
        status, _, answer = self.request("GET", "/.web/")
        assert status == 404

    def test_custom(self):
        """Custom web plugin."""
        self.configuration.update({
            "web": {"type": "tests.custom.web"}}, "test")
        self.application = Application(self.configuration)
        status, _, answer = self.request("GET", "/.web")
        assert status == 200
        assert answer == "custom"
