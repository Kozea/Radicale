# This file is part of Radicale - CalDAV and CardDAV server
# Copyright © 2025-2025 Peter Bieringer <pb@bieringer.de>
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
Radicale tests related to hook 'email'

"""

import logging
import os

from radicale.tests import BaseTest
from radicale.tests.helpers import get_file_content


class TestHooks(BaseTest):
    """Tests with hooks."""

    def setup_method(self) -> None:
        BaseTest.setup_method(self)
        rights_file_path = os.path.join(self.colpath, "rights")
        with open(rights_file_path, "w") as f:
            f.write("""\
[permit delete collection]
user: .*
collection: test-permit-delete
permissions: RrWwD

[forbid delete collection]
user: .*
collection: test-forbid-delete
permissions: RrWwd

[permit overwrite collection]
user: .*
collection: test-permit-overwrite
permissions: RrWwO

[forbid overwrite collection]
user: .*
collection: test-forbid-overwrite
permissions: RrWwo

[allow all]
user: .*
collection: .*
permissions: RrWw""")
        self.configure({"rights": {"file": rights_file_path,
                                   "type": "from_file"}})
        self.configure({"hook": {"type": "email",
                                 "dryrun": "True"}})

    def test_add_event(self, caplog) -> None:
        caplog.set_level(logging.WARNING)
        """Add an event."""
        self.mkcalendar("/calendar.ics/")
        event = get_file_content("event1.ics")
        path = "/calendar.ics/event1.ics"
        self.put(path, event)
        _, headers, answer = self.request("GET", path, check=200)
        assert "ETag" in headers
        assert headers["Content-Type"] == "text/calendar; charset=utf-8"
        assert "VEVENT" in answer
        assert "Event" in answer
        assert "UID:event" in answer
        found = 0
        for line in caplog.messages:
            if line.find("notification_item: {'type': 'upsert'") != -1:
                found = found | 1
            if line.find("to_addresses=['janedoe@example.com']") != -1:
                found = found | 2
            if line.find("to_addresses=['johndoe@example.com']") != -1:
                found = found | 4
        if (found != 7):
            raise ValueError("Logging misses expected log lines, found=%d", found)

    def test_delete_event(self, caplog) -> None:
        caplog.set_level(logging.WARNING)
        """Delete an event."""
        self.mkcalendar("/calendar.ics/")
        event = get_file_content("event1.ics")
        path = "/calendar.ics/event1.ics"
        self.put(path, event)
        _, responses = self.delete(path)
        assert responses[path] == 200
        _, answer = self.get("/calendar.ics/")
        assert "VEVENT" not in answer
        found = 0
        for line in caplog.messages:
            if line.find("notification_item: {'type': 'delete'") != -1:
                found = found | 1
            if line.find("to_addresses=['janedoe@example.com']") != -1:
                found = found | 2
            if line.find("to_addresses=['johndoe@example.com']") != -1:
                found = found | 4
        if (found != 7):
            raise ValueError("Logging misses expected log lines, found=%d", found)
