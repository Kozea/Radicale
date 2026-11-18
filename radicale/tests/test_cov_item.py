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

"""Outcome tests for calendar and address-book item handling and filters."""

import datetime
import logging
from xml.etree import ElementTree as ET

import pytest
import vobject

from radicale import pathutils, utils, xmlutils
from radicale.item import (UID_SUFFIX, Item, check_and_sanitize_items,
                           check_and_sanitize_props, find_available_uid,
                           find_tag, get_uid_from_object,
                           predict_tag_of_parent_collection,
                           predict_tag_of_whole_collection, read_components,
                           replace_placeholders, trigger_to_timedelta, verify)
from radicale.item.filter import (DATETIME_MAX, DATETIME_MIN, TIMESTAMP_MAX,
                                  TIMESTAMP_MIN, comp_match,
                                  param_filter_match, parse_time_range,
                                  simplify_prefilters, text_match,
                                  time_range_match, visit_time_ranges)
from radicale.log import LOG_LEVEL_TRACE
from radicale.tests.helpers import get_file_content

UTC = datetime.timezone.utc


@pytest.fixture(autouse=True)
def _radicale_warnings_only(caplog):
    """Suite default is DEBUG; the missing arcs are the debug-disabled sides."""
    caplog.set_level(logging.WARNING, logger="radicale")


def _calendar(body):
    text = (
        "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:test\r\n"
        + body + "END:VCALENDAR\r\n")
    return read_components(text)


def _item(text, **kwargs):
    kwargs.setdefault("collection_path", "calendar")
    return Item(vobject_item=vobject.readOne(text), **kwargs)


def _calendar_item(body, **kwargs):
    return _item(
        "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:test\r\n"
        + body + "END:VCALENDAR\r\n",
        **kwargs)


class _AddressBook:
    """Stand-in parent: conversion copies ``collection``, not the path."""

    path = "abook"


def _vcard(props, href="person.vcf", last_modified=None, etag=None):
    text = "BEGIN:VCARD\r\nVERSION:3.0\r\n" + "".join(
        prop + "\r\n" for prop in props) + "END:VCARD\r\n"
    return Item(
        collection_path="abook",
        collection=_AddressBook(),
        vobject_item=vobject.readOne(text),
        href=href,
        last_modified=last_modified,
        etag=etag)


def _el(tag, attrib=None, text=None, children=()):
    element = ET.Element(xmlutils.make_clark(tag))
    if attrib:
        for key, value in attrib.items():
            element.set(key, value)
    if text is not None:
        element.text = text
    for child in children:
        element.append(child)
    return element


def _time_range(start=None, end=None):
    attrib = {}
    if start is not None:
        attrib["start"] = start
    if end is not None:
        attrib["end"] = end
    return _el("C:time-range", attrib)


def _enable_periods(monkeypatch):
    monkeypatch.setattr(utils, "vobject_supports_period", lambda: True)


def _sanitize(items, limit=100, **kwargs):
    kwargs.setdefault("tag", "VCALENDAR")
    check_and_sanitize_items(items, limit, **kwargs)
    return items


# --- prediction, identity, constructors ------------------------------------


def test_parent_tag_is_none_unless_one_calendar_or_card():
    """A parent collection is predictable only for exactly one known object."""
    calendar = _calendar(
        "BEGIN:VEVENT\r\nUID:one\r\nDTSTART:20130101T000000Z\r\n"
        "END:VEVENT\r\n")[0]
    event = read_components(
        "BEGIN:VEVENT\r\nUID:bare\r\nDTSTART:20130101T000000Z\r\n"
        "END:VEVENT\r\n")[0]
    assert predict_tag_of_parent_collection([]) is None
    assert predict_tag_of_parent_collection([calendar, calendar]) is None
    assert predict_tag_of_parent_collection([calendar]) == "VCALENDAR"
    assert predict_tag_of_parent_collection([event]) is None
    assert event.name == "VEVENT"


def test_whole_collection_tag_falls_back_for_empty_and_unknown():
    """Empty input defaults to an address book; unknown objects use fallback."""
    event = read_components(
        "BEGIN:VEVENT\r\nUID:bare\r\nDTSTART:20130101T000000Z\r\n"
        "END:VEVENT\r\n")[0]
    assert predict_tag_of_whole_collection([]) == "VADDRESSBOOK"
    assert predict_tag_of_whole_collection(
        [], fallback_tag="VCALENDAR") == "VCALENDAR"
    assert predict_tag_of_whole_collection([event]) is None
    assert predict_tag_of_whole_collection(
        [event], fallback_tag="VADDRESSBOOK") == "VADDRESSBOOK"


def test_timezone_only_calendar_has_no_component_tag_or_uid():
    """A calendar that only carries a timezone has nothing to address."""
    calendar = _calendar(
        "BEGIN:VTIMEZONE\r\nTZID:Test/Zone\r\nBEGIN:STANDARD\r\n"
        "DTSTART:19701101T020000\r\nTZOFFSETFROM:-0400\r\nTZOFFSETTO:-0500\r\n"
        "TZNAME:EST\r\nEND:STANDARD\r\nEND:VTIMEZONE\r\n")[0]
    item = Item(collection_path="calendar", vobject_item=calendar)
    assert find_tag(calendar) == ""
    assert item.component_name == ""
    assert get_uid_from_object(calendar) == ""
    assert get_uid_from_object(read_components(
        "BEGIN:VLIST\r\nUID:list-1\r\nFN:List\r\nEND:VLIST\r\n")[0]) == ""


def test_item_requires_text_or_vobject_and_a_collection():
    """The constructor names which required argument is missing."""
    with pytest.raises(ValueError, match="text"):
        Item(collection_path="calendar")
    with pytest.raises(ValueError, match="collection_path"):
        Item(text="BEGIN:VCARD\r\nEND:VCARD\r\n")


def test_unparseable_text_raises_runtime_error_naming_the_item():
    """A stored blob that is not iCalendar or vCard fails when read back."""
    item = Item(collection_path="calendar", href="bad.ics", text="not-a-card")
    with pytest.raises(RuntimeError, match="Failed to parse item 'bad.ics' from 'calendar'"):
        item.vobject_item  # noqa: B018


def test_available_uid_skips_collisions_and_stops_after_1000(monkeypatch):
    """The generator skips one taken UID and gives up when every UID exists."""
    calls = []

    def _exists(name):
        calls.append(name)
        return len(calls) == 1

    uid = find_available_uid(_exists, suffix="-s")
    assert uid == calls[1]
    assert uid.endswith("-s")
    assert calls[0] != uid
    with pytest.raises(RuntimeError, match="No available random UID found"):
        find_available_uid(lambda _name: True)


