# This file is part of Radicale - CalDAV and CardDAV server
# Copyright © 2026-2026 Contributors to Radicale
#
# This library is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# If not, see <http://www.gnu.org/licenses/>.

"""Tests for server-side scheduling delivery in the email hook.

These tests cover the symptom that motivated the change: adding
one attendee to an existing event must not re-notify the attendees
who were already there. They test the pure planner in
``radicale.hook.email.scheduling`` directly, plus one end-to-end
PUT through the Radicale test harness with the hook in dry-run
mode, so a regression in the hook wiring is caught as well.
"""

import base64
import logging
from datetime import datetime, timedelta

from radicale.hook.email.scheduling import (build_itip_ics, build_itip_message,
                                            check_ownership, plan_messages)
from radicale.tests import BaseTest

OWNER = ["jeff@example.com"]


def plan(old, new, deleted=False, owner=OWNER):
    return plan_messages(old, new, deleted=deleted, owner_identities=owner)


def _event(attendees, dtstart="20261113T200000Z", dtend="20261113T220000Z",
           sequence=1, organizer_agent=""):
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Test//EN",
             "BEGIN:VEVENT", "UID:pizza-1", "DTSTAMP:20261030T120000Z",
             "DTSTART:%s" % dtstart, "DTEND:%s" % dtend,
             "SUMMARY:Pizza Party", "LOCATION:Home",
             "ORGANIZER;CN=Jeff%s:mailto:jeff@example.com" % organizer_agent]
    for name, email, extra in attendees:
        lines.append("ATTENDEE;CN=%s%s:mailto:%s" % (name, extra, email))
    lines.append("SEQUENCE:%d" % sequence)
    lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\n".join(lines) + "\n"


ALICE = ("Alice", "alice@example.com", "")
BOB = ("Bob", "bob@example.com", "")
CAROL = ("Carol", "carol@example.com", "")


def _recipients(planned):
    return [(p.method, p.recipient_email, p.kind) for p in planned]


