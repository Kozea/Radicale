# This file is part of Radicale - CalDAV and CardDAV server
# Copyright © 2008 Nicolas Kandel
# Copyright © 2008 Pascal Halter
# Copyright © 2008-2017 Guillaume Ayoub
# Copyright © 2017-2021 Unrud <unrud@outlook.com>
# Copyright © 2024-2024 Pieter Hijma <pieterhijma@users.noreply.github.com>
# Copyright © 2024-2024 Ray <ray@react0r.com>
# Copyright © 2024-2025 Georgiy <metallerok@gmail.com>
# Copyright © 2024-2025 Peter Bieringer <pb@bieringer.de>
# Copyright © 2025-2025 David Greaves <david@dgreaves.com>
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

import contextlib
import copy
import datetime
import posixpath
import socket
import xml.etree.ElementTree as ET
from http import client
from typing import (Callable, Iterable, Iterator, List, Optional, Sequence,
                    Tuple, Union)
from urllib.parse import unquote, urlparse

import vobject
import vobject.base
from vobject.base import ContentLine

import radicale.item as radicale_item
from radicale import httputils, pathutils, storage, types, xmlutils
from radicale.app.base import Access, ApplicationBase
from radicale.item import filter as radicale_filter
from radicale.log import logger

DT_FORMAT_TIMESTAMP: str = '%Y%m%dT%H%M%SZ'
DT_FORMAT_DATE: str = '%Y%m%d'


def free_busy_report(base_prefix: str, path: str, xml_request: Optional[ET.Element],
                     collection: storage.BaseCollection, encoding: str,
                     unlock_storage_fn: Callable[[], None],
                     max_occurrence: int
                     ) -> Tuple[int, Union[ET.Element, str]]:
    # NOTE: this function returns both an Element and a string because
    # free-busy reports are an edge-case on the return type according
    # to the spec.

    multistatus = ET.Element(xmlutils.make_clark("D:multistatus"))
    if xml_request is None:
        return client.MULTI_STATUS, multistatus
    root = xml_request
    if (root.tag == xmlutils.make_clark("C:free-busy-query") and
            collection.tag != "VCALENDAR"):
        logger.warning("Invalid REPORT method %r on %r requested",
                       xmlutils.make_human_tag(root.tag), path)
        return client.FORBIDDEN, xmlutils.webdav_error("D:supported-report")

    time_range_element = root.find(xmlutils.make_clark("C:time-range"))
    assert isinstance(time_range_element, ET.Element)

    # Build a single filter from the free busy query for retrieval
    # TODO: filter for VFREEBUSY in additional to VEVENT but
    # test_filter doesn't support that yet.
    vevent_cf_element = ET.Element(xmlutils.make_clark("C:comp-filter"),
                                   attrib={'name': 'VEVENT'})
    vevent_cf_element.append(time_range_element)
    vcalendar_cf_element = ET.Element(xmlutils.make_clark("C:comp-filter"),
                                      attrib={'name': 'VCALENDAR'})
    vcalendar_cf_element.append(vevent_cf_element)
    filter_element = ET.Element(xmlutils.make_clark("C:filter"))
    filter_element.append(vcalendar_cf_element)
    filters = (filter_element,)

    # First pull from storage
    retrieved_items = list(collection.get_filtered(filters))
    # !!! Don't access storage after this !!!
    unlock_storage_fn()

    cal = vobject.iCalendar()
    collection_tag = collection.tag
    while retrieved_items:
        # Second filtering before evaluating occurrences.
        # ``item.vobject_item`` might be accessed during filtering.
        # Don't keep reference to ``item``, because VObject requires a lot of
        # memory.
        item, filter_matched = retrieved_items.pop(0)
        if not filter_matched:
            try:
                if not test_filter(collection_tag, item, filter_element):
                    continue
            except ValueError as e:
                raise ValueError("Failed to free-busy filter item %r from %r: %s" %
                                 (item.href, collection.path, e)) from e
            except Exception as e:
                raise RuntimeError("Failed to free-busy filter item %r from %r: %s" %
                                   (item.href, collection.path, e)) from e

        fbtype = None
        if item.component_name == 'VEVENT':
            transp = getattr(item.vobject_item.vevent, 'transp', None)
            if transp and transp.value != 'OPAQUE':
                continue

            status = getattr(item.vobject_item.vevent, 'status', None)
            if not status or status.value == 'CONFIRMED':
                fbtype = 'BUSY'
            elif status.value == 'CANCELLED':
                fbtype = 'FREE'
            elif status.value == 'TENTATIVE':
                fbtype = 'BUSY-TENTATIVE'
            else:
                # Could do fbtype = status.value for x-name, I prefer this
                fbtype = 'BUSY'

        # TODO: coalesce overlapping periods

        if max_occurrence > 0:
            n_occurrences = max_occurrence+1
        else:
            n_occurrences = 0
        occurrences = radicale_filter.time_range_fill(item.vobject_item,
                                                      time_range_element,
                                                      "VEVENT",
                                                      n=n_occurrences)
        if len(occurrences) >= max_occurrence:
            raise ValueError("FREEBUSY occurrences limit of {} hit"
                             .format(max_occurrence))

        for occurrence in occurrences:
            vfb = cal.add('vfreebusy')
            vfb.add('dtstamp').value = item.vobject_item.vevent.dtstamp.value
            vfb.add('dtstart').value, vfb.add('dtend').value = occurrence
            if fbtype:
                vfb.add('fbtype').value = fbtype
    return (client.OK, cal.serialize())


