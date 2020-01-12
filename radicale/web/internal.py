# This file is part of Radicale Server - Calendar Server
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

"""
The default web backend.

Features:

  - Create and delete address books and calendars.
  - Edit basic metadata of existing address books and calendars.
  - Upload address books and calendars from files.

"""


import os
import posixpath
import time
from http import client

import pkg_resources

from radicale import httputils, pathutils, web
from radicale.log import logger

MIMETYPES = {
    ".css": "text/css",
    ".eot": "application/vnd.ms-fontobject",
    ".gif": "image/gif",
    ".html": "text/html",
    ".js": "application/javascript",
    ".manifest": "text/cache-manifest",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".ttf": "application/font-sfnt",
    ".txt": "text/plain",
    ".woff": "application/font-woff",
    ".woff2": "font/woff2",
    ".xml": "text/xml"}
FALLBACK_MIMETYPE = "application/octet-stream"


class Web(web.BaseWeb):
    def __init__(self, configuration):
        super().__init__(configuration)
        self.folder = pkg_resources.resource_filename(__name__,
                                                      "internal_data")

    def get(self, environ, base_prefix, path, user):
        assert path == "/.web" or path.startswith("/.web/")
        assert pathutils.sanitize_path(path) == path
        try:
            filesystem_path = pathutils.path_to_filesystem(
                self.folder, path[len("/.web"):].strip("/"))
        except ValueError as e:
            logger.debug("Web content with unsafe path %r requested: %s",
                         path, e, exc_info=True)
            return httputils.NOT_FOUND
        if os.path.isdir(filesystem_path) and not path.endswith("/"):
            location = posixpath.basename(path) + "/"
            return (client.FOUND,
                    {"Location": location, "Content-Type": "text/plain"},
                    "Redirected to %s" % location)
        if os.path.isdir(filesystem_path):
            filesystem_path = os.path.join(filesystem_path, "index.html")
        if not os.path.isfile(filesystem_path):
            return httputils.NOT_FOUND
        content_type = MIMETYPES.get(
            os.path.splitext(filesystem_path)[1].lower(), FALLBACK_MIMETYPE)
        with open(filesystem_path, "rb") as f:
            answer = f.read()
            last_modified = time.strftime(
                "%a, %d %b %Y %H:%M:%S GMT",
                time.gmtime(os.fstat(f.fileno()).st_mtime))
        headers = {
            "Content-Type": content_type,
            "Last-Modified": last_modified}
        return client.OK, headers, answer
