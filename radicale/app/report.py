# This file is part of Radicale Server - Calendar Server
# Copyright © 2008 Nicolas Kandel
# Copyright © 2008 Pascal Halter
# Copyright © 2008-2017 Guillaume Ayoub
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

import contextlib
import posixpath
import socket
import xml.etree.ElementTree as ET
from http import client
from urllib.parse import unquote, urlparse

from radicale import app, httputils, pathutils, storage, xmlutils
from radicale.item import filter as radicale_filter
from radicale.log import logger


def xml_report(base_prefix, path, xml_request, collection, encoding,
               unlock_storage_fn):
    """Read and answer REPORT requests.

    Read rfc3253-3.6 for info.

    """
    multistatus = ET.Element(xmlutils.make_clark("D:multistatus"))
    if xml_request is None:
        return client.MULTI_STATUS, multistatus
    root = xml_request
    if root.tag in (
            xmlutils.make_clark("D:principal-search-property-set"),
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
            collection.get_meta("tag") != "VCALENDAR" or
            root.tag == xmlutils.make_clark("CR:addressbook-multiget") and
            collection.get_meta("tag") != "VADDRESSBOOK" or
            root.tag == xmlutils.make_clark("D:sync-collection") and
            collection.get_meta("tag") not in ("VADDRESSBOOK", "VCALENDAR")):
        logger.warning("Invalid REPORT method %r on %r requested",
                       xmlutils.make_human_tag(root.tag), path)
        return (client.FORBIDDEN,
                xmlutils.webdav_error("D:supported-report"))
    prop_element = root.find(xmlutils.make_clark("D:prop"))
    props = (
        [prop.tag for prop in prop_element]
        if prop_element is not None else [])

    if root.tag in (
            xmlutils.make_clark("C:calendar-multiget"),
            xmlutils.make_clark("CR:addressbook-multiget")):
        # Read rfc4791-7.9 for info
        hreferences = set()
        for href_element in root.findall(xmlutils.make_clark("D:href")):
            href_path = pathutils.sanitize_path(
                unquote(urlparse(href_element.text).path))
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
            logger.warning("Client provided invalid sync token %r: %s",
                           old_sync_token, e, exc_info=True)
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
                    name = pathutils.name_from_path(hreference, collection)
                except ValueError as e:
                    logger.warning("Skipping invalid path %r in REPORT request"
                                   " on %r: %s", hreference, path, e)
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
                uri = pathutils.unstrip_path(
                    posixpath.join(collection.path, name))
                response = xml_item_response(base_prefix, uri,
                                             found_item=False)
                multistatus.append(response)
            else:
                yield item, False
        if collection_requested:
            yield from collection.get_filtered(filters)

    # Retrieve everything required for finishing the request.
    retrieved_items = list(retrieve_items(collection, hreferences,
                                          multistatus))
    collection_tag = collection.get_meta("tag")
    # Don't access storage after this!
    unlock_storage_fn()

    def match(item, filter_):
        tag = collection_tag
        if (tag == "VCALENDAR" and
                filter_.tag != xmlutils.make_clark("C:%s" % filter_)):
            if len(filter_) == 0:
                return True
            if len(filter_) > 1:
                raise ValueError("Filter with %d children" % len(filter_))
            if filter_[0].tag != xmlutils.make_clark("C:comp-filter"):
                raise ValueError("Unexpected %r in filter" % filter_[0].tag)
            return radicale_filter.comp_match(item, filter_[0])
        if (tag == "VADDRESSBOOK" and
                filter_.tag != xmlutils.make_clark("CR:%s" % filter_)):
            for child in filter_:
                if child.tag != xmlutils.make_clark("CR:prop-filter"):
                    raise ValueError("Unexpected %r in filter" % child.tag)
            test = filter_.get("test", "anyof")
            if test == "anyof":
                return any(
                    radicale_filter.prop_match(item.vobject_item, f, "CR")
                    for f in filter_)
            if test == "allof":
                return all(
                    radicale_filter.prop_match(item.vobject_item, f, "CR")
                    for f in filter_)
            raise ValueError("Unsupported filter test: %r" % test)
        raise ValueError("Unsupported filter %r for %r" % (filter_.tag, tag))

    while retrieved_items:
        # ``item.vobject_item`` might be accessed during filtering.
        # Don't keep reference to ``item``, because VObject requires a lot of
        # memory.
        item, filters_matched = retrieved_items.pop(0)
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
            if tag == xmlutils.make_clark("D:getetag"):
                element.text = item.etag
                found_props.append(element)
            elif tag == xmlutils.make_clark("D:getcontenttype"):
                element.text = xmlutils.get_content_type(item, encoding)
                found_props.append(element)
            elif tag in (
                    xmlutils.make_clark("C:calendar-data"),
                    xmlutils.make_clark("CR:address-data")):
                element.text = item.serialize()
                found_props.append(element)
            else:
                not_found_props.append(element)

        uri = pathutils.unstrip_path(
            posixpath.join(collection.path, item.href))
        multistatus.append(xml_item_response(
            base_prefix, uri, found_props=found_props,
            not_found_props=not_found_props, found_item=True))

    return client.MULTI_STATUS, multistatus


def xml_item_response(base_prefix, href, found_props=(), not_found_props=(),
                      found_item=True):
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


class ApplicationReportMixin:
    def do_REPORT(self, environ, base_prefix, path, user):
        """Manage REPORT request."""
        access = app.Access(self._rights, user, path)
        if not access.check("r"):
            return httputils.NOT_ALLOWED
        try:
            xml_content = self._read_xml_request_body(environ)
        except RuntimeError as e:
            logger.warning(
                "Bad REPORT request on %r: %s", path, e, exc_info=True)
            return httputils.BAD_REQUEST
        except socket.timeout:
            logger.debug("Client timed out", exc_info=True)
            return httputils.REQUEST_TIMEOUT
        with contextlib.ExitStack() as lock_stack:
            lock_stack.enter_context(self._storage.acquire_lock("r", user))
            item = next(self._storage.discover(path), None)
            if not item:
                return httputils.NOT_FOUND
            if not access.check("r", item):
                return httputils.NOT_ALLOWED
            if isinstance(item, storage.BaseCollection):
                collection = item
            else:
                collection = item.collection
            headers = {"Content-Type": "text/xml; charset=%s" % self._encoding}
            try:
                status, xml_answer = xml_report(
                    base_prefix, path, xml_content, collection, self._encoding,
                    lock_stack.close)
            except ValueError as e:
                logger.warning(
                    "Bad REPORT request on %r: %s", path, e, exc_info=True)
                return httputils.BAD_REQUEST
            return status, headers, self._xml_response(xml_answer)
