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

"""Scheduling decisions for the email hook.

This is not a full CalDAV Scheduling implementation (RFC 6638):
no inbox/outbox, no REPLY processing, no calendar-auto-schedule.

It decides, from the old and new events, which per-recipient
iTIP REQUEST/CANCEL messages a change requires, and builds
those messages as text/calendar parts listing only the
recipient.

Supported: single-VEVENT events only. A single VEVENT may
define a recurring series with RRULE. Multi-VEVENT objects are
rejected with no messages; per-instance (RECURRENCE-ID)
changes are not supported.

Delivery is best-effort SMTP: this module plans messages only,
it does not queue, retry, or track delivery. An SMTP failure
loses the message, and a repeated save plans nothing.
"""

import re
from dataclasses import dataclass
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate
from typing import Dict, List, Optional, Sequence, Tuple

import vobject
from dateutil.tz import tzutc

__all__ = [
    "AttendeeInfo",
    "EventInfo",
    "PlannedMessage",
    "build_itip_ics",
    "build_itip_message",
    "check_ownership",
    "parse_owner_map",
    "resolve_owner_identities",
    "username_email",
    "extract_email",
    "parse_event",
    "plan_messages",
]


def extract_email(value: Optional[str]) -> Optional[str]:
    """Extract a lower-cased email address from a calendar-user value."""
    if not value:
        return None
    value = value.strip().lower()
    match = re.search(r"mailto:([^;]+)", value)
    if match:
        return match.group(1)
    return value if "@" in value else None


def _content_lines(component, name: str):
    lines = component.contents.get(name.lower(), [])
    return lines if isinstance(lines, (list, tuple)) else [lines]


def _first_value(component, name: str):
    lines = _content_lines(component, name)
    return lines[0].value if lines else None


def _first_param(component, name: str, param: str):
    lines = _content_lines(component, name)
    if not lines:
        return None
    params = lines[0].params or {}
    values = params.get(param, [])
    return values[0] if values else None


def _param_of(line, param: str):
    params = getattr(line, "params", {}) or {}
    values = params.get(param, [])
    return values[0] if values else None


@dataclass(frozen=True)
class AttendeeInfo:
    email: str
    name: Optional[str] = None
    schedule_agent: Optional[str] = None
    partstat: Optional[str] = None


@dataclass
class EventInfo:
    uid: Optional[str]
    sequence: int
    organizer_email: Optional[str]
    organizer_schedule_agent: Optional[str]
    attendees: Dict[str, AttendeeInfo]
    # Hashable summary of everything except attendees, SEQUENCE and
    # DTSTAMP. DTSTAMP changes on almost every client save and must
    # not, by itself, count as an event update; SEQUENCE is preserved
    # in outgoing messages but is likewise not treated as a content
    # change here, because clients bump it on attendee-only edits too.
    details: Tuple


def parse_event(ics: Optional[str]) -> Optional[EventInfo]:
    """Parse the master VEVENT of a calendar object, or None.

    The master is the first VEVENT without a RECURRENCE-ID. If
    every VEVENT has one, there is no master to diff, so return
    None rather than diffing an override as if it were the master.
    """
    if not ics:
        return None
    try:
        calendar = vobject.readOne(ics)
    except Exception:
        return None
    vevents = getattr(calendar, "vevent_list", None)
    if not vevents:
        try:
            vevents = [calendar.vevent]
        except Exception:
            return None
    if not vevents:
        return None
    event = None
    for candidate in vevents:
        if _first_value(candidate, "recurrence-id") is None:
            event = candidate
            break
    if event is None:
        return None
    organizer_value = _first_value(event, "organizer")
    sequence_value = _first_value(event, "sequence")
    try:
        sequence = int(sequence_value) if sequence_value is not None else 0
    except (TypeError, ValueError):
        sequence = 0
    attendees: Dict[str, AttendeeInfo] = {}
    for line in _content_lines(event, "attendee"):
        email = extract_email(line.value)
        if email and email not in attendees:
            attendees[email] = AttendeeInfo(
                email=email,
                name=_param_of(line, "CN"),
                schedule_agent=_param_of(line, "SCHEDULE-AGENT"),
                partstat=_param_of(line, "PARTSTAT"),
            )

    def raw(name: str):
        value = _first_value(event, name)
        return None if value is None else str(value)

    details = (
        raw("summary"),
        raw("description"),
        raw("location"),
        raw("dtstart"),
        raw("dtend"),
        raw("duration"),
        raw("status"),
        raw("rrule"),
        raw("rdate"),
        raw("exdate"),
        raw("recurrence-id"),
        organizer_value,
    )
    return EventInfo(
        uid=raw("uid"),
        sequence=sequence,
        organizer_email=extract_email(organizer_value),
        organizer_schedule_agent=_first_param(event, "organizer", "SCHEDULE-AGENT"),
        attendees=attendees,
        details=details,
    )


