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
import socket
import xml.etree.ElementTree as ET
from http import client

from radicale import app, httputils
from radicale import item as radicale_item
from radicale import storage, xmlutils
from radicale.log import logger


def xml_proppatch(base_prefix, path, xml_request, collection):
    """Read and answer PROPPATCH requests.

    Read rfc4918-9.2 for info.

    """
    multistatus = ET.Element(xmlutils.make_clark("D:multistatus"))
    response = ET.Element(xmlutils.make_clark("D:response"))
    multistatus.append(response)
    href = ET.Element(xmlutils.make_clark("D:href"))
    href.text = xmlutils.make_href(base_prefix, path)
    response.append(href)
    # Create D:propstat element for props with status 200 OK
    propstat = ET.Element(xmlutils.make_clark("D:propstat"))
    status = ET.Element(xmlutils.make_clark("D:status"))
    status.text = xmlutils.make_response(200)
    props_ok = ET.Element(xmlutils.make_clark("D:prop"))
    propstat.append(props_ok)
    propstat.append(status)
    response.append(propstat)

    new_props = collection.get_meta()
    for short_name, value in xmlutils.props_from_request(xml_request).items():
        if value is None:
            with contextlib.suppress(KeyError):
                del new_props[short_name]
        else:
            new_props[short_name] = value
        props_ok.append(ET.Element(xmlutils.make_clark(short_name)))
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
            xml_content = self._read_xml_request_body(environ)
        except RuntimeError as e:
            logger.warning(
                "Bad PROPPATCH request on %r: %s", path, e, exc_info=True)
            return httputils.BAD_REQUEST
        except socket.timeout:
            logger.debug("Client timed out", exc_info=True)
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
            return client.MULTI_STATUS, headers, self._xml_response(xml_answer)
