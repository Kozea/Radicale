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
from http import client
from urllib.parse import quote

from radicale import httputils, pathutils, storage, types, xmlutils
from radicale.app.base import Access, ApplicationBase
from radicale.log import logger


def propose_filename(collection: storage.BaseCollection) -> str:
    """Propose a filename for a collection."""
    if collection.tag == "VADDRESSBOOK":
        fallback_title = "Address book"
        suffix = ".vcf"
    elif collection.tag == "VCALENDAR":
        fallback_title = "Calendar"
        suffix = ".ics"
    else:
        fallback_title = posixpath.basename(collection.path)
        suffix = ""
    title = collection.get_meta("D:displayname") or fallback_title
    if title and not title.lower().endswith(suffix.lower()):
        title += suffix
    return title


class ApplicationPartGet(ApplicationBase):

    def _content_disposition_attachment(self, filename: str) -> str:
        value = "attachment"
        try:
            encoded_filename = quote(filename, encoding=self._encoding)
        except UnicodeEncodeError:
            logger.warning("Failed to encode filename: %r", filename,
                           exc_info=True)
            encoded_filename = ""
        if encoded_filename:
            value += "; filename*=%s''%s" % (self._encoding, encoded_filename)
        return value

    def do_GET(self, environ: types.WSGIEnviron, base_prefix: str, path: str,
               user: str) -> types.WSGIResponse:
        """Manage GET request."""
        # Redirect to /.web if the root path is requested
        if not pathutils.strip_path(path):
            return httputils.redirect(base_prefix + "/.web")
        if path == "/.web" or path.startswith("/.web/"):
            # Redirect to sanitized path for all subpaths of /.web
            unsafe_path = environ.get("PATH_INFO", "")
            if unsafe_path != path:
                location = base_prefix + path
                logger.info("Redirecting to sanitized path: %r ==> %r",
                            base_prefix + unsafe_path, location)
                return httputils.redirect(location, client.MOVED_PERMANENTLY)
            # Dispatch /.web path to web module
            return self._web.get(environ, base_prefix, path, user)
        access = Access(self._rights, user, path)
        if not access.check("r") and "i" not in access.permissions:
            return httputils.NOT_ALLOWED
        with self._storage.acquire_lock("r", user):
            item = next(iter(self._storage.discover(path)), None)
            if not item:
                return httputils.NOT_FOUND
            if access.check("r", item):
                limited_access = False
            elif "i" in access.permissions:
                limited_access = True
            else:
                return httputils.NOT_ALLOWED
            if isinstance(item, storage.BaseCollection):
                if not item.tag:
                    return (httputils.NOT_ALLOWED if limited_access else
                            httputils.DIRECTORY_LISTING)
                content_type = xmlutils.MIMETYPES[item.tag]
                content_disposition = self._content_disposition_attachment(
                    propose_filename(item))
            elif limited_access:
                return httputils.NOT_ALLOWED
            else:
                content_type = xmlutils.OBJECT_MIMETYPES[item.name]
                content_disposition = ""
            assert item.last_modified
            headers = {
                "Content-Type": content_type,
                "Last-Modified": item.last_modified,
                "ETag": item.etag}
            if content_disposition:
                headers["Content-Disposition"] = content_disposition
            answer = item.serialize()
            return client.OK, headers, answer
