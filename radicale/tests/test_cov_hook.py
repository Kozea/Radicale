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

"""Outcome tests for hook notification and iTIP mail."""

import email
import logging
import sys
from datetime import datetime, timedelta

import pytest

from radicale.hook import HookNotificationItem, HookNotificationItemTypes
from radicale.tests import BaseTest


def _freeze_auth_clock(monkeypatch, nanos):
    import radicale.auth as auth_module

    clock = {"ns": nanos}
    monkeypatch.setattr(auth_module.time, "time_ns", lambda: clock["ns"])
    return clock


def _event_ics(uid="evt-1", summary="Title", sequence=1,
               organizer="mailto:owner@example.com", attendees=None,
               dtend=True, recurrence=False, method=None, dtstamp=True):
    if attendees is None:
        attendees = [("alice@example.com", "Alice")]
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Radicale test//EN"]
    if method:
        lines.append("METHOD:%s" % method)
    lines.extend(["BEGIN:VEVENT", "UID:%s" % uid])
    if dtstamp:
        lines.append("DTSTAMP:20300101T000000Z")
    lines.append("DTSTART:20300101T110000Z")
    if dtend:
        lines.append("DTEND:20300101T120000Z")
    if recurrence:
        lines.append("RECURRENCE-ID:20300101T110000Z")
    lines.append("SUMMARY:%s" % summary)
    if sequence is not None:
        lines.append("SEQUENCE:%s" % sequence)
    if organizer is not None:
        lines.append("ORGANIZER:%s" % organizer)
    for address, name in attendees:
        if name:
            lines.append("ATTENDEE;CN=%s:mailto:%s" % (name, address))
        else:
            lines.append("ATTENDEE:%s" % address)
    lines.extend(["END:VEVENT", "END:VCALENDAR"])
    return "\n".join(lines) + "\n"


def _mail_text(raw):
    """Headers plus every decoded MIME part.

    iTIP calendar parts are base64, so METHOD and SEQUENCE are not
    visible in the raw SMTP payload.
    """
    parsed = email.message_from_string(raw)
    chunks = [raw]
    for part in parsed.walk():
        payload = part.get_payload(decode=True)
        if not payload:
            continue
        charset = part.get_content_charset() or "utf-8"
        chunks.append(payload.decode(charset, "replace"))
    return "\n".join(chunks)


def _todo_ics():
    return "\n".join([
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "BEGIN:VTODO",
        "UID:todo-1",
        "SUMMARY:Task",
        "END:VTODO",
        "END:VCALENDAR",
        "",
    ])


class TestHookItems:
    """Path cleanup and content-type predicates."""

    def _item(self, path, content_type=None, content=None, uid=None,
              new_content=None, old_content=None):
        return HookNotificationItem(
            HookNotificationItemTypes.UPSERT, path, content=content,
            content_type=content_type, uid=uid, new_content=new_content,
            old_content=old_content)

    def test_point_is_empty_until_the_second_component(self):
        assert self._item("/").point == ""
        assert self._item("/user").point == ""
        assert self._item("/user/cal").point == "user/cal"
        assert self._item("/user/cal/").point == "user/cal"
        assert self._item("/user/cal/event.ics").point == "user/cal"

    def test_content_type_and_replacement_boundaries(self):
        assert self._item("/user/cal", content_type=None).is_calendar_item is False
        assert self._item("/user/cal", content_type="").is_calendar_item is False
        assert self._item("/user/cal", content_type=" vcalendar ").is_calendar_item is True
        assert self._item("/user/cal", content_type="vcalendarx").is_calendar_item is False
        assert self._item("/user/cal", content_type="").is_card_item is False
        assert self._item("/user/cal", content_type=" vcard ").is_card_item is True
        assert self._item("/user/cal", content_type="vcardx").is_card_item is False
        assert self._item("/user/cal", content_type="").is_addressbook_item is False
        assert self._item("/user/cal", content_type=" vaddressbook ").is_addressbook_item is True
        assert self._item("/user/cal", content_type="vaddressbookx").is_addressbook_item is False
        assert self._item("/user/cal", old_content=None).replaces_existing_item is False
        assert self._item("/user/cal", old_content="").replaces_existing_item is True

    def test_content_falls_back_and_json_includes_it(self):
        import json

        legacy = self._item("/user/cal", content="legacy", uid="uid",
                            new_content="new", old_content="old")
        assert legacy.content == "legacy"
        payload = json.loads(legacy.to_json())
        assert payload["content"] == "legacy"
        assert payload["point"] == "user/cal"
        assert self._item("/user/cal", uid="uid", new_content="new").content == "uid"
        assert self._item("/user/cal", new_content="new", old_content="old").content == "new"
        assert self._item("/user/cal", old_content="old").content == "old"


