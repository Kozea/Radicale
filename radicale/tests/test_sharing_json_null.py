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

"""JSON null in a sharing update is a client error or a clear, not HTTP 500."""

import json
import os

from radicale.tests import BaseTest


class TestSharingJsonNull(BaseTest):

    def setup_method(self):
        super().setup_method()
        accounts = os.path.join(self.colpath, "accounts")
        with open(accounts, "w", encoding="utf-8") as handle:
            handle.write("owner:ownerpw\nuser:userpw\n")
        self.configure({
            "auth": {"type": "htpasswd",
                     "htpasswd_filename": accounts,
                     "htpasswd_encryption": "plain"},
            "rights": {"type": "owner_only"},
            "sharing": {"type": "csv",
                        "collection_by_map": "true",
                        "permit_create_map": "true"},
        })

    def _post(self, path, payload):
        return self.request(
            "POST", path, json.dumps(payload),
            login="owner:ownerpw", content_type="application/json",
            accept="application/json", check=None)

    def _share_row(self, path):
        status, _, answer = self._post(
            "/.sharing/v1/map/list", {"PathOrToken": path})
        assert status == 200, answer
        body = json.loads(answer)
        assert body["Status"] == "success"
        assert body["Lines"] == 1
        return body["Content"][0]

    def test_null_path_is_rejected_and_null_fields_clear_an_existing_share(self):
        status, _, answer = self._post(
            "/.sharing/v1/map/update",
            {"PathOrToken": None, "Hidden": True})
        assert status == 400
        assert "Invalid value for PathOrToken" in answer
        assert "server error" not in answer.lower()

        mapped = "/owner/calendar.ics/"
        shared = "/user/quiet-null.ics/"
        self.mkcalendar(mapped, login="owner:ownerpw")
        status, _, answer = self._post("/.sharing/v1/map/create", {
            "User": "user",
            "PathMapped": mapped,
            "PathOrToken": shared,
            "Permissions": "rw",
            "Enabled": True,
        })
        assert status == 200, answer
        assert json.loads(answer)["Status"] == "success"

        status, _, answer = self._post("/.sharing/v1/map/update", {
            "PathOrToken": shared,
            "Properties": {"D:displayname": "Quiet"},
            "Actions": {"config": {"view": "freebusy"}},
        })
        assert status == 200, answer
        row = self._share_row(shared)
        assert row["Properties"]["D:displayname"] == "Quiet"
        assert row["Actions"]["config"]["view"] == "freebusy"

        status, _, answer = self._post("/.sharing/v1/map/update", {
            "PathOrToken": shared,
            "Properties": None,
        })
        assert status == 200, answer
        assert "server error" not in answer.lower()
        row = self._share_row(shared)
        assert row["Properties"] == {}
        assert row["Actions"]["config"]["view"] == "freebusy"

        status, _, answer = self._post("/.sharing/v1/map/update", {
            "PathOrToken": shared,
            "Actions": None,
        })
        assert status == 200, answer
        assert "server error" not in answer.lower()
        row = self._share_row(shared)
        assert row["Properties"] == {}
        assert row["Actions"] == {}