@dataclass(frozen=True)
class PlannedMessage:
    """One scheduling message the server should send, or none at all."""
    method: str  # "REQUEST" or "CANCEL"
    recipient_email: str
    recipient_name: Optional[str]
    # "created", "added", "removed", "updated" or "deleted".
    kind: str


def parse_owner_map(text: Optional[str]) -> Dict[str, str]:
    """Parse an actor-to-organizer-email map.

    Format: ``actor=email, actor2=email2``. Actors and emails are
    lower-cased. Raises ValueError on a malformed entry, an
    email without ``@``, or a duplicate actor, so a bad map
    fails at startup instead of being silently ignored.
    """
    result: Dict[str, str] = {}
    if not text:
        return result
    if not isinstance(text, str):
        raise ValueError("itip_owner_map must be a string")
    for entry in text.split(","):
        entry = entry.strip()
        if not entry:
            continue
        if entry.count("=") != 1:
            raise ValueError("malformed itip_owner_map entry: %r" % entry)
        actor, email = entry.split("=", 1)
        actor = actor.strip().lower()
        email = email.strip().lower()
        if not actor or not email or "@" not in email:
            raise ValueError("malformed itip_owner_map entry: %r" % entry)
        if actor in result:
            raise ValueError("duplicate actor in itip_owner_map: %r" % actor)
        result[actor] = email
    return result


# One "@" with a non-empty local part and domain, no whitespace.
_USERNAME_EMAIL = re.compile(r"[^@\s]+@[^@\s]+")


def username_email(actor: Optional[str]) -> Optional[str]:
    """The lower-cased email address an actor's username is, or None."""
    if not actor:
        return None
    actor = actor.strip().lower()
    return actor if _USERNAME_EMAIL.fullmatch(actor) else None


def resolve_owner_identities(actor: Optional[str],
                             owner_map: Optional[Dict[str, str]],
                             organizer_is_username: bool = False) -> List[str]:
    """Resolve the owner identities for one actor.

    The mapped email for the actor counts. With
    ``organizer_is_username``, an actor whose username is an
    email address also owns that address. Any other actor gets
    no identities. The SMTP ``from_email`` is never evidence of
    ownership.
    """
    if not actor:
        return []
    actor = actor.strip().lower()
    identities: List[str] = []
    mapped = (owner_map or {}).get(actor)
    if mapped:
        identities.append(mapped)
    if organizer_is_username:
        email = username_email(actor)
        if email and email not in identities:
            identities.append(email)
    return identities


def check_ownership(organizer_email: Optional[str],
                    owner_identities: Optional[Sequence[str]]) -> bool:
    """True only if an owner identity matches the organizer.

    Only a full email identity counts, matched exactly
    (case-insensitive). A bare username does not match. The
    SMTP ``from_email`` is never used here. No match means no
    messages may be sent: this is the guard against using an
    attendee copy to notify the organizer's other guests.
    """
    if not organizer_email or not owner_identities:
        return False
    organizer_email = organizer_email.strip().lower()
    for identity in owner_identities:
        if not identity:
            continue
        if identity.strip().lower() == organizer_email:
            return True
    return False


