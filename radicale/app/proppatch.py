# This file is part of Radicale - CalDAV and CardDAV server
# Copyright © 2008 Nicolas Kandel
# Copyright © 2008 Pascal Halter
# Copyright © 2008-2017 Guillaume Ayoub
# Copyright © 2017-2020 Unrud <unrud@outlook.com>
# Copyright © 2020-2020 Tuna Celik <tuna@jakpark.com>
# Copyright © 2025-2026 Peter Bieringer <pb@bieringer.de>
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

import errno
import re
import socket
import xml.etree.ElementTree as ET
from http import client
from typing import Dict, Optional, Union, cast

import defusedxml.ElementTree as DefusedET

import radicale.item as radicale_item
from radicale import httputils, sharing, storage, types, xmlutils
from radicale.app.base import Access, ApplicationBase
from radicale.hook import HookNotificationItem, HookNotificationItemTypes
from radicale.log import logger


def xml_proppatch(base_prefix: str, path: str,
                  xml_request: Optional[ET.Element],
                  collection: Union[storage.BaseCollection, None], sharing: Union[dict, None] = None, sharing_overlay: bool = False, _sharing: Union[sharing.BaseSharing, None] = None) -> ET.Element:
    """Read and answer PROPPATCH requests.

    Read rfc4918-9.2 for info.

    """
    multistatus = ET.Element(xmlutils.make_clark("D:multistatus"))
    response = ET.Element(xmlutils.make_clark("D:response"))
    multistatus.append(response)
    href = ET.Element(xmlutils.make_clark("D:href"))
    href.text = xmlutils.make_href(base_prefix, path)
    if sharing:
        # backmap
        href.text = href.text.replace(sharing['PathMapped'], sharing['PathOrToken'])
    response.append(href)
    # Create D:propstat element for props with status 200 OK
    propstat = ET.Element(xmlutils.make_clark("D:propstat"))
    status = ET.Element(xmlutils.make_clark("D:status"))
    status.text = xmlutils.make_response(200)
    props_ok = ET.Element(xmlutils.make_clark("D:prop"))
    propstat.append(props_ok)
    propstat.append(status)
    response.append(propstat)

    props_with_remove = xmlutils.props_from_request(xml_request)
    if sharing and sharing_overlay:
        # PROPPATCH overlay adjustment
        logger.debug("TRACE/PROPPATCH/xml_proppatch: sharing+sharing_overlay is active: %r", sharing)
        if sharing['Properties'] is not None:
            all_props_with_remove = cast(Dict[str, Optional[str]], radicale_item.check_and_sanitize_props(sharing['Properties']))
        else:
            all_props_with_remove = {}
        all_props_with_remove.update(props_with_remove)
        all_props = radicale_item.check_and_sanitize_props(all_props_with_remove)
        logger.debug("TRACE/PROPPATCH/xml_proppatch: sharing+sharing_overlay result: %r", all_props)
    else:
        if collection is not None:
            # always the case, but makes mypy happy
            all_props_with_remove = cast(Dict[str, Optional[str]], dict(collection.get_meta()))
    all_props_with_remove.update(props_with_remove)
    all_props = radicale_item.check_and_sanitize_props(all_props_with_remove)
    if sharing and sharing_overlay and _sharing is not None:
        # _sharing is not None: always the case, but makes mypy happy
        _sharing.update_sharing(ShareType=sharing['ShareType'],
                                PathOrToken=sharing['PathOrToken'],
                                OwnerOrUser=sharing['User'],
                                Properties=cast(Dict[str, str], all_props))
    else:
        if collection is not None:
            # always the case, but makes mypy happy
            collection.set_meta(all_props)
    for short_name in props_with_remove:
        props_ok.append(ET.Element(xmlutils.make_clark(short_name)))

    return multistatus


