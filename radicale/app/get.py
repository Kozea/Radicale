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

import posixpath
from http import client
from urllib.parse import quote

from radicale import httputils, pathutils, storage, xmlutils
from radicale.log import logger


def propose_filename(collection):
    """Propose a filename for a collection."""
    tag = collection.get_meta("tag")
    if tag == "VADDRESSBOOK":
        fallback_title = "Address book"
        suffix = ".vcf"
    elif tag == "VCALENDAR":
        fallback_title = "Calendar"
        suffix = ".ics"
    else:
        fallback_title = posixpath.basename(collection.path)
        suffix = ""
    title = collection.get_meta("D:displayname") or fallback_title
    if title and not title.lower().endswith(suffix.lower()):
        title += suffix
    return title


class ApplicationGetMixin:
    def _content_disposition_attachement(self, filename):
        value = "attachement"
        try:
            encoded_filename = quote(filename, encoding=self.encoding)
        except UnicodeEncodeError:
            logger.warning("Failed to encode filename: %r", filename,
                           exc_info=True)
            encoded_filename = ""
        if encoded_filename:
            value += "; filename*=%s''%s" % (self.encoding, encoded_filename)
        return value

    def do_GET(self, environ, base_prefix, path, user):
        """Manage GET request."""
        # Redirect to .web if the root URL is requested
        if not pathutils.strip_path(path):
            web_path = ".web"
            if not environ.get("PATH_INFO"):
                web_path = posixpath.join(posixpath.basename(base_prefix),
                                          web_path)
            return (client.FOUND,
                    {"Location": web_path, "Content-Type": "text/plain"},
                    "Redirected to %s" % web_path)
        # Dispatch .web URL to web module
        if path == "/.web" or path.startswith("/.web/"):
            return self.Web.get(environ, base_prefix, path, user)
        if not self.access(user, path, "r"):
            return httputils.NOT_ALLOWED
        with self.Collection.acquire_lock("r", user):
            item = next(self.Collection.discover(path), None)
            if not item:
                return httputils.NOT_FOUND
            if not self.access(user, path, "r", item):
                return httputils.NOT_ALLOWED
            if isinstance(item, storage.BaseCollection):
                tag = item.get_meta("tag")
                if not tag:
                    return httputils.DIRECTORY_LISTING
                content_type = xmlutils.MIMETYPES[tag]
                content_disposition = self._content_disposition_attachement(
                    propose_filename(item))
            else:
                content_type = xmlutils.OBJECT_MIMETYPES[item.name]
                content_disposition = ""
            headers = {
                "Content-Type": content_type,
                "Last-Modified": item.last_modified,
                "ETag": item.etag}
            if content_disposition:
                headers["Content-Disposition"] = content_disposition
            answer = item.serialize()
            return client.OK, headers, answer
