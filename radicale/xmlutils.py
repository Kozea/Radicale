# -*- coding: utf-8 -*-
#
# This file is part of Radicale Server - Calendar Server
# Copyright © 2008 Nicolas Kandel
# Copyright © 2008 Pascal Halter
# Copyright © 2008-2013 Guillaume Ayoub
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

try:
    from collections import OrderedDict
except ImportError:
    # Python 2.6 has no OrderedDict, use a dict instead
    OrderedDict = dict  # pylint: disable=C0103

# Manage Python2/3 different modules
# pylint: disable=F0401,E0611
try:
    from urllib.parse import unquote
except ImportError:
    from urllib import unquote
# pylint: enable=F0401,E0611

import re
import xml.etree.ElementTree as ET

from . import client, config, ical


NAMESPACES = {
    "A": "http://apple.com/ns/ical/",
    "C": "urn:ietf:params:xml:ns:caldav",
    "CR": "urn:ietf:params:xml:ns:carddav",
    "D": "DAV:",
    "CS": "http://calendarserver.org/ns/",
    "ICAL": "http://apple.com/ns/ical/",
    "ME": "http://me.com/_namespace/"}


NAMESPACES_REV = {}


for short, url in NAMESPACES.items():
    NAMESPACES_REV[url] = short
    if hasattr(ET, "register_namespace"):
        # Register namespaces cleanly with Python 2.7+ and 3.2+ ...
        ET.register_namespace("" if short == "D" else short, url)
    else:
        # ... and badly with Python 2.6 and 3.1
        ET._namespace_map[url] = short  # pylint: disable=W0212


CLARK_TAG_REGEX = re.compile(r"""
    {                        # {
    (?P<namespace>[^}]*)     # namespace URL
    }                        # }
    (?P<tag>.*)              # short tag name
    """, re.VERBOSE)


def _pretty_xml(element, level=0):
    """Indent an ElementTree ``element`` and its children."""
    i = "\n" + level * "  "
    if len(element):
        if not element.text or not element.text.strip():
            element.text = i + "  "
        if not element.tail or not element.tail.strip():
            element.tail = i
        for sub_element in element:
            _pretty_xml(sub_element, level + 1)
        # ``sub_element`` is always defined as len(element) > 0
        # pylint: disable=W0631
        if not sub_element.tail or not sub_element.tail.strip():
            sub_element.tail = i
        # pylint: enable=W0631
    else:
        if level and (not element.tail or not element.tail.strip()):
            element.tail = i
    if not level:
        output_encoding = config.get("encoding", "request")
        return ('<?xml version="1.0"?>\n' + ET.tostring(
            element, "utf-8").decode("utf-8")).encode(output_encoding)


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


def _response(code):
    """Return full W3C names from HTTP status codes."""
    return "HTTP/1.1 %i %s" % (code, client.responses[code])


def _href(href):
    """Return prefixed href."""
    return "%s%s" % (config.get("server", "base_prefix"), href.lstrip("/"))


def name_from_path(path, collection):
    """Return Radicale item name from ``path``."""
    collection_parts = collection.path.strip("/").split("/")
    path_parts = path.strip("/").split("/")
    if (len(path_parts) - len(collection_parts)):
        return path_parts[-1]


def props_from_request(root, actions=("set", "remove")):
    """Return a list of properties as a dictionary."""
    result = OrderedDict()
    if not hasattr(root, "tag"):
        root = ET.fromstring(root.encode("utf8"))

    for action in actions:
        action_element = root.find(_tag("D", action))
        if action_element is not None:
            break
    else:
        action_element = root

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


def delete(path, collection):
    """Read and answer DELETE requests.

    Read rfc4918-9.6 for info.

    """
    # Reading request
    if collection.path == path.strip("/"):
        # Delete the whole collection
        collection.delete()
    else:
        # Remove an item from the collection
        collection.remove(name_from_path(path, collection))

    # Writing answer
    multistatus = ET.Element(_tag("D", "multistatus"))
    response = ET.Element(_tag("D", "response"))
    multistatus.append(response)

    href = ET.Element(_tag("D", "href"))
    href.text = _href(path)
    response.append(href)

    status = ET.Element(_tag("D", "status"))
    status.text = _response(200)
    response.append(status)

    return _pretty_xml(multistatus)


def propfind(path, xml_request, collections, user=None):
    """Read and answer PROPFIND requests.

    Read rfc4918-9.1 for info.

    The collections parameter is a list of collections that are
    to be included in the output. Rights checking has to be done
    by the caller.

    """
    # Reading request
    if xml_request:
        root = ET.fromstring(xml_request.encode("utf8"))
        props = [prop.tag for prop in root.find(_tag("D", "prop"))]
    else:
        props = [_tag("D", "getcontenttype"),
                 _tag("D", "resourcetype"),
                 _tag("D", "displayname"),
                 _tag("D", "owner"),
                 _tag("D", "getetag"),
                 _tag("D", "current-user-principal"),
                 _tag("A", "calendar-color"),
                 _tag("CS", "getctag")]

    # Writing answer
    multistatus = ET.Element(_tag("D", "multistatus"))

    if collections:
        for collection in collections:
            response = _propfind_response(path, collection, props, user)
            multistatus.append(response)
    else:
        response = _propfind_response(path, None, props, user)
        multistatus.append(response)

    return _pretty_xml(multistatus)


