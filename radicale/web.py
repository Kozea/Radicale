# This file is part of Radicale Server - Calendar Server
# Copyright (C) 2017 Unrud <unrud@openaliasbox.org>
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

import os
import posixpath
import time
from http import client
from importlib import import_module

import pkg_resources

from . import storage

NOT_FOUND = (
    client.NOT_FOUND, (("Content-Type", "text/plain"),),
    "The requested resource could not be found.")

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

INTERNAL_TYPES = ("None", "none", "internal")


def load(configuration, logger):
    """Load the web module chosen in configuration."""
    web_type = configuration.get("web", "type")
    if web_type in ("None", "none"):  # DEPRECATED: use "none"
        web_class = NoneWeb
    elif web_type == "internal":
        web_class = Web
    else:
        try:
            web_class = import_module(web_type).Web
        except Exception as e:
            raise RuntimeError("Failed to load web module %r: %s" %
                               (web_type, e)) from e
    logger.info("Web type is %r", web_type)
    return web_class(configuration, logger)


class BaseWeb:
    def __init__(self, configuration, logger):
        self.configuration = configuration
        self.logger = logger

    def get(self, environ, base_prefix, path, user):
        """GET request.

        ``base_prefix`` is sanitized and never ends with "/".

        ``path`` is sanitized and always starts with "/.web"

        ``user`` is empty for anonymous users.

        """
        raise NotImplementedError


class NoneWeb(BaseWeb):
    def get(self, environ, base_prefix, path, user):
        if path != "/.web":
            return NOT_FOUND
        return client.OK, {"Content-Type": "text/plain"}, "Radicale works!"


class Web(BaseWeb):
    def __init__(self, configuration, logger):
        super().__init__(configuration, logger)
        self.folder = pkg_resources.resource_filename(__name__, "web")

    def get(self, environ, base_prefix, path, user):
        try:
            filesystem_path = storage.path_to_filesystem(
                self.folder, path[len("/.web"):])
        except ValueError as e:
            self.logger.debug("Web content with unsafe path %r requested: %s",
                              path, e, exc_info=True)
            return NOT_FOUND
        if os.path.isdir(filesystem_path) and not path.endswith("/"):
            location = posixpath.basename(path) + "/"
            return (client.FOUND,
                    {"Location": location, "Content-Type": "text/plain"},
                    "Redirected to %s" % location)
        if os.path.isdir(filesystem_path):
            filesystem_path = os.path.join(filesystem_path, "index.html")
        if not os.path.isfile(filesystem_path):
            return NOT_FOUND
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
