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

"""A lone recurrence override is one event, not two."""

import pytest
import vobject

from radicale.item import Item
from radicale.item.filter import visit_time_ranges


def _visit(body, range_fn, infinity_fn):
    text = (
        "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:test\r\n"
        + body + "END:VCALENDAR\r\n")
    item = Item(collection_path="calendar", vobject_item=vobject.readOne(text))
    visit_time_ranges(
        item.vobject_item, "VEVENT", range_fn, infinity_fn,
        max_occurrences=5)


def test_lone_override_is_visited_once():
    """One override and no master is that instance, from DTSTART to DTEND."""
    body = (
        "BEGIN:VEVENT\r\nUID:a\r\nRECURRENCE-ID:20130102T000000Z\r\n"
        "DTSTART:20130102T010000Z\r\nDTEND:20130102T020000Z\r\n"
        "END:VEVENT\r\n")
    seen = []

    def collect(start, end, is_recurrence):
        seen.append((start, end, is_recurrence))
        return False

    _visit(body, collect, lambda _start: False)
    assert len(seen) == 1
    start, end, is_recurrence = seen[0]
    assert is_recurrence is False
    assert start.hour == 1
    assert end.hour == 2


def test_two_overrides_without_a_master_are_rejected():
    body = (
        "BEGIN:VEVENT\r\nUID:a\r\nRECURRENCE-ID:20130102T000000Z\r\n"
        "DTSTART:20130102T010000Z\r\nEND:VEVENT\r\n"
        "BEGIN:VEVENT\r\nUID:a\r\nRECURRENCE-ID:20130103T000000Z\r\n"
        "DTSTART:20130103T010000Z\r\nEND:VEVENT\r\n")
    with pytest.raises(ValueError, match="Main component missing"):
        _visit(body, lambda *_args: False, lambda _start: False)


def test_master_with_one_override_still_visits_the_override_first():
    """The override stays a recurrence. The series is not a second copy of it."""
    body = (
        "BEGIN:VEVENT\r\nUID:a\r\nDTSTART:20130101T000000Z\r\n"
        "RRULE:FREQ=DAILY\r\nEND:VEVENT\r\n"
        "BEGIN:VEVENT\r\nUID:a\r\nRECURRENCE-ID:20130101T000000Z\r\n"
        "DTSTART:20130101T050000Z\r\nEND:VEVENT\r\n")
    trace = []

    def range_fn(start, _end, is_recurrence):
        trace.append(("range", start, is_recurrence))
        return False

    def infinity(start):
        trace.append(("inf", start))
        return True

    _visit(body, range_fn, infinity)
    assert trace[0][0] == "range"
    assert trace[0][2] is True
    assert trace[0][1].hour == 5
    assert trace[1][0] == "inf"
    assert trace[1][1] > trace[0][1]
    assert [row[2] for row in trace if row[0] == "range"].count(True) == 1
