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

"""A shared principal keeps one principal-URL."""

import json
import os

from radicale import xmlutils
from radicale.tests import BaseTest

PROPFIND = """<?xml version="1.0" encoding="utf-8"?>
<D:propfind xmlns:D="DAV:">
  <D:prop><D:principal-URL/></D:prop>
</D:propfind>"""


class TestSharedPrincipalUrl(BaseTest):

    def setup_method(self):
        super().setup_method()
        htpasswd = os.path.join(self.colpath, ".htpasswd")
        with open(htpasswd, "w", encoding="utf-8") as handle:
            handle.write("owner:ownerpw\nuser:userpw\n")
        self.configure({
            "auth": {"type": "htpasswd", "htpasswd_filename": htpasswd,
                     "htpasswd_encryption": "plain", "delay": "0"},
            "rights": {"type": "owner_only"},
            "sharing": {
                "type": "csv",
                "collection_by_map": "True",
                "permit_create_map": "True",
            },
            "server": {"delay_on_error": "0"},
        })

    def _map(self):
        status, _, body = self.request(
            "POST", "/.sharing/v1/map/create",
            json.dumps({
                "User": "user",
                "PathMapped": "/owner/",
                "PathOrToken": "/user/principal/",
                "Permissions": "Rr",
                "Enabled": True,
                "Hidden": False,
            }),
            login="owner:ownerpw",
            content_type="application/json",
            HTTP_ACCEPT="application/json",
            check=None)
        assert status == 200, body
        for login in ("owner:ownerpw", "user:userpw"):
            status, _, body = self.request(
                "POST", "/.sharing/v1/map/enable",
                json.dumps({"PathOrToken": "/user/principal/"}),
                login=login,
                content_type="application/json",
                HTTP_ACCEPT="application/json",
                check=None)
            assert status == 200, body
        status, _, body = self.request(
            "POST", "/.sharing/v1/map/unhide",
            json.dumps({"PathOrToken": "/user/principal/"}),
            login="user:userpw",
            content_type="application/json",
            HTTP_ACCEPT="application/json",
            check=None)
        assert status == 200, body

    def _principal_href(self, path, depth, response_path):
        status, responses = self.propfind(
            path, PROPFIND, HTTP_DEPTH=depth, login="user:userpw")
        assert status == 207
        element = responses[response_path]["D:principal-URL"]
        assert element[0] == 200
        href = element[1].find(xmlutils.make_clark("D:href"))
        assert href is not None and href.text
        return href.text

    def test_shared_principal_url_matches_at_depth_0_and_1(self):
        self._map()
        direct = self._principal_href("/user/principal/", "0", "/user/principal/")
        listed = self._principal_href("/user/", "1", "/user/principal/")
        assert direct == "/user/principal/"
        assert listed == direct
        owner = self.propfind(
            "/owner/", PROPFIND, HTTP_DEPTH="0", login="owner:ownerpw")
        href = owner[1]["/owner/"]["D:principal-URL"][1].find(
            xmlutils.make_clark("D:href"))
        assert href is not None and href.text == "/owner/"
