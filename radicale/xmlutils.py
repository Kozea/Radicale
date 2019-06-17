# This file is part of Radicale Server - Calendar Server
# Copyright © 2008 Nicolas Kandel
# Copyright © 2008 Pascal Halter
# Copyright © 2008-2015 Guillaume Ayoub
# Copyright © 2017-2018 Unrud <unrud@outlook.com>
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
import re
import xml.etree.ElementTree as ET
from collections import OrderedDict
from http import client
from urllib.parse import quote

from radicale import pathutils

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


def make_tag(short_name, local):
    """Get XML Clark notation {uri(``short_name``)}``local``."""
    return "{%s}%s" % (NAMESPACES[short_name], local)


def tag_from_clark(name):
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


def tag_from_human(name):
    """Get an XML Clark notation tag from human-readable variant ``name``."""
    match = HUMAN_REGEX.match(name)
    if match and match.group("namespace") in NAMESPACES:
        return make_tag(match.group("namespace"), match.group("tag"))
    return name


def make_response(code):
    """Return full W3C names from HTTP status codes."""
    return "HTTP/1.1 %i %s" % (code, client.responses[code])


def make_href(base_prefix, href):
    """Return prefixed href."""
    assert href == pathutils.sanitize_path(href)
    return quote("%s%s" % (base_prefix, href))


def webdav_error(namespace, name):
    """Generate XML error message."""
    root = ET.Element(make_tag("D", "error"))
    root.append(ET.Element(make_tag(namespace, name)))
    return root


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


def props_from_request(xml_request, actions=("set", "remove")):
    """Return a list of properties as a dictionary."""
    result = OrderedDict()
    if xml_request is None:
        return result

    for action in actions:
        action_element = xml_request.find(make_tag("D", action))
        if action_element is not None:
            break
    else:
        action_element = xml_request

    prop_element = action_element.find(make_tag("D", "prop"))
    if prop_element is not None:
        for prop in prop_element:
            if prop.tag == make_tag("D", "resourcetype"):
                for resource_type in prop:
                    if resource_type.tag == make_tag("C", "calendar"):
                        result["tag"] = "VCALENDAR"
                        break
                    elif resource_type.tag == make_tag("CR", "addressbook"):
                        result["tag"] = "VADDRESSBOOK"
                        break
            elif prop.tag == make_tag("C", "supported-calendar-component-set"):
                result[tag_from_clark(prop.tag)] = ",".join(
                    supported_comp.attrib["name"]
                    for supported_comp in prop
                    if supported_comp.tag == make_tag("C", "comp"))
            else:
                result[tag_from_clark(prop.tag)] = prop.text

    return result