def xml_report(base_prefix: str, path: str, xml_request: Optional[ET.Element],
               collection: storage.BaseCollection, encoding: str,
               unlock_storage_fn: Callable[[], None],
               max_occurrence: int = 0, user: str = "", remote_addr: str = "", remote_useragent: str = ""
               ) -> Tuple[int, ET.Element]:
    """Read and answer REPORT requests that return XML.

    Read rfc3253-3.6 for info.

    """
    logger.debug("TRACE/REPORT/xml_report: base_prefix=%r path=%r", base_prefix, path)
    multistatus = ET.Element(xmlutils.make_clark("D:multistatus"))
    if xml_request is None:
        return client.MULTI_STATUS, multistatus
    root = xml_request
    if root.tag in (xmlutils.make_clark("D:principal-search-property-set"),
                    xmlutils.make_clark("D:principal-property-search"),
                    xmlutils.make_clark("D:expand-property")):
        # We don't support searching for principals or indirect retrieving of
        # properties, just return an empty result.
        # InfCloud asks for expand-property reports (even if we don't announce
        # support for them) and stops working if an error code is returned.
        logger.warning("Unsupported REPORT method %r on %r requested",
                       xmlutils.make_human_tag(root.tag), path)
        return client.MULTI_STATUS, multistatus
    if (root.tag == xmlutils.make_clark("C:calendar-multiget") and
            collection.tag != "VCALENDAR" or
            root.tag == xmlutils.make_clark("CR:addressbook-multiget") and
            collection.tag != "VADDRESSBOOK" or
            root.tag == xmlutils.make_clark("D:sync-collection") and
            collection.tag not in ("VADDRESSBOOK", "VCALENDAR")):
        logger.warning("Invalid REPORT method %r on %r requested",
                       xmlutils.make_human_tag(root.tag), path)
        return client.FORBIDDEN, xmlutils.webdav_error("D:supported-report")

    props: Union[ET.Element, List]
    if root.find(xmlutils.make_clark("D:prop")) is not None:
        props = root.find(xmlutils.make_clark("D:prop"))  # type: ignore[assignment]
    else:
        props = []

    hreferences: Iterable[str]
    if root.tag in (
            xmlutils.make_clark("C:calendar-multiget"),
            xmlutils.make_clark("CR:addressbook-multiget")):
        # Read rfc4791-7.9 for info
        hreferences = set()
        for href_element in root.findall(xmlutils.make_clark("D:href")):
            temp_url_path = urlparse(href_element.text).path
            assert isinstance(temp_url_path, str)
            href_path = pathutils.sanitize_path(unquote(temp_url_path))
            if (href_path + "/").startswith(base_prefix + "/"):
                hreferences.add(href_path[len(base_prefix):])
            else:
                logger.warning("Skipping invalid path %r in REPORT request on "
                               "%r", href_path, path)
    elif root.tag == xmlutils.make_clark("D:sync-collection"):
        old_sync_token_element = root.find(
            xmlutils.make_clark("D:sync-token"))
        old_sync_token = ""
        if old_sync_token_element is not None and old_sync_token_element.text:
            old_sync_token = old_sync_token_element.text.strip()
        logger.debug("Client provided sync token: %r", old_sync_token)
        try:
            sync_token, names = collection.sync(old_sync_token)
        except ValueError as e:
            # Invalid sync token
            logger.warning("Client provided invalid sync token for path %r (user %r from %s%s): %s",
                           path, user, remote_addr, remote_useragent, e, exc_info=True)
            # client.CONFLICT doesn't work with some clients (e.g. InfCloud)
            return (client.FORBIDDEN,
                    xmlutils.webdav_error("D:valid-sync-token"))
        hreferences = (pathutils.unstrip_path(
            posixpath.join(collection.path, n)) for n in names)
        # Append current sync token to response
        sync_token_element = ET.Element(xmlutils.make_clark("D:sync-token"))
        sync_token_element.text = sync_token
        multistatus.append(sync_token_element)
    else:
        hreferences = (path,)
    filters = (
        root.findall(xmlutils.make_clark("C:filter")) +
        root.findall(xmlutils.make_clark("CR:filter")))
    expand = root.find(".//" + xmlutils.make_clark("C:expand"))

    # if we have expand prop we use "filter (except time range) -> expand -> filter (only time range)" approach
    time_range_element = None
    main_filters = []
    for filter_ in filters:
        # extract time-range filter for processing after main filters
        # for expand request
        filter_copy = copy.deepcopy(filter_)

        if expand is not None:
            logger.debug("TRACE/REPORT/xml_report: expand")
            for comp_filter in filter_copy.findall(".//" + xmlutils.make_clark("C:comp-filter")):
                if comp_filter.get("name", "").upper() == "VCALENDAR":
                    continue
                time_range_element = comp_filter.find(xmlutils.make_clark("C:time-range"))
                if time_range_element is not None:
                    comp_filter.remove(time_range_element)

        main_filters.append(filter_copy)

    # Retrieve everything required for finishing the request.
    retrieved_items = list(retrieve_items(
        base_prefix, path, collection, hreferences, main_filters, multistatus))
    collection_tag = collection.tag
    # !!! Don't access storage after this !!!
    unlock_storage_fn()

    n_vevents = 0
    while retrieved_items:
        # ``item.vobject_item`` might be accessed during filtering.
        # Don't keep reference to ``item``, because VObject requires a lot of
        # memory.
        item, filters_matched = retrieved_items.pop(0)
        if filters and not filters_matched:
            try:
                if not all(test_filter(collection_tag, item, filter_)
                           for filter_ in main_filters):
                    continue
            except ValueError as e:
                raise ValueError("Failed to filter item %r from %r: %s" %
                                 (item.href, collection.path, e)) from e
            except Exception as e:
                raise RuntimeError("Failed to filter item %r from %r: %s" %
                                   (item.href, collection.path, e)) from e

        found_props = []
        not_found_props = []

        for prop in props:
            element = ET.Element(prop.tag)
            if prop.tag == xmlutils.make_clark("D:getcontenttype"):
                element.text = xmlutils.get_content_type(item, encoding)
                found_props.append(element)
            elif prop.tag in (
                    xmlutils.make_clark("C:calendar-data"),
                    xmlutils.make_clark("D:getetag"),
                    xmlutils.make_clark("CR:address-data")):
                element.text = item.serialize()

                if (expand is not None) and item.component_name == 'VEVENT':
                    starts = expand.get('start')
                    ends = expand.get('end')

                    if (starts is None) or (ends is None):
                        return client.FORBIDDEN, \
                            xmlutils.webdav_error("C:expand")

                    start = datetime.datetime.strptime(
                        starts, DT_FORMAT_TIMESTAMP
                    ).replace(tzinfo=datetime.timezone.utc)
                    end = datetime.datetime.strptime(
                        ends, DT_FORMAT_TIMESTAMP
                    ).replace(tzinfo=datetime.timezone.utc)

                    time_range_start = None
                    time_range_end = None

                    if time_range_element is not None:
                        time_range_start, time_range_end = radicale_filter.parse_time_range(time_range_element)

                    (expanded_element, n_vev) = _expand(
                        element=element, item=copy.copy(item),
                        start=start, end=end,
                        time_range_start=time_range_start, time_range_end=time_range_end,
                        max_occurrence=max_occurrence,
                    )

                    if n_vev == 0:
                        logger.debug("No VEVENTs found after expansion for %r, skipping", item.href)
                        continue

                    n_vevents += n_vev
                    if prop.tag == xmlutils.make_clark("D:getetag"):
                        if n_vev > 0:
                            logger.debug("TRACE/REPORT/xml_report: getetag/expanded element")
                            element.text = item.etag
                            found_props.append(element)
                        else:
                            logger.debug("TRACE/REPORT/xml_report: getetag/no expanded element")
                    else:
                        logger.debug("TRACE/REPORT/xml_report: default")
                        found_props.append(expanded_element)
                else:
                    if prop.tag == xmlutils.make_clark("D:getetag"):
                        element.text = item.etag
                        found_props.append(element)
                    else:
                        found_props.append(element)
                        if hasattr(item.vobject_item, "vevent_list"):
                            n_vevents += len(item.vobject_item.vevent_list)
                # Avoid DoS with too many events
                if max_occurrence and n_vevents > max_occurrence:
                    raise ValueError("REPORT occurrences limit of {} hit"
                                     .format(max_occurrence))
            else:
                not_found_props.append(element)

        assert item.href
        uri = pathutils.unstrip_path(
            posixpath.join(collection.path, item.href))

        if found_props or not_found_props:
            multistatus.append(xml_item_response(
                base_prefix, uri, found_props=found_props,
                not_found_props=not_found_props, found_item=True))

    return client.MULTI_STATUS, multistatus


