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

import socket
from http import client
from xml.etree import ElementTree as ET

from radicale import app, httputils
from radicale import item as radicale_item
from radicale import storage, xmlutils
from radicale.log import logger


def xml_add_propstat_to(element, tag, status_number):
    """Add a PROPSTAT response structure to an element.

    The PROPSTAT answer structure is defined in rfc4918-9.1. It is added to the
    given ``element``, for the following ``tag`` with the given
    ``status_number``.

    """
    propstat = ET.Element(xmlutils.make_clark("D:propstat"))
    element.append(propstat)

    prop = ET.Element(xmlutils.make_clark("D:prop"))
    propstat.append(prop)

    clark_tag = xmlutils.make_clark(tag)
    prop_tag = ET.Element(clark_tag)
    prop.append(prop_tag)

    status = ET.Element(xmlutils.make_clark("D:status"))
    status.text = xmlutils.make_response(status_number)
    propstat.append(status)


def xml_proppatch(base_prefix, path, xml_request, collection):
    """Read and answer PROPPATCH requests.

    Read rfc4918-9.2 for info.

    """
    props_to_set = xmlutils.props_from_request(xml_request, actions=("set",))
    props_to_remove = xmlutils.props_from_request(xml_request,
                                                  actions=("remove",))

    multistatus = ET.Element(xmlutils.make_clark("D:multistatus"))
    response = ET.Element(xmlutils.make_clark("D:response"))
    multistatus.append(response)

    href = ET.Element(xmlutils.make_clark("D:href"))
    href.text = xmlutils.make_href(base_prefix, path)
    response.append(href)

    new_props = collection.get_meta()
    for short_name, value in props_to_set.items():
        new_props[short_name] = value
        xml_add_propstat_to(response, short_name, 200)
    for short_name in props_to_remove:
        try:
            del new_props[short_name]
        except KeyError:
            pass
        xml_add_propstat_to(response, short_name, 200)
    radicale_item.check_and_sanitize_props(new_props)
    collection.set_meta(new_props)

    return multistatus


class ApplicationProppatchMixin:
    def do_PROPPATCH(self, environ, base_prefix, path, user):
        """Manage PROPPATCH request."""
        access = app.Access(self._rights, user, path)
        if not access.check("w"):
            return httputils.NOT_ALLOWED
        try:
            xml_content = self._read_xml_content(environ)
        except RuntimeError as e:
            logger.warning(
                "Bad PROPPATCH request on %r: %s", path, e, exc_info=True)
            return httputils.BAD_REQUEST
        except socket.timeout:
            logger.debug("client timed out", exc_info=True)
            return httputils.REQUEST_TIMEOUT
        with self._storage.acquire_lock("w", user):
            item = next(self._storage.discover(path), None)
            if not item:
                return httputils.NOT_FOUND
            if not access.check("w", item):
                return httputils.NOT_ALLOWED
            if not isinstance(item, storage.BaseCollection):
                return httputils.FORBIDDEN
            headers = {"DAV": httputils.DAV_HEADERS,
                       "Content-Type": "text/xml; charset=%s" % self._encoding}
            try:
                xml_answer = xml_proppatch(base_prefix, path, xml_content,
                                           item)
            except ValueError as e:
                logger.warning(
                    "Bad PROPPATCH request on %r: %s", path, e, exc_info=True)
                return httputils.BAD_REQUEST
            return (client.MULTI_STATUS, headers,
                    self._write_xml_content(xml_answer))