def test_trigger_duration_units_and_rejected_text():
    """Alarm triggers accept one W/D/H/M count and reject everything else."""
    assert trigger_to_timedelta("2W") == datetime.timedelta(weeks=2)
    assert trigger_to_timedelta("-1W") == datetime.timedelta(weeks=-1)
    assert trigger_to_timedelta("0D") == datetime.timedelta(0)
    assert trigger_to_timedelta("+3D") == datetime.timedelta(days=3)
    assert trigger_to_timedelta("15M") == datetime.timedelta(minutes=15)
    assert trigger_to_timedelta("4H") == datetime.timedelta(hours=4)
    assert trigger_to_timedelta("1S") is None
    assert trigger_to_timedelta("P1D") is None
    assert trigger_to_timedelta("") is None


def test_placeholder_choice_resolves_without_debug_tracing():
    """A resolved ``[value|fallback]`` pair is kept and the walk continues."""
    assert replace_placeholders(
        "X [Ada|no] Y [Bea|no]", {}) == "X Ada Y Bea"
    assert replace_placeholders("[!fn!|Ada]", {}) == "Ada"


# --- check_and_sanitize_items / props --------------------------------------


def test_sanitize_rejects_bad_tag_and_wrong_component_count():
    """Tag and component-count checks fail before any object is rewritten."""
    event = _calendar(
        "BEGIN:VEVENT\r\nUID:a\r\nDTSTART:20130101T000000Z\r\nEND:VEVENT\r\n")
    with pytest.raises(ValueError, match="Unsupported collection tag: 'JOURNAL'"):
        check_and_sanitize_items(event, 10, tag="JOURNAL")
    with pytest.raises(ValueError, match="Item contains 0 components"):
        check_and_sanitize_items([], 10, tag="VCALENDAR")
    with pytest.raises(ValueError, match="Item contains 2 components"):
        check_and_sanitize_items(event + event, 10, tag="VCALENDAR")
    with pytest.raises(RuntimeError, match="VCALENDAR collection contains 2"):
        check_and_sanitize_items(
            event + event, 10, is_collection=True, tag="VCALENDAR")


def test_sanitize_rejects_wrong_object_type_for_the_collection():
    """A vCard cannot live in a calendar, and a calendar cannot be generic."""
    card = read_components(
        "BEGIN:VCARD\r\nVERSION:3.0\r\nUID:c\r\nFN:Ada\r\nEND:VCARD\r\n")
    with pytest.raises(ValueError, match="VCARD"):
        _sanitize(card)
    event = read_components(
        "BEGIN:VEVENT\r\nUID:a\r\nDTSTART:20130101T000000Z\r\nEND:VEVENT\r\n")
    with pytest.raises(ValueError, match="generic collection"):
        check_and_sanitize_items(event, 10, tag="")
    with pytest.raises(ValueError, match="'VSUBSCRIBED' collection"):
        check_and_sanitize_items(event, 10, tag="VSUBSCRIBED")
    # Empty subscribed/generic collections have nothing to reject.
    check_and_sanitize_items([], 10, is_collection=True, tag="")
    check_and_sanitize_items([], 10, is_collection=True, tag="VSUBSCRIBED")


def test_sanitize_rejects_mixed_components_and_uids():
    """One object may not mix component types or VEVENT UIDs."""
    mixed = _calendar(
        "BEGIN:VEVENT\r\nUID:a\r\nDTSTART:20130101T000000Z\r\nEND:VEVENT\r\n"
        "BEGIN:VTODO\r\nUID:a\r\nDTSTART:20130101T000000Z\r\nEND:VTODO\r\n")
    with pytest.raises(ValueError, match="VEVENT.*VTODO"):
        _sanitize(mixed)
    different = _calendar(
        "BEGIN:VEVENT\r\nUID:a\r\nDTSTART:20130101T000000Z\r\nEND:VEVENT\r\n"
        "BEGIN:VEVENT\r\nUID:b\r\nDTSTART:20130102T000000Z\r\nEND:VEVENT\r\n")
    with pytest.raises(ValueError, match="'a', 'b'"):
        _sanitize(different)
    missing = _calendar(
        "BEGIN:VEVENT\r\nUID:a\r\nDTSTART:20130101T000000Z\r\nEND:VEVENT\r\n"
        "BEGIN:VEVENT\r\nDTSTART:20130102T000000Z\r\nEND:VEVENT\r\n")
    with pytest.raises(ValueError, match="without UID"):
        _sanitize(missing)


def test_sanitize_skips_freebusy_and_keeps_it_without_a_uid():
    """VFREEBUSY is stored as-is; it is not given a synthesized UID."""
    items = _calendar(
        "BEGIN:VFREEBUSY\r\nDTSTART:20130101T000000Z\r\n"
        "DTEND:20130102T000000Z\r\nEND:VFREEBUSY\r\n")
    _sanitize(items)
    freebusy = items[0].vfreebusy
    assert freebusy.name == "VFREEBUSY"
    assert not hasattr(freebusy, "uid")


def test_sanitize_fills_an_empty_uid_property_in_a_collection():
    """An existing but blank UID is overwritten, not duplicated."""
    items = _calendar(
        "BEGIN:VEVENT\r\nUID:\r\nDTSTART:20130101T000000Z\r\nEND:VEVENT\r\n")
    assert items[0].vevent.uid.value == ""
    _sanitize(items, is_collection=True)
    filled = items[0].vevent.uid.value
    assert filled
    assert len(items[0].vevent.contents["uid"]) == 1


def test_sanitize_addressbook_skips_vlist_and_repairs_blank_uid():
    """Contact lists are ignored; a blank vCard UID is replaced in place."""
    card = read_components(
        "BEGIN:VCARD\r\nVERSION:3.0\r\nUID:\r\nFN:Ada\r\nEND:VCARD\r\n")
    listing = read_components(
        "BEGIN:VLIST\r\nUID:list-1\r\nFN:People\r\nEND:VLIST\r\n")
    check_and_sanitize_items(
        listing + card, 10, is_collection=True, tag="VADDRESSBOOK")
    assert listing[0].uid.value == "list-1"
    assert card[0].uid.value
    assert len(card[0].contents["uid"]) == 1
    event = read_components(
        "BEGIN:VEVENT\r\nUID:a\r\nDTSTART:20130101T000000Z\r\nEND:VEVENT\r\n")
    with pytest.raises(ValueError, match="VEVENT"):
        check_and_sanitize_items(event, 10, tag="VADDRESSBOOK")


def test_sanitize_props_rejects_non_string_keys_and_unknown_tags():
    """Collection properties must be strings, and the tag set is closed."""
    with pytest.raises(ValueError, match="Key must be 'str' not 'int'"):
        check_and_sanitize_props({1: "x"})
    with pytest.raises(ValueError, match="Unsupported collection tag: 'NOPE'"):
        check_and_sanitize_props({"tag": "NOPE"})
    assert check_and_sanitize_props({"tag": "VCALENDAR"})["tag"] == "VCALENDAR"