def _expand(
        element: ET.Element,
        item: radicale_item.Item,
        start: datetime.datetime,
        end: datetime.datetime,
        time_range_start: Optional[datetime.datetime] = None,
        time_range_end: Optional[datetime.datetime] = None,
        max_occurrence: int = 0,
) -> Tuple[ET.Element, int]:
    vevent_component: vobject.base.Component = copy.copy(item.vobject_item)
    logger.info("Expanding event %s", item.href)
    logger.debug(f"Expand range: {start} to {end}")
    logger.debug(f"Time range: {time_range_start} to {time_range_end}")

    # Split the vevents included in the component into one that contains the
    # recurrence information and others that contain a recurrence id to
    # override instances.
    base_vevent, vevents_overridden = _split_overridden_vevents(vevent_component)

    dt_format = DT_FORMAT_TIMESTAMP
    all_day_event = False

    if type(base_vevent.dtstart.value) is datetime.date:
        # If an event comes to us with a dtstart specified as a date
        # then in the response we return the date, not datetime
        dt_format = DT_FORMAT_DATE
        all_day_event = True
        # In case of dates, we need to remove timezone information since
        # rruleset.between computes with datetimes without timezone information
        start = start.replace(tzinfo=None)
        end = end.replace(tzinfo=None)
        if time_range_start is not None and time_range_end is not None:
            time_range_start = time_range_start.replace(tzinfo=None)
            time_range_end = time_range_end.replace(tzinfo=None)

    for vevent in vevents_overridden:
        _strip_single_event(vevent, dt_format)

    duration = None
    if hasattr(base_vevent, "dtend"):
        duration = base_vevent.dtend.value - base_vevent.dtstart.value
    elif hasattr(base_vevent, "duration"):
        try:
            duration = base_vevent.duration.value
            if duration.total_seconds() <= 0:
                logger.warning("Invalid DURATION: %s", duration)
                duration = None
        except (AttributeError, TypeError) as e:
            logger.warning("Failed to parse DURATION: %s", e)
            duration = None

    # Generate EXDATE to remove from expansion range
    exdates_set: set[datetime.datetime] = set()
    if hasattr(base_vevent, 'exdate'):
        exdates = base_vevent.exdate.value
        if not isinstance(exdates, list):
            exdates = [exdates]

        exdates_set = {
            exdate.astimezone(datetime.timezone.utc) if isinstance(exdate, datetime.datetime)
            else datetime.datetime.fromordinal(exdate.toordinal()).replace(tzinfo=None)
            for exdate in exdates
        }

        logger.debug("EXDATE values: %s", exdates_set)

    events_for_filtering = vevents_overridden

    rruleset = None
    if hasattr(base_vevent, 'rrule'):
        rruleset = base_vevent.getrruleset()
    else:
        # if event does not have rrule, only include base event
        events_for_filtering = [base_vevent]

    filtered_vevents = []
    if rruleset:
        # This function uses datetimes internally without timezone info for dates

        # A vobject rruleset is for the event dtstart.
        # Expanded over a given time range this will not include
        # events which started before the time range but are still
        # ongoing at the start of the range

        # To accomodate this, reduce the start time by the duration of
        # the event. If this introduces an extra reccurence point then
        # that event should be included as it is still ongoing. If no
        # extra point is generated then it was a no-op.
        rstart = start - duration if duration and duration.total_seconds() > 0 else start
        recurrences = rruleset.between(rstart, end, inc=True, count=max_occurrence)
        if max_occurrence and len(recurrences) >= max_occurrence:
            # this shouldn't be > and if it's == then assume a limit
            # was hit and ignore that maybe some would be filtered out
            # by EXDATE etc. This is anti-DoS, not precise limits
            raise ValueError("REPORT occurrences limit of {} hit"
                             .format(max_occurrence))

        _strip_component(vevent_component)
        _strip_single_event(base_vevent, dt_format)

        i_overridden = 0

        for recurrence_dt in recurrences:
            recurrence_utc = recurrence_dt if all_day_event else recurrence_dt.astimezone(datetime.timezone.utc)
            logger.debug("Processing recurrence: %s (all_day_event: %s)", recurrence_utc, all_day_event)

            # Apply time-range filter
            if time_range_start is not None and time_range_end is not None:
                dtstart = recurrence_utc
                dtend = dtstart + duration if duration else dtstart
                # Start includes the time, end does not
                if not (dtstart <= time_range_end and dtend > time_range_start):
                    logger.debug("Recurrence %s filtered out by time-range", recurrence_utc)
                    continue

            # Check exdate
            if recurrence_utc in exdates_set:
                logger.debug("Recurrence %s excluded by EXDATE", recurrence_utc)
                continue

            # Check for overridden instances
            i_overridden, vevent = _find_overridden(i_overridden, vevents_overridden, recurrence_utc, dt_format)

            if not vevent:
                # Create new instance from recurrence
                vevent = base_vevent.duplicate(base_vevent)

                # For all day events, the system timezone may influence the
                # results, so use recurrence_dt
                recurrence_id = recurrence_dt if all_day_event else recurrence_utc
                logger.debug("Creating new VEVENT with RECURRENCE-ID: %s", recurrence_id)

                vevent.recurrence_id = ContentLine(
                    name='RECURRENCE-ID',
                    value=recurrence_id, params={}
                )
                _convert_to_utc(vevent, 'recurrence_id', dt_format)
                suffix = ''
                if (dt_format == DT_FORMAT_DATE):
                    suffix = ';VALUE=DATE'
                else:
                    suffix = ''
                vevent.dtstart = ContentLine(
                    name='DTSTART' + suffix,
                    value=recurrence_id.strftime(dt_format), params={}
                )
                # if there is a DTEND, override it. Duration does not need changing
                if hasattr(vevent, "dtend"):
                    vevent.dtend = ContentLine(
                        name='DTEND' + suffix,
                        value=(recurrence_id + duration).strftime(dt_format), params={}
                    )

            filtered_vevents.append(vevent)

    # Filter overridden and non-recurring events
    if time_range_start is not None and time_range_end is not None:
        for vevent in events_for_filtering:
            dtstart = vevent.dtstart.value

            # Handle string values for DTSTART/DTEND
            if isinstance(dtstart, str):
                try:
                    dtstart = datetime.datetime.strptime(dtstart, dt_format)
                    if all_day_event:
                        dtstart = dtstart.date()
                except ValueError as e:
                    logger.warning("Invalid DTSTART format: %s, error: %s", dtstart, e)
                    continue

            dtend = dtstart + duration if duration else dtstart

            logger.debug(
                "Filtering VEVENT with DTSTART: %s (type: %s), DTEND: %s (type: %s)",
                dtstart, type(dtstart), dtend, type(dtend))

            # Convert to datetime for comparison
            if all_day_event and isinstance(dtstart, datetime.date) and not isinstance(dtstart, datetime.datetime):
                dtstart = datetime.datetime.fromordinal(dtstart.toordinal()).replace(tzinfo=None)
                dtend = datetime.datetime.fromordinal(dtend.toordinal()).replace(tzinfo=None)
            elif not all_day_event and isinstance(dtstart, datetime.datetime) \
                    and isinstance(dtend, datetime.datetime):
                dtstart = dtstart.replace(tzinfo=datetime.timezone.utc)
                dtend = dtend.replace(tzinfo=datetime.timezone.utc)
            else:
                logger.warning("Unexpected DTSTART/DTEND type: dtstart=%s, dtend=%s", type(dtstart), type(dtend))
                continue

            if dtstart < time_range_end and dtend > time_range_start:
                if vevent not in filtered_vevents:  # Avoid duplicates
                    logger.debug("VEVENT passed time-range filter: %s", dtstart)
                    filtered_vevents.append(vevent)
            else:
                logger.debug("VEVENT filtered out: %s", dtstart)

    # Rebuild component

    if not filtered_vevents:
        element.text = ""
        return element, 0
    else:
        vevent_component.vevent_list = filtered_vevents
        logger.debug("lbt: vevent_component %s", vevent_component)

    element.text = vevent_component.serialize()

    return element, len(filtered_vevents)


