# -*- coding: utf-8; indent-tabs-mode: nil; -*-
#
# This file is part of Radicale Server - Calendar Server
# Copyright © 2008-2009 Guillaume Ayoub
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

# TODO: Manage errors (see __init__)
# TODO: Manage depth and calendars/collections (see main)

import xml.etree.ElementTree as ET

import config
import ical

# TODO: This is a well-known and accepted hack for ET to avoid ET from renaming
#       namespaces, which is accepted in XML norm but often not in XML
#       readers. Is there another clean solution to force namespaces?
for key,value in config.items("namespace"):
    ET._namespace_map[value] = key

def _tag(short_name, local):
    """Get XML Clark notation {uri(``short_name``)}``local``."""
    return "{%s}%s"%(config.get("namespace", short_name), local)

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
    status.text = config.get("status", "200")
    response.append(status)

    return ET.tostring(multistatus, config.get("encoding", "request"))

def propfind(xml_request, calendar, url):
    """Read and answer PROPFIND requests.

    Read rfc4918-9.1 for info.
    """
    # Reading request
    root = ET.fromstring(xml_request)

    propElement = root.find(_tag("D", "prop"))
    propList = propElement.getchildren()
    properties = [property.tag for property in propList]
    
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

    if _tag("D", "resourcetype") in properties:
        resourcetype = ET.Element(_tag("D", "resourcetype"))
        resourcetype.append(ET.Element(_tag("D", "collection")))
        resourcetype.append(ET.Element(_tag("C", "calendar")))
        prop.append(resourcetype)

    if _tag("D", "owner") in properties:
        owner = ET.Element(_tag("D", "owner"))
        owner.text = calendar.owner
        prop.append(owner)

    if _tag("D", "getcontenttype") in properties:
        getcontenttype = ET.Element(_tag("D", "getcontenttype"))
        getcontenttype.text = "text/calendar"
        prop.append(getcontenttype)

    if _tag("D", "getetag") in properties:
        getetag = ET.Element(_tag("D", "getetag"))
        getetag.text = calendar.etag()
        prop.append(getetag)

    if _tag("CS", "getctag") in properties:
        getctag = ET.Element(_tag("CS", "getctag"))
        getctag.text = calendar.ctag
        prop.append(getctag)

    status = ET.Element(_tag("D", "status"))
    status.text = config.get("status", "200")
    propstat.append(status)

    return ET.tostring(multistatus, config.get("encoding", "request"))

def put(icalRequest, calendar, url, obj):
    """Read PUT requests."""
    if obj:
        # PUT is modifying obj
        calendar.replace(obj, icalRequest)
    else:
        # PUT is adding a new object
        calendar.append(icalRequest)

def report(xml_request, calendar, url):
    """Read and answer REPORT requests.

    Read rfc3253-3.6 for info.
    """
    # Reading request
    root = ET.fromstring(xml_request)

    propElement = root.find(_tag("D", "prop"))
    propList = propElement.getchildren()
    properties = [property.tag for property in propList]

    filters = {}
    filterElement = root.find(_tag("C", "filter"))
    filterList = propElement.getchildren()
    # TODO: This should be recursive
    # TODO: Really manage filters (see ical)
    for filter in filterList:
        sub = filters[filter.get("name")] = {}
        for subfilter in filter.getchildren():
            sub[subfilter.get("name")] = {}

    if root.tag == _tag("C", "calendar-multiget"):
        # Read rfc4791-7.9 for info
        hreferences = set([hrefElement.text for hrefElement in root.findall(_tag("D", "href"))])
    else:
        hreferences = [url]

    # Writing answer
    multistatus = ET.Element(_tag("D", "multistatus"))

    # TODO: WTF, sunbird needs one response by object,
    #       is that really what is needed?
    #       Read rfc4791-9.[6|10] for info
    for hreference in hreferences:
        headers = ical.headers(calendar.vcalendar())
        # TODO: Define timezones by obj
        timezones = ical.timezones(calendar.vcalendar())

        objects = []
        objects.extend(ical.events(calendar.vcalendar()))
        objects.extend(ical.todos(calendar.vcalendar()))

        if not objects:
            # TODO: Read rfc4791-9.[6|10] to find a right answer
            response = ET.Element(_tag("D", "response"))
            multistatus.append(response)

            href = ET.Element(_tag("D", "href"))
            href.text = url
            response.append(href)

            status = ET.Element(_tag("D", "status"))
            status.text = config.get("status", "204")
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

            if _tag("D", "getetag") in properties:
                # TODO: Can UID and ETAG be the same?
                getetag = ET.Element(_tag("D", "getetag"))
                getetag.text = obj.etag()
                prop.append(getetag)

            if _tag("C", "calendar-data") in properties:
                cdata = ET.Element(_tag("C", "calendar-data"))
                # TODO: Maybe assume that events and todos are not the same
                cdata.text = ical.write_calendar(headers, timezones, [obj])
                prop.append(cdata)

            status = ET.Element(_tag("D", "status"))
            status.text = config.get("status", "200")
            propstat.append(status)

    return ET.tostring(multistatus, config.get("encoding", "request"))