class TestPlanMessages:
    def test_adding_one_attendee_notifies_only_the_new_attendee(self):
        old = _event([ALICE, BOB])
        new = _event([ALICE, BOB, CAROL])
        assert _recipients(plan(old, new)) == [
            ("REQUEST", "carol@example.com", "added")]

    def test_removing_an_attendee_sends_cancel_only_to_them(self):
        old = _event([ALICE, BOB, CAROL])
        new = _event([ALICE, BOB])
        assert _recipients(plan(old, new)) == [
            ("CANCEL", "carol@example.com", "removed")]

    def test_changing_an_attendee_and_time_notifies_both_groups_once(self):
        old = _event([ALICE, BOB])
        new = _event([ALICE, CAROL], dtstart="20261113T210000Z")
        planned = _recipients(plan(old, new))
        assert ("REQUEST", "carol@example.com", "added") in planned
        assert ("CANCEL", "bob@example.com", "removed") in planned
        assert ("REQUEST", "alice@example.com", "updated") in planned
        assert len(planned) == 3

    def test_organizer_time_or_location_update_reaches_existing_attendees(self):
        old = _event([ALICE, BOB])
        new = _event([ALICE, BOB], dtstart="20261113T210000Z")
        assert _recipients(plan(old, new)) == [
            ("REQUEST", "alice@example.com", "updated"),
            ("REQUEST", "bob@example.com", "updated")]
        moved = _event([ALICE, BOB], dtstart="20261113T200000Z")
        moved = moved.replace("LOCATION:Home", "LOCATION:Elsewhere")
        assert [p.kind for p in plan(old, moved)] == ["updated", "updated"]

    def test_repeated_put_of_the_same_event_sends_nothing(self):
        event = _event([ALICE, BOB, CAROL])
        assert plan(event, event) == []
        # A client re-saving the event with a new DTSTAMP (and even a
        # bumped SEQUENCE, which clients do on attendee-only edits)
        # must not, by itself, re-notify anybody.
        resaved = event.replace("DTSTAMP:20261030T120000Z",
                                "DTSTAMP:20261030T130000Z")
        resaved = resaved.replace("SEQUENCE:1", "SEQUENCE:2")
        assert plan(event, resaved) == []

    def test_new_event_notifies_all_attendees_but_not_the_organizer(self):
        event = _event([ALICE, BOB, ("Jeff", "jeff@example.com", "")])
        assert _recipients(plan(None, event)) == [
            ("REQUEST", "alice@example.com", "created"),
            ("REQUEST", "bob@example.com", "created")]

    def test_event_deletion_cancels_for_all_attendees(self):
        old = _event([ALICE, BOB])
        assert _recipients(plan(old, None, deleted=True)) == [
            ("CANCEL", "alice@example.com", "deleted"),
            ("CANCEL", "bob@example.com", "deleted")]

    def test_schedule_agent_client_attendee_is_skipped(self):
        old = _event([ALICE])
        client_carol = ("Carol", "carol@example.com", ";SCHEDULE-AGENT=CLIENT")
        assert plan(old, _event([ALICE, client_carol])) == []

    def test_schedule_agent_client_organizer_does_not_suppress_attendees(self):
        # RFC 6638: the ORGANIZER flag governs messages to the
        # organizer, not REQUESTs to attendees. A client-owned
        # organizer flag must not suppress attendee delivery.
        old = _event([ALICE])
        new = _event([ALICE, CAROL], organizer_agent=";SCHEDULE-AGENT=CLIENT")
        assert _recipients(plan(old, new)) == [
            ("REQUEST", "carol@example.com", "added")]

    def test_unparseable_previous_event_sends_nothing(self):
        # Fail closed: notifying everybody on a parse failure
        # recreates the blast this patch is meant to stop.
        new = _event([ALICE, BOB])
        assert plan("not an ics file", new) == []

    def test_attendee_copy_sends_nothing(self):
        # Organizer is Jeff, owner is Alice: this is Alice's
        # attendee copy, not Jeff's organizer event.
        old = _event([ALICE, BOB])
        new = _event([ALICE, BOB, CAROL])
        assert plan(old, new, owner=["alice@example.com"]) == []
        assert plan(None, new, owner=["alice@example.com"]) == []
        assert plan(old, None, deleted=True, owner=["alice@example.com"]) == []

    def test_no_owner_identity_sends_nothing(self):
        assert plan(None, _event([ALICE, BOB]), owner=[]) == []
        assert plan(None, _event([ALICE, BOB]), owner=None) == []

    def test_bare_username_owner_no_longer_matches(self):
        # Only a full email identity counts. A bare username
        # must not match by local-part, even for the right user.
        assert check_ownership("jeff@example.com", ["jeff"]) is False
        assert check_ownership("jeff@example.com", ["jeff@example.com"]) is True
        assert check_ownership("jeff@example.com", ["alice"]) is False
        assert check_ownership("jeff@example.com", ["jeff@other.example"]) is False

    def test_schedule_agent_none_attendee_is_skipped(self):
        old = _event([ALICE])
        none_carol = ("Carol", "carol@example.com", ";SCHEDULE-AGENT=NONE")
        assert plan(old, _event([ALICE, none_carol])) == []

    def test_recurrence_rule_change_triggers_update(self):
        old = _event([ALICE, BOB])
        new = _event([ALICE, BOB])
        new = new.replace("LOCATION:Home",
                          "LOCATION:Home\nRRULE:FREQ=WEEKLY;COUNT=4")
        assert [p.kind for p in plan(old, new)] == ["updated", "updated"]

    def test_schedule_agent_params_are_stripped_from_itip(self):
        event = _event([ALICE, CAROL], organizer_agent=";SCHEDULE-AGENT=CLIENT")
        event = event.replace("ATTENDEE;CN=Carol:mailto:carol@example.com",
                              "ATTENDEE;CN=Carol;SCHEDULE-AGENT=SERVER:mailto:carol@example.com")
        itip = build_itip_ics(event, "REQUEST", "carol@example.com")
        assert "SCHEDULE-AGENT" not in itip
        assert "SCHEDULE-FORCE-SEND" not in itip