def _convert_timezone(vevent: vobject.icalendar.RecurringComponent,
                      name_prop: str,
                      name_content_line: str):
    prop = getattr(vevent, name_prop, None)
    if prop:
        if type(prop.value) is datetime.date:
            date_time = datetime.datetime.fromordinal(
                prop.value.toordinal()
            ).replace(tzinfo=datetime.timezone.utc)
        else:
            date_time = prop.value.astimezone(datetime.timezone.utc)

        setattr(vevent, name_prop, ContentLine(name=name_content_line, value=date_time, params=[]))


def _convert_to_utc(vevent: vobject.icalendar.RecurringComponent,
                    name_prop: str,
                    dt_format: str):
    prop = getattr(vevent, name_prop, None)
    if prop:
        setattr(vevent, name_prop, ContentLine(name=prop.name, value=prop.value.strftime(dt_format), params=[]))


def _strip_single_event(vevent: vobject.icalendar.RecurringComponent, dt_format: str) -> None:
    _convert_timezone(vevent, 'dtstart', 'DTSTART')
    _convert_timezone(vevent, 'dtend', 'DTEND')
    _convert_timezone(vevent, 'recurrence_id', 'RECURRENCE-ID')

    # There is something strange behaviour during serialization native datetime, so converting manually
    _convert_to_utc(vevent, 'dtstart', dt_format)
    _convert_to_utc(vevent, 'dtend', dt_format)
    _convert_to_utc(vevent, 'recurrence_id', dt_format)

    try:
        delattr(vevent, 'rrule')
        delattr(vevent, 'exdate')
        delattr(vevent, 'exrule')
        delattr(vevent, 'rdate')
    except AttributeError:
        pass


