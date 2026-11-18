# This file is part of Radicale - CalDAV and CardDAV server
# Copyright © 2026-2026 oliviasculley <olivia@sculley.dev>
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

"""Permission f does not hide a collection that R already allows."""

import os

from radicale.tests import BaseTest

PROPFIND_ONE = """<?xml version="1.0" encoding="utf-8"?>
<D:propfind xmlns:D="DAV:">
  <D:prop><D:displayname/></D:prop>
</D:propfind>"""


def _set_rights(test, text):
    path = os.path.join(test.colpath, "rights")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
    test.configure({
        "auth": {"type": "none", "delay": "0"},
        "rights": {"type": "from_file", "file": path},
        "server": {"delay_on_error": "0"},
    })


class TestFreeBusyKeepsCollectionRead(BaseTest):

    def test_propfind_root_with_read_and_freebusy(self):
        _set_rights(self, "[all]\nuser: .*\ncollection: .*\npermissions: Rf\n")
        status, _, body = self.request(
            "PROPFIND", "/", PROPFIND_ONE,
            HTTP_DEPTH="0", login="alice:secret", check=None)
        assert status == 207
        assert "response" in body
        assert "multistatus" in body