def test_sanitize_removes_zero_duration_when_dtend_is_present(caplog):
    """Lightning's DTEND plus DURATION:PT0S keeps DTEND and drops DURATION."""
    caplog.set_level(logging.DEBUG, logger="radicale")
    items = _calendar(
        "BEGIN:VEVENT\r\nUID:z\r\nDTSTART:20130101T000000Z\r\n"
        "DTEND:20130101T010000Z\r\nDURATION:PT0S\r\nEND:VEVENT\r\n")
    _sanitize(items)
    event = items[0].vevent
    assert not hasattr(event, "duration")
    assert event.dtend.value == datetime.datetime(2013, 1, 1, 1, 0, tzinfo=UTC) or (
        event.dtend.value.hour == 1 and event.dtend.value.tzinfo is not None)
    assert "Removing zero duration" in caplog.text
    # A positive duration next to DTEND is a different object and is kept
    # only when it is the sole bound; with both set, non-zero is not the quirk.
    kept = _calendar(
        "BEGIN:VEVENT\r\nUID:p\r\nDTSTART:20130101T000000Z\r\n"
        "DURATION:PT1H\r\nEND:VEVENT\r\n")
    _sanitize(kept)
    assert kept[0].vevent.duration.value == datetime.timedelta(hours=1)


def test_sanitize_aligns_exdate_timezone_with_dtstart():
    """EXDATE/RDATE datetimes take DTSTART's zone, or lose one DTSTART lacks."""
    aware = _calendar(
        "BEGIN:VEVENT\r\nUID:ex\r\nDTSTART:20130901T180000Z\r\n"
        "DTEND:20130901T190000Z\r\nEXDATE:20130902T160000\r\n"
        "EXDATE:20130903T160000\r\nEND:VEVENT\r\n")
    _sanitize(aware)
    for exdate in aware[0].vevent.contents["exdate"]:
        assert exdate.value[0].tzinfo is not None

    naive = _calendar(
        "BEGIN:VEVENT\r\nUID:ex3\r\nDTSTART:20130901T180000\r\n"
        "DTEND:20130901T190000\r\nEXDATE:20130902T160000Z\r\n"
        "EXDATE:20130903T160000\r\nEND:VEVENT\r\n")
    _sanitize(naive)
    for exdate in naive[0].vevent.contents["exdate"]:
        assert exdate.value[0].tzinfo is None


def test_sanitize_copies_dtstart_value_param_onto_converted_exdate():
    """A DATE exception is rewritten as DATE-TIME and inherits DTSTART's VALUE."""
    items = _calendar(
        "BEGIN:VEVENT\r\nUID:ex2\r\nDTSTART;VALUE=DATE-TIME:20130901T180000Z\r\n"
        "DTEND:20130901T190000Z\r\nEXDATE;VALUE=DATE:20130902\r\nEND:VEVENT\r\n")
    _sanitize(items)
    exdate = items[0].vevent.exdate
    assert exdate.value[0].year == 2013
    assert exdate.value[0].month == 9
    assert exdate.value[0].day == 2
    assert exdate.value[0].hour == 18
    assert exdate.params.get("VALUE") == ["DATE-TIME"]


def test_sanitize_rejects_period_when_vobject_cannot_round_trip():
    """This vobject build parses PERIOD but cannot serialize it."""
    items = read_components(get_file_content(
        "event_rdate_period_start_stop.ics"))
    with pytest.raises(ValueError, match="PERIOD not supported"):
        _sanitize(items)


def test_sanitize_checks_period_shape_when_support_is_enabled(
        monkeypatch, caplog):
    """Each PERIOD entry must be a 2-tuple of datetime or datetime+duration."""
    _enable_periods(monkeypatch)
    source = get_file_content("event_rdate_period_start_stop.ics")
    uid = "test-rdate-period-time-start-stop"

    def _load():
        return read_components(source)

    items = _load()
    start, stop = items[0].vevent.rdate.value[0]
    items[0].vevent.rdate.value = [(stop, start)]
    with pytest.raises(ValueError, match="end before start.*%s" % uid):
        _sanitize(items)

    equal = _load()
    start, _stop = equal[0].vevent.rdate.value[0]
    equal[0].vevent.rdate.value = [(start, start), (start, stop)]
    caplog.set_level(LOG_LEVEL_TRACE, logger="radicale")
    _sanitize(equal)
    assert "PERIOD/start-stop" in caplog.text
    assert equal[0].vevent.rdate.value[0] == (start, start)

    caplog.clear()
    caplog.set_level(logging.WARNING, logger="radicale")
    quiet = _load()
    quiet[0].vevent.rdate.value = [(start, stop), (start, stop)]
    _sanitize(quiet)
    assert "PERIOD/start-stop" not in caplog.text
    assert quiet[0].vevent.rdate.value == [(start, stop), (start, stop)]

    not_tuple = _load()
    # A bare datetime matches DTSTART and is skipped before the PERIOD checks.
    not_tuple[0].vevent.rdate.value = ["nope"]
    with pytest.raises(ValueError, match="not a tuple"):
        _sanitize(not_tuple)

    short = _load()
    short[0].vevent.rdate.value = [(start,)]
    with pytest.raises(ValueError, match="not 2 elements"):
        _sanitize(short)

    long = _load()
    long[0].vevent.rdate.value = [(start, stop, stop)]
    with pytest.raises(ValueError, match="not 2 elements"):
        _sanitize(long)

    bad_types = _load()
    bad_types[0].vevent.rdate.value = [(start, "PT1H")]
    with pytest.raises(ValueError, match="element types not matching"):
        _sanitize(bad_types)

    duration = read_components(get_file_content(
        "event_rdate_period_start_duration.ics"))
    caplog.set_level(LOG_LEVEL_TRACE, logger="radicale")
    _sanitize(duration)
    assert duration[0].vevent.rdate.value[0][1] == datetime.timedelta(hours=2)
    assert "PERIOD/start-duration" in caplog.text

    caplog.clear()
    caplog.set_level(logging.WARNING, logger="radicale")
    quiet_duration = read_components(get_file_content(
        "event_rdate_period_start_duration.ics"))
    _sanitize(quiet_duration)
    assert quiet_duration[0].vevent.rdate.value[0][1] == datetime.timedelta(hours=2)
    assert "PERIOD/start-duration" not in caplog.text