def _strip_component(vevent: vobject.base.Component) -> None:
    timezones_to_remove = []
    for component in vevent.components():
        if component.name == 'VTIMEZONE':
            timezones_to_remove.append(component)

    for timezone in timezones_to_remove:
        vevent.remove(timezone)


def _split_overridden_vevents(
        component: vobject.base.Component,
) -> Tuple[
    vobject.icalendar.RecurringComponent,
    List[vobject.icalendar.RecurringComponent]
]:
    vevent_recurrence = None
    vevents_overridden = []

    for vevent in component.vevent_list:
        if hasattr(vevent, 'recurrence_id'):
            vevents_overridden += [vevent]
        elif vevent_recurrence:
            raise ValueError(
                f"component with UID {vevent.uid} "
                f"has more than one vevent with recurrence information"
            )
        else:
            vevent_recurrence = vevent

    if vevent_recurrence:
        return (
            vevent_recurrence, sorted(
                vevents_overridden,
                key=lambda vevent: vevent.recurrence_id.value
            )
        )
    else:
        raise ValueError(
            f"component with UID {vevent.uid} "
            f"does not have a vevent without a recurrence_id"
        )


def _find_overridden(
        start: int,
        vevents: List[vobject.icalendar.RecurringComponent],
        dt: datetime.datetime,
        dt_format: str
) -> Tuple[int, Optional[vobject.icalendar.RecurringComponent]]:
    for i in range(start, len(vevents)):
        dt_event = datetime.datetime.strptime(
            vevents[i].recurrence_id.value,
            dt_format
        ).replace(tzinfo=datetime.timezone.utc)
        if dt_event == dt:
            return (i + 1, vevents[i])
    return (start, None)


