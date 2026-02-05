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
import re
from datetime import datetime, timedelta

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

    def _future_date_timestamp(self) -> str:
        """Return a date timestamp for a future date."""
        future_date = datetime.now() + timedelta(days=1)
        return future_date.strftime("%Y%m%dT%H%M%S")

    def _past_date_timestamp(self) -> str:
        past_date = datetime.now() - timedelta(days=1)
        return past_date.strftime("%Y%m%dT%H%M%S")

    def _replace_end_date_in_event(self, event: str, new_date: str) -> str:
        """Replace the end date in an event string."""
        return re.sub(r"DTEND;TZID=Europe/Paris:\d{8}T\d{6}",
                      f"DTEND;TZID=Europe/Paris:{new_date}", event)

    def test_add_event_with_future_end_date(self, caplog) -> None:
        caplog.set_level(logging.WARNING)
        """Add an event."""
        self.mkcalendar("/calendar.ics/")
        event = get_file_content("event1.ics")
        event = self._replace_end_date_in_event(event, self._future_date_timestamp())
        path = "/calendar.ics/event1.ics"
        self.put(path, event)
        _, headers, answer = self.request("GET", path, check=200)
        assert "ETag" in headers
        assert headers["Content-Type"] == "text/calendar; charset=utf-8"
        assert "VEVENT" in answer
        assert "Event" in answer
        assert "UID:event" in answer

        logs = caplog.messages
        # Should have a log saying the notification item was received
        assert len([log for log in logs if "received notification_item: {'type': 'upsert'," in log]) == 1
        # Should NOT have a log saying that no email is sent (email won't actually be sent due to dryrun)
        assert len([log for log in logs if "skipping notification for event: event1" in log]) == 0

    def test_add_event_with_past_end_date(self, caplog) -> None:
        caplog.set_level(logging.WARNING)
        """Add an event."""
        self.mkcalendar("/calendar.ics/")
        event = get_file_content("event1.ics")
        event = self._replace_end_date_in_event(event, self._past_date_timestamp())
        path = "/calendar.ics/event1.ics"
        self.put(path, event)
        _, headers, answer = self.request("GET", path, check=200)
        assert "ETag" in headers
        assert headers["Content-Type"] == "text/calendar; charset=utf-8"
        assert "VEVENT" in answer
        assert "Event" in answer
        assert "UID:event" in answer

        logs = caplog.messages
        # Should have a log saying the notification item was received
        assert len([log for log in logs if "received notification_item: {'type': 'upsert'," in log]) == 1
        # Should have a log saying that no email is sent due to past end date
        assert len([log for log in logs if "Event end time is in the past, skipping notification for event: event1" in log]) == 1

    def test_delete_event_with_future_end_date(self, caplog) -> None:
        caplog.set_level(logging.WARNING)
        """Delete an event."""
        self.mkcalendar("/calendar.ics/")
        event = get_file_content("event1.ics")
        event = self._replace_end_date_in_event(event, self._future_date_timestamp())
        path = "/calendar.ics/event1.ics"
        self.put(path, event)
        _, responses = self.delete(path)
        assert responses[path] == 200
        _, answer = self.get("/calendar.ics/")
        assert "VEVENT" not in answer

        logs = caplog.messages
        # Should have a log saying the notification item was received
        assert len([log for log in logs if "received notification_item: {'type': 'delete'," in log]) == 1
        # Should NOT have a log saying that no email is sent (email won't actually be sent due to dryrun)
        assert len([log for log in logs if "skipping notification for event: event1" in log]) == 0

    def test_delete_event_with_past_end_date(self, caplog) -> None:
        caplog.set_level(logging.WARNING)
        """Delete an event."""
        self.mkcalendar("/calendar.ics/")
        event = get_file_content("event1.ics")
        event = self._replace_end_date_in_event(event, self._past_date_timestamp())
        path = "/calendar.ics/event1.ics"
        self.put(path, event)
        _, responses = self.delete(path)
        assert responses[path] == 200
        _, answer = self.get("/calendar.ics/")
        assert "VEVENT" not in answer

        logs = caplog.messages
        # Should have a log saying the notification item was received
        assert len([log for log in logs if "received notification_item: {'type': 'delete'," in log]) == 1
        # Should have a log saying that no email is sent due to past end date
        assert len([log for log in logs if "Event end time is in the past, skipping notification for event: event1" in log]) == 1