def test_sanitize_recurrence_limits_and_until_order():
    """COUNT, expanded BYHOUR, and UNTIL before DTSTART are rejected."""
    def _rule(rrule, limit, uid="u"):
        return _calendar(
            "BEGIN:VEVENT\r\nUID:%s\r\nDTSTART:20200101T000000Z\r\n"
            "%s\r\nEND:VEVENT\r\n" % (uid, rrule)), limit

    passed, _limit = _rule("RRULE:FREQ=DAILY;COUNT=2", 2)
    _sanitize(passed, 2)
    assert "COUNT=2" in passed[0].vevent.rrule.value

    over = _calendar(
        "BEGIN:VEVENT\r\nUID:cnt\r\nDTSTART:20200101T000000Z\r\n"
        "RRULE:FREQ=DAILY;COUNT=3\r\nEND:VEVENT\r\n")
    with pytest.raises(ValueError, match="3 \\(limit: 2\\)"):
        _sanitize(over, 2)

    # Two days of hourly instances: the UNTIL estimate stays under the limit
    # and the expanded set does not.
    hourly = _calendar(
        "BEGIN:VEVENT\r\nUID:byh\r\nDTSTART:20200101T000000Z\r\n"
        "RRULE:FREQ=DAILY;BYHOUR=0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,"
        "16,17,18,19,20,21,22,23;UNTIL=20200103T000000Z\r\nEND:VEVENT\r\n")
    with pytest.raises(ValueError, match="byh.*limit: 10") as caught:
        _sanitize(hourly, 10)
    assert int(str(caught.value).split("byh': ")[1].split(" ")[0]) > 10

    early = _calendar(
        "BEGIN:VEVENT\r\nUID:untilbad\r\nDTSTART:20130901T180000Z\r\n"
        "RRULE:FREQ=DAILY;UNTIL=20130101T000000Z\r\nEND:VEVENT\r\n")
    with pytest.raises(ValueError, match="UNTIL < DTSTART"):
        _sanitize(early)

    floating = _calendar(
        "BEGIN:VEVENT\r\nUID:nu\r\nDTSTART:20200101T000000\r\n"
        "RRULE:FREQ=DAILY;UNTIL=20200105T000000\r\nEND:VEVENT\r\n")
    _sanitize(floating)
    assert floating[0].vevent.dtstart.value.tzinfo is None
    assert "UNTIL=20200105T000000" in floating[0].vevent.rrule.value


def test_sanitize_rejects_an_unknown_recurrence_frequency(monkeypatch):
    """A FREQ outside the seven RFC 5545 values is rejected before expansion."""
    frequencies = vobject.icalendar.FREQUENCIES + ("NOPE",)
    monkeypatch.setattr(vobject.icalendar, "FREQUENCIES", frequencies)

    class _Rule:
        _count = None
        _freq = len(frequencies) - 1
        _until = datetime.datetime(2020, 6, 1, tzinfo=UTC)

    monkeypatch.setattr(
        vobject.icalendar.rrule, "rrulestr", lambda *_args, **_kwargs: _Rule())
    items = _calendar(
        "BEGIN:VEVENT\r\nUID:freq\r\nDTSTART:20200101T000000Z\r\n"
        "RRULE:FREQ=DAILY;UNTIL=20200601T000000Z\r\nEND:VEVENT\r\n")
    with pytest.raises(ValueError, match="Unsupported FREQ.*7"):
        _sanitize(items)


def test_sanitize_wraps_rruleset_failures():
    """A recurrence set vobject cannot build becomes an invalid-rule error."""
    items = read_components(get_file_content(
        "event_rdate_period_start_stop.ics"))
    items[0].vevent.rdate.value = []
    with pytest.raises(ValueError, match="Invalid recurrence rules in VEVENT"):
        _sanitize(items)


def test_verify_reports_unpredictable_and_unconstructable_items(
        tmp_path, monkeypatch, caplog):
    """``verify`` is false when the tag or the Item constructor fails."""
    bare = tmp_path / "bare.ics"
    bare.write_bytes(
        b"BEGIN:VEVENT\r\nUID:x\r\nDTSTART:20130101T000000Z\r\nEND:VEVENT\r\n")
    assert verify(str(bare), "utf-8", 100) is False
    assert "collection tag cannot be predicted" in caplog.text

    good = tmp_path / "good.ics"
    good.write_bytes(
        b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nUID:x\r\n"
        b"DTSTART:20130101T000000Z\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n")
    monkeypatch.setattr(pathutils, "sanitize_path", lambda _path: "nope")
    assert verify(str(good), "utf-8", 100) is False


# --- vCard birthday conversion ---------------------------------------------


def _convert(item, actions=None, summary="{fn} is {age}"):
    if actions is None:
        actions = {"config": {
            "conversion_bday_summary_template": summary,
            "conversion_bday_categories": "Birthday,Personal",
            "conversion_bday_alarm_trigger_template": "1D;Wake {fn}$bogus;skip",
        }}
    return item.convert_vcf_to_ics(actions)


def test_convert_skips_non_vcards_bad_bdays_and_nameless_cards(caplog):
    """Conversion is skipped, with a trace only when tracing is enabled."""
    event = _calendar_item(
        "BEGIN:VEVENT\r\nUID:e\r\nDTSTART:20130101T000000Z\r\nEND:VEVENT\r\n",
        href="e.ics")
    caplog.set_level(LOG_LEVEL_TRACE, logger="radicale")
    assert event.convert_vcf_to_ics() is None
    assert "not a VCARD" in caplog.text
    caplog.clear()
    caplog.set_level(logging.WARNING, logger="radicale")
    assert event.convert_vcf_to_ics() is None
    assert "not a VCARD" not in caplog.text

    bad = _vcard(["FN:Ada", "BDAY:1990-5-6"])
    caplog.set_level(LOG_LEVEL_TRACE, logger="radicale")
    assert bad.convert_vcf_to_ics() is None
    assert "unsupported bday" in caplog.text
    caplog.clear()
    caplog.set_level(logging.WARNING, logger="radicale")
    assert _vcard(["FN:Ada", "BDAY:199005"]).convert_vcf_to_ics() is None
    assert "unsupported bday" not in caplog.text
    # Just inside the BDAY pattern: eight digits, no separators.
    kept = _convert(_vcard(
        ["FN:Ada", "BDAY:19900506"], href=None),
        actions={"config": {"conversion_bday_summary_template": "{fn}"}})
    assert kept is not None
    assert kept.href is None
    assert "19900506" in kept.vobject_item.vevent.uid.value

    nameless = _vcard(["BDAY:19900506"])
    caplog.set_level(LOG_LEVEL_TRACE, logger="radicale")
    assert nameless.convert_vcf_to_ics() is None
    assert "neither FN or N or NICKNAME" in caplog.text
    caplog.clear()
    caplog.set_level(logging.WARNING, logger="radicale")
    assert _vcard(["BDAY:1990-05-06"]).convert_vcf_to_ics() is None
    assert "neither FN or N or NICKNAME" not in caplog.text

    # Present name, absent birthday: one step before a malformed BDAY.
    caplog.clear()
    assert _vcard(["FN:Ada"]).convert_vcf_to_ics() is None
    assert "miss bday" not in caplog.text
    caplog.set_level(LOG_LEVEL_TRACE, logger="radicale")
    assert _vcard(["FN:Ada"]).convert_vcf_to_ics() is None
    assert "miss bday" in caplog.text


