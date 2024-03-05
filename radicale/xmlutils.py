# This file is part of Radicale - CalDAV and CardDAV server
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
Helper functions for XML.

"""

import copy
import xml.etree.ElementTree as ET
from collections import OrderedDict
from http import client
from typing import Dict, Mapping, Optional
from urllib.parse import quote

from radicale import item, pathutils

MIMETYPES: Mapping[str, str] = {
    "VADDRESSBOOK": "text/vcard",
    "VCALENDAR": "text/calendar",
    "VSUBSCRIBED": "text/calendar"}

OBJECT_MIMETYPES: Mapping[str, str] = {
    "VCARD": "text/vcard",
    "VLIST": "text/x-vlist",
    "VCALENDAR": "text/calendar"}

NAMESPACES: Mapping[str, str] = {
    "C": "urn:ietf:params:xml:ns:caldav",
    "CR": "urn:ietf:params:xml:ns:carddav",
    "D": "DAV:",
    "CS": "http://calendarserver.org/ns/",
    "ICAL": "http://apple.com/ns/ical/",
    "ME": "http://me.com/_namespace/",
    "RADICALE": "http://radicale.org/ns/"}

NAMESPACES_REV: Mapping[str, str] = {v: k for k, v in NAMESPACES.items()}

for short, url in NAMESPACES.items():
    ET.register_namespace("" if short == "D" else short, url)


def pretty_xml(element: ET.Element) -> str:
    """Indent an ElementTree ``element`` and its children."""
    def pretty_xml_recursive(element: ET.Element, level: int) -> None:
        indent = "\n" + level * "  "
        if len(element) > 0:
            if not (element.text or "").strip():
                element.text = indent + "  "
            if not (element.tail or "").strip():
                element.tail = indent
            for sub_element in element:
                pretty_xml_recursive(sub_element, level + 1)
            if not (sub_element.tail or "").strip():
                sub_element.tail = indent
        elif level > 0 and not (element.tail or "").strip():
            element.tail = indent
    element = copy.deepcopy(element)
    pretty_xml_recursive(element, 0)
    return '<?xml version="1.0"?>\n%s' % ET.tostring(element, "unicode")


def make_clark(human_tag: str) -> str:
    """Get XML Clark notation from human tag ``human_tag``.

    If ``human_tag`` is already in XML Clark notation it is returned as-is.

    """
    if human_tag.startswith("{"):
        ns, tag = human_tag[len("{"):].split("}", maxsplit=1)
        if not ns or not tag:
            raise ValueError("Invalid XML tag: %r" % human_tag)
        return human_tag
    ns_prefix, tag = human_tag.split(":", maxsplit=1)
    if not ns_prefix or not tag:
        raise ValueError("Invalid XML tag: %r" % human_tag)
    ns = NAMESPACES.get(ns_prefix, "")
    if not ns:
        raise ValueError("Unknown XML namespace prefix: %r" % human_tag)
    return "{%s}%s" % (ns, tag)


def make_human_tag(clark_tag: str) -> str:
    """Replace known namespaces in XML Clark notation ``clark_tag`` with
       prefix.

    If the namespace is not in ``NAMESPACES`` the tag is returned as-is.

    """
    if not clark_tag.startswith("{"):
        ns_prefix, tag = clark_tag.split(":", maxsplit=1)
        if not ns_prefix or not tag:
            raise ValueError("Invalid XML tag: %r" % clark_tag)
        if ns_prefix not in NAMESPACES:
            raise ValueError("Unknown XML namespace prefix: %r" % clark_tag)
        return clark_tag
    ns, tag = clark_tag[len("{"):].split("}", maxsplit=1)
    if not ns or not tag:
        raise ValueError("Invalid XML tag: %r" % clark_tag)
    ns_prefix = NAMESPACES_REV.get(ns, "")
    if ns_prefix:
        return "%s:%s" % (ns_prefix, tag)
    return clark_tag


def make_response(code: int) -> str:
    """Return full W3C names from HTTP status codes."""
    return "HTTP/1.1 %i %s" % (code, client.responses[code])


def make_href(base_prefix: str, href: str) -> str:
    """Return prefixed href."""
    assert href == pathutils.sanitize_path(href)
    return quote("%s%s" % (base_prefix, href))


def webdav_error(human_tag: str) -> ET.Element:
    """Generate XML error message."""
    root = ET.Element(make_clark("D:error"))
    root.append(ET.Element(make_clark(human_tag)))
    return root


def get_content_type(item: "item.Item", encoding: str) -> str:
    """Get the content-type of an item with charset and component parameters.
    """
    mimetype = OBJECT_MIMETYPES[item.name]
    tag = item.component_name
    content_type = "%s;charset=%s" % (mimetype, encoding)
    if tag:
        content_type += ";component=%s" % tag
    return content_type


def props_from_request(xml_request: Optional[ET.Element]
                       ) -> Dict[str, Optional[str]]:
    """Return a list of properties as a dictionary.

    Properties that should be removed are set to `None`.

    """
    result: OrderedDict = OrderedDict()
    if xml_request is None:
        return result

    # Requests can contain multipe <D:set> and <D:remove> elements.
    # Each of these elements must contain exactly one <D:prop> element which
    # can contain multpile properties.
    # The order of the elements in the document must be respected.
    props = []
    for element in xml_request:
        if element.tag in (make_clark("D:set"), make_clark("D:remove")):
            for prop in element.findall("./%s/*" % make_clark("D:prop")):
                props.append((element.tag == make_clark("D:set"), prop))
    for is_set, prop in props:
        key = make_human_tag(prop.tag)
        value = None
        if prop.tag == make_clark("D:resourcetype"):
            key = "tag"
            if is_set:
                for resource_type in prop:
                    if resource_type.tag == make_clark("C:calendar"):
                        value = "VCALENDAR"
                        break
                    if resource_type.tag == make_clark("CS:subscribed"):
                        value = "VSUBSCRIBED"
                        break
                    if resource_type.tag == make_clark("CR:addressbook"):
                        value = "VADDRESSBOOK"
                        break
        elif prop.tag == make_clark("C:supported-calendar-component-set"):
            if is_set:
                value = ",".join(
                    supported_comp.attrib["name"] for supported_comp in prop
                    if supported_comp.tag == make_clark("C:comp"))
        elif is_set:
            value = prop.text or ""
        result[key] = value
        result.move_to_end(key)

    return result
