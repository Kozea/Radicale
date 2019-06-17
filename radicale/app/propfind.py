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

import itertools
import posixpath
import socket
from http import client
from xml.etree import ElementTree as ET

from radicale import httputils, pathutils, rights, storage, xmlutils
from radicale.log import logger


def xml_propfind(base_prefix, path, xml_request, allowed_items, user):
    """Read and answer PROPFIND requests.

    Read rfc4918-9.1 for info.

    The collections parameter is a list of collections that are to be included
    in the output.

    """
    # A client may choose not to submit a request body.  An empty PROPFIND
    # request body MUST be treated as if it were an 'allprop' request.
    top_tag = (xml_request[0] if xml_request is not None else
               ET.Element(xmlutils.make_tag("D", "allprop")))

    props = ()
    allprop = False
    propname = False
    if top_tag.tag == xmlutils.make_tag("D", "allprop"):
        allprop = True
    elif top_tag.tag == xmlutils.make_tag("D", "propname"):
        propname = True
    elif top_tag.tag == xmlutils.make_tag("D", "prop"):
        props = [prop.tag for prop in top_tag]

    if xmlutils.make_tag("D", "current-user-principal") in props and not user:
        # Ask for authentication
        # Returning the DAV:unauthenticated pseudo-principal as specified in
        # RFC 5397 doesn't seem to work with DAVdroid.
        return client.FORBIDDEN, None

    # Writing answer
    multistatus = ET.Element(xmlutils.make_tag("D", "multistatus"))

    for item, permission in allowed_items:
        write = permission == "w"
        response = xml_propfind_response(
            base_prefix, path, item, props, user, write=write,
            allprop=allprop, propname=propname)
        if response:
            multistatus.append(response)

    return client.MULTI_STATUS, multistatus


