# This file is part of Radicale - CalDAV and CardDAV server
# Copyright © 2008 Nicolas Kandel
# Copyright © 2008 Pascal Halter
# Copyright © 2008-2015 Guillaume Ayoub
# Copyright © 2017-2021 Unrud <unrud@outlook.com>
# Copyright © 2024-2024 Peter Bieringer <pb@bieringer.de>
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


import math
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from itertools import chain
from typing import (Callable, Iterable, Iterator, List, Optional, Sequence,
                    Tuple)

import vobject

from radicale import item, xmlutils
from radicale.log import logger

DAY: timedelta = timedelta(days=1)
SECOND: timedelta = timedelta(seconds=1)
DATETIME_MIN: datetime = datetime.min.replace(tzinfo=timezone.utc)
DATETIME_MAX: datetime = datetime.max.replace(tzinfo=timezone.utc)
TIMESTAMP_MIN: int = math.floor(DATETIME_MIN.timestamp())
TIMESTAMP_MAX: int = math.ceil(DATETIME_MAX.timestamp())


def date_to_datetime(d: date) -> datetime:
    """Transform any date to a UTC datetime.

    If ``d`` is a datetime without timezone, return as UTC datetime. If ``d``
    is already a datetime with timezone, return as is.

    """
    if not isinstance(d, datetime):
        d = datetime.combine(d, datetime.min.time())
    if not d.tzinfo:
        # NOTE: using vobject's UTC as it wasn't playing well with datetime's.
        d = d.replace(tzinfo=vobject.icalendar.utc)
    return d


def parse_time_range(time_filter: ET.Element) -> Tuple[datetime, datetime]:
    start_text = time_filter.get("start")
    end_text = time_filter.get("end")
    if start_text:
        start = datetime.strptime(
            start_text, "%Y%m%dT%H%M%SZ").replace(
                tzinfo=timezone.utc)
    else:
        start = DATETIME_MIN
    if end_text:
        end = datetime.strptime(
            end_text, "%Y%m%dT%H%M%SZ").replace(
                tzinfo=timezone.utc)
    else:
        end = DATETIME_MAX
    return start, end


def time_range_timestamps(time_filter: ET.Element) -> Tuple[int, int]:
    start, end = parse_time_range(time_filter)
    return (math.floor(start.timestamp()), math.ceil(end.timestamp()))


def comp_match(item: "item.Item", filter_: ET.Element, level: int = 0) -> bool:
    """Check whether the ``item`` matches the comp ``filter_``.

    If ``level`` is ``0``, the filter is applied on the
    item's collection. Otherwise, it's applied on the item.

    See rfc4791-9.7.1.

    """

    # TODO: Filtering VALARM and VFREEBUSY is not implemented
    # HACK: the filters are tested separately against all components

    if level == 0:
        tag = item.name
    elif level == 1:
        tag = item.component_name
    else:
        logger.warning(
            "Filters with three levels of comp-filter are not supported")
        return True
    if not tag:
        return False
    name = filter_.get("name", "").upper()
    if len(filter_) == 0:
        # Point #1 of rfc4791-9.7.1
        return name == tag
    if len(filter_) == 1:
        if filter_[0].tag == xmlutils.make_clark("C:is-not-defined"):
            # Point #2 of rfc4791-9.7.1
            return name != tag
    if name != tag:
        return False
    if (level == 0 and name != "VCALENDAR" or
            level == 1 and name not in ("VTODO", "VEVENT", "VJOURNAL")):
        logger.warning("Filtering %s is not supported", name)
        return True
    # Point #3 and #4 of rfc4791-9.7.1
    components = ([item.vobject_item] if level == 0
                  else list(getattr(item.vobject_item,
                                    "%s_list" % tag.lower())))
    for child in filter_:
        if child.tag == xmlutils.make_clark("C:prop-filter"):
            if not any(prop_match(comp, child, "C")
                       for comp in components):
                return False
        elif child.tag == xmlutils.make_clark("C:time-range"):
            if not time_range_match(item.vobject_item, filter_[0], tag):
                return False
        elif child.tag == xmlutils.make_clark("C:comp-filter"):
            if not comp_match(item, child, level=level + 1):
                return False
        else:
            raise ValueError("Unexpected %r in comp-filter" % child.tag)
    return True


