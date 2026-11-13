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

    def _publish_with_fake_pika(self, monkeypatch, failures):
        """Configure a live rabbitmq hook whose pika connection is fake."""
        import radicale.hook.rabbitmq as rabbitmq_hook

        published = []
        connections = []
        pending = list(failures)

        class Channel:
            def queue_declare(self, **kwargs):
                self.declared = kwargs

            def basic_publish(self, exchange, routing_key, body):
                if pending:
                    failure = pending.pop(0)
                    if failure is not None:
                        raise failure
                published.append(body)

        class Connection:
            def __init__(self, parameters):
                # URLParameters already validated the endpoint.
                assert parameters.host
                connections.append(parameters)
                self._channel = Channel()

            def channel(self):
                return self._channel

        monkeypatch.setattr(rabbitmq_hook.pika, "BlockingConnection", Connection)
        self.configure({
            "hook": {
                "type": "rabbitmq",
                "dryrun": "False",
                "rabbitmq_endpoint": "amqp://guest:guest@127.0.0.1:5672/%2F",
                "rabbitmq_topic": "radicale",
                "rabbitmq_queue_type": "classic",
            }})
        return published, connections

    @pytest.mark.skipif(has_pika == 0, reason="No pika module installed")
    def test_publish_sends_notification_json(self, monkeypatch) -> None:
        published, connections = self._publish_with_fake_pika(monkeypatch, [])
        self.mkcalendar("/calendar.ics/")
        event = get_file_content("event1.ics")
        self.put("/calendar.ics/event1.ics", event)
        assert len(connections) == 1
        assert len(published) == 1
        body = published[0]
        assert isinstance(body, bytes)
        parsed = json.loads(body.decode())
        assert body.decode() == json.dumps(parsed, sort_keys=True, indent=4)
        assert parsed["type"] == "upsert"
        assert "UID:event1" in parsed["content"]

    @pytest.mark.skipif(has_pika == 0, reason="No pika module installed")
    def test_channel_error_reconnects_and_publishes_once(self, monkeypatch) -> None:
        from pika.exceptions import ChannelWrongStateError

        published, connections = self._publish_with_fake_pika(
            monkeypatch, [ChannelWrongStateError()])
        self.mkcalendar("/calendar.ics/")
        self.put("/calendar.ics/event1.ics", get_file_content("event1.ics"))
        assert len(connections) == 2
        assert len(published) == 1
        parsed = json.loads(published[0].decode())
        assert parsed["type"] == "upsert"
        assert "UID:event1" in parsed["content"]

    @pytest.mark.skipif(has_pika == 0, reason="No pika module installed")
    def test_second_publish_failure_does_not_recurse(self, monkeypatch, caplog) -> None:
        from pika.exceptions import ChannelWrongStateError

        caplog.set_level(logging.ERROR)
        published, connections = self._publish_with_fake_pika(
            monkeypatch, [ChannelWrongStateError(), ChannelWrongStateError()])
        self.mkcalendar("/calendar.ics/")
        self.put("/calendar.ics/event1.ics", get_file_content("event1.ics"))
        assert published == []
        assert len(connections) == 2
        assert any(
            "An exception occurred during publishing hook notification item" in line
            for line in caplog.messages)
