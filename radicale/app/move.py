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
import re
from http import client
from urllib.parse import urlparse

from radicale import httputils, pathutils, storage, types
from radicale.app.base import Access, ApplicationBase
from radicale.log import logger


def get_server_netloc(environ: types.WSGIEnviron, force_port: bool = False):
    if environ.get("HTTP_X_FORWARDED_HOST"):
        host = environ["HTTP_X_FORWARDED_HOST"]
        proto = environ.get("HTTP_X_FORWARDED_PROTO") or "http"
        port = "443" if proto == "https" else "80"
        port = environ["HTTP_X_FORWARDED_PORT"] or port
    else:
        host = environ.get("HTTP_HOST") or environ["SERVER_NAME"]
        proto = environ["wsgi.url_scheme"]
        port = environ["SERVER_PORT"]
    if (not force_port and port == ("443" if proto == "https" else "80") or
            re.search(r":\d+$", host)):
        return host
    return host + ":" + port


class ApplicationPartMove(ApplicationBase):

    def do_MOVE(self, environ: types.WSGIEnviron, base_prefix: str,
                path: str, user: str) -> types.WSGIResponse:
        """Manage MOVE request."""
        raw_dest = environ.get("HTTP_DESTINATION", "")
        to_url = urlparse(raw_dest)
        to_netloc_with_port = to_url.netloc
        if to_url.port is None:
            to_netloc_with_port += (":443" if to_url.scheme == "https"
                                    else ":80")
        if to_netloc_with_port != get_server_netloc(environ, force_port=True):
            logger.info("Unsupported destination address: %r", raw_dest)
            # Remote destination server, not supported
            return httputils.REMOTE_DESTINATION
        access = Access(self._rights, user, path)
        if not access.check("w"):
            return httputils.NOT_ALLOWED
        to_path = pathutils.sanitize_path(to_url.path)
        if not (to_path + "/").startswith(base_prefix + "/"):
            logger.warning("Destination %r from MOVE request on %r doesn't "
                           "start with base prefix", to_path, path)
            return httputils.NOT_ALLOWED
        to_path = to_path[len(base_prefix):]
        to_access = Access(self._rights, user, to_path)
        if not to_access.check("w"):
            return httputils.NOT_ALLOWED

        with self._storage.acquire_lock("w", user):
            item = next(iter(self._storage.discover(path)), None)
            if not item:
                return httputils.NOT_FOUND
            if (not access.check("w", item) or
                    not to_access.check("w", item)):
                return httputils.NOT_ALLOWED
            if isinstance(item, storage.BaseCollection):
                # TODO: support moving collections
                return httputils.METHOD_NOT_ALLOWED

            to_item = next(iter(self._storage.discover(to_path)), None)
            if isinstance(to_item, storage.BaseCollection):
                return httputils.FORBIDDEN
            to_parent_path = pathutils.unstrip_path(
                posixpath.dirname(pathutils.strip_path(to_path)), True)
            to_collection = next(iter(
                self._storage.discover(to_parent_path)), None)
            if not to_collection:
                return httputils.CONFLICT
            assert isinstance(to_collection, storage.BaseCollection)
            assert item.collection is not None
            collection_tag = item.collection.tag
            if not collection_tag or collection_tag != to_collection.tag:
                return httputils.FORBIDDEN
            if to_item and environ.get("HTTP_OVERWRITE", "F") != "T":
                return httputils.PRECONDITION_FAILED
            if (to_item and item.uid != to_item.uid or
                    not to_item and
                    to_collection.path != item.collection.path and
                    to_collection.has_uid(item.uid)):
                return self._webdav_error_response(
                    client.CONFLICT, "%s:no-uid-conflict" % (
                        "C" if collection_tag == "VCALENDAR" else "CR"))
            to_href = posixpath.basename(pathutils.strip_path(to_path))
            try:
                self._storage.move(item, to_collection, to_href)
            except ValueError as e:
                logger.warning(
                    "Bad MOVE request on %r: %s", path, e, exc_info=True)
                return httputils.BAD_REQUEST
            return client.NO_CONTENT if to_item else client.CREATED, {}, None
