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

"""A failed hide is the same client error as a failed update."""

import json
import os

from radicale.tests import BaseTest


class TestSharingToggleError(BaseTest):

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

    def _post(self, action, payload, check=200):
        return self.request(
            "POST", "/.sharing/v1/map/%s" % action, json.dumps(payload),
            login="owner:ownerpw", content_type="application/json",
            accept="application/json", check=check)

    def test_hide_error_status_is_internal_error(self):
        collection = "/owner/cal.ics/"
        shared = "/user/cal.ics/"
        self.mkcalendar(collection, login="owner:ownerpw")
        self._post("create", {
            "User": "user",
            "PathMapped": collection,
            "PathOrToken": shared,
            "Permissions": "r",
            "Enabled": True,
            "Hidden": False,
        })

        def error(*_args, **_kwargs):
            return {"status": "error"}

        self.application._sharing.database_update_sharing = error
        status, _, answer = self._post(
            "hide", {"PathOrToken": shared}, check=None)
        assert status == 400
        assert "Internal Error" in answer
        parsed = json.loads(answer) if answer[:1] in "{[" else None
        assert parsed is None or parsed.get("Status") != "success"