class TestRabbitmqGaps(BaseTest):
    def test_import_error_names_pika(self):
        saved = {}
        for name in list(sys.modules):
            if name == "radicale.hook.rabbitmq" or name == "pika" or name.startswith("pika."):
                saved[name] = sys.modules.pop(name)
        sys.modules["pika"] = None
        try:
            with pytest.raises(ImportError, match="pika"):
                import radicale.hook.rabbitmq  # noqa: F401
        finally:
            sys.modules.pop("pika", None)
            sys.modules.pop("radicale.hook.rabbitmq", None)
            sys.modules.update(saved)

    def test_notify_ignores_objects_that_are_not_notification_items(self, caplog):
        caplog.set_level(logging.WARNING)
        self.configure({"hook": {
            "type": "rabbitmq",
            "dryrun": "True",
            "rabbitmq_endpoint": "amqp://127.0.0.1/",
            "rabbitmq_topic": "radicale",
            "rabbitmq_queue_type": "classic",
        }})
        self.application._hook.notify(object())
        assert "DRY-RUN _notify" not in caplog.text


class TestEmailParser:
    """Enum parsing and vobject property edges."""

    def test_security_and_verify_enums_reject_near_misses(self):
        from radicale.hook.email import (SMTP_SECURITY_TYPE_ENUM,
                                         SMTP_SSL_VERIFY_MODE_ENUM,
                                         extract_email)

        assert SMTP_SECURITY_TYPE_ENUM.from_string("starttls") is SMTP_SECURITY_TYPE_ENUM.STARTTLS
        assert SMTP_SECURITY_TYPE_ENUM.from_string("") is SMTP_SECURITY_TYPE_ENUM.EMPTY
        assert SMTP_SECURITY_TYPE_ENUM.from_string("tls") is SMTP_SECURITY_TYPE_ENUM.TLS
        with pytest.raises(ValueError, match="Invalid security type"):
            SMTP_SECURITY_TYPE_ENUM.from_string("start-tls")
        assert SMTP_SSL_VERIFY_MODE_ENUM.from_string("REQUIRED") is SMTP_SSL_VERIFY_MODE_ENUM.REQUIRED
        assert SMTP_SSL_VERIFY_MODE_ENUM.from_string("") is SMTP_SSL_VERIFY_MODE_ENUM.EMPTY
        assert SMTP_SSL_VERIFY_MODE_ENUM.from_string("NONE") is SMTP_SSL_VERIFY_MODE_ENUM.NONE
        with pytest.raises(ValueError, match="Invalid SSL verify mode"):
            SMTP_SSL_VERIFY_MODE_ENUM.from_string("required")
        assert extract_email(None) is None
        assert extract_email("") is None
        assert extract_email("A@B.com") == "a@b.com"
        assert extract_email("not-an-email") is None

    def test_component_properties_templates_and_config_repr(self):
        import vobject

        from radicale.hook.email import (Alarm, Attendee, Calendar,
                                         ContentLine, DaylightTimezone,
                                         EmailConfig, Event, MessageTemplate,
                                         StandardTimezone, TimeWithTimezone,
                                         Timezone)

        with pytest.raises(ValueError, match="must be a vobject"):
            Event(object())
        with pytest.raises(ValueError, match="Invalid component type"):
            Event(vobject.base.Component("VTODO"))

        def line(name, value, params=None):
            return vobject.base.ContentLine(name, params or {}, value)

        alarm = vobject.base.Component("VALARM")
        alarm.contents["action"] = line("action", "DISPLAY")
        alarm.contents["description"] = [line("description", "Wake")]
        alarm.contents["trigger"] = [line("trigger", timedelta(minutes=-5))]
        alarm.contents["repeat"] = [line("repeat", "2")]
        alarm.contents["duration"] = [line("duration", "PT5M")]
        parsed = Alarm(alarm)
        assert parsed.action == "DISPLAY"
        assert parsed.description == "Wake"
        assert parsed.trigger == timedelta(minutes=-5)
        assert parsed.repeat == 2
        assert parsed.duration == "PT5M"
        assert Alarm(vobject.base.Component("VALARM")).repeat is None

        start = datetime(2030, 1, 1, 11, 0, 0)
        stamped = TimeWithTimezone(ContentLine("dtstart", start, {"TZID": ["UTC"]}))
        assert stamped.timezone_id == "UTC"
        assert stamped.time_string() == "2030-01-01 11:00:00"
        assert TimeWithTimezone(ContentLine("dtstart", None, {})).time_string() is None

        std = vobject.base.Component("STANDARD")
        std.contents["dtstart"] = [line("dtstart", start)]
        std.contents["tzname"] = [line("tzname", "EST")]
        std.contents["tzoffsetfrom"] = [line("tzoffsetfrom", "-0500")]
        std.contents["tzoffsetto"] = [line("tzoffsetto", "-0400")]
        zone = vobject.base.Component("VTIMEZONE")
        zone.contents["tzid"] = [line("tzid", "America/New_York")]
        object.__setattr__(zone, "standard", [std, "nope"])
        parsed_zone = Timezone(zone)
        assert parsed_zone.timezone_id == "America/New_York"
        assert parsed_zone.standard.timezone_name == "EST"
        assert parsed_zone.standard.timezone_offset_from == "-0500"
        assert parsed_zone.standard.timezone_offset_to == "-0400"
        assert parsed_zone.standard.datetime_start == start
        assert parsed_zone.daylight is None
        day = vobject.base.Component("DAYLIGHT")
        day.contents["tzname"] = [line("tzname", "EDT")]
        assert DaylightTimezone(day).timezone_name == "EDT"
        assert StandardTimezone(std).timezone_name == "EST"

        event = vobject.base.Component("VEVENT")
        event.contents["dtstamp"] = [line("dtstamp", "20300101T000000Z")]
        event.contents["dtstart"] = [line("dtstart", start, {"TZID": ["UTC"]})]
        event.contents["summary"] = [line("summary", "Title")]
        event.contents["uid"] = [line("uid", "u1")]
        object.__setattr__(event, "valarm", [alarm, "nope"])
        parsed_event = Event(event)
        assert parsed_event.datetime_stamp == "20300101T000000Z"
        assert parsed_event.summary == "Title"
        assert len(parsed_event.alarms) == 1
        assert parsed_event.alarms[0].action == "DISPLAY"

        alice = Attendee(ContentLine(
            "attendee", "mailto:alice@example.com",
            {"ROLE": ["REQ-PARTICIPANT"], "PARTSTAT": ["ACCEPTED"],
             "CN": ["Alice"], "DELEGATED-FROM": ["mailto:boss@example.com"]}))
        bob = Attendee(ContentLine("attendee", "mailto:bob@example.com", {}))
        assert alice.role == "REQ-PARTICIPANT"
        assert alice.participation_status == "ACCEPTED"
        assert alice.name == "Alice"
        assert alice.delegated_from == "boss@example.com"
        assert bob.role is None
        assert bob.delegated_from is None

        calendar = vobject.base.Component("VCALENDAR")
        calendar.contents["version"] = [line("version", "2.0")]
        calendar.contents["prodid"] = [line("prodid", "-//Test//EN")]
        object.__setattr__(calendar, "vevent", [event])
        object.__setattr__(calendar, "vtimezone", [zone, "nope"])
        parsed_calendar = Calendar(calendar)
        assert parsed_calendar.version == "2.0"
        assert parsed_calendar.product_id == "-//Test//EN"
        assert parsed_calendar.event.uid == "u1"
        assert parsed_calendar.timezone.timezone_id == "America/New_York"

        with pytest.raises(ValueError, match="Invalid subject template"):
            MessageTemplate("Hello $nope", "Body")
        with pytest.raises(ValueError, match="Invalid body template"):
            MessageTemplate("Hello", "Body $nope")
        template = MessageTemplate("Hello $attendee_name", "Body $attendee_name")
        assert "Hello $attendee_name" in repr(template)
        assert str(template) == "Hello $attendee_name: Body $attendee_name"
        config = EmailConfig(
            "smtp.example", 25, "none", "NONE", "", "", "calendar@example.com",
            False, True, template, template, template)
        assert "smtp.example" in repr(config)