class TestItipMessage:
    def test_request_contains_only_the_recipient_and_the_organizer(self):
        new = _event([ALICE, BOB, CAROL], sequence=3)
        itip = build_itip_ics(new, "REQUEST", "carol@example.com")
        assert "METHOD:REQUEST" in itip
        assert "SEQUENCE:3" in itip
        assert itip.count("ATTENDEE") == 1
        assert "carol@example.com" in itip
        assert "alice@example.com" not in itip
        assert "bob@example.com" not in itip

    def test_cancel_is_built_from_the_old_event(self):
        old = _event([ALICE, BOB, CAROL])
        itip = build_itip_ics(old, "CANCEL", "carol@example.com")
        assert "METHOD:CANCEL" in itip
        assert "carol@example.com" in itip

    def test_itip_email_carries_text_calendar_with_method(self):
        new = _event([ALICE, CAROL])
        itip = build_itip_ics(new, "REQUEST", "carol@example.com")
        message = build_itip_message(
            "jeff@example.com", "carol@example.com", "Added",
            "Hello Carol", itip, "REQUEST")
        assert 'method="REQUEST"' in message
        assert "text/calendar" in message
        # The calendar part is base64-encoded; decode it and check
        # the method survives the round trip.
        decoded = base64.b64decode(
            "".join(message.split("filename=\"event.ics\"")[1].split("--")[0].split())).decode()
        assert "METHOD:REQUEST" in decoded

    def test_cancel_increments_sequence_and_updates_dtstamp(self):
        old = _event([ALICE, BOB, CAROL], sequence=3)
        itip = build_itip_ics(old, "CANCEL", "carol@example.com")
        assert "METHOD:CANCEL" in itip
        assert "SEQUENCE:4" in itip
        assert "DTSTAMP:20261030T120000Z" not in itip

    def test_itip_builder_rejects_multi_vevent(self):
        # The builder enforces the planner's restriction
        # independently, instead of filtering overrides.
        import pytest
        base = _event([ALICE, BOB, CAROL])
        override = ("BEGIN:VEVENT\nUID:pizza-1\nDTSTAMP:20261030T120000Z\n"
                    "RECURRENCE-ID:20261120T200000Z\nDTSTART:20261120T200000Z\n"
                    "DTEND:20261120T220000Z\nSUMMARY:Pizza Party\n"
                    "ORGANIZER;CN=Jeff:mailto:jeff@example.com\n"
                    "ATTENDEE;CN=Alice:mailto:alice@example.com\n"
                    "ATTENDEE;CN=Bob:mailto:bob@example.com\n"
                    "ATTENDEE;CN=Carol:mailto:carol@example.com\n"
                    "SEQUENCE:1\nEND:VEVENT\n")
        event = base.replace("END:VCALENDAR", override + "END:VCALENDAR")
        with pytest.raises(ValueError):
            build_itip_ics(event, "REQUEST", "carol@example.com")


class TestHookWiring(BaseTest):
    """End-to-end: a PUT that adds one attendee, hook in dry-run."""

    def setup_method(self) -> None:
        BaseTest.setup_method(self)
        # Same rights setup as test_hook_email.py: without it,
        # anonymous requests are denied by the default owner_only
        # rights, and MKCALENDAR returns 401.
        import os
        rights_file_path = os.path.join(self.colpath, "rights")
        with open(rights_file_path, "w") as f:
            f.write("[allow all]\nuser: .*\ncollection: .*\npermissions: RrWw")
        self.configure({
            "rights": {"file": rights_file_path, "type": "from_file"}})
        self.configure({"auth": {"type": "none"}})
        self.configure({
            "hook": {"type": "email", "dryrun": "True",
                     "itip_enabled": "True",
                     "from_email": "jeff@example.com",
                     "itip_owner_map": "jeff=jeff@example.com"}})

    def _future_event(self, attendees, start):
        return _event(
            attendees,
            dtstart=start.strftime("%Y%m%dT%H%M%SZ"),
            dtend=(start + timedelta(hours=2)).strftime("%Y%m%dT%H%M%SZ"))

    def test_put_adding_one_attendee_dryrun_logs_only_the_new_attendee(self, caplog):
        caplog.set_level(logging.INFO)
        self.mkcalendar("/calendar.ics/", login="jeff:password")
        path = "/calendar.ics/event1.ics"
        # Use the same event time for both PUTs. Only attendees change.
        start = datetime.now() + timedelta(days=1)
        self.put(path, self._future_event([ALICE, BOB], start), login="jeff:password")
        # An update to an existing item returns 204, not 201.
        self.put(path, self._future_event([ALICE, BOB, CAROL], start),
                 check=204, login="jeff:password")
        dryrun_to = [log for log in caplog.messages
                     if "DRY-RUN send_scheduling_email / to_addresses" in log]
        # First PUT notifies Alice and Bob; the second notifies Carol only.
        assert dryrun_to == [
            "Hook 'email': DRY-RUN send_scheduling_email / to_addresses=['alice@example.com']",
            "Hook 'email': DRY-RUN send_scheduling_email / to_addresses=['bob@example.com']",
            "Hook 'email': DRY-RUN send_scheduling_email / to_addresses=['carol@example.com']",
        ]