def prop_match(vobject_item: vobject.base.Component,
               filter_: ET.Element, ns: str) -> bool:
    """Check whether the ``item`` matches the prop ``filter_``.

    See rfc4791-9.7.2 and rfc6352-10.5.1.

    """
    name = filter_.get("name", "").lower()
    if len(filter_) == 0:
        # Point #1 of rfc4791-9.7.2
        return name in vobject_item.contents
    if len(filter_) == 1:
        if filter_[0].tag == xmlutils.make_clark("%s:is-not-defined" % ns):
            # Point #2 of rfc4791-9.7.2
            return name not in vobject_item.contents
    if name not in vobject_item.contents:
        return False
    # Point #3 and #4 of rfc4791-9.7.2
    for child in filter_:
        if ns == "C" and child.tag == xmlutils.make_clark("C:time-range"):
            if not time_range_match(vobject_item, child, name):
                return False
        elif child.tag == xmlutils.make_clark("%s:text-match" % ns):
            if not text_match(vobject_item, child, name, ns):
                return False
        elif child.tag == xmlutils.make_clark("%s:param-filter" % ns):
            if not param_filter_match(vobject_item, child, name, ns):
                return False
        else:
            raise ValueError("Unexpected %r in prop-filter" % child.tag)
    return True


def time_range_match(vobject_item: vobject.base.Component,
                     filter_: ET.Element, child_name: str) -> bool:
    """Check whether the component/property ``child_name`` of
       ``vobject_item`` matches the time-range ``filter_``."""

    if not filter_.get("start") and not filter_.get("end"):
        return False

    start, end = parse_time_range(filter_)
    matched = False

    def range_fn(range_start: datetime, range_end: datetime,
                 is_recurrence: bool) -> bool:
        nonlocal matched
        if start < range_end and range_start < end:
            matched = True
            return True
        if end < range_start and not is_recurrence:
            return True
        return False

    def infinity_fn(start: datetime) -> bool:
        return False

    visit_time_ranges(vobject_item, child_name, range_fn, infinity_fn)
    return matched


def time_range_fill(vobject_item: vobject.base.Component,
                    filter_: ET.Element, child_name: str, n: int = 1
                    ) -> List[Tuple[datetime, datetime]]:
    """Create a list of ``n`` occurances from the component/property ``child_name``
       of ``vobject_item``."""
    if not filter_.get("start") and not filter_.get("end"):
        return []

    start, end = parse_time_range(filter_)
    ranges: List[Tuple[datetime, datetime]] = []

    def range_fn(range_start: datetime, range_end: datetime,
                 is_recurrence: bool) -> bool:
        nonlocal ranges
        if start < range_end and range_start < end:
            ranges.append((range_start, range_end))
            if n > 0 and len(ranges) >= n:
                return True
        if end < range_start and not is_recurrence:
            return True
        return False

    def infinity_fn(range_start: datetime) -> bool:
        return False

    visit_time_ranges(vobject_item, child_name, range_fn, infinity_fn)
    return ranges