class TestEmailHookGaps(BaseTest):
    """SMTP outcomes and the iTIP / legacy notification edges."""

    def _install_smtp(self, monkeypatch):
        import radicale.hook.email as email_hook

        class FakeSMTP:
            messages = []
            fail_after = None
            errors = None
            require_login = False
            logged_in = None

            def __init__(self, host=None, port=None, context=None, **kwargs):
                self.host = host
                self.port = port

            def ehlo(self):
                return (250, b"ok")

            def starttls(self, context=None, **kwargs):
                return (220, b"ready")

            def login(self, user=None, password=None, **kwargs):
                FakeSMTP.logged_in = (user, password)
                return (235, b"ok")

            def sendmail(self, from_addr, to_addrs, msg):
                if FakeSMTP.require_login and FakeSMTP.logged_in is None:
                    raise email_hook.smtplib.SMTPException("not logged in")
                if (FakeSMTP.fail_after is not None and
                        len(FakeSMTP.messages) >= FakeSMTP.fail_after):
                    raise email_hook.smtplib.SMTPException("send failed")
                FakeSMTP.messages.append((from_addr, list(to_addrs), msg))
                return dict(FakeSMTP.errors or {})

            def quit(self):
                return (221, b"bye")

        FakeSMTP.messages = []
        FakeSMTP.fail_after = None
        FakeSMTP.errors = None
        FakeSMTP.require_login = False
        FakeSMTP.logged_in = None
        monkeypatch.setattr(email_hook.smtplib, "SMTP", FakeSMTP)
        monkeypatch.setattr(email_hook.smtplib, "SMTP_SSL", FakeSMTP)
        return FakeSMTP

    def _hook(self, monkeypatch, **hook):
        smtp = self._install_smtp(monkeypatch)
        config = {
            "type": "email",
            "dryrun": "False",
            "smtp_server": "127.0.0.1",
            "smtp_port": "2525",
            "smtp_security": "none",
            "from_email": "calendar@example.com",
        }
        config.update(hook)
        self.configure({"hook": config})
        return self.application._hook, smtp

    def _notify(self, hook, kind, new=None, old=None, actor="owner",
                content_type="VCALENDAR"):
        item = HookNotificationItem(
            kind, "/owner/cal/event.ics", content_type=content_type,
            new_content=new, old_content=old, actor=actor)
        hook.notify(item)
        return item

    def test_smtp_login_partial_failure_and_undeliverable_addresses(self, monkeypatch, caplog):
        from radicale.hook.email import Attendee, ContentLine

        caplog.set_level(logging.WARNING)
        hook, smtp = self._hook(
            monkeypatch, smtp_username="mailer", smtp_password="secret")
        smtp.require_login = True
        event = _event_ics(attendees=[("a@b.com", "Ann"), ("c@d.com", "Cy")])
        import radicale.hook.email as email_hook
        email_event = email_hook._read_event(event)
        assert hook.email_config.send_added_email(
            email_event.event.attendees, email_event) is True
        assert smtp.logged_in == ("mailer", "secret")
        assert len(smtp.messages) == 2

        smtp.messages.clear()
        smtp.logged_in = ("mailer", "secret")
        smtp.fail_after = 1
        assert hook.email_config.send_added_email(
            email_event.event.attendees, email_event) is False
        assert len(smtp.messages) == 1

        smtp.fail_after = None
        smtp.messages.clear()
        smtp.errors = {"a@b.com": (550, b"no such user")}
        caplog.clear()
        assert hook.email_config.send_added_email(
            [email_event.event.attendees[0]], email_event) is False
        assert "a@b.com" in caplog.text
        assert len(smtp.messages) == 1

        smtp.errors = None
        smtp.messages.clear()
        bad = Attendee(ContentLine("attendee", "not-an-email", {"CN": ["X"]}))
        caplog.clear()
        assert hook.email_config.send_added_email([bad], email_event) is False
        assert "No valid email" in caplog.text
        assert smtp.messages == []

    def test_scheduling_kinds_choose_templates_and_send(self, monkeypatch):
        from radicale.hook.email.scheduling import PlannedMessage

        hook, smtp = self._hook(monkeypatch)
        import radicale.hook.email as email_hook
        ics = _event_ics(attendees=[("carol@example.com", "Carol")], summary="Standup")
        email_event = email_hook._read_event(ics)
        subjects = {
            "created": "You have been added to an event",
            "added": "You have been added to an event",
            "removed": "An event you were invited to has been deleted",
            "deleted": "An event you were invited to has been deleted",
            "updated": "An event you are invited to has been updated",
        }
        for kind, subject in subjects.items():
            smtp.messages.clear()
            method = "CANCEL" if kind in ("removed", "deleted") else "REQUEST"
            planned = PlannedMessage(method, "carol@example.com", "Carol", kind)
            assert hook.email_config.send_scheduling_email(
                planned, email_event, ics) is True
            _addr, recipients, message = smtp.messages[0]
            decoded = _mail_text(message)
            assert recipients == ["carol@example.com"]
            assert subject in message
            assert "Hello Carol" in message
            assert "text/calendar" in message
            assert "METHOD:%s" % method in decoded

        smtp.messages.clear()
        missing = PlannedMessage("REQUEST", "nobody@example.com", "Nobody", "created")
        assert hook.email_config.send_scheduling_email(missing, email_event, ics) is False
        assert smtp.messages == []

    def test_itip_cancel_uses_the_higher_sequence_plus_one(self, monkeypatch):
        hook, smtp = self._hook(
            monkeypatch, itip_enabled="True",
            itip_owner_map='{"owner": "owner@example.com"}')
        old = _event_ics(summary="OldTitle", sequence=2, attendees=[
            ("alice@example.com", "Alice"), ("bob@example.com", "Bob")])
        new = _event_ics(summary="NewTitle", sequence=9, attendees=[
            ("alice@example.com", "Alice"), ("carol@example.com", "Carol")])
        self._notify(hook, HookNotificationItemTypes.UPSERT, new=new, old=old)
        by_to = {message.split("To: ", 1)[1].splitlines()[0]: _mail_text(message)
                 for _addr, _rcpt, message in smtp.messages}
        assert "OldTitle" in by_to["bob@example.com"]
        assert "SEQUENCE:10" in by_to["bob@example.com"]
        assert "NewTitle" in by_to["carol@example.com"]
        assert "SEQUENCE:9" in by_to["carol@example.com"]

    def test_cancel_sequence_uses_zero_when_one_side_does_not_parse(self, monkeypatch):
        from radicale.hook.email.scheduling import PlannedMessage

        hook, smtp = self._hook(monkeypatch, itip_enabled="True",
                                itip_owner_map='{"owner": "owner@example.com"}')
        import radicale.hook.email as email_hook
        previous = _event_ics(summary="OldTitle", sequence=4,
                              attendees=[("bob@example.com", "Bob")])
        email_event = email_hook._read_event(previous)
        hook._send_planned(
            [PlannedMessage("CANCEL", "bob@example.com", "Bob", "removed")],
            email_event, previous, "not a calendar")
        assert "SEQUENCE:5" in _mail_text(smtp.messages[0][2])
        assert "OldTitle" in smtp.messages[0][2]

        smtp.messages.clear()
        recurrence = _event_ics(summary="Override", sequence=4, recurrence=True,
                                attendees=[("bob@example.com", "Bob")])
        new = _event_ics(summary="NewTitle", sequence=6,
                         attendees=[("bob@example.com", "Bob")])
        hook._send_planned(
            [PlannedMessage("CANCEL", "bob@example.com", "Bob", "removed")],
            email_hook._read_event(recurrence), recurrence, new)
        assert "SEQUENCE:7" in _mail_text(smtp.messages[0][2])

    def test_mass_email_guard_sends_nothing_for_itip(self, monkeypatch, caplog):
        caplog.set_level(logging.ERROR)
        hook, smtp = self._hook(
            monkeypatch, itip_enabled="True",
            itip_owner_map='{"owner": "owner@example.com"}')
        hook.email_config.send_mass_emails = True
        self._notify(hook, HookNotificationItemTypes.UPSERT, new=_event_ics())
        assert smtp.messages == []
        assert "mass_email is incompatible" in caplog.text

    def test_unknown_cpatch_and_foreign_items_send_nothing(self, monkeypatch, caplog):
        caplog.set_level(logging.WARNING)
        hook, smtp = self._hook(monkeypatch)
        item = self._notify(hook, HookNotificationItemTypes.UPSERT, new=_event_ics())
        smtp.messages.clear()
        caplog.clear()
        item.type = "explode"
        hook.notify(item)
        assert smtp.messages == []
        assert "Unknown notification item type" in caplog.text

        caplog.clear()
        self._notify(hook, HookNotificationItemTypes.CPATCH, new=_event_ics())
        assert smtp.messages == []
        assert "New event detected" not in caplog.text

        class Calendarish:
            is_calendar_item = True

        hook.notify(Calendarish())
        assert smtp.messages == []

    def test_todo_upsert_and_delete_send_nothing(self, monkeypatch, caplog):
        caplog.set_level(logging.DEBUG)
        hook, smtp = self._hook(monkeypatch)
        self._notify(hook, HookNotificationItemTypes.UPSERT, new=_todo_ics())
        assert smtp.messages == []
        assert "No event found" in caplog.text
        assert "Failed to read" not in caplog.text
        caplog.clear()
        self._notify(hook, HookNotificationItemTypes.DELETE, old=_todo_ics())
        assert smtp.messages == []
        assert "No event found" in caplog.text

    def test_event_without_end_is_still_mailed(self, monkeypatch):
        hook, smtp = self._hook(monkeypatch)
        self._notify(hook, HookNotificationItemTypes.UPSERT,
                     new=_event_ics(dtend=False, attendees=[("bob@example.com", "Bob")]))
        assert len(smtp.messages) == 1
        assert "Hello Bob" in smtp.messages[0][2]

    def test_unreadable_event_and_null_event_are_skipped(self, monkeypatch, caplog):
        import radicale.hook.email as email_hook

        caplog.set_level(logging.ERROR)
        hook, smtp = self._hook(monkeypatch)

        class Holder:
            event = None

        assert hook._is_past_event(Holder()) is False
        monkeypatch.setattr(email_hook, "_read_event", lambda vobject_data: None)
        self._notify(hook, HookNotificationItemTypes.UPSERT, new=_event_ics())
        assert smtp.messages == []
        assert "Failed to read event" in caplog.text

    def test_legacy_unparseable_previous_is_sent_as_new(self, monkeypatch, caplog):
        caplog.set_level(logging.WARNING)
        hook, smtp = self._hook(monkeypatch)
        new = _event_ics(attendees=[("bob@example.com", "Bob")])
        self._notify(hook, HookNotificationItemTypes.UPSERT, new=new, old=_todo_ics())
        assert len(smtp.messages) == 1
        assert "treating as a new event" in caplog.text

        smtp.messages.clear()
        smtp.fail_after = 0
        caplog.clear()
        self._notify(hook, HookNotificationItemTypes.UPSERT, new=new, old=_todo_ics())
        assert smtp.messages == []
        assert "treating as a new event" in caplog.text
        assert "Failed to send some or all added" in caplog.text

    def test_legacy_read_of_new_event_none_sends_nothing(self, monkeypatch, caplog):
        import radicale.hook.email as email_hook

        caplog.set_level(logging.WARNING)
        hook, smtp = self._hook(monkeypatch)
        ics = _event_ics()
        email_event = email_hook._read_event(ics)
        monkeypatch.setattr(email_hook, "read_ics_event", lambda contents: None)
        hook._process_legacy_upsert(ics, ics, email_event)
        assert smtp.messages == []
        assert "treating as a new event" not in caplog.text

    def test_legacy_unchanged_details_send_nothing(self, monkeypatch):
        hook, smtp = self._hook(monkeypatch)
        ics = _event_ics(attendees=[("bob@example.com", "Bob")])
        self._notify(hook, HookNotificationItemTypes.UPSERT, new=ics, old=ics)
        assert smtp.messages == []

    def test_legacy_send_failures_are_logged(self, monkeypatch, caplog):
        caplog.set_level(logging.ERROR)
        hook, smtp = self._hook(monkeypatch)
        smtp.fail_after = 0
        self._notify(hook, HookNotificationItemTypes.UPSERT, new=_event_ics())
        assert "Failed to send some or all added" in caplog.text

        caplog.clear()
        old = _event_ics(attendees=[("bob@example.com", "Bob")])
        new = _event_ics(attendees=[("carol@example.com", "Carol")])
        self._notify(hook, HookNotificationItemTypes.UPSERT, new=new, old=old)
        assert "Failed to send some or all added" in caplog.text
        assert "Failed to send some or all deleted" in caplog.text

        caplog.clear()
        updated = _event_ics(summary="Changed", attendees=[("bob@example.com", "Bob")])
        self._notify(hook, HookNotificationItemTypes.UPSERT, new=updated, old=old)
        assert "Failed to send some or all updated" in caplog.text

        caplog.clear()
        self._notify(hook, HookNotificationItemTypes.DELETE, old=old)
        assert "Failed to send some or all deleted" in caplog.text

    def test_legacy_attendee_changes_are_mailed_when_send_succeeds(self, monkeypatch, caplog):
        caplog.set_level(logging.ERROR)
        hook, smtp = self._hook(monkeypatch)
        old = _event_ics(summary="Standup", attendees=[
            ("alice@example.com", "Alice"), ("bob@example.com", "Bob")])
        new = _event_ics(summary="Moved", attendees=[
            ("bob@example.com", "Bob"), ("carol@example.com", "Carol")])
        self._notify(hook, HookNotificationItemTypes.UPSERT, new=new, old=old)
        by_to = {addrs[0]: message for _addr, addrs, message in smtp.messages}
        assert set(by_to) == {"alice@example.com", "bob@example.com", "carol@example.com"}
        assert "has been deleted" in by_to["alice@example.com"]
        assert "has been updated" in by_to["bob@example.com"]
        assert "have been added" in by_to["carol@example.com"]
        assert "Failed to send" not in caplog.text

    def test_itip_unparseable_previous_sends_nothing(self, monkeypatch, caplog):
        caplog.set_level(logging.ERROR)
        hook, smtp = self._hook(
            monkeypatch, itip_enabled="True",
            itip_owner_map='{"owner": "owner@example.com"}')
        self._notify(hook, HookNotificationItemTypes.UPSERT,
                     new=_event_ics(), old=_todo_ics())
        assert smtp.messages == []
        assert "could not be parsed" in caplog.text

    def test_itip_delete_sends_cancel(self, monkeypatch, caplog):
        caplog.set_level(logging.ERROR)
        hook, smtp = self._hook(
            monkeypatch, itip_enabled="True",
            itip_owner_map='{"owner": "owner@example.com"}')
        old = _event_ics(sequence=2, attendees=[("bob@example.com", "Bob")])
        self._notify(hook, HookNotificationItemTypes.DELETE, old=old)
        assert "SEQUENCE:3" in _mail_text(smtp.messages[0][2])
        assert "Reply-To:" not in smtp.messages[0][2]
        smtp.messages.clear()
        smtp.fail_after = 0
        self._notify(hook, HookNotificationItemTypes.DELETE, old=old)
        assert smtp.messages == []
        assert "Failed to send scheduling notification" in caplog.text

    def test_itip_reply_to_is_the_mapped_owner_or_absent(self, monkeypatch):
        hook, smtp = self._hook(
            monkeypatch, itip_enabled="True", itip_owner_reply_to="True",
            itip_owner_map='{"owner": "owner@example.com"}')
        ics = _event_ics(attendees=[("bob@example.com", "Bob")])
        self._notify(hook, HookNotificationItemTypes.UPSERT, new=ics,
                     actor=" owner ")
        assert len(smtp.messages) == 1
        assert "Reply-To: owner@example.com" in smtp.messages[0][2]
        assert "Reply-To: calendar@example.com" not in smtp.messages[0][2]

        # A blank actor is not an owner, so the delete sends nothing.
        smtp.messages.clear()
        self._notify(hook, HookNotificationItemTypes.DELETE, old=ics, actor="")
        assert smtp.messages == []
        blank = HookNotificationItem(
            HookNotificationItemTypes.DELETE, "/owner/cal/event.ics",
            content_type="VCALENDAR", old_content=ics, actor="")
        assert hook._owner_reply_to(blank) is None
        blank.actor = None
        assert hook._owner_reply_to(blank) is None
        missing = HookNotificationItem(
            HookNotificationItemTypes.DELETE, "/owner/cal/event.ics",
            content_type="VCALENDAR", old_content=ics)
        assert hook._owner_reply_to(missing) is None

    def test_one_attendee_mass_email_skips_trace_when_debug_is_off(self, monkeypatch):
        from radicale.log import logger

        hook, smtp = self._hook(monkeypatch, mass_email="True")
        logger.setLevel(logging.INFO)

        def trace(*args, **kwargs):
            raise AssertionError("trace called")

        monkeypatch.setattr(logger, "trace", trace)
        self._notify(hook, HookNotificationItemTypes.UPSERT,
                     new=_event_ics(attendees=[("bob@example.com", "Bob")]))
        assert len(smtp.messages) == 1
        assert "Hello Bob" in smtp.messages[0][2]
        assert "everyone" not in smtp.messages[0][2]

    def test_security_outside_the_enum_does_not_open_a_tls_socket(self, monkeypatch):
        hook, _smtp = self._hook(monkeypatch)
        hook.email_config.security = "bogus"
        with pytest.raises(UnboundLocalError):
            hook.email_config._smtp_send("text", ["a@b.com"])

    def test_delete_branch_is_not_taken_for_a_foreign_type(self, monkeypatch):
        hook, smtp = self._hook(monkeypatch)
        monkeypatch.setattr(hook, "_notification_type", lambda item: "other")
        self._notify(hook, HookNotificationItemTypes.UPSERT, new=_event_ics())
        assert smtp.messages == []