def _propfind_response(path, item, props, user):
    """Build and return a PROPFIND response."""
    is_collection = isinstance(item, ical.Collection)
    if is_collection:
        with item.props as properties:
            collection_props = properties

    response = ET.Element(_tag("D", "response"))

    href = ET.Element(_tag("D", "href"))
    if item:
        uri = item.url if is_collection else "%s/%s" % (path, item.name)
        href.text = _href(uri.replace("//", "/"))
    else:
        href.text = _href(path)
    response.append(href)

    propstat404 = ET.Element(_tag("D", "propstat"))
    propstat200 = ET.Element(_tag("D", "propstat"))
    response.append(propstat200)

    prop200 = ET.Element(_tag("D", "prop"))
    propstat200.append(prop200)

    prop404 = ET.Element(_tag("D", "prop"))
    propstat404.append(prop404)

    for tag in props:
        element = ET.Element(tag)
        is404 = False
        if tag in (_tag("D", "principal-URL"),
                   _tag("D", "current-user-principal")):
            if user:
                tag = ET.Element(_tag("D", "href"))
                tag.text = _href("%s/" % user)
            else:
                is404 = True
                tag = ET.Element(_tag("D", "unauthenticated"))
            element.append(tag)
        elif tag == _tag("D", "principal-collection-set"):
            tag = ET.Element(_tag("D", "href"))
            tag.text = _href("/")
            element.append(tag)
        elif tag in (_tag("C", "calendar-home-set"),
                     _tag("CR", "addressbook-home-set")):
            if user and path == "/%s/" % user:
                tag = ET.Element(_tag("D", "href"))
                tag.text = _href(path)
                element.append(tag)
            else:
                is404 = True
        elif tag == _tag("C", "calendar-user-address-set"):
            tag = ET.Element(_tag("D", "href"))
            tag.text = _href(path)
            element.append(tag)
        elif tag == _tag("C", "supported-calendar-component-set"):
            # This is not a Todo
            # pylint: disable=W0511
            human_tag = _tag_from_clark(tag)
            if is_collection and human_tag in collection_props:
                # TODO: what do we have to do if it's not a collection?
                components = collection_props[human_tag].split(",")
            else:
                components = ("VTODO", "VEVENT", "VJOURNAL")
            for component in components:
                comp = ET.Element(_tag("C", "comp"))
                comp.set("name", component)
                element.append(comp)
            # pylint: enable=W0511
        elif tag == _tag("D", "current-user-privilege-set"):
            privilege = ET.Element(_tag("D", "privilege"))
            privilege.append(ET.Element(_tag("D", "all")))
            privilege.append(ET.Element(_tag("D", "read")))
            privilege.append(ET.Element(_tag("D", "write")))
            privilege.append(ET.Element(_tag("D", "write-properties")))
            privilege.append(ET.Element(_tag("D", "write-content")))
            element.append(privilege)
        elif tag == _tag("D", "supported-report-set"):
            for report_name in (
                    "principal-property-search", "sync-collection",
                    "expand-property", "principal-search-property-set"):
                supported = ET.Element(_tag("D", "supported-report"))
                report_tag = ET.Element(_tag("D", "report"))
                report_tag.text = report_name
                supported.append(report_tag)
                element.append(supported)
        # item related properties
        elif item:
            if tag == _tag("D", "getetag"):
                element.text = item.etag
            elif is_collection:
                if tag == _tag("D", "getcontenttype"):
                    element.text = item.mimetype
                elif tag == _tag("D", "resourcetype"):
                    if item.is_principal:
                        tag = ET.Element(_tag("D", "principal"))
                        element.append(tag)
                    if item.is_leaf(item.path) or (
                            not item.exists and item.resource_type):
                        # 2nd case happens when the collection is not stored yet,
                        # but the resource type is guessed
                        if item.resource_type == "addressbook":
                            tag = ET.Element(_tag("CR", item.resource_type))
                        else:
                            tag = ET.Element(_tag("C", item.resource_type))
                        element.append(tag)
                    tag = ET.Element(_tag("D", "collection"))
                    element.append(tag)
                elif tag == _tag("D", "owner") and item.owner_url:
                    element.text = item.owner_url
                elif tag == _tag("CS", "getctag"):
                    element.text = item.etag
                elif tag == _tag("C", "calendar-timezone"):
                    element.text = ical.serialize(
                        item.tag, item.headers, item.timezones)
                elif tag == _tag("D", "displayname"):
                    element.text = item.name
                elif tag == _tag("A", "calendar-color"):
                    element.text = item.color
                else:
                    human_tag = _tag_from_clark(tag)
                    if human_tag in collection_props:
                        element.text = collection_props[human_tag]
                    else:
                        is404 = True
            # Not for collections
            elif tag == _tag("D", "getcontenttype"):
                element.text = "%s; component=%s" % (
                    item.mimetype, item.tag.lower())
            elif tag == _tag("D", "resourcetype"):
                # resourcetype must be returned empty for non-collection elements
                pass
            else:
                is404 = True
        # Not for items
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

    if "{" in tag:
        clark_tag = tag
    else:
        clark_tag = _tag(*tag.split(":", 1))
    prop_tag = ET.Element(clark_tag)
    prop.append(prop_tag)

    status = ET.Element(_tag("D", "status"))
    status.text = _response(status_number)
    propstat.append(status)