def test_convert_names_come_from_n_then_nickname_when_fn_is_absent():
    """Without FN, the synthesized UID uses N and then NICKNAME."""
    # A card without FN cannot be serialized; the stored etag is already known.
    from_n = _convert(_vcard(
        ["N:Lovelace;Ada;;;", "BDAY:1990-05-06"], etag='"preset-etag"'),
        actions={"config": {"conversion_bday_summary_template": "{n:g}"}})
    assert from_n is not None
    assert "Lovelace-Ada" in from_n.vobject_item.vevent.uid.value
    assert "SUMMARY:Ada" in from_n.serialize()

    from_nick = _convert(_vcard(
        ["NICKNAME:Addy", "BDAY:1990-05-06"], etag='"preset-etag"'),
        actions={"config": {"conversion_bday_summary_template": "{nickname}"}})
    assert from_nick is not None
    assert "Addy" in from_nick.vobject_item.vevent.uid.value
    assert "SUMMARY:Addy" in from_nick.serialize()


def test_convert_default_age_span_categories_alarm_and_no_year(caplog):
    """Config templates apply; a missing age cap falls back to 99 years."""
    recent = _convert(_vcard([
        "FN:Ada Lovelace",
        "N:Lovelace;Ada;;;",
        "BDAY:2026-11-01",
        "UID:11111111-2222-3333-4444-555555555555",
    ], href="ada.vcf", last_modified="Wed, 30 Sep 2026 05:58:48 GMT"))
    assert recent is not None
    text = recent.serialize()
    assert len(recent.vobject_item.vevent_list) == 100
    assert "SUMMARY:Ada Lovelace is 0" in text
    assert "SUMMARY:Ada Lovelace is 99" in text
    assert "SUMMARY:Ada Lovelace is 100" not in text
    assert "COUNT=100" in text
    assert "CATEGORIES:Birthday,Personal" in text or (
        "Birthday" in text and "Personal" in text)
    assert "Wake Ada Lovelace" in text
    assert "skip" not in text
    assert "DTSTAMP:20260930T055848Z" in text
    assert recent.href == "ada.ics"
    assert "X-RADICALE-NAME:ada.ics" in text
    assert recent.etag.startswith('"bda020261101')

    caplog.set_level(logging.WARNING, logger="radicale")
    old = _convert(_vcard(["FN:Old", "BDAY:1900-01-02", "UID:old-person"]))
    old_text = old.serialize()
    assert len(old.vobject_item.vevent_list) == 1
    assert "SUMMARY:Old is !age!" in old_text
    assert "FREQ=YEARLY" in old_text
    assert "COUNT=" not in old_text

    undated = _convert(_vcard([
        "FN:Timeless", "BDAY:1604-05-06", "UID:no-year"]))
    undated_text = undated.serialize()
    assert "????" in undated_text
    assert "is ??" in undated_text
    assert undated.vobject_item.vevent.dtstart.value == datetime.date(1604, 5, 6)
    assert undated.vobject_item.vevent.uid.value == "no-year" + UID_SUFFIX
    assert "16040506" in undated.etag


def test_convert_without_uid_builds_one_from_the_birthday_and_name():
    """A card with no UID property still produces a stable event UID."""
    converted = _convert(
        _vcard(["FN:Ada Lovelace", "BDAY:1990-05-06"], href="ada.vcf"),
        actions={"config": {"conversion_bday_summary_template": "{fn}"}})
    uid = converted.vobject_item.vevent.uid.value
    assert uid == "19900506@Ada-Lovelace" + UID_SUFFIX
    assert converted.href == "ada.ics"
    assert "DTSTAMP:19700101T000000Z" in converted.serialize()

    class _Categories:
        def __init__(self, text):
            self._text = text

        def split(self, _sep):
            return self._text.split(",") if self._text else []

    one = _convert(
        _vcard(["FN:Ada", "BDAY:1990-05-06", "UID:one-cat"], href="one.vcf"),
        actions={"config": {
            "conversion_bday_summary_template": "{fn}",
            "conversion_bday_categories": _Categories("Solo"),
        }})
    assert "CATEGORIES:Solo" in one.serialize()
    assert "Birthday" not in one.serialize()

    empty = _convert(
        _vcard(["FN:Ada", "BDAY:1990-05-06", "UID:no-cat"], href="none.vcf"),
        actions={"config": {
            "conversion_bday_summary_template": "{fn}",
            "conversion_bday_categories": _Categories(""),
        }})
    empty_text = empty.serialize()
    assert "SUMMARY:Ada" in empty_text
    assert "CATEGORIES" not in empty_text


def test_convert_traces_the_generated_event_when_tracing_is_on(caplog):
    """A successful conversion records the generated object only while tracing."""
    card = _vcard(
        ["FN:Ada", "BDAY:1990-05-06", "UID:trace-me"], href="trace.vcf")
    actions = {"config": {"conversion_bday_summary_template": "{fn}"}}
    caplog.set_level(LOG_LEVEL_TRACE, logger="radicale")
    traced = card.convert_vcf_to_ics(actions)
    assert traced is not None
    assert "SUMMARY:Ada" in traced.serialize()
    assert "item generated/vobject" in caplog.text
    caplog.clear()
    caplog.set_level(logging.WARNING, logger="radicale")
    quiet = _vcard(
        ["FN:Ada", "BDAY:1990-05-06", "UID:trace-me"], href="trace.vcf"
    ).convert_vcf_to_ics(actions)
    assert "SUMMARY:Ada" in quiet.serialize()
    assert "item generated/vobject" not in caplog.text


# --- filters ---------------------------------------------------------------


def test_trigger_annotation_matches_the_running_interpreter():
    """The trigger alias is the 3.9 union when the interpreter reports 3.9."""
    import importlib
    import sys
    from typing import Union

    import radicale.item.filter as item_filter

    real_version = sys.version_info
    real_trigger = item_filter.TRIGGER
    event = _calendar_item(
        "BEGIN:VEVENT\r\nUID:e\r\nDTSTART:20130101T120000Z\r\n"
        "DTEND:20130101T130000Z\r\nEND:VEVENT\r\n").vobject_item
    sys.version_info = (3, 9, 18, "final", 0)
    try:
        importlib.reload(item_filter)
        assert item_filter.time_range_match.__annotations__["trigger"] == (
            Union[datetime.datetime, None])
        assert item_filter.time_range_match(
            event, _time_range(), "VEVENT", None) is False
        assert item_filter.time_range_match(
            event, _time_range("20130101T000000Z", "20130102T000000Z"),
            "VEVENT", None) is True
    finally:
        sys.version_info = real_version
        importlib.reload(item_filter)
    assert item_filter.TRIGGER == real_trigger
    assert time_range_match(
        event, _time_range("20130101T000000Z", "20130102T000000Z"),
        "VEVENT", None) is True