class TestHookWiringLegacy(BaseTest):
    """With itip_enabled off, the hook uses the legacy path, not the planner."""

    def setup_method(self) -> None:
        BaseTest.setup_method(self)
        import os
        rights_file_path = os.path.join(self.colpath, "rights")
        with open(rights_file_path, "w") as f:
            f.write("[allow all]\nuser: .*\ncollection: .*\npermissions: RrWw")
        self.configure({
            "rights": {"file": rights_file_path, "type": "from_file"}})
        self.configure({
            "hook": {"type": "email", "dryrun": "True",
                     "itip_enabled": "False",
                     "from_email": "jeff@example.com"}})

    def test_put_adding_one_attendee_uses_legacy_send_email(self, caplog):
        caplog.set_level(logging.INFO)
        self.mkcalendar("/calendar.ics/")
        path = "/calendar.ics/event1.ics"
        start = (datetime.now() + timedelta(days=1)).strftime("%Y%m%dT%H%M%SZ")
        end = (datetime.now() + timedelta(days=1, hours=2)).strftime("%Y%m%dT%H%M%SZ")
        event = _event([ALICE, BOB], dtstart=start, dtend=end)
        self.put(path, event)
        legacy = [log for log in caplog.messages
                  if "DRY-RUN _send_email" in log]
        itip = [log for log in caplog.messages
                if "DRY-RUN send_scheduling_email" in log]
        assert legacy, "legacy _send_email should be used when itip_enabled is False"
        assert not itip


