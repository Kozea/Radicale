# -*- coding: utf-8 -*-
#
# This file is part of Radicale Server - Calendar Server
# Copyright © 2008-2010 Guillaume Ayoub
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

# TODO: Manage depth and calendars/collections

import xml.etree.ElementTree as ET

from radicale import client, config, ical


# TODO: This is a well-known and accepted hack for ET to avoid ET from renaming
#       namespaces, which is accepted in XML norm but often not in XML
#       readers. Is there another clean solution to force namespaces?
PROTECTED_NAMESPACES = {
    "C": "urn:ietf:params:xml:ns:caldav",
    "D": "DAV:",
    "CS": "http://calendarserver.org/ns/"}
for key, value in PROTECTED_NAMESPACES.items():
    ET._namespace_map[value] = key


def _tag(short_name, local):
    """Get XML Clark notation {uri(``short_name``)}``local``."""
    return "{%s}%s" % (PROTECTED_NAMESPACES[short_name], local)


def _response(code):
    """Return full W3C names from HTTP status codes."""
    return "HTTP/1.1 %i %s" % (code, client.responses[code])


def delete(obj, calendar, url):
    """Read and answer DELETE requests.

    Read rfc4918-9.6 for info.

    """
    # Reading request
    calendar.remove(obj)

    # Writing answer
    multistatus = ET.Element(_tag("D", "multistatus"))
    response = ET.Element(_tag("D", "response"))
    multistatus.append(response)

    href = ET.Element(_tag("D", "href"))
    href.text = url
    response.append(href)

    status = ET.Element(_tag("D", "status"))
    status.text = _response(200)
    response.append(status)

    return ET.tostring(multistatus, config.get("encoding", "request"))

def propfind(xml_request, calendar, url):
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
    response = ET.Element(_tag("D", "response"))
    multistatus.append(response)

    href = ET.Element(_tag("D", "href"))
    href.text = url
    response.append(href)

    propstat = ET.Element(_tag("D", "propstat"))
    response.append(propstat)

    prop = ET.Element(_tag("D", "prop"))
    propstat.append(prop)

    if _tag("D", "resourcetype") in props:
        element = ET.Element(_tag("D", "resourcetype"))
        element.append(ET.Element(_tag("C", "calendar")))
        prop.append(element)

    if _tag("D", "owner") in props:
        element = ET.Element(_tag("D", "owner"))
        element.text = calendar.owner
        prop.append(element)

    if _tag("D", "getcontenttype") in props:
        element = ET.Element(_tag("D", "getcontenttype"))
        element.text = "text/calendar"
        prop.append(element)

    if _tag("D", "getetag") in props:
        element = ET.Element(_tag("D", "getetag"))
        element.text = calendar.etag
        prop.append(element)

    if _tag("CS", "getctag") in props:
        element = ET.Element(_tag("CS", "getctag"))
        element.text = calendar.ctag
        prop.append(element)

    status = ET.Element(_tag("D", "status"))
    status.text = _response(200)
    propstat.append(status)

    return ET.tostring(multistatus, config.get("encoding", "request"))

def put(ical_request, calendar, url, obj):
    """Read PUT requests."""
    # TODO: use url to set hreference
    if obj:
        # PUT is modifying obj
        calendar.replace(obj, ical_request)
    else:
        # PUT is adding a new object
        calendar.append(ical_request)

def report(xml_request, calendar, url):
    """Read and answer REPORT requests.

    Read rfc3253-3.6 for info.

    """
    # Reading request
    root = ET.fromstring(xml_request)

    prop_element = root.find(_tag("D", "prop"))
    prop_list = prop_element.getchildren()
    props = [prop.tag for prop in prop_list]

    if root.tag == _tag("C", "calendar-multiget"):
        # Read rfc4791-7.9 for info
        hreferences = set([href_element.text for href_element
                           in root.findall(_tag("D", "href"))])
    else:
        hreferences = [url]

    # Writing answer
    multistatus = ET.Element(_tag("D", "multistatus"))

    # TODO: WTF, sunbird needs one response by object,
    #       is that really what is needed?
    #       Read rfc4791-9.[6|10] for info
    for hreference in hreferences:
        headers = ical.headers(calendar.text)
        timezones = ical.timezones(calendar.text)

        objects = ical.events(calendar.text) + ical.todos(calendar.text)

        if not objects:
            # TODO: Read rfc4791-9.[6|10] to find a right answer
            response = ET.Element(_tag("D", "response"))
            multistatus.append(response)

            href = ET.Element(_tag("D", "href"))
            href.text = url
            response.append(href)

            status = ET.Element(_tag("D", "status"))
            status.text = _response(204)
            response.append(status)

        for obj in objects:
            # TODO: Use the hreference to read data and create href.text
            #       We assume here that hreference is url
            response = ET.Element(_tag("D", "response"))
            multistatus.append(response)

            href = ET.Element(_tag("D", "href"))
            href.text = url
            response.append(href)

            propstat = ET.Element(_tag("D", "propstat"))
            response.append(propstat)

            prop = ET.Element(_tag("D", "prop"))
            propstat.append(prop)

            if _tag("D", "getetag") in props:
                element = ET.Element(_tag("D", "getetag"))
                element.text = obj.etag
                prop.append(element)

            if _tag("C", "calendar-data") in props:
                element = ET.Element(_tag("C", "calendar-data"))
                # TODO: Maybe assume that events and todos are not the same
                element.text = ical.write_calendar(headers, timezones, [obj])
                prop.append(element)

            status = ET.Element(_tag("D", "status"))
            status.text = _response(200)
            propstat.append(status)

    return ET.tostring(multistatus, config.get("encoding", "request"))