def visit_time_ranges(vobject_item: vobject.base.Component, child_name: str,
                      range_fn: Callable[[datetime, datetime, bool], bool],
                      infinity_fn: Callable[[datetime], bool]) -> None:
    """Visit all time ranges in the component/property ``child_name`` of
    `vobject_item`` with visitors ``range_fn`` and ``infinity_fn``.

    ``range_fn`` gets called for every time_range with ``start`` and ``end``
    datetimes and ``is_recurrence`` as arguments. If the function returns True,
    the operation is cancelled.

    ``infinity_fn`` gets called when an infinite recurrence rule is detected
    with ``start`` datetime as argument. If the function returns True, the
    operation is cancelled.

    See rfc4791-9.9.

    """

    # HACK: According to rfc5545-3.8.4.4 a recurrence that is rescheduled
    # with Recurrence ID affects the recurrence itself and all following
    # recurrences too. This is not respected and client don't seem to bother
    # either.

    def getrruleset(child: vobject.base.Component, ignore: Sequence[date]
                    ) -> Tuple[Iterable[date], bool]:
        infinite = False
        for rrule in child.contents.get("rrule", []):
            if (";UNTIL=" not in rrule.value.upper() and
                    ";COUNT=" not in rrule.value.upper()):
                infinite = True
                break
        if infinite:
            for dtstart in child.getrruleset(addRDate=True):
                if dtstart in ignore:
                    continue
                if infinity_fn(date_to_datetime(dtstart)):
                    return (), True
                break
        return filter(lambda dtstart: dtstart not in ignore,
                      child.getrruleset(addRDate=True)), False

    def get_children(components: Iterable[vobject.base.Component]) -> Iterator[
                         Tuple[vobject.base.Component, bool, List[date]]]:
        main = None
        rec_main = None
        recurrences = []
        for comp in components:
            if hasattr(comp, "recurrence_id") and comp.recurrence_id.value:
                recurrences.append(comp.recurrence_id.value)
                if comp.rruleset:
                    if comp.rruleset._len is None:
                        logger.warning("Ignore empty RRULESET in item at RECURRENCE-ID with value '%s' and UID '%s'", comp.recurrence_id.value, comp.uid.value)
                    else:
                        # Prevent possible infinite loop
                        raise ValueError("Overwritten recurrence with RRULESET")
                rec_main = comp
                yield comp, True, []
            else:
                if main is not None:
                    raise ValueError("Multiple main components. Got comp: {}".format(comp))
                main = comp
        if main is None and len(recurrences) == 1:
            main = rec_main
        if main is None:
            raise ValueError("Main component missing")
        yield main, False, recurrences

    # Comments give the lines in the tables of the specification
    if child_name == "VEVENT":
        for child, is_recurrence, recurrences in get_children(
                vobject_item.vevent_list):
            # TODO: check if there's a timezone
            dtstart = child.dtstart.value

            if child.rruleset:
                dtstarts, infinity = getrruleset(child, recurrences)
                if infinity:
                    return
            else:
                dtstarts = (dtstart,)

            dtend = getattr(child, "dtend", None)
            if dtend is not None:
                dtend = dtend.value
                original_duration = (dtend - dtstart).total_seconds()
                dtend = date_to_datetime(dtend)

            duration = getattr(child, "duration", None)
            if duration is not None:
                original_duration = duration = duration.value

            for dtstart in dtstarts:
                dtstart_is_datetime = isinstance(dtstart, datetime)
                dtstart = date_to_datetime(dtstart)

                if dtend is not None:
                    # Line 1
                    dtend = dtstart + timedelta(seconds=original_duration)
                    if range_fn(dtstart, dtend, is_recurrence):
                        return
                elif duration is not None:
                    if original_duration is None:
                        original_duration = duration.seconds
                    if duration.seconds > 0:
                        # Line 2
                        if range_fn(dtstart, dtstart + duration,
                                    is_recurrence):
                            return
                    else:
                        # Line 3
                        if range_fn(dtstart, dtstart + SECOND, is_recurrence):
                            return
                elif dtstart_is_datetime:
                    # Line 4
                    if range_fn(dtstart, dtstart + SECOND, is_recurrence):
                        return
                else:
                    # Line 5
                    if range_fn(dtstart, dtstart + DAY, is_recurrence):
                        return

    elif child_name == "VTODO":
        for child, is_recurrence, recurrences in get_children(
                vobject_item.vtodo_list):
            dtstart = getattr(child, "dtstart", None)
            duration = getattr(child, "duration", None)
            due = getattr(child, "due", None)
            completed = getattr(child, "completed", None)
            created = getattr(child, "created", None)

            if dtstart is not None:
                dtstart = date_to_datetime(dtstart.value)
            if duration is not None:
                duration = duration.value
            if due is not None:
                due = date_to_datetime(due.value)
                if dtstart is not None:
                    original_duration = (due - dtstart).total_seconds()
            if completed is not None:
                completed = date_to_datetime(completed.value)
                if created is not None:
                    created = date_to_datetime(created.value)
                    original_duration = (completed - created).total_seconds()
            elif created is not None:
                created = date_to_datetime(created.value)

            if child.rruleset:
                reference_dates, infinity = getrruleset(child, recurrences)
                if infinity:
                    return
            else:
                if dtstart is not None:
                    reference_dates = (dtstart,)
                elif due is not None:
                    reference_dates = (due,)
                elif completed is not None:
                    reference_dates = (completed,)
                elif created is not None:
                    reference_dates = (created,)
                else:
                    # Line 8
                    if range_fn(DATETIME_MIN, DATETIME_MAX, is_recurrence):
                        return
                    reference_dates = ()

            for reference_date in reference_dates:
                reference_date = date_to_datetime(reference_date)

                if dtstart is not None and duration is not None:
                    # Line 1
                    if range_fn(reference_date,
                                reference_date + duration + SECOND,
                                is_recurrence):
                        return
                    if range_fn(reference_date + duration - SECOND,
                                reference_date + duration + SECOND,
                                is_recurrence):
                        return
                elif dtstart is not None and due is not None:
                    # Line 2
                    due = reference_date + timedelta(seconds=original_duration)
                    if (range_fn(reference_date, due, is_recurrence) or
                            range_fn(reference_date,
                                     reference_date + SECOND, is_recurrence) or
                            range_fn(due - SECOND, due, is_recurrence) or
                            range_fn(due - SECOND, reference_date + SECOND,
                                     is_recurrence)):
                        return
                elif dtstart is not None:
                    if range_fn(reference_date, reference_date + SECOND,
                                is_recurrence):
                        return
                elif due is not None:
                    # Line 4
                    if range_fn(reference_date - SECOND, reference_date,
                                is_recurrence):
                        return
                elif completed is not None and created is not None:
                    # Line 5
                    completed = reference_date + timedelta(
                        seconds=original_duration)
                    if (range_fn(reference_date - SECOND,
                                 reference_date + SECOND,
                                 is_recurrence) or
                            range_fn(completed - SECOND, completed + SECOND,
                                     is_recurrence) or
                            range_fn(reference_date - SECOND,
                                     reference_date + SECOND, is_recurrence) or
                            range_fn(completed - SECOND, completed + SECOND,
                                     is_recurrence)):
                        return
                elif completed is not None:
                    # Line 6
                    if range_fn(reference_date - SECOND,
                                reference_date + SECOND, is_recurrence):
                        return
                elif created is not None:
                    # Line 7
                    if range_fn(reference_date, DATETIME_MAX, is_recurrence):
                        return

    elif child_name == "VJOURNAL":
        for child, is_recurrence, recurrences in get_children(
                vobject_item.vjournal_list):
            dtstart = getattr(child, "dtstart", None)

            if dtstart is not None:
                dtstart = dtstart.value
                if child.rruleset:
                    dtstarts, infinity = getrruleset(child, recurrences)
                    if infinity:
                        return
                else:
                    dtstarts = (dtstart,)

                for dtstart in dtstarts:
                    dtstart_is_datetime = isinstance(dtstart, datetime)
                    dtstart = date_to_datetime(dtstart)

                    if dtstart_is_datetime:
                        # Line 1
                        if range_fn(dtstart, dtstart + SECOND, is_recurrence):
                            return
                    else:
                        # Line 2
                        if range_fn(dtstart, dtstart + DAY, is_recurrence):
                            return

    else:
        # Match a property
        child = getattr(vobject_item, child_name.lower())
        if isinstance(child, date):
            child_is_datetime = isinstance(child, datetime)
            child = date_to_datetime(child)
            if child_is_datetime:
                range_fn(child, child + SECOND, False)
            else:
                range_fn(child, child + DAY, False)