class TestOwnerMapAndRecurrence:
    """Explicit mapping, recurrence cases, config validation."""

    def test_parse_owner_map_valid(self):
        from radicale.hook.email.scheduling import parse_owner_map
        assert parse_owner_map("alice=alice@example.com, Bob=Bob@Example.com") == {
            "alice": "alice@example.com", "bob": "bob@example.com"}
        assert parse_owner_map("") == {}
        assert parse_owner_map(None) == {}

    def test_parse_owner_map_malformed(self):
        import pytest

        from radicale.hook.email.scheduling import parse_owner_map
        for bad in ["alice", "alice=no-at-sign", "a=a@x.com, a=b@x.com", " =a@x.com"]:
            with pytest.raises(ValueError):
                parse_owner_map(bad)

    def test_resolve_owner_identities_mapped_and_unmapped(self):
        from radicale.hook.email.scheduling import resolve_owner_identities
        m = {"alice": "alice@example.com"}
        assert resolve_owner_identities("alice", m) == ["alice@example.com"]
        assert resolve_owner_identities("someone-else", m) == []
        assert resolve_owner_identities(None, m) == []
        assert resolve_owner_identities("jeff", {}) == []  # map is mandatory
        assert resolve_owner_identities(None, {}) == []

    def test_mapped_owner_plans_and_unmapped_owner_plans_nothing(self):
        from radicale.hook.email.scheduling import resolve_owner_identities
        old = _event([ALICE, BOB])
        new = _event([ALICE, BOB, CAROL])
        # The test event is organized by jeff@example.com, so the mapped
        # identity must be that address for ownership to be proved.
        mapped = resolve_owner_identities("jeff", {"jeff": "jeff@example.com"})
        assert _recipients(plan(old, new, owner=mapped)) == [("REQUEST", "carol@example.com", "added")]
        unmapped = resolve_owner_identities("mallory", {"jeff": "jeff@example.com"})
        assert plan(old, new, owner=unmapped) == []

    def test_uid_change_plans_nothing(self):
        old = _event([ALICE, BOB])
        new = _event([ALICE, BOB, CAROL]).replace("UID:pizza-1", "UID:other-1")
        assert plan(old, new) == []

    def test_organizer_change_plans_nothing(self):
        old = _event([ALICE, BOB])
        new = _event([ALICE, BOB, CAROL]).replace("mailto:jeff@example.com", "mailto:other@example.com")
        assert plan(old, new) == []

    def test_multi_uid_calendar_plans_nothing(self):
        old = _event([ALICE, BOB])
        extra = ("BEGIN:VEVENT\nUID:second-1\nDTSTAMP:20261030T120000Z\n"
                 "DTSTART:20261114T200000Z\nDTEND:20261114T220000Z\nSUMMARY:Other\n"
                 "ORGANIZER:mailto:jeff@example.com\n"
                 "ATTENDEE;CN=Alice:mailto:alice@example.com\nSEQUENCE:1\nEND:VEVENT\n")
        new = _event([ALICE, BOB, CAROL]).replace("END:VCALENDAR", extra + "END:VCALENDAR")
        assert plan(old, new) == []

    def test_override_with_different_attendees_plans_nothing(self):
        old = _event([ALICE, BOB, CAROL])
        override = ("BEGIN:VEVENT\nUID:pizza-1\nDTSTAMP:20261030T120000Z\n"
                    "RECURRENCE-ID:20261120T200000Z\nDTSTART:20261120T200000Z\n"
                    "DTEND:20261120T220000Z\nSUMMARY:Pizza Party\n"
                    "ORGANIZER:mailto:jeff@example.com\n"
                    "ATTENDEE;CN=Alice:mailto:alice@example.com\nSEQUENCE:1\nEND:VEVENT\n")
        new = old.replace("END:VCALENDAR", override + "END:VCALENDAR")
        # Same master attendees, but the override drops Bob and Carol:
        # a per-instance change, explicitly unsupported.
        assert plan(old, new) == []

    def test_override_with_same_attendees_now_plans_nothing(self):
        # Multi-VEVENT objects are rejected entirely, even
        # when the override's attendee set matches the master.
        old = _event([ALICE, BOB])
        override = ("BEGIN:VEVENT\nUID:pizza-1\nDTSTAMP:20261030T120000Z\n"
                    "RECURRENCE-ID:20261120T200000Z\nDTSTART:20261120T200000Z\n"
                    "DTEND:20261120T220000Z\nSUMMARY:Pizza Party\n"
                    "ORGANIZER:mailto:jeff@example.com\n"
                    "ATTENDEE;CN=Alice:mailto:alice@example.com\n"
                    "ATTENDEE;CN=Bob:mailto:bob@example.com\nSEQUENCE:1\nEND:VEVENT\n")
        new = _event([ALICE, BOB], dtstart="20261113T210000Z").replace(
            "END:VCALENDAR", override + "END:VCALENDAR")
        assert plan(old, new) == []

    def test_unsupported_itip_method_raises(self):
        import pytest

        from radicale.hook.email.scheduling import build_itip_ics
        with pytest.raises(ValueError):
            build_itip_ics(_event([ALICE]), "PUBLISH", "alice@example.com")

    def test_mass_email_and_itip_is_config_error(self):
        import pytest

        from radicale.hook.email import EmailConfig, MessageTemplate
        cfg = EmailConfig(host="smtp.example.com", port=587, security="starttls",
                          ssl_verify_mode="REQUIRED", username="", password="",
                          from_email="jeff@example.com", send_mass_emails=True,
                          dryrun=True,
                          new_or_added_to_event_template=MessageTemplate(subject="x", body="y"),
                          deleted_or_removed_from_event_template=MessageTemplate(subject="x", body="y"),
                          updated_event_template=MessageTemplate(subject="x", body="y"),
                          itip_enabled=True, itip_owner_map="jeff=jeff@example.com")
        with pytest.raises(ValueError):
            cfg.validate_itip_config()

    def test_itip_message_parses_as_client_would(self):
        # Client-compatibility check without a GUI client: parse the
        # MIME message the way Gmail/Outlook/Thunderbird would, and
        # require method, METHOD property, recipient, and no leak.
        import email
        from email import policy
        new = _event([ALICE, CAROL])
        itip = build_itip_ics(new, "REQUEST", "carol@example.com")
        message = build_itip_message("jeff@example.com", "carol@example.com",
                                     "Added", "Hello Carol", itip, "REQUEST")
        parsed = email.message_from_string(message, policy=policy.default)
        parts = list(parsed.walk())
        cal = [p for p in parts if p.get_content_type() == "text/calendar"]
        assert len(cal) == 1
        assert cal[0].get_param("method") == "REQUEST"
        payload = cal[0].get_payload(decode=True).decode()
        assert "METHOD:REQUEST" in payload
        assert "carol@example.com" in payload
        assert "alice@example.com" not in payload


