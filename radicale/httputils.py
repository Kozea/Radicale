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

"""
Helper functions for HTTP.

"""

import contextlib
import os
import time
from http import client
from typing import List, Mapping, cast

from radicale import config, pathutils, types
from radicale.log import logger

NOT_ALLOWED: types.WSGIResponse = (
    client.FORBIDDEN, (("Content-Type", "text/plain"),),
    "Access to the requested resource forbidden.")
FORBIDDEN: types.WSGIResponse = (
    client.FORBIDDEN, (("Content-Type", "text/plain"),),
    "Action on the requested resource refused.")
BAD_REQUEST: types.WSGIResponse = (
    client.BAD_REQUEST, (("Content-Type", "text/plain"),), "Bad Request")
NOT_FOUND: types.WSGIResponse = (
    client.NOT_FOUND, (("Content-Type", "text/plain"),),
    "The requested resource could not be found.")
CONFLICT: types.WSGIResponse = (
    client.CONFLICT, (("Content-Type", "text/plain"),),
    "Conflict in the request.")
METHOD_NOT_ALLOWED: types.WSGIResponse = (
    client.METHOD_NOT_ALLOWED, (("Content-Type", "text/plain"),),
    "The method is not allowed on the requested resource.")
PRECONDITION_FAILED: types.WSGIResponse = (
    client.PRECONDITION_FAILED,
    (("Content-Type", "text/plain"),), "Precondition failed.")
REQUEST_TIMEOUT: types.WSGIResponse = (
    client.REQUEST_TIMEOUT, (("Content-Type", "text/plain"),),
    "Connection timed out.")
REQUEST_ENTITY_TOO_LARGE: types.WSGIResponse = (
    client.REQUEST_ENTITY_TOO_LARGE, (("Content-Type", "text/plain"),),
    "Request body too large.")
REMOTE_DESTINATION: types.WSGIResponse = (
    client.BAD_GATEWAY, (("Content-Type", "text/plain"),),
    "Remote destination not supported.")
DIRECTORY_LISTING: types.WSGIResponse = (
    client.FORBIDDEN, (("Content-Type", "text/plain"),),
    "Directory listings are not supported.")
INTERNAL_SERVER_ERROR: types.WSGIResponse = (
    client.INTERNAL_SERVER_ERROR, (("Content-Type", "text/plain"),),
    "A server error occurred.  Please contact the administrator.")

DAV_HEADERS: str = "1, 2, 3, calendar-access, addressbook, extended-mkcol"

MIMETYPES: Mapping[str, str] = {
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
FALLBACK_MIMETYPE: str = "application/octet-stream"


def decode_request(configuration: "config.Configuration",
                   environ: types.WSGIEnviron, text: bytes) -> str:
    """Try to magically decode ``text`` according to given ``environ``."""
    # List of charsets to try
    charsets: List[str] = []

    # First append content charset given in the request
    content_type = environ.get("CONTENT_TYPE")
    if content_type and "charset=" in content_type:
        charsets.append(
            content_type.split("charset=")[1].split(";")[0].strip())
    # Then append default Radicale charset
    charsets.append(cast(str, configuration.get("encoding", "request")))
    # Then append various fallbacks
    charsets.append("utf-8")
    charsets.append("iso8859-1")
    # Remove duplicates
    for i, s in reversed(list(enumerate(charsets))):
        if s in charsets[:i]:
            del charsets[i]

    # Try to decode
    for charset in charsets:
        with contextlib.suppress(UnicodeDecodeError):
            return text.decode(charset)
    raise UnicodeDecodeError("decode_request", text, 0, len(text),
                             "all codecs failed [%s]" % ", ".join(charsets))


def read_raw_request_body(configuration: "config.Configuration",
                          environ: types.WSGIEnviron) -> bytes:
    content_length = int(environ.get("CONTENT_LENGTH") or 0)
    if not content_length:
        return b""
    content = environ["wsgi.input"].read(content_length)
    if len(content) < content_length:
        raise RuntimeError("Request body too short: %d" % len(content))
    return content


def read_request_body(configuration: "config.Configuration",
                      environ: types.WSGIEnviron) -> str:
    content = decode_request(configuration, environ,
                             read_raw_request_body(configuration, environ))
    logger.debug("Request content:\n%s", content)
    return content


def redirect(location: str, status: int = client.FOUND) -> types.WSGIResponse:
    return (status,
            {"Location": location, "Content-Type": "text/plain"},
            "Redirected to %s" % location)


def serve_folder(folder: str, base_prefix: str, path: str,
                 path_prefix: str = "/.web", index_file: str = "index.html",
                 mimetypes: Mapping[str, str] = MIMETYPES,
                 fallback_mimetype: str = FALLBACK_MIMETYPE,
                 ) -> types.WSGIResponse:
    if path != path_prefix and not path.startswith(path_prefix):
        raise ValueError("path must start with path_prefix: %r --> %r" %
                         (path_prefix, path))
    assert pathutils.sanitize_path(path) == path
    try:
        filesystem_path = pathutils.path_to_filesystem(
            folder, path[len(path_prefix):].strip("/"))
    except ValueError as e:
        logger.debug("Web content with unsafe path %r requested: %s",
                     path, e, exc_info=True)
        return NOT_FOUND
    if os.path.isdir(filesystem_path) and not path.endswith("/"):
        return redirect(base_prefix + path + "/")
    if os.path.isdir(filesystem_path) and index_file:
        filesystem_path = os.path.join(filesystem_path, index_file)
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