def xml_item_response(base_prefix: str, href: str,
                      found_props: Sequence[ET.Element] = (),
                      not_found_props: Sequence[ET.Element] = (),
                      found_item: bool = True) -> ET.Element:
    response = ET.Element(xmlutils.make_clark("D:response"))

    href_element = ET.Element(xmlutils.make_clark("D:href"))
    href_element.text = xmlutils.make_href(base_prefix, href)
    response.append(href_element)

    if found_item:
        for code, props in ((200, found_props), (404, not_found_props)):
            if props:
                propstat = ET.Element(xmlutils.make_clark("D:propstat"))
                status = ET.Element(xmlutils.make_clark("D:status"))
                status.text = xmlutils.make_response(code)
                prop_element = ET.Element(xmlutils.make_clark("D:prop"))
                for prop in props:
                    prop_element.append(prop)
                propstat.append(prop_element)
                propstat.append(status)
                response.append(propstat)
    else:
        status = ET.Element(xmlutils.make_clark("D:status"))
        status.text = xmlutils.make_response(404)
        response.append(status)

    return response


def retrieve_items(
        base_prefix: str, path: str, collection: storage.BaseCollection,
        hreferences: Iterable[str], filters: Sequence[ET.Element],
        multistatus: ET.Element) -> Iterator[Tuple[radicale_item.Item, bool]]:
    """Retrieves all items that are referenced in ``hreferences`` from
       ``collection`` and adds 404 responses for missing and invalid items
       to ``multistatus``."""
    collection_requested = False

    def get_names() -> Iterator[str]:
        """Extracts all names from references in ``hreferences`` and adds
           404 responses for invalid references to ``multistatus``.
           If the whole collections is referenced ``collection_requested``
           gets set to ``True``."""
        nonlocal collection_requested
        for hreference in hreferences:
            try:
                name = pathutils.name_from_path(hreference, collection)
            except ValueError as e:
                logger.warning("Skipping invalid path %r in REPORT request on "
                               "%r: %s", hreference, path, e)
                response = xml_item_response(base_prefix, hreference,
                                             found_item=False)
                multistatus.append(response)
                continue
            if name:
                # Reference is an item
                yield name
            else:
                # Reference is a collection
                collection_requested = True

    for name, item in collection.get_multi(get_names()):
        if not item:
            uri = pathutils.unstrip_path(posixpath.join(collection.path, name))
            response = xml_item_response(base_prefix, uri, found_item=False)
            multistatus.append(response)
        else:
            yield item, False
    if collection_requested:
        logger.debug("TRACE/REPORT/retrieve_items: get_filtered")
        yield from collection.get_filtered(filters)