def _eligible(event: EventInfo, attendee: AttendeeInfo) -> bool:
    if attendee.email == event.organizer_email:
        return False
    # RFC 6638, section 3.2.1.1: only SERVER (the default, when the
    # parameter is absent) gets a scheduling message. CLIENT and
    # NONE both mean the server sends nothing to that attendee.
    agent = (attendee.schedule_agent or "").upper()
    return agent in ("", "SERVER")


def _vevent_count(ics: Optional[str]) -> int:
    """Number of VEVENTs in a calendar object, or 0 on parse failure."""
    if not ics:
        return 0
    try:
        calendar = vobject.readOne(ics)
    except Exception:
        return 0
    vevents = getattr(calendar, "vevent_list", None)
    if vevents:
        return len(vevents)
    try:
        calendar.vevent
        return 1
    except Exception:
        return 0


def plan_messages(old_ics: Optional[str], new_ics: Optional[str],
                  deleted: bool = False,
                  owner_identities: Optional[Sequence[str]] = None) -> List[PlannedMessage]:
    """Decide which scheduling messages an event change requires.

    ``old_ics`` is the event before the change (None for a new
    event), ``new_ics`` is the event after it. For
    ``deleted=True`` only ``old_ics`` is used and every eligible
    attendee gets a CANCEL. An empty list means nothing is sent:
    a repeated save, an unproved organizer, an unparseable
    previous event, or a rejected multi-VEVENT object. The
    caller logs the unproved-ownership and unparseable cases.
    """
    new_event = None if deleted else parse_event(new_ics)
    if deleted:
        old_event = parse_event(old_ics)
        if old_event is None:
            return []
        if _vevent_count(old_ics) > 1:
            return []
        if not check_ownership(old_event.organizer_email, owner_identities):
            return []
        return [PlannedMessage("CANCEL", a.email, a.name, "deleted")
                for a in old_event.attendees.values()
                if _eligible(old_event, a)]
    if new_event is None:
        return []
    if not check_ownership(new_event.organizer_email, owner_identities):
        return []
    if old_ics is None:
        if _vevent_count(new_ics) > 1:
            return []
        return [PlannedMessage("REQUEST", a.email, a.name, "created")
                for a in new_event.attendees.values()
                if _eligible(new_event, a)]
    old_event = parse_event(old_ics)
    if old_event is None:
        # Without a previous event there is nothing to diff against.
        return []
    # Do not infer changes across different events or organizers.
    if not old_event.uid or old_event.uid != new_event.uid:
        return []
    if old_event.organizer_email != new_event.organizer_email:
        return []
    # Multi-VEVENT objects are rejected, not approximated.
    if _vevent_count(old_ics) > 1 or _vevent_count(new_ics) > 1:
        return []
    planned: List[PlannedMessage] = []
    for email, attendee in new_event.attendees.items():
        if email not in old_event.attendees and _eligible(new_event, attendee):
            planned.append(PlannedMessage("REQUEST", email, attendee.name, "added"))
    for email, attendee in old_event.attendees.items():
        if email not in new_event.attendees and _eligible(old_event, attendee):
            planned.append(PlannedMessage("CANCEL", email, attendee.name, "removed"))
    if new_event.details != old_event.details:
        for email, attendee in new_event.attendees.items():
            if email in old_event.attendees and _eligible(new_event, attendee):
                planned.append(PlannedMessage("REQUEST", email, attendee.name, "updated"))
    return planned


def _strip_scheduling_params(line) -> None:
    """Remove CalDAV server directives from a property line, in place."""
    params = getattr(line, "params", None)
    if not params:
        return
    for key in ("SCHEDULE-AGENT", "SCHEDULE-FORCE-SEND"):
        params.pop(key, None)


