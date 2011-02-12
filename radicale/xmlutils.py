# -*- coding: utf-8 -*-
#
# This file is part of Radicale Server - Calendar Server
# Copyright © 2008-2011 Guillaume Ayoub
# Copyright © 2008 Nicolas Kandel
# Copyright © 2008 Pascal Halter
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

import xml.etree.ElementTree as ET

from radicale import client, config, ical


NAMESPACES = {
    "C": "urn:ietf:params:xml:ns:caldav",
    "D": "DAV:",
    "CS": "http://calendarserver.org/ns/"}


def _tag(short_name, local):
    """Get XML Clark notation {uri(``short_name``)}``local``."""
    return "{%s}%s" % (NAMESPACES[short_name], local)


def _response(code):
    """Return full W3C names from HTTP status codes."""
    return "HTTP/1.1 %i %s" % (code, client.responses[code])


def name_from_path(path):
    """Return Radicale item name from ``path``."""
    path_parts = path.strip("/").split("/")
    return path_parts[-1] if len(path_parts) > 2 else None


def delete(path, calendar):
    """Read and answer DELETE requests.

    Read rfc4918-9.6 for info.

    """
    # Reading request
    calendar.remove(name_from_path(path))

    # Writing answer
    multistatus = ET.Element(_tag("D", "multistatus"))
    response = ET.Element(_tag("D", "response"))
    multistatus.append(response)

    href = ET.Element(_tag("D", "href"))
    href.text = path
    response.append(href)

    status = ET.Element(_tag("D", "status"))
    status.text = _response(200)
    response.append(status)

    return ET.tostring(multistatus, config.get("encoding", "request"))


def propfind(path, xml_request, calendar, depth):
    """Read and answer PROPFIND requests.

    Read rfc4918-9.1 for info.

    """
    # Reading request
    root = ET.fromstring(xml_request)

    prop_element = root.find(_tag("D", "prop"))
    prop_list = prop_element.getchildren()
    props = [prop.tag for prop in prop_list]
    
    # Writing answer
    multistatus = ET.Element(_tag("D", "multistatus"))

    if calendar:
        if depth == "0":
            items = [calendar]
        else:
            # depth is 1, infinity or not specified
            # we limit ourselves to depth == 1
            items = [calendar] + calendar.events + calendar.todos
    else:
        items = []

    for item in items:
        is_calendar = isinstance(item, ical.Calendar)

        response = ET.Element(_tag("D", "response"))
        multistatus.append(response)

        href = ET.Element(_tag("D", "href"))
        href.text = path if is_calendar else path + item.name
        response.append(href)

        propstat = ET.Element(_tag("D", "propstat"))
        response.append(propstat)

        prop = ET.Element(_tag("D", "prop"))
        propstat.append(prop)

        for tag in props:
            element = ET.Element(tag)
            if tag == _tag("D", "resourcetype") and is_calendar:
                tag = ET.Element(_tag("C", "calendar"))
                element.append(tag)
                tag = ET.Element(_tag("D", "collection"))
                element.append(tag)
            elif tag == _tag("D", "owner"):
                element.text = calendar.owner
            elif tag == _tag("D", "getcontenttype"):
                element.text = "text/calendar"
            elif tag == _tag("CS", "getctag") and is_calendar:
                element.text = item.etag
            elif tag == _tag("D", "getetag"):
                element.text = item.etag
            elif tag == _tag("D", "displayname") and is_calendar:
                element.text = calendar.name
            elif tag == _tag("D", "principal-URL"):
                # TODO: use a real principal URL, read rfc3744-4.2 for info
                tag = ET.Element(_tag("D", "href"))
                tag.text = path
                element.append(tag)
            elif tag in (
                _tag("D", "principal-collection-set"),
                _tag("C", "calendar-user-address-set"),
                _tag("C", "calendar-home-set")):
                tag = ET.Element(_tag("D", "href"))
                tag.text = path
                element.append(tag)
            elif tag == _tag("C", "supported-calendar-component-set"):
                comp = ET.Element(_tag("C", "comp"))
                comp.set("name", "VTODO") # pylint: disable=W0511
                element.append(comp)
                comp = ET.Element(_tag("C", "comp"))
                comp.set("name", "VEVENT")
                element.append(comp)
            elif tag == _tag("D", "current-user-privilege-set"):
                privilege = ET.Element(_tag("D", "privilege"))
                privilege.append(ET.Element(_tag("D", "all")))
                element.append(privilege)
            prop.append(element)

        status = ET.Element(_tag("D", "status"))
        status.text = _response(200)
        propstat.append(status)

    return ET.tostring(multistatus, config.get("encoding", "request"))


def put(path, ical_request, calendar):
    """Read PUT requests."""
    name = name_from_path(path)
    if name in (item.name for item in calendar.items):
        # PUT is modifying an existing item
        calendar.replace(name, ical_request)
    else:
        # PUT is adding a new item
        calendar.append(name, ical_request)


def report(path, xml_request, calendar):
    """Read and answer REPORT requests.

    Read rfc3253-3.6 for info.

    """
    # Reading request
    root = ET.fromstring(xml_request)

    prop_element = root.find(_tag("D", "prop"))
    prop_list = prop_element.getchildren()
    props = [prop.tag for prop in prop_list]

    if calendar:
        if root.tag == _tag("C", "calendar-multiget"):
            # Read rfc4791-7.9 for info
            hreferences = set((href_element.text for href_element
                               in root.findall(_tag("D", "href"))))
        else:
            hreferences = (path,)
    else:
        hreferences = ()

    # Writing answer
    multistatus = ET.Element(_tag("D", "multistatus"))

    for hreference in hreferences:
        # Check if the reference is an item or a calendar
        name = name_from_path(hreference)
        if name:
            # Reference is an item
            path = "/".join(hreference.split("/")[:-1]) + "/"
            items = (item for item in calendar.items if item.name == name)
        else:
            # Reference is a calendar
            path = hreference
            items = calendar.events + calendar.todos

        for item in items:
            response = ET.Element(_tag("D", "response"))
            multistatus.append(response)

            href = ET.Element(_tag("D", "href"))
            href.text = path + item.name
            response.append(href)

            propstat = ET.Element(_tag("D", "propstat"))
            response.append(propstat)

            prop = ET.Element(_tag("D", "prop"))
            propstat.append(prop)

            for tag in props:
                element = ET.Element(tag)
                if tag == _tag("D", "getetag"):
                    element.text = item.etag
                elif tag == _tag("C", "calendar-data"):
                    if isinstance(item, (ical.Event, ical.Todo)):
                        element.text = ical.serialize(
                            calendar.headers, calendar.timezones + [item])
                prop.append(element)

            status = ET.Element(_tag("D", "status"))
            status.text = _response(200)
            propstat.append(status)

    return ET.tostring(multistatus, config.get("encoding", "request"))
