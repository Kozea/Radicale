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
Radicale tests related to hook 'rabbitmq'

"""

import json
import logging
import os

import pytest

from radicale.tests import BaseTest
from radicale.tests.helpers import get_file_content


class TestHooks(BaseTest):
    """Tests with hooks."""

    # test for available pika module
    try:
        import pika
    except ImportError:
        has_pika = 0
    else:
        has_pika = 1

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
        self.configure({"hook": {"type": "rabbitmq",
                                 "dryrun": "True"}})

    @pytest.mark.skipif(has_pika == 0, reason="No pika module installed")
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
        found = False
        for line in caplog.messages:
            if line.find("notification_item: {'type': 'upsert'") != -1:
                found = True
        if (found is False):
            raise ValueError("Logging misses expected log line")

    @pytest.mark.skipif(has_pika == 0, reason="No pika module installed")
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
        found = False
        for line in caplog.messages:
            if line.find("notification_item: {'type': 'delete'") != -1:
                found = True
        if (found is False):
            raise ValueError("Logging misses expected log line")

    @pytest.mark.skipif(has_pika == 0, reason="No pika module installed")
    def test_shared_event_actor(self, caplog) -> None:
        caplog.set_level(logging.WARNING)

        htpasswd_file_path = os.path.join(self.colpath, ".htpasswd")
        encoding: str = self.configuration.get("encoding", "stock")
        with open(htpasswd_file_path, "w", encoding=encoding) as f:
            f.write("owner:ownerpw\nuser:userpw")

        self.configure({
            "auth": {"type": "htpasswd",
                     "htpasswd_filename": htpasswd_file_path,
                     "htpasswd_encryption": "plain"},
            "rights": {"type": "owner_only"},
            "sharing": {"type": "csv",
                        "collection_by_map": "True",
                        "permit_create_map": "True"}})

        path_owner = "/owner/calendar.ics/"
        path_shared = "/user/calendar-shared.ics/"

        self.mkcalendar(path_owner, login="owner:ownerpw")
        self.request("POST", "/.sharing/v1/map/create",
                     data=json.dumps({"User": "user",
                                      "PathMapped": path_owner,
                                      "PathOrToken": path_shared,
                                      "Permissions": "rw",
                                      "Enabled": True}),
                     content_type="application/json", accept="application/json",
                     login="owner:ownerpw", check=200)
        self.request("POST", "/.sharing/v1/map/enable",
                     data=json.dumps({"PathOrToken": path_shared}),
                     content_type="application/json", accept="application/json",
                     login="user:userpw", check=200)

        caplog.clear()
        event = get_file_content("event1.ics")
        path = path_shared + "event1.ics"

        self.put(path, event, login="user:userpw")
        assert any("notification_item: {'type': 'upsert'" in line and
                   "'actor': 'user'" in line
                   for line in caplog.messages)

        caplog.clear()
        self.request("DELETE", path, login="user:userpw", check=200)
        assert any("notification_item: {'type': 'delete'" in line and
                   "'actor': 'user'" in line
                   for line in caplog.messages)