def build_itip_ics(source_ics: str, method: str, recipient_email: str,
                   sequence: Optional[int] = None) -> str:
    """Build a per-recipient iTIP calendar object.

    ``source_ics`` is the new event for REQUEST and the old event
    for CANCEL (a removed attendee is not in the new event). The
    result has METHOD set, the organizer preserved, and exactly
    one ATTENDEE (the recipient). ``SCHEDULE-AGENT`` and
    ``SCHEDULE-FORCE-SEND`` are stripped from ORGANIZER and
    ATTENDEE lines.

    A multi-VEVENT source raises ValueError, matching the
    planner's rejection; the builder enforces the restriction
    independently.

    Revision handling (RFC 5546, RFC 6638 section 3.2.5):
    DTSTAMP is set to generation time. For REQUEST, SEQUENCE is
    preserved from the source. For CANCEL, SEQUENCE is
    ``sequence`` if given, otherwise source SEQUENCE + 1. The
    hook passes max(old, new) + 1 for a removed attendee, so
    the CANCEL supersedes both event revisions. Live-client
    behaviour for out-of-order CANCELs is not yet verified.
    """
    if method not in ("REQUEST", "CANCEL"):
        raise ValueError("unsupported iTIP method: %r" % method)
    if _vevent_count(source_ics) > 1:
        raise ValueError("multi-VEVENT calendar objects are rejected")
    calendar = vobject.readOne(source_ics)
    # vobject stores METHOD as a top-level property of VCALENDAR.
    if "method" in calendar.contents:
        calendar.contents["method"][0].value = method
    else:
        calendar.add("method").value = method
    vevents = getattr(calendar, "vevent_list", None) or [calendar.vevent]
    recipient = recipient_email.strip().lower()
    # vobject serializes DTSTAMP via dateutil's tzutc, not via
    # datetime.timezone.utc (which it cannot guess a TZID for).
    now = datetime.now(tzutc())
    found_recipient = False
    for event in vevents:
        # DTSTAMP: time this message is generated.
        dtstamp_lines = _content_lines(event, "dtstamp")
        if dtstamp_lines:
            dtstamp_lines[0].value = now
        # SEQUENCE: preserve for REQUEST; for CANCEL use the
        # explicit sequence if given, otherwise source + 1.
        if method == "CANCEL":
            sequence_lines = _content_lines(event, "sequence")
            target = sequence
            if target is None:
                try:
                    target = int(sequence_lines[0].value) + 1 if sequence_lines else 1
                except (TypeError, ValueError):
                    target = 1
            if sequence_lines:
                sequence_lines[0].value = target
            else:
                try:
                    event.add("sequence").value = target
                except Exception:
                    pass
        # Strip server directives from the organizer line.
        for line in _content_lines(event, "organizer"):
            _strip_scheduling_params(line)
        # Filter attendees in this VEVENT to the recipient only.
        attendee_lines = _content_lines(event, "attendee")
        if not attendee_lines:
            continue
        kept = []
        for line in attendee_lines:
            if extract_email(line.value) == recipient:
                _strip_scheduling_params(line)
                kept.append(line)
                found_recipient = True
        if kept:
            event.contents["attendee"] = kept
        else:
            # This VEVENT lists other attendees but not the
            # recipient: drop its attendee list rather than
            # leaking it to the recipient.
            event.contents.pop("attendee", None)
    if not found_recipient:
        # The recipient was not an attendee of the source event
        # (should not happen for a planned message, but never invent
        # a recipient line with invented parameters).
        raise ValueError("recipient %r is not an attendee of the event" % recipient_email)
    return calendar.serialize()


def build_itip_message(from_email: str, to_email: str, subject: str,
                       body_text: str, itip_ics: str, method: str) -> str:
    """Build an iMIP message: plain text plus a text/calendar part.

    The calendar part carries ``method=REQUEST`` (or CANCEL) so a
    receiving client can process it as an update to the existing
    event instead of importing a second, duplicate event.
    """
    message = MIMEMultipart("mixed")
    message["From"] = from_email
    message["To"] = to_email
    message["Subject"] = subject
    message["Date"] = formatdate(localtime=True)
    message.attach(MIMEText(body_text, "plain"))
    calendar_part = MIMEText(itip_ics, "calendar", "utf-8")
    calendar_part.set_param("method", method)
    calendar_part.add_header("Content-Disposition",
                             'attachment; filename="event.ics"')
    message.attach(calendar_part)
    return message.as_string()
