# This file is part of Radicale Server - Calendar Server
# Copyright © 2008 Nicolas Kandel
# Copyright © 2008 Pascal Halter
# Copyright © 2008-2015 Guillaume Ayoub
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
XML and iCal requests manager.

Note that all these functions need to receive unicode objects for full
iCal requests (PUT) and string objects with charset correctly defined
in them for XML requests (all but PUT).

"""

import copy
import math
import posixpath
import re
import xml.etree.ElementTree as ET
from collections import OrderedDict
from datetime import date, datetime, timedelta, timezone
from http import client
from itertools import chain
from urllib.parse import quote, unquote, urlparse

from . import storage

MIMETYPES = {
    "VADDRESSBOOK": "text/vcard",
    "VCALENDAR": "text/calendar"}

OBJECT_MIMETYPES = {
    "VCARD": "text/vcard",
    "VLIST": "text/x-vlist",
    "VCALENDAR": "text/calendar"}

NAMESPACES = {
    "C": "urn:ietf:params:xml:ns:caldav",
    "CR": "urn:ietf:params:xml:ns:carddav",
    "D": "DAV:",
    "CS": "http://calendarserver.org/ns/",
    "ICAL": "http://apple.com/ns/ical/",
    "ME": "http://me.com/_namespace/",
    "RADICALE": "http://radicale.org/ns/"}

NAMESPACES_REV = {}
for short, url in NAMESPACES.items():
    NAMESPACES_REV[url] = short
    ET.register_namespace("" if short == "D" else short, url)

CLARK_TAG_REGEX = re.compile(r"{(?P<namespace>[^}]*)}(?P<tag>.*)", re.VERBOSE)
HUMAN_REGEX = re.compile(r"(?P<namespace>[^:{}]*):(?P<tag>.*)", re.VERBOSE)

DAY = timedelta(days=1)
SECOND = timedelta(seconds=1)
DATETIME_MIN = datetime.min.replace(tzinfo=timezone.utc)
DATETIME_MAX = datetime.max.replace(tzinfo=timezone.utc)
TIMESTAMP_MIN = math.floor(DATETIME_MIN.timestamp())
TIMESTAMP_MAX = math.ceil(DATETIME_MAX.timestamp())


def pretty_xml(element, level=0):
    """Indent an ElementTree ``element`` and its children."""
    if not level:
        element = copy.deepcopy(element)
    i = "\n" + level * "  "
    if len(element):
        if not element.text or not element.text.strip():
            element.text = i + "  "
        if not element.tail or not element.tail.strip():
            element.tail = i
        for sub_element in element:
            pretty_xml(sub_element, level + 1)
        if not sub_element.tail or not sub_element.tail.strip():
            sub_element.tail = i
    else:
        if level and (not element.tail or not element.tail.strip()):
            element.tail = i
    if not level:
        return '<?xml version="1.0"?>\n%s' % ET.tostring(element, "unicode")


def _tag(short_name, local):
    """Get XML Clark notation {uri(``short_name``)}``local``."""
    return "{%s}%s" % (NAMESPACES[short_name], local)


def _tag_from_clark(name):
    """Get a human-readable variant of the XML Clark notation tag ``name``.

    For a given name using the XML Clark notation, return a human-readable
    variant of the tag name for known namespaces. Otherwise, return the name as
    is.

    """
    match = CLARK_TAG_REGEX.match(name)
    if match and match.group("namespace") in NAMESPACES_REV:
        args = {
            "ns": NAMESPACES_REV[match.group("namespace")],
            "tag": match.group("tag")}
        return "%(ns)s:%(tag)s" % args
    return name


def _tag_from_human(name):
    """Get an XML Clark notation tag from human-readable variant ``name``."""
    match = HUMAN_REGEX.match(name)
    if match and match.group("namespace") in NAMESPACES:
        return _tag(match.group("namespace"), match.group("tag"))
    return name


def _response(code):
    """Return full W3C names from HTTP status codes."""
    return "HTTP/1.1 %i %s" % (code, client.responses[code])


def _href(base_prefix, href):
    """Return prefixed href."""
    return quote("%s%s" % (base_prefix, href))


def _webdav_error(namespace, name):
    """Generate XML error message."""
    root = ET.Element(_tag("D", "error"))
    root.append(ET.Element(_tag(namespace, name)))
    return root


def _date_to_datetime(date_):
    """Transform a date to a UTC datetime.

    If date_ is a datetime without timezone, return as UTC datetime. If date_
    is already a datetime with timezone, return as is.

    """
    if not isinstance(date_, datetime):
        date_ = datetime.combine(date_, datetime.min.time())
    if not date_.tzinfo:
        date_ = date_.replace(tzinfo=timezone.utc)
    return date_


def _comp_match(item, filter_, level=0):
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
        item.collection.logger.warning(
            "Filters with three levels of comp-filter are not supported")
        return True
    if not tag:
        return False
    name = filter_.get("name").upper()
    if len(filter_) == 0:
        # Point #1 of rfc4791-9.7.1
        return name == tag
    if len(filter_) == 1:
        if filter_[0].tag == _tag("C", "is-not-defined"):
            # Point #2 of rfc4791-9.7.1
            return name != tag
    if name != tag:
        return False
    if (level == 0 and name != "VCALENDAR" or
            level == 1 and name not in ("VTODO", "VEVENT", "VJOURNAL")):
        item.collection.logger.warning("Filtering %s is not supported" % name)
        return True
    # Point #3 and #4 of rfc4791-9.7.1
    components = ([item.item] if level == 0
                  else list(getattr(item, "%s_list" % tag.lower())))
    for child in filter_:
        if child.tag == _tag("C", "prop-filter"):
            if not any(_prop_match(comp, child, "C")
                       for comp in components):
                return False
        elif child.tag == _tag("C", "time-range"):
            if not _time_range_match(item.item, filter_[0], tag):
                return False
        elif child.tag == _tag("C", "comp-filter"):
            if not _comp_match(item, child, level=level + 1):
                return False
        else:
            raise ValueError("Unexpected %r in comp-filter" % child.tag)
    return True


def _prop_match(vobject_item, filter_, ns):
    """Check whether the ``item`` matches the prop ``filter_``.

    See rfc4791-9.7.2 and rfc6352-10.5.1.

    """
    name = filter_.get("name").lower()
    if len(filter_) == 0:
        # Point #1 of rfc4791-9.7.2
        return name in vobject_item.contents
    if len(filter_) == 1:
        if filter_[0].tag == _tag("C", "is-not-defined"):
            # Point #2 of rfc4791-9.7.2
            return name not in vobject_item.contents
    if name not in vobject_item.contents:
        return False
    # Point #3 and #4 of rfc4791-9.7.2
    for child in filter_:
        if ns == "C" and child.tag == _tag("C", "time-range"):
            if not _time_range_match(vobject_item, child, name):
                return False
        elif child.tag == _tag(ns, "text-match"):
            if not _text_match(vobject_item, child, name, ns):
                return False
        elif child.tag == _tag(ns, "param-filter"):
            if not _param_filter_match(vobject_item, child, name, ns):
                return False
        else:
            raise ValueError("Unexpected %r in prop-filter" % child.tag)
    return True


def _time_range_match(vobject_item, filter_, child_name):
    """Check whether the component/property ``child_name`` of
       ``vobject_item`` matches the time-range ``filter_``."""

    start = filter_.get("start")
    end = filter_.get("end")
    if not start and not end:
        return False
    if start:
        start = datetime.strptime(start, "%Y%m%dT%H%M%SZ")
    else:
        start = datetime.min
    if end:
        end = datetime.strptime(end, "%Y%m%dT%H%M%SZ")
    else:
        end = datetime.max
    start = start.replace(tzinfo=timezone.utc)
    end = end.replace(tzinfo=timezone.utc)

    matched = False

    def range_fn(range_start, range_end, is_recurrence):
        nonlocal matched
        if start < range_end and range_start < end:
            matched = True
            return True
        if end < range_start and not is_recurrence:
            return True
        return False

    def infinity_fn(start):
        return False

    _visit_time_ranges(vobject_item, child_name, range_fn, infinity_fn)
    return matched


def _visit_time_ranges(vobject_item, child_name, range_fn, infinity_fn):
    """Visit all time ranges in the component/property ``child_name`` of
    `vobject_item`` with visitors ``range_fn`` and ``infinity_fn``.

    ``range_fn`` gets called for every time_range with ``start`` and ``end``
    datetimes and ``is_recurrence`` as arguments. If the function returns True,
    the operation is cancelled.

    ``infinity_fn`` gets called when an infiite recurrence rule is detected
    with ``start`` datetime as argument. If the function returns True, the
    operation is cancelled.

    See rfc4791-9.9.

    """

    # HACK: According to rfc5545-3.8.4.4 an recurrance that is resheduled
    # with Recurrence ID affects the recurrence itself and all following
    # recurrences too. This is not respected and client don't seem to bother
    # either.

    def getrruleset(child, ignore=()):
        if (hasattr(child, "rrule") and
                ";UNTIL=" not in child.rrule.value.upper() and
                ";COUNT=" not in child.rrule.value.upper()):
            for dtstart in child.getrruleset(addRDate=True):
                if dtstart in ignore:
                    continue
                if infinity_fn(_date_to_datetime(dtstart)):
                    return (), True
                break
        return filter(lambda dtstart: dtstart not in ignore,
                      child.getrruleset(addRDate=True)), False

    def get_children(components):
        main = None
        recurrences = []
        for comp in components:
            if hasattr(comp, "recurrence_id") and comp.recurrence_id.value:
                recurrences.append(comp.recurrence_id.value)
                if comp.rruleset:
                    # Prevent possible infinite loop
                    raise ValueError("Overwritten recurrence with RRULESET")
                yield comp, True, ()
            else:
                if main is not None:
                    raise ValueError("Multiple main components")
                main = comp
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
                dtend = _date_to_datetime(dtend)

            duration = getattr(child, "duration", None)
            if duration is not None:
                original_duration = duration = duration.value

            for dtstart in dtstarts:
                dtstart_is_datetime = isinstance(dtstart, datetime)
                dtstart = _date_to_datetime(dtstart)

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
                dtstart = _date_to_datetime(dtstart.value)
            if duration is not None:
                duration = duration.value
            if due is not None:
                due = _date_to_datetime(due.value)
                if dtstart is not None:
                    original_duration = (due - dtstart).total_seconds()
            if completed is not None:
                completed = _date_to_datetime(completed.value)
                if created is not None:
                    created = _date_to_datetime(created.value)
                    original_duration = (completed - created).total_seconds()
            elif created is not None:
                created = _date_to_datetime(created.value)

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
                reference_date = _date_to_datetime(reference_date)

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
                    dtstart = _date_to_datetime(dtstart)

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
            range_fn(child, child + DAY, False)
        elif isinstance(child, datetime):
            range_fn(child, child + SECOND, False)


def _text_match(vobject_item, filter_, child_name, ns, attrib_name=None):
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

    def match(value):
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
    if attrib_name:
        condition = any(
            match(attrib) for child in children
            for attrib in child.params.get(attrib_name, []))
    else:
        condition = any(match(child.value) for child in children)
    if filter_.get("negate-condition") == "yes":
        return not condition
    else:
        return condition


def _param_filter_match(vobject_item, filter_, parent_name, ns):
    """Check whether the ``item`` matches the param-filter ``filter_``.

    See rfc4791-9.7.3.

    """
    name = filter_.get("name").upper()
    children = getattr(vobject_item, "%s_list" % parent_name, [])
    condition = any(name in child.params for child in children)
    if len(filter_):
        if filter_[0].tag == _tag(ns, "text-match"):
            return condition and _text_match(
                vobject_item, filter_[0], parent_name, ns, name)
        elif filter_[0].tag == _tag(ns, "is-not-defined"):
            return not condition
    else:
        return condition


def simplify_prefilters(filters, collection_tag="VCALENDAR"):
    """Creates a simplified condition from ``filters``.

    Returns a tuple (``tag``, ``start``, ``end``, ``simple``) where ``tag`` is
    a string or None (match all) and ``start`` and ``end`` are POSIX
    timestamps (as int). ``simple`` is a bool that indicates that ``filters``
    and the simplified condition are identical.

    """
    flat_filters = tuple(chain.from_iterable(filters))
    simple = len(flat_filters) <= 1
    for col_filter in flat_filters:
        if collection_tag != "VCALENDAR":
            simple = False
            break
        if (col_filter.tag != _tag("C", "comp-filter") or
                col_filter.get("name").upper() != "VCALENDAR"):
            simple = False
            continue
        simple &= len(col_filter) <= 1
        for comp_filter in col_filter:
            if comp_filter.tag != _tag("C", "comp-filter"):
                simple = False
                continue
            tag = comp_filter.get("name").upper()
            if comp_filter.find(_tag("C", "is-not-defined")) is not None:
                simple = False
                continue
            simple &= len(comp_filter) <= 1
            for time_filter in comp_filter:
                if tag not in ("VTODO", "VEVENT", "VJOURNAL"):
                    simple = False
                    break
                if time_filter.tag != _tag("C", "time-range"):
                    simple = False
                    continue
                start = time_filter.get("start")
                end = time_filter.get("end")
                if start:
                    start = math.floor(datetime.strptime(
                        start, "%Y%m%dT%H%M%SZ").replace(
                            tzinfo=timezone.utc).timestamp())
                else:
                    start = TIMESTAMP_MIN
                if end:
                    end = math.ceil(datetime.strptime(
                        end, "%Y%m%dT%H%M%SZ").replace(
                            tzinfo=timezone.utc).timestamp())
                else:
                    end = TIMESTAMP_MAX
                return tag, start, end, simple
            return tag, TIMESTAMP_MIN, TIMESTAMP_MAX, simple
    return None, TIMESTAMP_MIN, TIMESTAMP_MAX, simple


def get_content_type(item):
    """Get the content-type of an item with charset and component parameters.
    """
    mimetype = OBJECT_MIMETYPES[item.name]
    encoding = item.collection.configuration.get("encoding", "request")
    tag = item.component_name
    content_type = "%s;charset=%s" % (mimetype, encoding)
    if tag:
        content_type += ";component=%s" % tag
    return content_type


def find_tag(vobject_item):
    """Find tag from ``vobject_item``."""
    if vobject_item.name == "VCALENDAR":
        for component in vobject_item.components():
            if component.name != "VTIMEZONE":
                return component.name
    return None


def find_tag_and_time_range(vobject_item):
    """Find tag and enclosing time range from ``vobject item``.

    Returns a tuple (``tag``, ``start``, ``end``) where ``tag`` is a string
    and ``start`` and ``end`` are POSIX timestamps (as int).

    This is intened to be used for matching against simplified prefilters.

    """
    tag = find_tag(vobject_item)
    if not tag:
        return (None, TIMESTAMP_MIN, TIMESTAMP_MAX)
    start = end = None

    def range_fn(range_start, range_end, is_recurrence):
        nonlocal start, end
        if start is None or range_start < start:
            start = range_start
        if end is None or end < range_end:
            end = range_end
        return False

    def infinity_fn(range_start):
        nonlocal start, end
        if start is None or range_start < start:
            start = range_start
        end = DATETIME_MAX
        return True

    _visit_time_ranges(vobject_item, tag, range_fn, infinity_fn)
    if start is None:
        start = DATETIME_MIN
    if end is None:
        end = DATETIME_MAX
    return tag, math.floor(start.timestamp()), math.ceil(end.timestamp())


def name_from_path(path, collection):
    """Return Radicale item name from ``path``."""
    path = path.strip("/") + "/"
    start = collection.path + "/"
    if not path.startswith(start):
        raise ValueError("%r doesn't start with %r" % (path, start))
    name = path[len(start):][:-1]
    if name and not storage.is_safe_path_component(name):
        raise ValueError("%r is not a component in collection %r" %
                         (name, collection.path))
    return name


def props_from_request(xml_request, actions=("set", "remove")):
    """Return a list of properties as a dictionary."""
    result = OrderedDict()
    if xml_request is None:
        return result

    for action in actions:
        action_element = xml_request.find(_tag("D", action))
        if action_element is not None:
            break
    else:
        action_element = xml_request

    prop_element = action_element.find(_tag("D", "prop"))
    if prop_element is not None:
        for prop in prop_element:
            if prop.tag == _tag("D", "resourcetype"):
                for resource_type in prop:
                    if resource_type.tag == _tag("C", "calendar"):
                        result["tag"] = "VCALENDAR"
                        break
                    elif resource_type.tag == _tag("CR", "addressbook"):
                        result["tag"] = "VADDRESSBOOK"
                        break
            elif prop.tag == _tag("C", "supported-calendar-component-set"):
                result[_tag_from_clark(prop.tag)] = ",".join(
                    supported_comp.attrib["name"]
                    for supported_comp in prop
                    if supported_comp.tag == _tag("C", "comp"))
            else:
                result[_tag_from_clark(prop.tag)] = prop.text

    return result


def delete(base_prefix, path, collection, href=None):
    """Read and answer DELETE requests.

    Read rfc4918-9.6 for info.

    """
    collection.delete(href)

    multistatus = ET.Element(_tag("D", "multistatus"))
    response = ET.Element(_tag("D", "response"))
    multistatus.append(response)

    href = ET.Element(_tag("D", "href"))
    href.text = _href(base_prefix, path)
    response.append(href)

    status = ET.Element(_tag("D", "status"))
    status.text = _response(200)
    response.append(status)

    return multistatus


def propfind(base_prefix, path, xml_request, read_collections,
             write_collections, user):
    """Read and answer PROPFIND requests.

    Read rfc4918-9.1 for info.

    The collections parameter is a list of collections that are to be included
    in the output.

    """
    # A client may choose not to submit a request body.  An empty PROPFIND
    # request body MUST be treated as if it were an 'allprop' request.
    top_tag = (xml_request[0] if xml_request is not None else
               ET.Element(_tag("D", "allprop")))

    props = ()
    allprop = False
    propname = False
    if top_tag.tag == _tag("D", "allprop"):
        allprop = True
    elif top_tag.tag == _tag("D", "propname"):
        propname = True
    elif top_tag.tag == _tag("D", "prop"):
        props = [prop.tag for prop in top_tag]

    if _tag("D", "current-user-principal") in props and not user:
        # Ask for authentication
        # Returning the DAV:unauthenticated pseudo-principal as specified in
        # RFC 5397 doesn't seem to work with DAVdroid.
        return client.FORBIDDEN, None

    # Writing answer
    multistatus = ET.Element(_tag("D", "multistatus"))

    collections = []
    for collection in write_collections:
        collections.append(collection)
        response = _propfind_response(
            base_prefix, path, collection, props, user, write=True,
            allprop=allprop, propname=propname)
        if response:
            multistatus.append(response)
    for collection in read_collections:
        if collection in collections:
            continue
        response = _propfind_response(
            base_prefix, path, collection, props, user, write=False,
            allprop=allprop, propname=propname)
        if response:
            multistatus.append(response)

    return client.MULTI_STATUS, multistatus


def _propfind_response(base_prefix, path, item, props, user, write=False,
                       propname=False, allprop=False):
    """Build and return a PROPFIND response."""
    if propname and allprop or (props and (propname or allprop)):
        raise ValueError("Only use one of props, propname and allprops")
    is_collection = isinstance(item, storage.BaseCollection)
    if is_collection:
        is_leaf = item.get_meta("tag") in ("VADDRESSBOOK", "VCALENDAR")
        collection = item
    else:
        collection = item.collection

    response = ET.Element(_tag("D", "response"))

    href = ET.Element(_tag("D", "href"))
    if is_collection:
        # Some clients expect collections to end with /
        uri = "/%s/" % item.path if item.path else "/"
    else:
        uri = "/" + posixpath.join(collection.path, item.href)

    href.text = _href(base_prefix, uri)
    response.append(href)

    propstat404 = ET.Element(_tag("D", "propstat"))
    propstat200 = ET.Element(_tag("D", "propstat"))
    response.append(propstat200)

    prop200 = ET.Element(_tag("D", "prop"))
    propstat200.append(prop200)

    prop404 = ET.Element(_tag("D", "prop"))
    propstat404.append(prop404)

    if propname or allprop:
        props = []
        # Should list all properties that can be retrieved by the code below
        props.append(_tag("D", "principal-collection-set"))
        props.append(_tag("D", "current-user-principal"))
        props.append(_tag("D", "current-user-privilege-set"))
        props.append(_tag("D", "supported-report-set"))
        props.append(_tag("D", "resourcetype"))
        props.append(_tag("D", "owner"))

        if is_collection and collection.is_principal:
            props.append(_tag("C", "calendar-user-address-set"))
            props.append(_tag("D", "principal-URL"))
            props.append(_tag("CR", "addressbook-home-set"))
            props.append(_tag("C", "calendar-home-set"))

        if not is_collection or is_leaf:
            props.append(_tag("D", "getetag"))
            props.append(_tag("D", "getlastmodified"))
            props.append(_tag("D", "getcontenttype"))
            props.append(_tag("D", "getcontentlength"))

        if is_collection:
            if is_leaf:
                props.append(_tag("D", "displayname"))
                props.append(_tag("D", "sync-token"))
            if collection.get_meta("tag") == "VCALENDAR":
                props.append(_tag("CS", "getctag"))
                props.append(_tag("C", "supported-calendar-component-set"))

            meta = item.get_meta()
            for tag in meta:
                if tag == "tag":
                    continue
                clark_tag = _tag_from_human(tag)
                if clark_tag not in props:
                    props.append(clark_tag)

    if propname:
        for tag in props:
            prop200.append(ET.Element(tag))
        props = ()

    for tag in props:
        element = ET.Element(tag)
        is404 = False
        if tag == _tag("D", "getetag"):
            if not is_collection or is_leaf:
                element.text = item.etag
            else:
                is404 = True
        elif tag == _tag("D", "getlastmodified"):
            if not is_collection or is_leaf:
                element.text = item.last_modified
            else:
                is404 = True
        elif tag == _tag("D", "principal-collection-set"):
            tag = ET.Element(_tag("D", "href"))
            tag.text = _href(base_prefix, "/")
            element.append(tag)
        elif (tag in (_tag("C", "calendar-user-address-set"),
                      _tag("D", "principal-URL"),
                      _tag("CR", "addressbook-home-set"),
                      _tag("C", "calendar-home-set")) and
                collection.is_principal and is_collection):
            tag = ET.Element(_tag("D", "href"))
            tag.text = _href(base_prefix, path)
            element.append(tag)
        elif tag == _tag("C", "supported-calendar-component-set"):
            human_tag = _tag_from_clark(tag)
            if is_collection and is_leaf:
                meta = item.get_meta(human_tag)
                if meta:
                    components = meta.split(",")
                else:
                    components = ("VTODO", "VEVENT", "VJOURNAL")
                for component in components:
                    comp = ET.Element(_tag("C", "comp"))
                    comp.set("name", component)
                    element.append(comp)
            else:
                is404 = True
        elif tag == _tag("D", "current-user-principal"):
            if user:
                tag = ET.Element(_tag("D", "href"))
                tag.text = _href(base_prefix, "/%s/" % user)
                element.append(tag)
            else:
                element.append(ET.Element(_tag("D", "unauthenticated")))
        elif tag == _tag("D", "current-user-privilege-set"):
            privileges = [("D", "read")]
            if write:
                privileges.append(("D", "all"))
                privileges.append(("D", "write"))
                privileges.append(("D", "write-properties"))
                privileges.append(("D", "write-content"))
            for ns, privilege_name in privileges:
                privilege = ET.Element(_tag("D", "privilege"))
                privilege.append(ET.Element(_tag(ns, privilege_name)))
                element.append(privilege)
        elif tag == _tag("D", "supported-report-set"):
            # These 3 reports are not implemented
            reports = [
                ("D", "expand-property"),
                ("D", "principal-search-property-set"),
                ("D", "principal-property-search")]
            if is_collection and is_leaf:
                reports.append(("D", "sync-collection"))
                if item.get_meta("tag") == "VADDRESSBOOK":
                    reports.append(("CR", "addressbook-multiget"))
                    reports.append(("CR", "addressbook-query"))
                elif item.get_meta("tag") == "VCALENDAR":
                    reports.append(("C", "calendar-multiget"))
                    reports.append(("C", "calendar-query"))
            for ns, report_name in reports:
                supported = ET.Element(_tag("D", "supported-report"))
                report_tag = ET.Element(_tag("D", "report"))
                supported_report_tag = ET.Element(_tag(ns, report_name))
                report_tag.append(supported_report_tag)
                supported.append(report_tag)
                element.append(supported)
        elif tag == _tag("D", "getcontentlength"):
            if not is_collection or is_leaf:
                encoding = collection.configuration.get("encoding", "request")
                element.text = str(len(item.serialize().encode(encoding)))
            else:
                is404 = True
        elif tag == _tag("D", "owner"):
            # return empty elment, if no owner available (rfc3744-5.1)
            if collection.owner:
                tag = ET.Element(_tag("D", "href"))
                tag.text = _href(base_prefix, "/%s/" % collection.owner)
                element.append(tag)
        elif is_collection:
            if tag == _tag("D", "getcontenttype"):
                if is_leaf:
                    element.text = MIMETYPES[item.get_meta("tag")]
                else:
                    is404 = True
            elif tag == _tag("D", "resourcetype"):
                if item.is_principal:
                    tag = ET.Element(_tag("D", "principal"))
                    element.append(tag)
                if is_leaf:
                    if item.get_meta("tag") == "VADDRESSBOOK":
                        tag = ET.Element(_tag("CR", "addressbook"))
                        element.append(tag)
                    elif item.get_meta("tag") == "VCALENDAR":
                        tag = ET.Element(_tag("C", "calendar"))
                        element.append(tag)
                tag = ET.Element(_tag("D", "collection"))
                element.append(tag)
            elif tag == _tag("RADICALE", "displayname"):
                # Only for internal use by the web interface
                displayname = item.get_meta("D:displayname")
                if displayname is not None:
                    element.text = displayname
                else:
                    is404 = True
            elif tag == _tag("D", "displayname"):
                displayname = item.get_meta("D:displayname")
                if not displayname and is_leaf:
                    displayname = item.path
                if displayname is not None:
                    element.text = displayname
                else:
                    is404 = True
            elif tag == _tag("CS", "getctag"):
                if is_leaf:
                    element.text = item.etag
                else:
                    is404 = True
            elif tag == _tag("D", "sync-token"):
                if is_leaf:
                    element.text, _ = item.sync()
                else:
                    is404 = True
            else:
                human_tag = _tag_from_clark(tag)
                meta = item.get_meta(human_tag)
                if meta is not None:
                    element.text = meta
                else:
                    is404 = True
        # Not for collections
        elif tag == _tag("D", "getcontenttype"):
            element.text = get_content_type(item)
        elif tag == _tag("D", "resourcetype"):
            # resourcetype must be returned empty for non-collection elements
            pass
        else:
            is404 = True

        if is404:
            prop404.append(element)
        else:
            prop200.append(element)

    status200 = ET.Element(_tag("D", "status"))
    status200.text = _response(200)
    propstat200.append(status200)

    status404 = ET.Element(_tag("D", "status"))
    status404.text = _response(404)
    propstat404.append(status404)
    if len(prop404):
        response.append(propstat404)

    return response


def _add_propstat_to(element, tag, status_number):
    """Add a PROPSTAT response structure to an element.

    The PROPSTAT answer structure is defined in rfc4918-9.1. It is added to the
    given ``element``, for the following ``tag`` with the given
    ``status_number``.

    """
    propstat = ET.Element(_tag("D", "propstat"))
    element.append(propstat)

    prop = ET.Element(_tag("D", "prop"))
    propstat.append(prop)

    clark_tag = tag if "{" in tag else _tag(*tag.split(":", 1))
    prop_tag = ET.Element(clark_tag)
    prop.append(prop_tag)

    status = ET.Element(_tag("D", "status"))
    status.text = _response(status_number)
    propstat.append(status)


def proppatch(base_prefix, path, xml_request, collection):
    """Read and answer PROPPATCH requests.

    Read rfc4918-9.2 for info.

    """
    props_to_set = props_from_request(xml_request, actions=("set",))
    props_to_remove = props_from_request(xml_request, actions=("remove",))

    multistatus = ET.Element(_tag("D", "multistatus"))
    response = ET.Element(_tag("D", "response"))
    multistatus.append(response)

    href = ET.Element(_tag("D", "href"))
    href.text = _href(base_prefix, path)
    response.append(href)

    new_props = collection.get_meta()
    for short_name, value in props_to_set.items():
        new_props[short_name] = value
        _add_propstat_to(response, short_name, 200)
    for short_name in props_to_remove:
        try:
            del new_props[short_name]
        except KeyError:
            pass
        _add_propstat_to(response, short_name, 200)
    storage.check_and_sanitize_props(new_props)
    collection.set_meta_all(new_props)

    return multistatus


def report(base_prefix, path, xml_request, collection):
    """Read and answer REPORT requests.

    Read rfc3253-3.6 for info.

    """
    logger = collection.logger
    multistatus = ET.Element(_tag("D", "multistatus"))
    if xml_request is None:
        return client.MULTI_STATUS, multistatus
    root = xml_request
    if root.tag in (
            _tag("D", "principal-search-property-set"),
            _tag("D", "principal-property-search"),
            _tag("D", "expand-property")):
        # We don't support searching for principals or indirect retrieving of
        # properties, just return an empty result.
        # InfCloud asks for expand-property reports (even if we don't announce
        # support for them) and stops working if an error code is returned.
        logger.warning("Unsupported REPORT method %r on %r requested",
                       root.tag, path)
        return client.MULTI_STATUS, multistatus
    prop_element = root.find(_tag("D", "prop"))
    props = (
        [prop.tag for prop in prop_element]
        if prop_element is not None else [])

    if root.tag in (
            _tag("C", "calendar-multiget"),
            _tag("CR", "addressbook-multiget")):
        # Read rfc4791-7.9 for info
        hreferences = set()
        for href_element in root.findall(_tag("D", "href")):
            href_path = storage.sanitize_path(
                unquote(urlparse(href_element.text).path))
            if (href_path + "/").startswith(base_prefix + "/"):
                hreferences.add(href_path[len(base_prefix):])
            else:
                logger.warning("Skipping invalid path %r in REPORT request on "
                               "%r", href_path, path)
    elif root.tag == _tag("D", "sync-collection"):
        old_sync_token_element = root.find(_tag("D", "sync-token"))
        old_sync_token = ""
        if old_sync_token_element is not None and old_sync_token_element.text:
            old_sync_token = old_sync_token_element.text.strip()
        logger.debug("Client provided sync token: %r", old_sync_token)
        try:
            sync_token, names = collection.sync(old_sync_token)
        except ValueError as e:
            # Invalid sync token
            logger.warning("Client provided invalid sync token %r: %s",
                           old_sync_token, e, exc_info=True)
            return (client.PRECONDITION_FAILED,
                    _webdav_error("D", "valid-sync-token"))
        hreferences = ("/" + posixpath.join(collection.path, n) for n in names)
        # Append current sync token to response
        sync_token_element = ET.Element(_tag("D", "sync-token"))
        sync_token_element.text = sync_token
        multistatus.append(sync_token_element)
    else:
        hreferences = (path,)
    filters = (
        root.findall("./%s" % _tag("C", "filter")) +
        root.findall("./%s" % _tag("CR", "filter")))

    def retrieve_items(collection, hreferences, multistatus):
        """Retrieves all items that are referenced in ``hreferences`` from
           ``collection`` and adds 404 responses for missing and invalid items
           to ``multistatus``."""
        collection_requested = False

        def get_names():
            """Extracts all names from references in ``hreferences`` and adds
               404 responses for invalid references to ``multistatus``.
               If the whole collections is referenced ``collection_requested``
               gets set to ``True``."""
            nonlocal collection_requested
            for hreference in hreferences:
                try:
                    name = name_from_path(hreference, collection)
                except ValueError as e:
                    logger.warning("Skipping invalid path %r in REPORT request"
                                   " on %r: %s", hreference, path, e)
                    response = _item_response(base_prefix, hreference,
                                              found_item=False)
                    multistatus.append(response)
                    continue
                if name:
                    # Reference is an item
                    yield name
                else:
                    # Reference is a collection
                    collection_requested = True

        for name, item in collection.get_multi2(get_names()):
            if not item:
                uri = "/" + posixpath.join(collection.path, name)
                response = _item_response(base_prefix, uri,
                                          found_item=False)
                multistatus.append(response)
            else:
                yield item, False
        if collection_requested:
            yield from collection.get_all_filtered(filters)

    def match(item, filter_):
        tag = collection.get_meta("tag")
        if (tag == "VCALENDAR" and filter_.tag != _tag("C", filter_)):
            if len(filter_) == 0:
                return True
            if len(filter_) > 1:
                raise ValueError("Filter with %d children" % len(filter_))
            if filter_[0].tag != _tag("C", "comp-filter"):
                raise ValueError("Unexpected %r in filter" % filter_[0].tag)
            return _comp_match(item, filter_[0])
        if tag == "VADDRESSBOOK" and filter_.tag != _tag("CR", filter_):
            for child in filter_:
                if child.tag != _tag("CR", "prop-filter"):
                    raise ValueError("Unexpected %r in filter" % child.tag)
            test = filter_.get("test", "anyof")
            if test == "anyof":
                return any(_prop_match(item.item, f, "CR") for f in filter_)
            if test == "allof":
                return all(_prop_match(item.item, f, "CR") for f in filter_)
            raise ValueError("Unsupported filter test: %r" % test)
            return all(_prop_match(item.item, f, "CR") for f in filter_)
        raise ValueError("unsupported filter %r for %r" % (filter_.tag, tag))

    for item, filters_matched in retrieve_items(collection, hreferences,
                                                multistatus):
        if filters and not filters_matched:
            try:
                if not all(match(item, filter_) for filter_ in filters):
                    continue
            except ValueError as e:
                raise ValueError("Failed to filter item %r from %r: %s" %
                                 (item.href, collection.path, e)) from e
            except Exception as e:
                raise RuntimeError("Failed to filter item %r from %r: %s" %
                                   (item.href, collection.path, e)) from e

        found_props = []
        not_found_props = []

        for tag in props:
            element = ET.Element(tag)
            if tag == _tag("D", "getetag"):
                element.text = item.etag
                found_props.append(element)
            elif tag == _tag("D", "getcontenttype"):
                element.text = get_content_type(item)
                found_props.append(element)
            elif tag in (
                    _tag("C", "calendar-data"),
                    _tag("CR", "address-data")):
                element.text = item.serialize()
                found_props.append(element)
            else:
                not_found_props.append(element)

        uri = "/" + posixpath.join(collection.path, item.href)
        multistatus.append(_item_response(
            base_prefix, uri, found_props=found_props,
            not_found_props=not_found_props, found_item=True))

    return client.MULTI_STATUS, multistatus


def _item_response(base_prefix, href, found_props=(), not_found_props=(),
                   found_item=True):
    response = ET.Element(_tag("D", "response"))

    href_tag = ET.Element(_tag("D", "href"))
    href_tag.text = _href(base_prefix, href)
    response.append(href_tag)

    if found_item:
        for code, props in ((200, found_props), (404, not_found_props)):
            if props:
                propstat = ET.Element(_tag("D", "propstat"))
                status = ET.Element(_tag("D", "status"))
                status.text = _response(code)
                prop_tag = ET.Element(_tag("D", "prop"))
                for prop in props:
                    prop_tag.append(prop)
                propstat.append(prop_tag)
                propstat.append(status)
                response.append(propstat)
    else:
        status = ET.Element(_tag("D", "status"))
        status.text = _response(404)
        response.append(status)

    return response
