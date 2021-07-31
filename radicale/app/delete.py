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

import xml.etree.ElementTree as ET
from http import client
from typing import Optional

from radicale import httputils, storage, types, xmlutils
from radicale.app.base import Access, ApplicationBase


def xml_delete(base_prefix: str, path: str, collection: storage.BaseCollection,
               item_href: Optional[str] = None) -> ET.Element:
    """Read and answer DELETE requests.

    Read rfc4918-9.6 for info.

    """
    collection.delete(item_href)

    multistatus = ET.Element(xmlutils.make_clark("D:multistatus"))
    response = ET.Element(xmlutils.make_clark("D:response"))
    multistatus.append(response)

    href_element = ET.Element(xmlutils.make_clark("D:href"))
    href_element.text = xmlutils.make_href(base_prefix, path)
    response.append(href_element)

    status = ET.Element(xmlutils.make_clark("D:status"))
    status.text = xmlutils.make_response(200)
    response.append(status)

    return multistatus


class ApplicationPartDelete(ApplicationBase):

    def do_DELETE(self, environ: types.WSGIEnviron, base_prefix: str,
                  path: str, user: str) -> types.WSGIResponse:
        """Manage DELETE request."""
        access = Access(self._rights, user, path)
        if not access.check("w"):
            return httputils.NOT_ALLOWED
        with self._storage.acquire_lock("w", user):
            item = next(iter(self._storage.discover(path)), None)
            if not item:
                return httputils.NOT_FOUND
            if not access.check("w", item):
                return httputils.NOT_ALLOWED
            if_match = environ.get("HTTP_IF_MATCH", "*")
            if if_match not in ("*", item.etag):
                # ETag precondition not verified, do not delete item
                return httputils.PRECONDITION_FAILED
            if isinstance(item, storage.BaseCollection):
                xml_answer = xml_delete(base_prefix, path, item)
            else:
                assert item.collection is not None
                assert item.href is not None
                xml_answer = xml_delete(
                    base_prefix, path, item.collection, item.href)
            headers = {"Content-Type": "text/xml; charset=%s" % self._encoding}
            return client.OK, headers, self._xml_response(xml_answer)