def test_filter(collection_tag: str, item: radicale_item.Item,
                filter_: ET.Element) -> bool:
    """Match an item against a filter."""
    if (collection_tag == "VCALENDAR" and
            filter_.tag != xmlutils.make_clark("C:%s" % filter_)):
        if len(filter_) == 0:
            return True
        if len(filter_) > 1:
            raise ValueError("Filter with %d children" % len(filter_))
        if filter_[0].tag != xmlutils.make_clark("C:comp-filter"):
            raise ValueError("Unexpected %r in filter" % filter_[0].tag)
        return radicale_filter.comp_match(item, filter_[0])
    if (collection_tag == "VADDRESSBOOK" and
            filter_.tag != xmlutils.make_clark("CR:%s" % filter_)):
        for child in filter_:
            if child.tag != xmlutils.make_clark("CR:prop-filter"):
                raise ValueError("Unexpected %r in filter" % child.tag)
        test = filter_.get("test", "anyof")
        if test == "anyof":
            return any(radicale_filter.prop_match(item.vobject_item, f, "CR")
                       for f in filter_)
        if test == "allof":
            return all(radicale_filter.prop_match(item.vobject_item, f, "CR")
                       for f in filter_)
        raise ValueError("Unsupported filter test: %r" % test)
    raise ValueError("Unsupported filter %r for %r" %
                     (filter_.tag, collection_tag))