def test_parse_time_range_open_start_matches_only_events_before_end():
    """A missing start is the beginning of time; both ends missing match nothing."""
    event = _calendar_item(
        "BEGIN:VEVENT\r\nUID:e\r\nDTSTART:20130101T120000Z\r\n"
        "DTEND:20130101T130000Z\r\nEND:VEVENT\r\n")
    start, end = parse_time_range(_time_range(end="20130102T000000Z"))
    assert start == DATETIME_MIN
    assert end == datetime.datetime(2013, 1, 2, tzinfo=UTC)
    assert time_range_match(
        event.vobject_item, _time_range(end="20130102T000000Z"),
        "VEVENT", None) is True
    assert time_range_match(
        event.vobject_item, _time_range(end="20121231T000000Z"),
        "VEVENT", None) is False
    assert time_range_match(
        event.vobject_item, _time_range(), "VEVENT", None) is False
    _start, open_end = parse_time_range(_time_range(start="20130101T000000Z"))
    assert open_end == DATETIME_MAX


def test_time_range_edges_for_events_journals_and_properties():
    """Point, zero-length, and all-day bounds include or exclude the filter."""
    def _match(body, start, end, kind="VEVENT"):
        item = _calendar_item(body)
        return time_range_match(
            item.vobject_item, _time_range(start, end), kind, None)

    point = (
        "BEGIN:VEVENT\r\nUID:s\r\nDTSTART:20130101T120000Z\r\nEND:VEVENT\r\n")
    assert _match(point, "20130101T120000Z", "20130101T120002Z") is True
    assert _match(point, "20130101T120001Z", "20130101T130000Z") is False

    zero = (
        "BEGIN:VEVENT\r\nUID:z\r\nDTSTART:20130101T120000Z\r\n"
        "DURATION:PT0S\r\nEND:VEVENT\r\n")
    assert _match(zero, "20130101T120000Z", "20130101T120002Z") is True
    assert _match(zero, "20130101T130000Z", "20130101T140000Z") is False

    allday = (
        "BEGIN:VEVENT\r\nUID:d\r\nDTSTART;VALUE=DATE:20130101\r\nEND:VEVENT\r\n")
    assert _match(allday, "20130101T120000Z", "20130101T130000Z") is True
    assert _match(allday, "20130103T000000Z", "20130104T000000Z") is False

    journal = (
        "BEGIN:VJOURNAL\r\nUID:j\r\nDTSTART;VALUE=DATE:20130101\r\n"
        "SUMMARY:j\r\nEND:VJOURNAL\r\n")
    assert _match(
        journal, "20130101T100000Z", "20130101T110000Z", "VJOURNAL") is True
    assert _match(
        journal, "20130201T100000Z", "20130201T110000Z", "VJOURNAL") is False

    todo = _calendar_item(
        "BEGIN:VTODO\r\nUID:t\r\nDUE;VALUE=DATE:20130903\r\n"
        "SUMMARY:words\r\nEND:VTODO\r\n").vobject_item.vtodo
    assert time_range_match(
        todo, _time_range("20130903T100000Z", "20130903T110000Z"),
        "DUE", None) is True
    assert time_range_match(
        todo, _time_range("20130905T100000Z", "20130905T110000Z"),
        "DUE", None) is False
    assert time_range_match(
        todo, _time_range("20130903T100000Z", "20130903T110000Z"),
        "SUMMARY", None) is False


def test_todo_time_range_lines_match_only_their_window():
    """VTODO DTSTART, DURATION, and COMPLETED use the RFC 4791 windows."""
    def _todo(body, start, end):
        item = _calendar_item(body)
        return time_range_match(
            item.vobject_item, _time_range(start, end), "VTODO", None)

    duration = (
        "BEGIN:VTODO\r\nUID:t\r\nDTSTART:20130901T200000Z\r\n"
        "DURATION:PT1H\r\nSUMMARY:t\r\nEND:VTODO\r\n")
    assert _todo(duration, "20130901T203000Z", "20130901T204000Z") is True
    assert _todo(duration, "20130903T200000Z", "20130903T210000Z") is False

    # Zero duration: the end window sticks out one second before DTSTART.
    zero = (
        "BEGIN:VTODO\r\nUID:t0\r\nDTSTART:20130901T200000Z\r\n"
        "DURATION:PT0S\r\nSUMMARY:t\r\nEND:VTODO\r\n")
    assert _todo(zero, "20130901T195959Z", "20130901T200000Z") is True
    assert _todo(zero, "20130901T190000Z", "20130901T195000Z") is False

    start_only = (
        "BEGIN:VTODO\r\nUID:t2\r\nDTSTART:20130901T200000Z\r\n"
        "SUMMARY:t\r\nEND:VTODO\r\n")
    assert _todo(start_only, "20130901T200000Z", "20130901T200002Z") is True
    assert _todo(start_only, "20130903T200000Z", "20130903T210000Z") is False

    completed = (
        "BEGIN:VTODO\r\nUID:t3\r\nCOMPLETED:20130903T160000Z\r\n"
        "SUMMARY:t\r\nEND:VTODO\r\n")
    assert _todo(completed, "20130903T155959Z", "20130903T160000Z") is True
    assert _todo(completed, "20131003T150000Z", "20131003T170000Z") is False


def test_mixed_tz_awareness_still_matches_the_event_hour():
    """A naive DTSTART or DTEND is aligned before the overlap test."""
    for name in ("event_issue1847_1.ics", "event_issue1847_2.ics"):
        item = _item(get_file_content(name))
        assert time_range_match(
            item.vobject_item,
            _time_range("20250814T000000Z", "20250815T000000Z"),
            "VEVENT", None) is True
        assert time_range_match(
            item.vobject_item,
            _time_range("20250816T000000Z", "20250817T000000Z"),
            "VEVENT", None) is False