class TestMandatoryMapAndMasterParsing:
    """Mandatory map, master-only parsing, multi-VEVENT rejection."""

    def test_parse_event_selects_master_not_first_vevent(self):
        from radicale.hook.email.scheduling import parse_event
        override = ("BEGIN:VEVENT\nUID:pizza-1\nDTSTAMP:20261030T120000Z\n"
                    "RECURRENCE-ID:20261120T200000Z\nDTSTART:20261120T200000Z\n"
                    "DTEND:20261120T220000Z\nSUMMARY:Override\n"
                    "ORGANIZER:mailto:jeff@example.com\n"
                    "ATTENDEE;CN=Alice:mailto:alice@example.com\nSEQUENCE:1\nEND:VEVENT\n")
        # Override first, master second: parse_event must return the master.
        master = _event([ALICE, BOB])
        ics = master.replace("BEGIN:VEVENT", override + "BEGIN:VEVENT", 1)
        parsed = parse_event(ics)
        assert parsed is not None
        assert parsed.uid == "pizza-1"
        assert set(parsed.attendees) == {"alice@example.com", "bob@example.com"}

    def test_parse_event_no_master_returns_none(self):
        from radicale.hook.email.scheduling import parse_event
        override_only = ("BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//Test//EN\n"
                         "BEGIN:VEVENT\nUID:pizza-1\nDTSTAMP:20261030T120000Z\n"
                         "RECURRENCE-ID:20261120T200000Z\nDTSTART:20261120T200000Z\n"
                         "DTEND:20261120T220000Z\nSUMMARY:Override\n"
                         "ORGANIZER:mailto:jeff@example.com\n"
                         "ATTENDEE;CN=Alice:mailto:alice@example.com\nSEQUENCE:1\nEND:VEVENT\n"
                         "END:VCALENDAR\n")
        assert parse_event(override_only) is None

    def test_multi_vevent_created_event_plans_nothing(self):
        extra = ("BEGIN:VEVENT\nUID:second-1\nDTSTAMP:20261030T120000Z\n"
                 "DTSTART:20261114T200000Z\nDTEND:20261114T220000Z\nSUMMARY:Other\n"
                 "ORGANIZER:mailto:jeff@example.com\n"
                 "ATTENDEE;CN=Alice:mailto:alice@example.com\nSEQUENCE:1\nEND:VEVENT\n")
        new = _event([ALICE, BOB]).replace("END:VCALENDAR", extra + "END:VCALENDAR")
        assert plan(None, new) == []

    def test_itip_without_owner_map_is_config_error(self):
        import pytest

        from radicale.hook.email import EmailConfig, MessageTemplate
        cfg = EmailConfig(host="smtp.example.com", port=587, security="starttls",
                          ssl_verify_mode="REQUIRED", username="", password="",
                          from_email="jeff@example.com", send_mass_emails=False,
                          dryrun=True,
                          new_or_added_to_event_template=MessageTemplate(subject="x", body="y"),
                          deleted_or_removed_from_event_template=MessageTemplate(subject="x", body="y"),
                          updated_event_template=MessageTemplate(subject="x", body="y"),
                          itip_enabled=True, itip_owner_map="")
        with pytest.raises(ValueError):
            cfg.validate_itip_config()
        cfg.itip_owner_map = "jeff=jeff@example.com"
        cfg.validate_itip_config()  # no error with an explicit map

    def test_itip_disabled_without_map_is_allowed(self):
        from radicale.hook.email import EmailConfig, MessageTemplate
        cfg = EmailConfig(host="smtp.example.com", port=587, security="starttls",
                          ssl_verify_mode="REQUIRED", username="", password="",
                          from_email="jeff@example.com", send_mass_emails=False,
                          dryrun=True,
                          new_or_added_to_event_template=MessageTemplate(subject="x", body="y"),
                          deleted_or_removed_from_event_template=MessageTemplate(subject="x", body="y"),
                          updated_event_template=MessageTemplate(subject="x", body="y"),
                          itip_enabled=False, itip_owner_map="")
        cfg.validate_itip_config()  # legacy mode needs no map