class ApplicationPartReport(ApplicationBase):

    def do_REPORT(self, environ: types.WSGIEnviron, base_prefix: str,
                  path: str, user: str, remote_host: str, remote_useragent: str) -> types.WSGIResponse:
        """Manage REPORT request."""
        access = Access(self._rights, user, path)
        if not access.check("r"):
            return httputils.NOT_ALLOWED
        try:
            xml_content = self._read_xml_request_body(environ)
        except RuntimeError as e:
            logger.warning("Bad REPORT request on %r: %s", path, e,
                           exc_info=True)
            return httputils.BAD_REQUEST
        except socket.timeout:
            logger.debug("Client timed out", exc_info=True)
            return httputils.REQUEST_TIMEOUT
        with contextlib.ExitStack() as lock_stack:
            lock_stack.enter_context(self._storage.acquire_lock("r", user))
            item = next(iter(self._storage.discover(path)), None)
            if not item:
                return httputils.NOT_FOUND
            if not access.check("r", item):
                return httputils.NOT_ALLOWED
            if isinstance(item, storage.BaseCollection):
                collection = item
            else:
                assert item.collection is not None
                collection = item.collection

            max_occurrence = self.configuration.get("reporting", "max_freebusy_occurrence")
            if xml_content is not None and \
               xml_content.tag == xmlutils.make_clark("C:free-busy-query"):
                try:
                    status, body = free_busy_report(
                        base_prefix, path, xml_content, collection, self._encoding,
                        lock_stack.close, max_occurrence)
                except ValueError as e:
                    logger.warning(
                        "Bad REPORT request on %r: %s", path, e, exc_info=True)
                    return httputils.BAD_REQUEST
                headers = {"Content-Type": "text/calendar; charset=%s" % self._encoding}
                return status, headers, str(body)
            else:
                try:
                    status, xml_answer = xml_report(
                        base_prefix, path, xml_content, collection, self._encoding,
                        lock_stack.close, max_occurrence, user, remote_host, remote_useragent)
                except ValueError as e:
                    logger.warning(
                        "Bad REPORT request on %r: %s", path, e, exc_info=True)
                    return httputils.BAD_REQUEST
                headers = {"Content-Type": "text/xml; charset=%s" % self._encoding}
                return status, headers, self._xml_response(xml_answer)
