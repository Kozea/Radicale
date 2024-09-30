# This file is part of Radicale - CalDAV and CardDAV server
# Copyright © 2008 Nicolas Kandel
# Copyright © 2008 Pascal Halter
# Copyright © 2008-2017 Guillaume Ayoub
# Copyright © 2017-2018 Unrud <unrud@outlook.com>
# Copyright © 2024-2024 Peter Bieringer <pb@bieringer.de>
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
from radicale.hook import HookNotificationItem, HookNotificationItemTypes
from radicale.log import logger


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
            hook_notification_item_list = []
            if isinstance(item, storage.BaseCollection):
                if self._permit_delete_collection:
                    if access.check("d", item):
                        logger.info("delete of collection is permitted by config/option [rights] permit_delete_collection but explicit forbidden by permission 'd': %s", path)
                        return httputils.NOT_ALLOWED
                else:
                    if not access.check("D", item):
                        logger.info("delete of collection is prevented by config/option [rights] permit_delete_collection and not explicit allowed by permission 'D': %s", path)
                        return httputils.NOT_ALLOWED
                for i in item.get_all():
                    hook_notification_item_list.append(
                        HookNotificationItem(
                            HookNotificationItemTypes.DELETE,
                            access.path,
                            i.uid
                        )
                    )
                xml_answer = xml_delete(base_prefix, path, item)
            else:
                assert item.collection is not None
                assert item.href is not None
                hook_notification_item_list.append(
                    HookNotificationItem(
                        HookNotificationItemTypes.DELETE,
                        access.path,
                        item.uid
                    )
                )
                xml_answer = xml_delete(
                    base_prefix, path, item.collection, item.href)
            for notification_item in hook_notification_item_list:
                self._hook.notify(notification_item)
            headers = {"Content-Type": "text/xml; charset=%s" % self._encoding}
            return client.OK, headers, self._xml_response(xml_answer)
