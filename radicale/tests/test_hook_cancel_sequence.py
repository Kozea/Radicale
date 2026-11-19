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

"""A CANCEL for an event with no SEQUENCE is still built."""


def _event_ics(sequence=None):
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Radicale test//EN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        "UID:evt-1",
        "DTSTAMP:20300101T000000Z",
        "DTSTART:20300101T110000Z",
        "DTEND:20300101T120000Z",
        "SUMMARY:Title",
        "ORGANIZER:mailto:owner@example.com",
        "ATTENDEE;CN=Bob:mailto:bob@example.com",
    ]
    if sequence is not None:
        lines.append("SEQUENCE:%s" % sequence)
    lines.extend(["END:VEVENT", "END:VCALENDAR"])
    return "\n".join(lines) + "\n"


def test_cancel_without_sequence_is_sent_as_sequence_one():
    from radicale.hook.email import scheduling

    source = _event_ics(sequence=None)
    cancelled = scheduling.build_itip_ics(source, "CANCEL", "bob@example.com")
    assert "METHOD:CANCEL" in cancelled
    assert "SEQUENCE:1" in cancelled
    assert "mailto:bob@example.com" in cancelled.lower()