def text_match(vobject_item: vobject.base.Component,
               filter_: ET.Element, child_name: str, ns: str,
               attrib_name: Optional[str] = None) -> bool:
    """Check whether the ``item`` matches the text-match ``filter_``.

    See rfc4791-9.7.5.

    """
    # TODO: collations are not supported, but the default ones needed
    # for DAV servers are actually pretty useless. Texts are lowered to
    # be case-insensitive, almost as the "i;ascii-casemap" value.
    text = next(filter_.itertext()).lower()
    match_type = "contains"
    if ns == "CR":
        match_type = filter_.get("match-type", match_type)

    def match(value: str) -> bool:
        value = value.lower()
        if match_type == "equals":
            return value == text
        if match_type == "contains":
            return text in value
        if match_type == "starts-with":
            return value.startswith(text)
        if match_type == "ends-with":
            return value.endswith(text)
        raise ValueError("Unexpected text-match match-type: %r" % match_type)

    children = getattr(vobject_item, "%s_list" % child_name, [])
    if attrib_name is not None:
        condition = any(
            match(attrib) for child in children
            for attrib in child.params.get(attrib_name, []))
    else:
        res = []
        for child in children:
            # Some filters such as CATEGORIES provide a list in child.value
            if type(child.value) is list:
                for value in child.value:
                    res.append(match(value))
            else:
                res.append(match(child.value))
        condition = any(res)
    if filter_.get("negate-condition") == "yes":
        return not condition
    return condition


