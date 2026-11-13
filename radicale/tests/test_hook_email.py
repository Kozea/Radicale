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

import pytest

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

    def _future_date(self) -> str:
        """Return a date for a future date."""
        future_date = datetime.now() + timedelta(days=1)
        return future_date.strftime("%Y%m%d")

    def _past_date_timestamp(self) -> str:
        past_date = datetime.now() - timedelta(days=1)
        return past_date.strftime("%Y%m%dT%H%M%S")

    def _past_date(self) -> str:
        past_date = datetime.now() - timedelta(days=1)
        return past_date.strftime("%Y%m%d")

    def _replace_end_date_in_event(self, event: str, new_date: str) -> str:
        """Replace the end date in an event string."""
        return re.sub(r"DTEND;TZID=Europe/Paris:\d{8}T\d{6}",
                      f"DTEND;TZID=Europe/Paris:{new_date}", event)

    def _replace_end_onlydate_in_event(self, event: str, new_date: str) -> str:
        """Replace the end date in an event string."""
        return re.sub(r"DTEND;VALUE=DATE:\d{8}",
                      f"DTEND;VALUE=DATE:{new_date}", event)

    def test_add_event_with_future_end_date(self, caplog) -> None:
        caplog.set_level(logging.INFO)
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
        assert len([log for log in logs if "New event detected, sending notifications to all attendees: event1" in log]) == 1

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
        caplog.set_level(logging.INFO)
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
        assert len([log for log in logs if "New event detected, sending notifications to all attendees: event1" in log]) == 1

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

    def test_delete_event_with_future_end_onlydate(self, caplog) -> None:
        caplog.set_level(logging.INFO)
        """Delete an event."""
        self.mkcalendar("/calendar.ics/")
        event = get_file_content("event_issue1917_1.ics")
        event = self._replace_end_onlydate_in_event(event, self._future_date())
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
        assert len([log for log in logs if "New event detected, sending notifications to all attendees: event1" in log]) == 1

    def test_delete_event_with_past_onlyend_date(self, caplog) -> None:
        caplog.set_level(logging.WARNING)
        """Delete an event."""
        self.mkcalendar("/calendar.ics/")
        event = get_file_content("event_issue1917_1.ics")
        event = self._replace_end_onlydate_in_event(event, self._past_date())
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

    def test_add_event_with_future_mass1_end_date(self, caplog) -> None:
        self.configure({"hook": {"type": "email",
                                 "mass_email": "True",
                                 "dryrun": "True"}})

        caplog.set_level(logging.INFO)
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
        assert len([log for log in logs if "New event detected, sending notifications to all attendees: event1" in log]) == 1
        assert len([log for log in logs if "Hello everyone" in log]) == 1

    def test_add_event_with_future_mass2_end_date(self, caplog) -> None:
        self.configure({"hook": {"type": "email",
                                 "mass_email": "True",
                                 "dryrun": "True"}})

        caplog.set_level(logging.INFO)
        """Add an event."""
        self.mkcalendar("/calendar.ics/")
        event = get_file_content("event1a1.ics")
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
        assert len([log for log in logs if "New event detected, sending notifications to all attendees: event1" in log]) == 1
        assert len([log for log in logs if "Hello everyone" in log]) == 0

    def test_smtp_password_file(self) -> None:
        from radicale.hook.email import Hook

        secret = os.path.join(self.colpath, "smtp_password")
        self.configure({
            "hook": {
                "type": "email",
                "smtp_server": "localhost",
                "smtp_password": "inline-secret",
                "smtp_password_file": secret,
                "dryrun": "True",
            }
        })
        hook = Hook(self.configuration)
        assert hook.email_config.password == "inline-secret"
        with open(secret, "w") as f:
            f.write("file-secret\n")
        hook = Hook(self.configuration)
        assert hook.email_config.password == "file-secret"

    def test_smtp_port_config(self) -> None:
        # check for invalid port
        logging.info("Try invalid port: 0")
        try:
            self.configure({
                "hook": {
                    "type": "email",
                    "smtp_server": "localhost",
                    "smtp_port": 0,
                    "smtp_password": "inline-secret",
                    "dryrun": "True",
                }
            })
        except RuntimeError as e:
            logging.info("Exception: %s", str(e))
        else:
            raise

        # check for invalid port
        logging.info("Try invalid port: 65535")
        try:
            self.configure({
                "hook": {
                    "type": "email",
                    "smtp_server": "localhost",
                    "smtp_port": 65535,
                    "smtp_password": "inline-secret",
                    "dryrun": "True",
                }
            })
        except RuntimeError as e:
            logging.info("Exception: %s", str(e))
        else:
            raise

        # check for valid port
        logging.info("Try valid port")
        self.configure({
            "hook": {
                "type": "email",
                "smtp_server": "localhost",
                "smtp_port": 25,
                "smtp_password": "inline-secret",
                "dryrun": "True",
            }
        })

    def _install_fake_smtp(self, monkeypatch, boom=False):
        import smtplib

        import radicale.hook.email as email_hook

        fail = boom

        class FakeSMTP:
            created = []
            messages = []

            def __init__(self, host=None, port=None, context=None, **kwargs):
                self.host = host
                self.port = port
                self.context = context
                self.starttls_context = None
                FakeSMTP.created.append(self)

            def ehlo(self):
                return (250, b"ok")

            def starttls(self, context=None, **kwargs):
                self.starttls_context = context
                return (220, b"ready")

            def login(self, user=None, password=None):
                return (235, b"ok")

            def sendmail(self, from_addr, to_addrs, msg):
                if fail:
                    raise smtplib.SMTPException("send failed")
                FakeSMTP.messages.append((from_addr, list(to_addrs), msg))
                return {}

            def quit(self):
                return (221, b"bye")

        FakeSMTP.created = []
        FakeSMTP.messages = []
        monkeypatch.setattr(email_hook.smtplib, "SMTP", FakeSMTP)
        monkeypatch.setattr(email_hook.smtplib, "SMTP_SSL", FakeSMTP)
        return FakeSMTP

    def _email_hook(self, security="none", verify_mode="REQUIRED", dryrun="False"):
        self.configure({
            "hook": {
                "type": "email",
                "dryrun": dryrun,
                "smtp_server": "127.0.0.1",
                "smtp_port": "2525",
                "smtp_security": security,
                "smtp_ssl_verify_mode": verify_mode,
                "from_email": "calendar@example.com",
                "mass_email": "False",
            }})

    def _future_event(self, summary="Event") -> str:
        event = get_file_content("event1.ics")
        event = self._replace_end_date_in_event(event, self._future_date_timestamp())
        return event.replace("SUMMARY:Event", "SUMMARY:" + summary, 1)

    def test_send_includes_attendee_and_subject(self, monkeypatch) -> None:
        fake = self._install_fake_smtp(monkeypatch)
        self._email_hook()
        self.mkcalendar("/calendar.ics/")
        self.put("/calendar.ics/event1.ics", self._future_event())
        assert fake.messages
        for _sender, recipients, message in fake.messages:
            assert "You have been added to an event" in message
        recipients = [address for _sender, addresses, _message in fake.messages for address in addresses]
        assert "janedoe@example.com" in recipients
        assert "johndoe@example.com" in recipients
        sent = self.application._hook.email_config._send_email(
            "subject line", "body", [type("A", (), {"email": "janedoe@example.com"})()])
        assert sent is True

    def test_smtp_exception_returns_false(self, monkeypatch) -> None:
        self._install_fake_smtp(monkeypatch, boom=True)
        self._email_hook()
        sent = self.application._hook.email_config._send_email(
            "subject line", "body", [type("A", (), {"email": "janedoe@example.com"})()])
        assert sent is False

    def test_empty_smtp_security_raises(self) -> None:
        self._email_hook(security="")
        with pytest.raises(ValueError, match="SMTP security type cannot be empty"):
            self.application._hook.email_config._send_email(
                "subject line", "body", [type("A", (), {"email": "janedoe@example.com"})()])

    def test_starttls_and_tls_verify_mode(self, monkeypatch) -> None:
        import ssl

        expected = {
            "REQUIRED": ssl.CERT_REQUIRED,
            "OPTIONAL": ssl.CERT_OPTIONAL,
            "NONE": ssl.CERT_NONE,
        }
        for security in ("starttls", "tls"):
            for mode, verify in expected.items():
                fake = self._install_fake_smtp(monkeypatch)
                self._email_hook(security=security, verify_mode=mode)
                self.mkcalendar("/calendar.ics/", check=None)
                self.put("/calendar.ics/event1.ics",
                         self._future_event(summary="Mode " + mode + " " + security),
                         check=None)
                assert fake.created
                contexts = []
                for client in fake.created:
                    if client.starttls_context is not None:
                        contexts.append(client.starttls_context)
                    if client.context is not None:
                        contexts.append(client.context)
                assert contexts
                assert all(context.verify_mode == verify for context in contexts)

    def test_event_update_uses_updated_template(self, monkeypatch) -> None:
        fake = self._install_fake_smtp(monkeypatch)
        self._email_hook()
        self.mkcalendar("/calendar.ics/")
        self.put("/calendar.ics/event1.ics", self._future_event())
        fake.messages.clear()
        self.put("/calendar.ics/event1.ics", self._future_event(summary="Event moved"), check=None)
        assert fake.messages
        assert any("An event you are invited to has been updated" in message
                   for _sender, _recipients, message in fake.messages)
        recipients = [address for _sender, addresses, _message in fake.messages for address in addresses]
        assert "janedoe@example.com" in recipients

    def test_non_calendar_item_sends_nothing(self, monkeypatch) -> None:
        fake = self._install_fake_smtp(monkeypatch)
        self._email_hook()
        self.create_addressbook("/contacts.vcf/")
        self.put("/contacts.vcf/contact1.vcf", get_file_content("contact1.vcf"))
        assert fake.messages == []
        assert fake.created == []