def test_unsupported_trigger_does_not_count_as_a_time_match(caplog):
    """An absolute trigger matches on its own; a string trigger matches nothing."""
    event = _calendar_item(
        "BEGIN:VEVENT\r\nUID:e\r\nDTSTART:20130101T120000Z\r\n"
        "DTEND:20130101T130000Z\r\nEND:VEVENT\r\n").vobject_item
    inside = datetime.datetime(2013, 6, 1, 12, 0, tzinfo=UTC)
    assert time_range_match(
        event, _time_range("20130601T000000Z", "20130602T000000Z"),
        "VEVENT", inside) is True
    assert time_range_match(
        event, _time_range("20130101T000000Z", "20130102T000000Z"),
        "VEVENT", inside) is False
    # The event itself overlaps this filter, so a bogus trigger must not fall
    # through to the event overlap.
    assert time_range_match(
        event, _time_range("20130101T000000Z", "20130102T000000Z"),
        "VEVENT", "nope") is False
    assert "unsupported data format" in caplog.text


def test_comp_match_depth_name_and_unknown_children(caplog):
    """comp-filter depth, name, and child tags decide include, exclude, or error."""
    event = _calendar_item(
        "BEGIN:VEVENT\r\nUID:e\r\nDTSTART:20130101T120000Z\r\n"
        "SUMMARY:Meet\r\nEND:VEVENT\r\n")
    assert comp_match(event, _el("C:comp-filter", {"name": "VEVENT"}), level=3) is True
    assert "3 levels" in caplog.text

    blank = Item(
        collection_path="calendar", vobject_item=event.vobject_item, name="")
    assert comp_match(
        blank, _el("C:comp-filter", {"name": "VCALENDAR"}), level=0) is False

    todo = _calendar_item(
        "BEGIN:VTODO\r\nUID:t\r\nDTSTART:20130101T120000Z\r\nEND:VTODO\r\n")
    assert comp_match(todo, _el(
        "C:comp-filter", {"name": "VEVENT"},
        children=[_time_range("20130101T000000Z", "20130102T000000Z")]),
        level=1) is False

    freebusy = _calendar_item(
        "BEGIN:VFREEBUSY\r\nUID:f\r\nDTSTART:20130101T000000Z\r\n"
        "DTEND:20130102T000000Z\r\nEND:VFREEBUSY\r\n")
    failing = _el("C:prop-filter", {"name": "SUMMARY"}, children=[
        _el("C:text-match", text="absent")])
    assert comp_match(freebusy, _el(
        "C:comp-filter", {"name": "VFREEBUSY"}, children=[failing]),
        level=1) is True
    assert "Filtering VFREEBUSY is not supported" in caplog.text

    nested = _el("C:comp-filter", {"name": "VCALENDAR"}, children=[
        _el("C:comp-filter", {"name": "VEVENT"})])
    assert comp_match(event, nested, level=0) is True
    assert "comp-filter level" not in caplog.text
    assert comp_match(event, _el(
        "C:comp-filter", {"name": "VCALENDAR"}, children=[
            _el("C:comp-filter", {"name": "VTODO"})]), level=0) is False

    unexpected = _el("C:comp-filter", {"name": "VCALENDAR"}, children=[
        _el("C:not-a-filter")])
    with pytest.raises(ValueError, match="Unexpected"):
        comp_match(event, unexpected, level=0)

    bad_prop = _el("C:comp-filter", {"name": "VEVENT"}, children=[
        _el("C:prop-filter", {"name": "SUMMARY"}, children=[
            _el("C:not-a-match")])])
    with pytest.raises(ValueError, match="prop-filter"):
        comp_match(event, bad_prop, level=1)


def test_valarm_filter_requires_the_component_and_ignores_a_missing_trigger():
    """No VALARM excludes the event; a VALARM without TRIGGER uses the event time."""
    plain = _calendar_item(
        "BEGIN:VEVENT\r\nUID:e\r\nDTSTART:20130101T120000Z\r\n"
        "DTEND:20130101T130000Z\r\nEND:VEVENT\r\n")
    alarm_filter = _el("C:comp-filter", {"name": "VALARM"}, children=[
        _time_range("20130101T120000Z", "20130101T121000Z")])
    assert comp_match(plain, alarm_filter, level=2) is False

    with_alarm = _calendar_item(
        "BEGIN:VEVENT\r\nUID:e\r\nDTSTART:20130101T120000Z\r\n"
        "DTEND:20130101T130000Z\r\nBEGIN:VALARM\r\nACTION:DISPLAY\r\n"
        "DESCRIPTION:x\r\nEND:VALARM\r\nEND:VEVENT\r\n")
    assert comp_match(with_alarm, alarm_filter, level=2) is True
    assert comp_match(with_alarm, _el(
        "C:comp-filter", {"name": "VALARM"}, children=[
            _time_range("20130102T120000Z", "20130102T121000Z")]),
        level=2) is False


def test_recurrence_sets_require_one_master_and_ignore_its_first_override():
    """Overrides do not replace the master, and an infinite rule skips them."""
    def _visit(body, range_fn, infinity_fn):
        item = _calendar_item(body)
        visit_time_ranges(
            item.vobject_item, "VEVENT", range_fn, infinity_fn,
            max_occurrences=5)

    only = (
        "BEGIN:VEVENT\r\nUID:a\r\nRECURRENCE-ID:20130102T000000Z\r\n"
        "DTSTART:20130102T010000Z\r\nEND:VEVENT\r\n")
    _visit(only, lambda *_args: False, lambda _start: False)

    two = (
        "BEGIN:VEVENT\r\nUID:a\r\nRECURRENCE-ID:20130102T000000Z\r\n"
        "DTSTART:20130102T010000Z\r\nEND:VEVENT\r\n"
        "BEGIN:VEVENT\r\nUID:a\r\nRECURRENCE-ID:20130103T000000Z\r\n"
        "DTSTART:20130103T010000Z\r\nEND:VEVENT\r\n")
    with pytest.raises(ValueError, match="Main component missing"):
        _visit(two, lambda *_args: False, lambda _start: False)

    masters = (
        "BEGIN:VEVENT\r\nUID:a\r\nDTSTART:20130101T000000Z\r\nEND:VEVENT\r\n"
        "BEGIN:VEVENT\r\nUID:a\r\nDTSTART:20130102T000000Z\r\nEND:VEVENT\r\n")
    with pytest.raises(ValueError, match="Multiple main components"):
        _visit(masters, lambda *_args: False, lambda _start: False)

    class _Empty:
        vevent_list = []

    with pytest.raises(ValueError, match="Main component missing"):
        visit_time_ranges(
            _Empty(), "VEVENT", lambda *_args: False, lambda _start: False)

    infinite = (
        "BEGIN:VEVENT\r\nUID:a\r\nDTSTART:20130101T000000Z\r\n"
        "RRULE:FREQ=DAILY\r\nEND:VEVENT\r\n"
        "BEGIN:VEVENT\r\nUID:a\r\nRECURRENCE-ID:20130101T000000Z\r\n"
        "DTSTART:20130101T050000Z\r\nEND:VEVENT\r\n")
    trace = []

    def _range(start, _end, is_recurrence):
        trace.append(("range", start, is_recurrence))
        return False

    def _infinity(start):
        trace.append(("inf", start))
        return True

    _visit(infinite, _range, _infinity)
    assert trace[0][0] == "range" and trace[0][2] is True
    assert trace[1][0] == "inf"
    assert trace[1][1] > trace[0][1]