class TestBuilderGuardAndCancelSequence:
    """No bare-username fallback, builder guard, CANCEL sequence."""

    def test_cancel_sequence_uses_explicit_sequence(self):
        old = _event([ALICE, BOB, CAROL], sequence=3)
        itip = build_itip_ics(old, "CANCEL", "carol@example.com", sequence=6)
        assert "SEQUENCE:6" in itip
        # Without an explicit sequence, the old behaviour remains: source + 1.
        itip = build_itip_ics(old, "CANCEL", "carol@example.com")
        assert "SEQUENCE:4" in itip

    def test_cancel_sequence_for_removed_attendee_uses_max_plus_one(self):
        # Simulate the hook's _send_planned calculation: an update
        # that removes Carol and bumps SEQUENCE from 1 to 5 must
        # cancel with 6, not 2, so the CANCEL is newer than the
        # updated event as well as the old one.
        from radicale.hook.email.scheduling import parse_event
        old = _event([ALICE, BOB, CAROL], sequence=1)
        new = _event([ALICE, BOB], sequence=5, dtstart="20261113T210000Z")
        old_seq = parse_event(old).sequence
        new_seq = parse_event(new).sequence
        itip = build_itip_ics(old, "CANCEL", "carol@example.com",
                              sequence=max(old_seq, new_seq) + 1)
        assert "SEQUENCE:6" in itip
        assert "METHOD:CANCEL" in itip


def _email_config(**kwargs):
    from radicale.hook.email import EmailConfig, MessageTemplate
    options = dict(host="smtp.example.com", port=587, security="starttls",
                   ssl_verify_mode="REQUIRED", username="", password="",
                   from_email="jeff@example.com", send_mass_emails=False,
                   dryrun=True,
                   new_or_added_to_event_template=MessageTemplate(subject="x", body="y"),
                   deleted_or_removed_from_event_template=MessageTemplate(subject="x", body="y"),
                   updated_event_template=MessageTemplate(subject="x", body="y"),
                   itip_enabled=True, itip_owner_map="")
    options.update(kwargs)
    return EmailConfig(**options)


class TestOrganizerIsUsername:
    """itip_organizer_is_username: a username that is an email owns it."""

    def test_email_username_is_an_owner_identity(self):
        from radicale.hook.email.scheduling import resolve_owner_identities
        assert resolve_owner_identities(
            "jeff@example.com", {}, organizer_is_username=True) == ["jeff@example.com"]
        # Compared case-insensitively, like the map.
        assert resolve_owner_identities(
            "Jeff@Example.COM", {}, organizer_is_username=True) == ["jeff@example.com"]

    def test_username_email(self):
        from radicale.hook.email.scheduling import username_email
        assert username_email(" Jeff@Example.COM ") == "jeff@example.com"
        for actor in ["jeff", "jeff@", "@example.com", "a@b@example.com",
                      "jeff smith@example.com", "", None]:
            assert username_email(actor) is None, actor

    def test_non_email_username_gets_nothing(self):
        from radicale.hook.email.scheduling import resolve_owner_identities
        for actor in ["jeff", "jeff@", "@example.com", "a@b@example.com",
                      "jeff smith@example.com", "", None]:
            assert resolve_owner_identities(
                actor, {}, organizer_is_username=True) == [], actor

    def test_option_off_keeps_map_only(self):
        from radicale.hook.email.scheduling import resolve_owner_identities
        assert resolve_owner_identities("jeff@example.com", {}) == []
        assert resolve_owner_identities(
            "jeff@example.com", {"jeff@example.com": "other@example.com"}) == [
            "other@example.com"]

    def test_map_and_option_together(self):
        from radicale.hook.email.scheduling import resolve_owner_identities
        m = {"jeff": "jeff@example.com",
             "boss@example.com": "jeff@example.com",
             "alice@example.com": "alice@example.com"}
        # A non-email actor still gets its mapped address.
        assert resolve_owner_identities("jeff", m, True) == ["jeff@example.com"]
        # An email actor gets both its mapped address and itself.
        owner = resolve_owner_identities("boss@example.com", m, True)
        assert owner == ["jeff@example.com", "boss@example.com"]
        event = _event([ALICE, BOB])
        assert len(plan(None, event, owner=owner)) == 2
        # Same address in the map and as username: listed once.
        assert resolve_owner_identities("alice@example.com", m, True) == [
            "alice@example.com"]

    def test_mismatched_organizer_plans_nothing(self):
        from radicale.hook.email.scheduling import resolve_owner_identities
        owner = resolve_owner_identities("alice@example.com", {}, True)
        assert plan(None, _event([ALICE, BOB]), owner=owner) == []

    def test_empty_map_with_option_is_accepted(self):
        _email_config(itip_organizer_is_username=True).validate_itip_config()

    def test_empty_map_without_option_is_still_config_error(self):
        import pytest
        with pytest.raises(ValueError):
            _email_config(itip_organizer_is_username=False).validate_itip_config()

    def test_mass_email_with_option_is_still_config_error(self):
        import pytest
        with pytest.raises(ValueError):
            _email_config(itip_organizer_is_username=True,
                          send_mass_emails=True).validate_itip_config()


