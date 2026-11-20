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

"""A share whose collection folder was removed on disk.

Reads of the missing collection are 404. A write that still needs that
folder is 409. OPTIONS never looks the collection up, so it stays 200.
PROPPATCH stays 207 because the share property overlay is stored on the
share. DELETE of a mapped collection stays 403. POST stays 405. MKCOL
stays 403 and MKCALENDAR stays 409. None of these answers are 500.
"""

import json
import os
import shutil

from radicale.tests import BaseTest
from radicale.tests.helpers import get_file_content

PROPFIND_ONE = """<?xml version="1.0" encoding="utf-8"?>
<D:propfind xmlns:D="DAV:">
  <D:prop><D:displayname/></D:prop>
</D:propfind>"""

REPORT_ONE = """<?xml version="1.0" encoding="utf-8" ?>
<C:calendar-query xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
  <D:prop><D:getetag /></D:prop>
  <C:filter>
    <C:comp-filter name="VCALENDAR">
      <C:comp-filter name="VEVENT" />
    </C:comp-filter>
  </C:filter>
</C:calendar-query>"""

PROPPATCH_ONE = """<?xml version="1.0" encoding="utf-8"?>
<D:propertyupdate xmlns:D="DAV:">
  <D:set>
    <D:prop>
      <I:calendar-color xmlns:I="http://apple.com/ns/ical/">#BADA55</I:calendar-color>
    </D:prop>
  </D:set>
</D:propertyupdate>"""

EXTRA = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Radicale//EN
BEGIN:VEVENT
UID:extra-share-item
SUMMARY:Extra
DTSTART:20130902T160000Z
DTEND:20130902T170000Z
END:VEVENT
END:VCALENDAR
"""

NOT_FOUND = "The requested resource could not be found."


class TestShareOfDeletedCollection(BaseTest):

    def test_methods_after_collection_folder_is_removed(self) -> None:
        htpasswd = os.path.join(self.colpath, ".htpasswd")
        with open(htpasswd, "w", encoding="utf-8") as handle:
            handle.write("owner:ownerpw\nuser:userpw\n")
        self.configure({
            "auth": {"type": "htpasswd",
                     "htpasswd_filename": htpasswd,
                     "htpasswd_encryption": "plain",
                     "delay": "0"},
            "sharing": {"type": "csv",
                        "database_path": "",
                        "permit_create_map": True,
                        "collection_by_map": "True"},
            "rights": {"type": "owner_only"},
            "server": {"delay_on_error": "0"},
        })
        owner = "owner:ownerpw"
        user = "user:userpw"
        col1 = "/owner/one.ics/"
        col2 = "/owner/two.ics/"
        share1 = "/user/one.ics/"
        share2 = "/user/two.ics/"
        self.mkcalendar(col1, login=owner)
        self.mkcalendar(col2, login=owner)
        self.put(col1 + "event1.ics", get_file_content("event1.ics"),
                 login=owner)
        self.put(col2 + "event2.ics", get_file_content("event2.ics"),
                 login=owner)
        for mapped, shared in ((col1, share1), (col2, share2)):
            self._share(owner, user, mapped, shared)

        def call(method, path, data=None, **extra):
            status, headers, body = self.request(
                method, path, data, login=user, check=None, **extra)
            if isinstance(body, bytes):
                text = body.decode()
            else:
                text = body or ""
            return status, headers, text

        status, headers, _ = call("OPTIONS", share1)
        assert status == 200 and "GET" in headers["Allow"]
        status, _, text = call("GET", share1)
        assert status == 200 and "UID:event1" in text
        status, _, _ = call("HEAD", share1)
        assert status == 200
        status, _, text = call(
            "PROPFIND", share1, PROPFIND_ONE, HTTP_DEPTH="0")
        assert status == 207 and "multistatus" in text
        status, _, text = call("REPORT", share1, REPORT_ONE)
        assert status == 207 and "multistatus" in text
        status, _, text = call("PROPPATCH", share1, PROPPATCH_ONE)
        assert status == 207 and "multistatus" in text
        status, _, _ = call("PUT", share1 + "extra.ics", EXTRA)
        assert status == 201
        status, _, text = call("POST", share1, "")
        assert status == 405 and "not allowed" in text
        status, _, _ = call("MKCOL", share1)
        assert status == 403
        status, _, _ = call("MKCALENDAR", share1)
        assert status == 409
        status, _, text = call("DELETE", share1)
        assert status == 403 and "forbidden" in text

        status, _, _ = call(
            "MOVE", share1 + "event1.ics",
            HTTP_DESTINATION="http://127.0.0.1" + share2 + "event1.ics")
        assert status == 201
        status, _, _ = call(
            "MOVE", share2 + "event2.ics",
            HTTP_DESTINATION="http://127.0.0.1" + share1 + "event2.ics")
        assert status == 201
        status, _, text = call("GET", share2 + "event1.ics")
        assert status == 200 and "UID:event1" in text
        status, _, text = call("GET", share1 + "event2.ics")
        assert status == 200 and "UID:event2" in text

        folder = os.path.join(
            self.colpath, "collection-root", "owner", "one.ics")
        assert os.path.isdir(folder)
        shutil.rmtree(folder)

        status, headers, _ = call("OPTIONS", share1)
        assert status == 200 and "GET" in headers["Allow"]
        status, _, text = call("GET", share1)
        assert status == 404 and text == NOT_FOUND
        status, _, text = call("HEAD", share1)
        assert status == 404 and text == ""
        status, _, text = call(
            "PROPFIND", share1, PROPFIND_ONE, HTTP_DEPTH="0")
        assert status == 404 and text == NOT_FOUND
        status, _, text = call("REPORT", share1, REPORT_ONE)
        assert status == 404 and text == NOT_FOUND
        status, _, text = call("PROPPATCH", share1, PROPPATCH_ONE)
        assert status == 207 and "multistatus" in text
        assert not os.path.isdir(folder)
        status, _, text = call("PUT", share1 + "extra.ics", EXTRA)
        assert status == 409 and "Conflict" in text
        status, _, text = call("POST", share1, "")
        assert status == 405 and "not allowed" in text
        status, _, _ = call("MKCOL", share1)
        assert status == 403
        status, _, _ = call("MKCALENDAR", share1)
        assert status == 409
        status, _, text = call("DELETE", share1)
        assert status == 403 and "forbidden" in text

        status, _, text = call(
            "MOVE", share1 + "event1.ics",
            HTTP_DESTINATION="http://127.0.0.1" + share2 + "event1.ics")
        assert status == 404 and text == NOT_FOUND
        status, _, text = call(
            "MOVE", share2 + "event1.ics",
            HTTP_DESTINATION="http://127.0.0.1" + share1 + "event1.ics")
        assert status == 409 and "Conflict" in text

    def _share(self, owner, user, mapped, shared) -> None:
        _, _, answer = self.request(
            "POST", "/.sharing/v1/map/create",
            json.dumps({
                "User": "user",
                "PathMapped": mapped,
                "PathOrToken": shared,
                "Permissions": "rw",
                "Enabled": True,
                "Hidden": False,
            }),
            login=owner, content_type="application/json",
            accept="application/json", check=200)
        assert json.loads(answer)["Status"] == "success"
        _, _, answer = self.request(
            "POST", "/.sharing/v1/map/update",
            json.dumps({"PathOrToken": shared, "Enabled": True, "Hidden": False}),
            login=user, content_type="application/json",
            accept="application/json", check=200)
        assert json.loads(answer)["Status"] == "success"
