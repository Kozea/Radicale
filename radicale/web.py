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

from http import client
from importlib import import_module

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


def load(configuration, logger):
    """Load the web module chosen in configuration."""
    web_type = configuration.get("web", "type")
    if web_type in ("None", "none"):  # DEPRECATED: use "none"
        web_class = NoneWeb
    else:
        try:
            web_class = import_module(web_type).Web
        except ImportError as e:
            raise RuntimeError("Web module %r not found" %
                               web_type) from e
    logger.info("Web type is %r", web_type)
    return web_class(configuration, logger)


class BaseWeb:
    def __init__(self, configuration, logger):
        self.configuration = configuration
        self.logger = logger


class NoneWeb(BaseWeb):
    def get(self, environ, base_prefix, path, user):
        if path != "/.web":
            return NOT_FOUND
        return client.OK, {"Content-Type": "text/plain"}, "Radicale works!"
