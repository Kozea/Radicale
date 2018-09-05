# This file is part of Radicale Server - Calendar Server
# Copyright © 2008 Nicolas Kandel
# Copyright © 2008 Pascal Halter
# Copyright © 2008-2017 Guillaume Ayoub
# Copyright © 2017-2018 Unrud<unrud@outlook.com>
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

from http import client
from urllib.parse import urlparse

from radicale import httputils, pathutils, storage
from radicale.log import logger

import posixpath  # isort:skip


class ApplicationMoveMixin:
    def do_MOVE(self, environ, base_prefix, path, user):
        """Manage MOVE request."""
        raw_dest = environ.get("HTTP_DESTINATION", "")
        to_url = urlparse(raw_dest)
        if to_url.netloc != environ["HTTP_HOST"]:
            logger.info("Unsupported destination address: %r", raw_dest)
            # Remote destination server, not supported
            return httputils.REMOTE_DESTINATION
        if not self.access(user, path, "w"):
            return httputils.NOT_ALLOWED
        to_path = pathutils.sanitize_path(to_url.path)
        if not (to_path + "/").startswith(base_prefix + "/"):
            logger.warning("Destination %r from MOVE request on %r doesn't "
                           "start with base prefix", to_path, path)
            return httputils.NOT_ALLOWED
        to_path = to_path[len(base_prefix):]
        if not self.access(user, to_path, "w"):
            return httputils.NOT_ALLOWED

        with self.Collection.acquire_lock("w", user):
            item = next(self.Collection.discover(path), None)
            if not item:
                return httputils.NOT_FOUND
            if (not self.access(user, path, "w", item) or
                    not self.access(user, to_path, "w", item)):
                return httputils.NOT_ALLOWED
            if isinstance(item, storage.BaseCollection):
                # TODO: support moving collections
                return httputils.METHOD_NOT_ALLOWED

            to_item = next(self.Collection.discover(to_path), None)
            if isinstance(to_item, storage.BaseCollection):
                return httputils.FORBIDDEN
            to_parent_path = pathutils.unstrip_path(
                posixpath.dirname(pathutils.strip_path(to_path)), True)
            to_collection = next(
                self.Collection.discover(to_parent_path), None)
            if not to_collection:
                return httputils.CONFLICT
            tag = item.collection.get_meta("tag")
            if not tag or tag != to_collection.get_meta("tag"):
                return httputils.FORBIDDEN
            if to_item and environ.get("HTTP_OVERWRITE", "F") != "T":
                return httputils.PRECONDITION_FAILED
            if (to_item and item.uid != to_item.uid or
                    not to_item and
                    to_collection.path != item.collection.path and
                    to_collection.has_uid(item.uid)):
                return self.webdav_error_response(
                    "C" if tag == "VCALENDAR" else "CR", "no-uid-conflict")
            to_href = posixpath.basename(pathutils.strip_path(to_path))
            try:
                self.Collection.move(item, to_collection, to_href)
            except ValueError as e:
                logger.warning(
                    "Bad MOVE request on %r: %s", path, e, exc_info=True)
                return httputils.BAD_REQUEST
            return client.NO_CONTENT if to_item else client.CREATED, {}, None