class TestHookWiringOrganizerIsUsername(BaseTest):
    """End-to-end: empty map, ownership from the username, dry-run."""

    def setup_method(self) -> None:
        BaseTest.setup_method(self)
        import os
        rights_file_path = os.path.join(self.colpath, "rights")
        with open(rights_file_path, "w") as f:
            f.write("[allow all]\nuser: .*\ncollection: .*\npermissions: RrWw")
        self.configure({
            "rights": {"file": rights_file_path, "type": "from_file"}})
        self.configure({"auth": {"type": "none"}})
        # No itip_owner_map: hook load must accept it with the option.
        self.configure({
            "hook": {"type": "email", "dryrun": "True",
                     "itip_enabled": "True",
                     "from_email": "calendar@example.com",
                     "itip_organizer_is_username": "True"}})

    def _put_new_event(self, login, caplog):
        caplog.set_level(logging.INFO)
        self.mkcalendar("/calendar.ics/", login=login)
        start = datetime.now() + timedelta(days=1)
        event = _event([ALICE, BOB], dtstart=start.strftime("%Y%m%dT%H%M%SZ"),
                       dtend=(start + timedelta(hours=2)).strftime("%Y%m%dT%H%M%SZ"))
        self.put("/calendar.ics/event1.ics", event, login=login)
        return [log for log in caplog.messages
                if "DRY-RUN send_scheduling_email / to_addresses" in log]

    def test_email_username_matching_organizer_sends(self, caplog):
        assert self._put_new_event("Jeff@Example.com:password", caplog) == [
            "Hook 'email': DRY-RUN send_scheduling_email / to_addresses=['alice@example.com']",
            "Hook 'email': DRY-RUN send_scheduling_email / to_addresses=['bob@example.com']",
        ]

    def test_email_username_other_organizer_sends_nothing(self, caplog):
        # Organizer is jeff@example.com, the user is Alice.
        assert self._put_new_event("alice@example.com:password", caplog) == []

    def test_non_email_username_sends_nothing(self, caplog):
        assert self._put_new_event("jeff:password", caplog) == []


class TestCalendarUserAddressSet(BaseTest):
    """calendar-user-address-set lists mailto:<username> with the option."""

    PROPFIND = """<?xml version="1.0" encoding="utf-8"?>
<propfind xmlns="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
  <prop><C:calendar-user-address-set/></prop>
</propfind>"""

    def setup_method(self) -> None:
        BaseTest.setup_method(self)
        import os
        rights_file_path = os.path.join(self.colpath, "rights")
        with open(rights_file_path, "w") as f:
            f.write("[allow all]\nuser: .*\ncollection: .*\npermissions: RrWw")
        self.configure({
            "rights": {"file": rights_file_path, "type": "from_file"}})
        self.configure({"auth": {"type": "none"}})

    def _enable(self, enabled=True):
        self.configure({
            "hook": {"type": "email", "dryrun": "True",
                     "itip_enabled": "True",
                     "from_email": "calendar@example.com",
                     "itip_owner_map": "" if enabled else "jeff=jeff@example.com",
                     "itip_organizer_is_username": str(enabled)}})

    def _hrefs(self, path, user):
        _, responses = self.propfind(path, self.PROPFIND,
                                     login="%s:password" % user)
        response = responses[path.replace("@", "%40")]
        assert not isinstance(response, int)
        status, prop = response["C:calendar-user-address-set"]
        assert status == 200
        return [href.text for href in prop]

    def test_email_user_gets_mailto_and_path(self):
        self._enable()
        assert self._hrefs("/Jeff@Example.com/", "Jeff@Example.com") == [
            "mailto:jeff@example.com", "/Jeff%40Example.com/"]

    def test_option_off_gets_path_only(self):
        self._enable(False)
        assert self._hrefs("/jeff@example.com/", "jeff@example.com") == [
            "/jeff%40example.com/"]

    def test_non_email_user_gets_path_only(self):
        self._enable()
        assert self._hrefs("/jeff/", "jeff") == ["/jeff/"]

    def test_other_users_principal_gets_no_mailto(self):
        self._enable()
        # Create Bob's principal, then look at it as Jeff.
        self._hrefs("/bob@example.com/", "bob@example.com")
        assert self._hrefs("/bob@example.com/", "jeff@example.com") == [
            "/bob%40example.com/"]