def param_filter_match(vobject_item: vobject.base.Component,
                       filter_: ET.Element, parent_name: str, ns: str) -> bool:
    """Check whether the ``item`` matches the param-filter ``filter_``.

    See rfc4791-9.7.3.

    """
    name = filter_.get("name", "").upper()
    children = getattr(vobject_item, "%s_list" % parent_name, [])
    condition = any(name in child.params for child in children)
    if len(filter_) > 0:
        if filter_[0].tag == xmlutils.make_clark("%s:text-match" % ns):
            return condition and text_match(
                vobject_item, filter_[0], parent_name, ns, name)
        if filter_[0].tag == xmlutils.make_clark("%s:is-not-defined" % ns):
            return not condition
    return condition


def simplify_prefilters(filters: Iterable[ET.Element], collection_tag: str
                        ) -> Tuple[Optional[str], int, int, bool]:
    """Creates a simplified condition from ``filters``.

    Returns a tuple (``tag``, ``start``, ``end``, ``simple``) where ``tag`` is
    a string or None (match all) and ``start`` and ``end`` are POSIX
    timestamps (as int). ``simple`` is a bool that indicates that ``filters``
    and the simplified condition are identical.

    """
    flat_filters = list(chain.from_iterable(filters))
    simple = len(flat_filters) <= 1
    for col_filter in flat_filters:
        if collection_tag != "VCALENDAR":
            simple = False
            break
        if (col_filter.tag != xmlutils.make_clark("C:comp-filter") or
                col_filter.get("name", "").upper() != "VCALENDAR"):
            simple = False
            continue
        simple &= len(col_filter) <= 1
        for comp_filter in col_filter:
            if comp_filter.tag != xmlutils.make_clark("C:comp-filter"):
                simple = False
                continue
            tag = comp_filter.get("name", "").upper()
            if comp_filter.find(
                    xmlutils.make_clark("C:is-not-defined")) is not None:
                simple = False
                continue
            simple &= len(comp_filter) <= 1
            for time_filter in comp_filter:
                if tag not in ("VTODO", "VEVENT", "VJOURNAL"):
                    simple = False
                    break
                if time_filter.tag != xmlutils.make_clark("C:time-range"):
                    simple = False
                    continue
                start, end = time_range_timestamps(time_filter)
                return tag, start, end, simple
            return tag, TIMESTAMP_MIN, TIMESTAMP_MAX, simple
    return None, TIMESTAMP_MIN, TIMESTAMP_MAX, simple