def proppatch(path, xml_request, collection):
    """Read and answer PROPPATCH requests.

    Read rfc4918-9.2 for info.

    """
    # Reading request
    root = ET.fromstring(xml_request.encode("utf8"))
    props_to_set = props_from_request(root, actions=("set",))
    props_to_remove = props_from_request(root, actions=("remove",))

    # Writing answer
    multistatus = ET.Element(_tag("D", "multistatus"))

    response = ET.Element(_tag("D", "response"))
    multistatus.append(response)

    href = ET.Element(_tag("D", "href"))
    href.text = _href(path)
    response.append(href)

    with collection.props as collection_props:
        for short_name, value in props_to_set.items():
            if short_name.split(":")[-1] == "calendar-timezone":
                collection.replace(None, value)
            collection_props[short_name] = value
            _add_propstat_to(response, short_name, 200)
        for short_name in props_to_remove:
            try:
                del collection_props[short_name]
            except KeyError:
                _add_propstat_to(response, short_name, 412)
            else:
                _add_propstat_to(response, short_name, 200)

    return _pretty_xml(multistatus)


def put(path, ical_request, collection):
    """Read PUT requests."""
    name = name_from_path(path, collection)
    if name in (item.name for item in collection.items):
        # PUT is modifying an existing item
        collection.replace(name, ical_request)
    else:
        # PUT is adding a new item
        collection.append(name, ical_request)


def report(path, xml_request, collection):
    """Read and answer REPORT requests.

    Read rfc3253-3.6 for info.

    """
    # Reading request
    root = ET.fromstring(xml_request.encode("utf8"))

    prop_element = root.find(_tag("D", "prop"))
    props = [prop.tag for prop in prop_element]

    if collection:
        if root.tag in (_tag("C", "calendar-multiget"),
                        _tag("CR", "addressbook-multiget")):
            # Read rfc4791-7.9 for info
            base_prefix = config.get("server", "base_prefix")
            hreferences = set(
                unquote(href_element.text)[len(base_prefix):] for href_element
                in root.findall(_tag("D", "href"))
                if unquote(href_element.text).startswith(base_prefix))
        else:
            hreferences = (path,)
        # TODO: handle other filters
        # TODO: handle the nested comp-filters correctly
        # Read rfc4791-9.7.1 for info
        tag_filters = set(
            element.get("name") for element
            in root.findall(".//%s" % _tag("C", "comp-filter")))
    else:
        hreferences = ()
        tag_filters = None

    # Writing answer
    multistatus = ET.Element(_tag("D", "multistatus"))

    collection_tag = collection.tag
    collection_items = collection.items
    collection_headers = collection.headers
    collection_timezones = collection.timezones

    for hreference in hreferences:
        # Check if the reference is an item or a collection
        name = name_from_path(hreference, collection)
        if name:
            # Reference is an item
            path = "/".join(hreference.split("/")[:-1]) + "/"
            items = (item for item in collection_items if item.name == name)
        else:
            # Reference is a collection
            path = hreference
            items = collection.components

        for item in items:
            if tag_filters and item.tag not in tag_filters:
                continue

            response = ET.Element(_tag("D", "response"))
            multistatus.append(response)

            href = ET.Element(_tag("D", "href"))
            href.text = _href("%s/%s" % (path.rstrip("/"), item.name))
            response.append(href)

            propstat = ET.Element(_tag("D", "propstat"))
            response.append(propstat)

            prop = ET.Element(_tag("D", "prop"))
            propstat.append(prop)

            for tag in props:
                element = ET.Element(tag)
                if tag == _tag("D", "getetag"):
                    element.text = item.etag
                elif tag == _tag("D", "getcontenttype"):
                    element.text = "%s; component=%s" % (
                        item.mimetype, item.tag.lower())
                elif tag in (_tag("C", "calendar-data"),
                             _tag("CR", "address-data")):
                    if isinstance(item, ical.Component):
                        element.text = ical.serialize(
                            collection_tag, collection_headers,
                            collection_timezones + [item])
                prop.append(element)

            status = ET.Element(_tag("D", "status"))
            status.text = _response(200)
            propstat.append(status)

    return _pretty_xml(multistatus)
