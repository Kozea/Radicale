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

"""Free-busy PROPFIND stays on calendar collections."""

import os

from radicale.tests import BaseTest

PROPFIND_ONE = """<?xml version="1.0" encoding="utf-8"?>
<D:propfind xmlns:D="DAV:">
  <D:prop><D:displayname/></D:prop>
</D:propfind>"""

_LOGIN = "alice:secret"


def _set_rights(test, text):
    path = os.path.join(test.colpath, "rights")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
    test.configure({
        "auth": {"type": "none", "delay": "0"},
        "rights": {"type": "from_file", "file": path},
        "server": {"delay_on_error": "0"},
    })


def _text(body):
    if isinstance(body, bytes):
        return body.decode()
    return body


class TestFreeBusyKeepsCollectionRead(BaseTest):

    def test_propfind_root_with_read_and_freebusy(self):
        """R with f does not name the storage root in a free-busy PROPFIND."""
        _set_rights(self, "[all]\nuser: .*\ncollection: .*\npermissions: Rf\n")
        status, _, body = self.request(
            "PROPFIND", "/", PROPFIND_ONE,
            HTTP_DEPTH="0", login=_LOGIN, check=None)
        assert status == 207
        text = _text(body)
        assert "multistatus" in text
        assert "response" not in text

    def test_freebusy_propfind_lists_calendars_only(self):
        """A calendar answers; an address book and a plain collection do not."""
        # w creates a calendar or address book. W creates a plain collection.
        # Lowercase r is absent, so the request stays free-busy only.
        _set_rights(
            self, "[all]\nuser: .*\ncollection: .*\npermissions: RfwW\n")
        self.mkcalendar("/cal/", login=_LOGIN)
        self.create_addressbook("/book/", login=_LOGIN)
        self.mkcol("/plain/", login=_LOGIN)

        status, _, body = self.request(
            "PROPFIND", "/cal/", PROPFIND_ONE,
            HTTP_DEPTH="0", login=_LOGIN, check=None)
        assert status == 207
        assert "/cal/" in _text(body)

        status, _, body = self.request(
            "PROPFIND", "/book/", PROPFIND_ONE,
            HTTP_DEPTH="0", login=_LOGIN, check=None)
        assert status == 403
        assert "/book/" not in _text(body)

        status, _, body = self.request(
            "PROPFIND", "/plain/", PROPFIND_ONE,
            HTTP_DEPTH="0", login=_LOGIN, check=None)
        assert status == 207
        assert "response" not in _text(body)
        assert "/plain/" not in _text(body)

        status, _, _ = self.request(
            "PROPFIND", "/cal/", PROPFIND_ONE,
            HTTP_DEPTH="1", login=_LOGIN, check=None)
        assert status == 403