def test_overwritten_recurrence_with_a_materialized_ruleset_is_rejected():
    """An override whose rruleset was already consumed is not expandable."""

    class _Value:
        def __init__(self, value):
            self.value = value

    class _Ruleset:
        _len = 2

    class _Override:
        recurrence_id = _Value(datetime.datetime(2013, 1, 2, tzinfo=UTC))
        rruleset = _Ruleset()
        uid = _Value("uid-1")

    class _Calendar:
        vevent_list = [_Override()]

    with pytest.raises(ValueError, match="Overwritten recurrence with RRULESET"):
        visit_time_ranges(
            _Calendar(), "VEVENT", lambda *_args: False, lambda _start: False)


def test_empty_infinite_rule_and_unanchored_todo_do_not_match():
    """No occurrences, and a todo with no date fields, are outside every filter."""

    class _Event:
        rruleset = True
        contents = {"rrule": [type("Rule", (), {"value": "FREQ=DAILY"})()]}
        dtstart = type("Start", (), {
            "value": datetime.datetime(2013, 1, 1, tzinfo=UTC)})()

        def getrruleset(self, addRDate=True):
            return []

    class _Events:
        vevent_list = [_Event()]

    seen = []
    visit_time_ranges(
        _Events(), "VEVENT",
        lambda *args: seen.append(args) or False,
        lambda start: seen.append(("inf", start)) or True,
        max_occurrences=3)
    assert seen == []
    assert time_range_match(
        _Events(), _time_range("20130101T000000Z", "20130102T000000Z"),
        "VEVENT", None) is False

    class _Todo:
        rruleset = True
        contents = {}

        def getrruleset(self, addRDate=True):
            return [datetime.datetime(2013, 6, 1, 12, 0, tzinfo=UTC)]

    class _Todos:
        vtodo_list = [_Todo()]

    assert time_range_match(
        _Todos(), _time_range("20130601T000000Z", "20130602T000000Z"),
        "VTODO", None) is False


def test_text_and_param_filters_reject_or_ignore_unknown_children():
    """Unknown match-types fail; a param-filter with no text test uses presence."""
    card = vobject.readOne(
        "BEGIN:VCARD\r\nVERSION:3.0\r\nFN:Ada\r\nEND:VCARD\r\n")
    weird = _el("CR:text-match", {"match-type": "regex"}, text="A")
    with pytest.raises(ValueError, match="regex"):
        text_match(card, weird, "fn", "CR")

    event = _calendar_item(
        "BEGIN:VEVENT\r\nUID:e\r\nDTSTART:20130101T000000Z\r\n"
        "ATTENDEE;PARTSTAT=ACCEPTED:mailto:a@example.com\r\n"
        "END:VEVENT\r\n").vobject_item.vevent
    assert param_filter_match(
        event, _el("C:param-filter", {"name": "PARTSTAT"}),
        "attendee", "C") is True
    assert param_filter_match(
        event, _el("C:param-filter", {"name": "UNKNOWN"}),
        "attendee", "C") is False
    assert param_filter_match(
        event, _el("C:param-filter", {"name": "PARTSTAT"}, children=[
            _el("C:not-a-test")]),
        "attendee", "C") is True
    assert param_filter_match(
        event, _el("C:param-filter", {"name": "UNKNOWN"}, children=[
            _el("C:not-a-test")]),
        "attendee", "C") is False


def test_simplify_prefilters_keeps_only_a_single_supported_time_window(caplog):
    """Prefilters collapse one VEVENT window and refuse anything wider."""
    def _parent(*children):
        root = ET.Element("filters")
        for child in children:
            root.append(child)
        return [root]

    window = _el("C:comp-filter", {"name": "VCALENDAR"}, children=[
        _el("C:comp-filter", {"name": "VEVENT"}, children=[
            _time_range("20130101T000000Z", "20130201T000000Z")])])
    tag, start, end, simple = simplify_prefilters(_parent(window), "VCALENDAR")
    assert (tag, simple) == ("VEVENT", True)
    assert TIMESTAMP_MIN < start < end < TIMESTAMP_MAX
    assert "time-filter on level 1" not in caplog.text

    caplog.set_level(LOG_LEVEL_TRACE, logger="radicale")
    assert simplify_prefilters(_parent(window), "VCALENDAR")[0] == "VEVENT"
    assert "time-filter on level 1" in caplog.text

    top = _el("C:comp-filter", {"name": "VCALENDAR"}, children=[
        _time_range("20130101T000000Z", "20130201T000000Z")])
    caplog.clear()
    caplog.set_level(logging.WARNING, logger="radicale")
    tag, start, end, simple = simplify_prefilters(_parent(top), "VCALENDAR")
    assert tag is None and simple is True
    assert start < end
    assert "time-filter on level 0" not in caplog.text

    other = _el("C:prop-filter", {"name": "SUMMARY"})
    assert simplify_prefilters(_parent(other), "VCALENDAR") == (
        None, TIMESTAMP_MIN, TIMESTAMP_MAX, False)

    caplog.clear()
    nested = _el("C:comp-filter", {"name": "VCALENDAR"}, children=[
        _el("C:prop-filter", {"name": "SUMMARY"}),
        _el("C:comp-filter", {"name": "VEVENT"})])
    caplog.set_level(LOG_LEVEL_TRACE, logger="radicale")
    tag, start, end, simple = simplify_prefilters(_parent(nested), "VCALENDAR")
    assert (tag, start, end, simple) == (
        "VEVENT", TIMESTAMP_MIN, TIMESTAMP_MAX, False)
    assert "no comp-filter on level 0" in caplog.text
    caplog.clear()
    caplog.set_level(logging.WARNING, logger="radicale")
    assert simplify_prefilters(_parent(nested), "VCALENDAR")[3] is False
    assert "no comp-filter on level 0" not in caplog.text

    freebusy = _el("C:comp-filter", {"name": "VCALENDAR"}, children=[
        _el("C:comp-filter", {"name": "VFREEBUSY"}, children=[
            _time_range("20130101T000000Z", "20130201T000000Z")])])
    tag, start, end, simple = simplify_prefilters(_parent(freebusy), "VCALENDAR")
    assert (tag, start, end, simple) == (
        "VFREEBUSY", TIMESTAMP_MIN, TIMESTAMP_MAX, False)

    assert simplify_prefilters([], "VCALENDAR") == (
        None, TIMESTAMP_MIN, TIMESTAMP_MAX, True)