class TestSchedulingGaps:
    """Planner and iTIP builder edges."""

    def test_extract_email_and_parse_edges(self):
        from radicale.hook.email import scheduling

        assert scheduling.extract_email(None) is None
        assert scheduling.extract_email("") is None
        assert scheduling.extract_email("  ") is None
        assert scheduling.extract_email("A@B.c") == "a@b.c"
        assert scheduling.extract_email("nope") is None
        assert scheduling.extract_email("MAILTO:A@B.c;x") == "a@b.c"
        assert scheduling.parse_event(None) is None
        assert scheduling.parse_event("") is None
        empty = "BEGIN:VCALENDAR\nVERSION:2.0\nEND:VCALENDAR\n"
        assert scheduling.parse_event(empty) is None
        no_organizer = _event_ics(organizer=None, attendees=[])
        parsed = scheduling.parse_event(no_organizer)
        assert parsed.organizer_email is None
        assert parsed.organizer_schedule_agent is None
        assert scheduling.plan_messages(
            None, no_organizer, owner_identities=["a@b.com"]) == []
        messy = "\n".join([
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "BEGIN:VEVENT",
            "UID:u",
            "DTSTART:20300101T110000Z",
            "SUMMARY:S",
            "SEQUENCE:nope",
            "ORGANIZER:mailto:a@b.com",
            "ATTENDEE:mailto:A@B.com",
            "ATTENDEE:mailto:a@b.com",
            "ATTENDEE:not-an-email",
            "END:VEVENT",
            "END:VCALENDAR",
            "",
        ])
        parsed = scheduling.parse_event(messy)
        assert parsed.sequence == 0
        assert list(parsed.attendees) == ["a@b.com"]

    def test_owner_map_and_ownership_skip_blanks(self):
        from radicale.hook.email import scheduling

        rules = scheduling.parse_owner_map('{"owner": "owner@example.com"}')
        # No actor, and an actor that is only whitespace, produce no address.
        # An actor with surrounding space still maps: that is just outside empty.
        assert scheduling.mapped_owner_email(None, rules) is None
        assert scheduling.mapped_owner_email("", rules) is None
        assert scheduling.mapped_owner_email("   ", rules) is None
        assert scheduling.mapped_owner_email(" owner ", rules) == "owner@example.com"
        assert scheduling.mapped_owner_email("other", rules) is None

        # Blank identities are skipped. A later real address still matches,
        # and a whitespace-only identity does not.
        assert scheduling.check_ownership(
            "A@B.com", ["", None, "a@b.com"]) is True
        assert scheduling.check_ownership("a@b.com", ["", None, "   "]) is False
        assert scheduling.check_ownership("", ["a@b.com"]) is False
        assert scheduling.check_ownership(None, ["a@b.com"]) is False
        assert scheduling.check_ownership("  A@B.com ", ["a@b.com"]) is True

    def test_plan_rejects_unparseable_multivevent_and_organizer_change(self):
        from radicale.hook.email import scheduling

        assert scheduling._vevent_count("") == 0
        assert scheduling._vevent_count(None) == 0
        assert scheduling._vevent_count("@@@") == 0
        assert scheduling._vevent_count(
            "BEGIN:VCALENDAR\nVERSION:2.0\nEND:VCALENDAR\n") == 0
        assert scheduling._vevent_count(_event_ics()) == 1
        assert scheduling.plan_messages("@@@", None, deleted=True,
                                        owner_identities=["owner@example.com"]) == []
        multi = "\n".join([
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "BEGIN:VEVENT",
            "UID:u",
            "DTSTART:20300101T110000Z",
            "DTEND:20300101T120000Z",
            "SUMMARY:Master",
            "ORGANIZER:mailto:owner@example.com",
            "ATTENDEE;CN=Bob:mailto:bob@example.com",
            "END:VEVENT",
            "BEGIN:VEVENT",
            "UID:u",
            "RECURRENCE-ID:20300102T110000Z",
            "DTSTART:20300102T110000Z",
            "DTEND:20300102T120000Z",
            "SUMMARY:Override",
            "ORGANIZER:mailto:owner@example.com",
            "ATTENDEE;CN=Bob:mailto:bob@example.com",
            "END:VEVENT",
            "END:VCALENDAR",
            "",
        ])
        assert scheduling.plan_messages(
            multi, None, deleted=True,
            owner_identities=["owner@example.com"]) == []
        old = _event_ics(summary="Same")
        assert scheduling.plan_messages(
            old, "garbage", owner_identities=["owner@example.com"]) == []
        changed = _event_ics(
            summary="Same", organizer="mailto:new@example.com",
            attendees=[("alice@example.com", "Alice"), ("c@d.com", "Cy")])
        assert scheduling.plan_messages(
            old, changed,
            owner_identities=["owner@example.com", "new@example.com"]) == []

    def test_vevent_count_without_a_list_attribute(self, monkeypatch):
        from radicale.hook.email import scheduling

        class FakeCalendar:
            vevent = object()

        monkeypatch.setattr(scheduling.vobject, "readOne", lambda text: FakeCalendar())
        assert scheduling._vevent_count("BEGIN:VCALENDAR") == 1

    def test_build_itip_rewrites_method_and_cancel_sequence(self):
        from radicale.hook.email import scheduling

        base = _event_ics(method="PUBLISH", attendees=[("bob@example.com", "Bob")])
        rewritten = scheduling.build_itip_ics(base, "REQUEST", "bob@example.com")
        assert "METHOD:REQUEST" in rewritten
        assert "PUBLISH" not in rewritten
        nope = _event_ics(sequence="nope", attendees=[("bob@example.com", "Bob")])
        cancelled = scheduling.build_itip_ics(nope, "CANCEL", "bob@example.com")
        assert "SEQUENCE:1" in cancelled
        plain = _event_ics(sequence=2, attendees=[("bob@example.com", "Bob")],
                           dtstamp=False)
        requested = scheduling.build_itip_ics(plain, "REQUEST", "bob@example.com")
        assert "METHOD:REQUEST" in requested

    def test_cancel_without_sequence_is_still_built_when_add_fails(self, monkeypatch):
        import vobject

        from radicale.hook.email import scheduling

        original = vobject.base.Component.add

        def add(self, name, group=None):
            if isinstance(name, str) and name.lower() == "sequence":
                raise RuntimeError("sequence store failed")
            return original(self, name, group)

        monkeypatch.setattr(vobject.base.Component, "add", add)
        source = _event_ics(sequence=None, attendees=[("bob@example.com", "Bob")])
        cancelled = scheduling.build_itip_ics(source, "CANCEL", "bob@example.com")
        assert "METHOD:CANCEL" in cancelled
        assert "SEQUENCE" not in cancelled
        assert "mailto:bob@example.com" in cancelled.lower()
        no_attendees = _event_ics(attendees=[])
        with pytest.raises(ValueError, match="not an attendee"):
            scheduling.build_itip_ics(no_attendees, "REQUEST", "bob@example.com")
        with pytest.raises(ValueError, match="not an attendee"):
            scheduling.build_itip_ics(
                _event_ics(attendees=[("alice@example.com", "Alice")]),
                "REQUEST", "bob@example.com")
