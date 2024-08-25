# This file is part of Radicale - CalDAV and CardDAV server
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

import posixpath
import socket
from http import client

import radicale.item as radicale_item
from radicale import httputils, pathutils, rights, storage, types, xmlutils
from radicale.app.base import ApplicationBase
from radicale.log import logger


class ApplicationPartMkcol(ApplicationBase):

    def do_MKCOL(self, environ: types.WSGIEnviron, base_prefix: str,
                 path: str, user: str) -> types.WSGIResponse:
        """Manage MKCOL request."""
        permissions = self._rights.authorization(user, path)
        if not rights.intersect(permissions, "Ww"):
            return httputils.NOT_ALLOWED
        try:
            xml_content = self._read_xml_request_body(environ)
        except RuntimeError as e:
            logger.warning(
                "Bad MKCOL request on %r: %s", path, e, exc_info=True)
            return httputils.BAD_REQUEST
        except socket.timeout:
            logger.debug("Client timed out", exc_info=True)
            return httputils.REQUEST_TIMEOUT
        # Prepare before locking
        props_with_remove = xmlutils.props_from_request(xml_content)
        try:
            props = radicale_item.check_and_sanitize_props(props_with_remove)
        except ValueError as e:
            logger.warning(
                "Bad MKCOL request on %r: %s", path, e, exc_info=True)
            return httputils.BAD_REQUEST
        collection_type = props.get("tag") or "UNKNOWN"
        if props.get("tag") and "w" not in permissions:
            logger.warning("MKCOL request %r (type:%s): %s", path, collection_type, "rejected because of missing rights 'w'")
            return httputils.NOT_ALLOWED
        if not props.get("tag") and "W" not in permissions:
            logger.warning("MKCOL request %r (type:%s): %s", path, collection_type, "rejected because of missing rights 'W'")
            return httputils.NOT_ALLOWED
        with self._storage.acquire_lock("w", user):
            item = next(iter(self._storage.discover(path)), None)
            if item:
                return httputils.METHOD_NOT_ALLOWED
            parent_path = pathutils.unstrip_path(
                posixpath.dirname(pathutils.strip_path(path)), True)
            parent_item = next(iter(self._storage.discover(parent_path)), None)
            if not parent_item:
                return httputils.CONFLICT
            if (not isinstance(parent_item, storage.BaseCollection) or
                    parent_item.tag):
                return httputils.FORBIDDEN
            try:
                self._storage.create_collection(path, props=props)
            except ValueError as e:
                logger.warning(
                    "Bad MKCOL request on %r (type:%s): %s", path, collection_type, e, exc_info=True)
                return httputils.BAD_REQUEST
            logger.info("MKCOL request %r (type:%s): %s", path, collection_type, "successful")
            return client.CREATED, {}, None