class ApplicationPartProppatch(ApplicationBase):

    def do_PROPPATCH(self, environ: types.WSGIEnviron, base_prefix: str,
                     path: str, user: str, remote_host: str, remote_useragent: str) -> types.WSGIResponse:
        """Manage PROPPATCH request."""
        permissions_filter = None
        sharing = None
        sharing_overlay = False
        path_orig = path
        if self._sharing._enabled:
            # Sharing by token or map (if enabled)
            sharing = self._sharing.sharing_collection_resolver(path, user)
            if sharing:
                # overwrite and run through extended permission check
                path = sharing['PathMapped']
                user = sharing['Owner']
                permissions_filter = sharing['Permissions']
        access = Access(self._rights, user, path, permissions_filter)
        if not access.check("w"):
            logger.debug("TRACE/PROPPATCH/xml_proppatch: no write-access: %r", path)
            if sharing:
                # no write access -> use properties overlay
                if self._sharing.permit_properties_overlay:
                    if permissions_filter is not None and "p" in permissions_filter:
                        logger.info("PROPPATCH request on shared %r: no write-permissions, overlay permitted, but denied by permission 'p'", path_orig)
                        return httputils.NOT_ALLOWED
                    else:
                        logger.info("PROPPATCH request on shared %r: no write-permissions, overlay permitted by option", path_orig)
                        sharing_overlay = True
                else:
                    if permissions_filter is not None and "P" in permissions_filter:
                        logger.info("PROPPATCH request on shared %r: no write-permissions, overlay denied, but granted by permission 'P'", path_orig)
                        sharing_overlay = True
                    else:
                        logger.info("PROPPATCH request on shared %r: no write-permissions and overlay denied by option", path_orig)
                        return httputils.NOT_ALLOWED
            else:
                return httputils.NOT_ALLOWED
        else:
            logger.debug("TRACE/PROPPATCH/xml_proppatch: write-access: %r", path)
            if sharing:
                # write access -> check for enforced properties overlay
                logger.debug("TRACE/PROPPATCH/xml_proppatch: write-access/sharing: %r", path_orig)
                if self._sharing.enforce_properties_overlay:
                    if permissions_filter is not None and "e" in permissions_filter:
                        logger.info("PROPPATCH request on shared %r: write-permissions, overlay enforced, but disabled by permission 'e'", path_orig)
                    else:
                        sharing_overlay = True
                else:
                    if permissions_filter is not None and "E" in permissions_filter:
                        logger.info("PROPPATCH request on shared %r: write-permissions, overlay not enforced, but enforced by permission 'E'", path_orig)
                        sharing_overlay = True
        try:
            xml_content = self._read_xml_request_body(environ)
        except RuntimeError as e:
            logger.warning(
                "Bad PROPPATCH request on %r: %s", path, e, exc_info=True)
            return httputils.BAD_REQUEST
        except socket.timeout:
            logger.debug("Client timed out", exc_info=True)
            return httputils.REQUEST_TIMEOUT

        if sharing_overlay:
            # call API function internally and no not trigger any hook
            headers = {"DAV": httputils.DAV_HEADERS,
                       "Content-Type": "text/xml; charset=%s" % self._encoding}
            try:
                xml_answer = xml_proppatch(base_prefix, path, xml_content,
                                           None, sharing, sharing_overlay, self._sharing)
                if xml_content is not None:
                    content = DefusedET.tostring(
                        xml_content,
                        encoding=self._encoding
                    ).decode(encoding=self._encoding)
            except ValueError as e:
                # return better matching HTTP result in case errno is provided and catched
                errno_match = re.search("\\[Errno ([0-9]+)\\]", str(e))
                if errno_match:
                    logger.error(
                        "Failed PROPPATCH request on %r: %s", path, e, exc_info=True)
                    errno_e = int(errno_match.group(1))
                    if errno_e == errno.ENOSPC:
                        return httputils.INSUFFICIENT_STORAGE
                    elif errno_e in [errno.EPERM, errno.EACCES]:
                        return httputils.FORBIDDEN
                    else:
                        return httputils.INTERNAL_SERVER_ERROR
                else:
                    logger.warning(
                        "Bad PROPPATCH request on %r: %s", path, e, exc_info=True)
                    return httputils.BAD_REQUEST
            return client.MULTI_STATUS, headers, self._xml_response(xml_answer), xmlutils.pretty_xml(xml_content)

        with self._storage.acquire_lock("w", user, path=path, request="PROPPATCH"):
            item = next(iter(self._storage.discover(path)), None)
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
                                           item, sharing)
                if xml_content is not None:
                    content = DefusedET.tostring(
                        xml_content,
                        encoding=self._encoding
                    ).decode(encoding=self._encoding)
                    hook_notification_item = HookNotificationItem(
                        notification_item_type=HookNotificationItemTypes.CPATCH,
                        path=access.path,
                        content=content,
                        uid=None,
                        old_content=None,
                        new_content=content
                    )
                    self._hook.notify(hook_notification_item)
            except ValueError as e:
                # return better matching HTTP result in case errno is provided and catched
                errno_match = re.search("\\[Errno ([0-9]+)\\]", str(e))
                if errno_match:
                    logger.error(
                        "Failed PROPPATCH request on %r: %s", path, e, exc_info=True)
                    errno_e = int(errno_match.group(1))
                    if errno_e == errno.ENOSPC:
                        return httputils.INSUFFICIENT_STORAGE
                    elif errno_e in [errno.EPERM, errno.EACCES]:
                        return httputils.FORBIDDEN
                    else:
                        return httputils.INTERNAL_SERVER_ERROR
                else:
                    logger.warning(
                        "Bad PROPPATCH request on %r: %s", path, e, exc_info=True)
                    return httputils.BAD_REQUEST
            return client.MULTI_STATUS, headers, self._xml_response(xml_answer), xmlutils.pretty_xml(xml_content)