def xml_propfind_response(base_prefix, path, item, props, user, write=False,
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

    response = ET.Element(xmlutils.make_tag("D", "response"))

    href = ET.Element(xmlutils.make_tag("D", "href"))
    if is_collection:
        # Some clients expect collections to end with /
        uri = pathutils.unstrip_path(item.path, True)
    else:
        uri = pathutils.unstrip_path(
            posixpath.join(collection.path, item.href))

    href.text = xmlutils.make_href(base_prefix, uri)
    response.append(href)

    propstat404 = ET.Element(xmlutils.make_tag("D", "propstat"))
    propstat200 = ET.Element(xmlutils.make_tag("D", "propstat"))
    response.append(propstat200)

    prop200 = ET.Element(xmlutils.make_tag("D", "prop"))
    propstat200.append(prop200)

    prop404 = ET.Element(xmlutils.make_tag("D", "prop"))
    propstat404.append(prop404)

    if propname or allprop:
        props = []
        # Should list all properties that can be retrieved by the code below
        props.append(xmlutils.make_tag("D", "principal-collection-set"))
        props.append(xmlutils.make_tag("D", "current-user-principal"))
        props.append(xmlutils.make_tag("D", "current-user-privilege-set"))
        props.append(xmlutils.make_tag("D", "supported-report-set"))
        props.append(xmlutils.make_tag("D", "resourcetype"))
        props.append(xmlutils.make_tag("D", "owner"))

        if is_collection and collection.is_principal:
            props.append(xmlutils.make_tag("C", "calendar-user-address-set"))
            props.append(xmlutils.make_tag("D", "principal-URL"))
            props.append(xmlutils.make_tag("CR", "addressbook-home-set"))
            props.append(xmlutils.make_tag("C", "calendar-home-set"))

        if not is_collection or is_leaf:
            props.append(xmlutils.make_tag("D", "getetag"))
            props.append(xmlutils.make_tag("D", "getlastmodified"))
            props.append(xmlutils.make_tag("D", "getcontenttype"))
            props.append(xmlutils.make_tag("D", "getcontentlength"))

        if is_collection:
            if is_leaf:
                props.append(xmlutils.make_tag("D", "displayname"))
                props.append(xmlutils.make_tag("D", "sync-token"))
            if collection.get_meta("tag") == "VCALENDAR":
                props.append(xmlutils.make_tag("CS", "getctag"))
                props.append(
                    xmlutils.make_tag("C", "supported-calendar-component-set"))

            meta = item.get_meta()
            for tag in meta:
                if tag == "tag":
                    continue
                clark_tag = xmlutils.tag_from_human(tag)
                if clark_tag not in props:
                    props.append(clark_tag)

    if propname:
        for tag in props:
            prop200.append(ET.Element(tag))
        props = ()

    for tag in props:
        element = ET.Element(tag)
        is404 = False
        if tag == xmlutils.make_tag("D", "getetag"):
            if not is_collection or is_leaf:
                element.text = item.etag
            else:
                is404 = True
        elif tag == xmlutils.make_tag("D", "getlastmodified"):
            if not is_collection or is_leaf:
                element.text = item.last_modified
            else:
                is404 = True
        elif tag == xmlutils.make_tag("D", "principal-collection-set"):
            tag = ET.Element(xmlutils.make_tag("D", "href"))
            tag.text = xmlutils.make_href(base_prefix, "/")
            element.append(tag)
        elif (tag in (xmlutils.make_tag("C", "calendar-user-address-set"),
                      xmlutils.make_tag("D", "principal-URL"),
                      xmlutils.make_tag("CR", "addressbook-home-set"),
                      xmlutils.make_tag("C", "calendar-home-set")) and
                collection.is_principal and is_collection):
            tag = ET.Element(xmlutils.make_tag("D", "href"))
            tag.text = xmlutils.make_href(base_prefix, path)
            element.append(tag)
        elif tag == xmlutils.make_tag("C", "supported-calendar-component-set"):
            human_tag = xmlutils.tag_from_clark(tag)
            if is_collection and is_leaf:
                meta = item.get_meta(human_tag)
                if meta:
                    components = meta.split(",")
                else:
                    components = ("VTODO", "VEVENT", "VJOURNAL")
                for component in components:
                    comp = ET.Element(xmlutils.make_tag("C", "comp"))
                    comp.set("name", component)
                    element.append(comp)
            else:
                is404 = True
        elif tag == xmlutils.make_tag("D", "current-user-principal"):
            if user:
                tag = ET.Element(xmlutils.make_tag("D", "href"))
                tag.text = xmlutils.make_href(base_prefix, "/%s/" % user)
                element.append(tag)
            else:
                element.append(ET.Element(
                    xmlutils.make_tag("D", "unauthenticated")))
        elif tag == xmlutils.make_tag("D", "current-user-privilege-set"):
            privileges = [("D", "read")]
            if write:
                privileges.append(("D", "all"))
                privileges.append(("D", "write"))
                privileges.append(("D", "write-properties"))
                privileges.append(("D", "write-content"))
            for ns, privilege_name in privileges:
                privilege = ET.Element(xmlutils.make_tag("D", "privilege"))
                privilege.append(ET.Element(
                    xmlutils.make_tag(ns, privilege_name)))
                element.append(privilege)
        elif tag == xmlutils.make_tag("D", "supported-report-set"):
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
                supported = ET.Element(
                    xmlutils.make_tag("D", "supported-report"))
                report_tag = ET.Element(xmlutils.make_tag("D", "report"))
                supported_report_tag = ET.Element(
                    xmlutils.make_tag(ns, report_name))
                report_tag.append(supported_report_tag)
                supported.append(report_tag)
                element.append(supported)
        elif tag == xmlutils.make_tag("D", "getcontentlength"):
            if not is_collection or is_leaf:
                encoding = collection.configuration.get("encoding", "request")
                element.text = str(len(item.serialize().encode(encoding)))
            else:
                is404 = True
        elif tag == xmlutils.make_tag("D", "owner"):
            # return empty elment, if no owner available (rfc3744-5.1)
            if collection.owner:
                tag = ET.Element(xmlutils.make_tag("D", "href"))
                tag.text = xmlutils.make_href(
                    base_prefix, "/%s/" % collection.owner)
                element.append(tag)
        elif is_collection:
            if tag == xmlutils.make_tag("D", "getcontenttype"):
                if is_leaf:
                    element.text = xmlutils.MIMETYPES[item.get_meta("tag")]
                else:
                    is404 = True
            elif tag == xmlutils.make_tag("D", "resourcetype"):
                if item.is_principal:
                    tag = ET.Element(xmlutils.make_tag("D", "principal"))
                    element.append(tag)
                if is_leaf:
                    if item.get_meta("tag") == "VADDRESSBOOK":
                        tag = ET.Element(
                            xmlutils.make_tag("CR", "addressbook"))
                        element.append(tag)
                    elif item.get_meta("tag") == "VCALENDAR":
                        tag = ET.Element(xmlutils.make_tag("C", "calendar"))
                        element.append(tag)
                tag = ET.Element(xmlutils.make_tag("D", "collection"))
                element.append(tag)
            elif tag == xmlutils.make_tag("RADICALE", "displayname"):
                # Only for internal use by the web interface
                displayname = item.get_meta("D:displayname")
                if displayname is not None:
                    element.text = displayname
                else:
                    is404 = True
            elif tag == xmlutils.make_tag("D", "displayname"):
                displayname = item.get_meta("D:displayname")
                if not displayname and is_leaf:
                    displayname = item.path
                if displayname is not None:
                    element.text = displayname
                else:
                    is404 = True
            elif tag == xmlutils.make_tag("CS", "getctag"):
                if is_leaf:
                    element.text = item.etag
                else:
                    is404 = True
            elif tag == xmlutils.make_tag("D", "sync-token"):
                if is_leaf:
                    element.text, _ = item.sync()
                else:
                    is404 = True
            else:
                human_tag = xmlutils.tag_from_clark(tag)
                meta = item.get_meta(human_tag)
                if meta is not None:
                    element.text = meta
                else:
                    is404 = True
        # Not for collections
        elif tag == xmlutils.make_tag("D", "getcontenttype"):
            element.text = xmlutils.get_content_type(item)
        elif tag == xmlutils.make_tag("D", "resourcetype"):
            # resourcetype must be returned empty for non-collection elements
            pass
        else:
            is404 = True

        if is404:
            prop404.append(element)
        else:
            prop200.append(element)

    status200 = ET.Element(xmlutils.make_tag("D", "status"))
    status200.text = xmlutils.make_response(200)
    propstat200.append(status200)

    status404 = ET.Element(xmlutils.make_tag("D", "status"))
    status404.text = xmlutils.make_response(404)
    propstat404.append(status404)
    if len(prop404):
        response.append(propstat404)

    return response


class ApplicationPropfindMixin:
    def _collect_allowed_items(self, items, user):
        """Get items from request that user is allowed to access."""
        for item in items:
            if isinstance(item, storage.BaseCollection):
                path = pathutils.unstrip_path(item.path, True)
                if item.get_meta("tag"):
                    permissions = self.Rights.authorized(user, path, "rw")
                    target = "collection with tag %r" % item.path
                else:
                    permissions = self.Rights.authorized(user, path, "RW")
                    target = "collection %r" % item.path
            else:
                path = pathutils.unstrip_path(item.collection.path, True)
                permissions = self.Rights.authorized(user, path, "rw")
                target = "item %r from %r" % (item.href, item.collection.path)
            if rights.intersect_permissions(permissions, "Ww"):
                permission = "w"
                status = "write"
            elif rights.intersect_permissions(permissions, "Rr"):
                permission = "r"
                status = "read"
            else:
                permission = ""
                status = "NO"
            logger.debug(
                "%s has %s access to %s",
                repr(user) if user else "anonymous user", status, target)
            if permission:
                yield item, permission

    def do_PROPFIND(self, environ, base_prefix, path, user):
        """Manage PROPFIND request."""
        if not self.access(user, path, "r"):
            return httputils.NOT_ALLOWED
        try:
            xml_content = self.read_xml_content(environ)
        except RuntimeError as e:
            logger.warning(
                "Bad PROPFIND request on %r: %s", path, e, exc_info=True)
            return httputils.BAD_REQUEST
        except socket.timeout:
            logger.debug("client timed out", exc_info=True)
            return httputils.REQUEST_TIMEOUT
        with self.Collection.acquire_lock("r", user):
            items = self.Collection.discover(
                path, environ.get("HTTP_DEPTH", "0"))
            # take root item for rights checking
            item = next(items, None)
            if not item:
                return httputils.NOT_FOUND
            if not self.access(user, path, "r", item):
                return httputils.NOT_ALLOWED
            # put item back
            items = itertools.chain([item], items)
            allowed_items = self._collect_allowed_items(items, user)
            headers = {"DAV": httputils.DAV_HEADERS,
                       "Content-Type": "text/xml; charset=%s" % self.encoding}
            status, xml_answer = xml_propfind(
                base_prefix, path, xml_content, allowed_items, user)
            if status == client.FORBIDDEN:
                return httputils.NOT_ALLOWED
            return status, headers, self.write_xml_content(xml_answer)
