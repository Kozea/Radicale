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

"""
Helper functions for HTTP.

"""

from http import client

from radicale.log import logger

NOT_ALLOWED = (
    client.FORBIDDEN, (("Content-Type", "text/plain"),),
    "Access to the requested resource forbidden.")
FORBIDDEN = (
    client.FORBIDDEN, (("Content-Type", "text/plain"),),
    "Action on the requested resource refused.")
BAD_REQUEST = (
    client.BAD_REQUEST, (("Content-Type", "text/plain"),), "Bad Request")
NOT_FOUND = (
    client.NOT_FOUND, (("Content-Type", "text/plain"),),
    "The requested resource could not be found.")
CONFLICT = (
    client.CONFLICT, (("Content-Type", "text/plain"),),
    "Conflict in the request.")
METHOD_NOT_ALLOWED = (
    client.METHOD_NOT_ALLOWED, (("Content-Type", "text/plain"),),
    "The method is not allowed on the requested resource.")
PRECONDITION_FAILED = (
    client.PRECONDITION_FAILED,
    (("Content-Type", "text/plain"),), "Precondition failed.")
REQUEST_TIMEOUT = (
    client.REQUEST_TIMEOUT, (("Content-Type", "text/plain"),),
    "Connection timed out.")
REQUEST_ENTITY_TOO_LARGE = (
    client.REQUEST_ENTITY_TOO_LARGE, (("Content-Type", "text/plain"),),
    "Request body too large.")
REMOTE_DESTINATION = (
    client.BAD_GATEWAY, (("Content-Type", "text/plain"),),
    "Remote destination not supported.")
DIRECTORY_LISTING = (
    client.FORBIDDEN, (("Content-Type", "text/plain"),),
    "Directory listings are not supported.")
INTERNAL_SERVER_ERROR = (
    client.INTERNAL_SERVER_ERROR, (("Content-Type", "text/plain"),),
    "A server error occurred.  Please contact the administrator.")

DAV_HEADERS = "1, 2, 3, calendar-access, addressbook, extended-mkcol"


def decode_request(configuration, environ, text):
    """Try to magically decode ``text`` according to given ``environ``."""
    # List of charsets to try
    charsets = []

    # First append content charset given in the request
    content_type = environ.get("CONTENT_TYPE")
    if content_type and "charset=" in content_type:
        charsets.append(
            content_type.split("charset=")[1].split(";")[0].strip())
    # Then append default Radicale charset
    charsets.append(configuration.get("encoding", "request"))
    # Then append various fallbacks
    charsets.append("utf-8")
    charsets.append("iso8859-1")
    # Remove duplicates
    for i, s in reversed(list(enumerate(charsets))):
        if s in charsets[:i]:
            del charsets[i]

    # Try to decode
    for charset in charsets:
        try:
            return text.decode(charset)
        except UnicodeDecodeError:
            pass
    raise UnicodeDecodeError("decode_request", text, 0, len(text),
                             "all codecs failed [%s]" % ", ".join(charsets))


def read_raw_request_body(configuration, environ):
    content_length = int(environ.get("CONTENT_LENGTH") or 0)
    if not content_length:
        return b""
    content = environ["wsgi.input"].read(content_length)
    if len(content) < content_length:
        raise RuntimeError("Request body too short: %d" % len(content))
    return content


def read_request_body(configuration, environ):
    content = decode_request(
        configuration, environ, read_raw_request_body(configuration, environ))
    logger.debug("Request content:\n%s", content)
    return content
