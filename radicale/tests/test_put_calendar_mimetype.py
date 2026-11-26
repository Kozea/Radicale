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

"""An empty text/calendar PUT is not stored as a subscription."""

import os

from radicale.tests import BaseTest

PROPFIND_TYPE = """<?xml version="1.0" encoding="utf-8"?>
<D:propfind xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav"
            xmlns:CS="http://calendarserver.org/ns/">
  <D:prop><D:resourcetype/></D:prop>
</D:propfind>"""

SUBSCRIBED_MKCOL = """<?xml version="1.0" encoding="utf-8" ?>
<mkcol xmlns="DAV:" xmlns:CS="http://calendarserver.org/ns/">
  <set><prop><resourcetype><collection/><CS:subscribed/></resourcetype></prop></set>
</mkcol>"""


def _tags(element):
    return [child.tag for child in element.iter()]


class TestCalendarMediaType(BaseTest):

    def setup_method(self):
        super().setup_method()
        path = os.path.join(self.colpath, "rights")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("[all]\nuser: .*\ncollection: .*\npermissions: RrWw\n")
        self.configure({
            "auth": {"type": "none", "delay": "0"},
            "rights": {"type": "from_file", "file": path},
            "server": {"delay_on_error": "0"},
        })

    def test_empty_text_calendar_put_is_rejected(self):
        status, _, body = self.request(
            "PUT", "/calendar.ics/", "",
            content_type="text/calendar", check=None)
        assert status == 400, body
        assert "Bad Request" in body
        assert self.request("GET", "/calendar.ics/", check=None)[0] == 404

    def test_mkcol_still_creates_a_subscribed_collection(self):
        status, _, body = self.request(
            "MKCOL", "/subscribed.ics/", SUBSCRIBED_MKCOL, check=None)
        assert status in (201, 200), body
        _, responses = self.propfind("/subscribed.ics/", PROPFIND_TYPE)
        tags = _tags(responses["/subscribed.ics/"]["D:resourcetype"][1])
        assert any("subscribed" in tag for tag in tags)
