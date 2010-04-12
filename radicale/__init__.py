# -*- coding: utf-8 -*-
#
# This file is part of Radicale Server - Calendar Server
# Copyright © 2008-2010 Guillaume Ayoub
# Copyright © 2008 Nicolas Kandel
# Copyright © 2008 Pascal Halter
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
Radicale Server module.

This module offers 3 useful classes:

- ``HTTPServer`` is a simple HTTP server;
- ``HTTPSServer`` is a HTTPS server, wrapping the HTTP server in a socket
  managing SSL connections;
- ``CalendarHTTPHandler`` is a CalDAV request handler for HTTP(S) servers.

To use this module, you should take a look at the file ``radicale.py`` that
should have been included in this package.

"""

import os
import posixpath
import base64
import socket
# Manage Python2/3 different modules
# pylint: disable-msg=F0401
try:
    from http import client, server
except ImportError:
    import httplib as client
    import BaseHTTPServer as server
# pylint: enable-msg=F0401

from radicale import acl, config, ical, xmlutils


def _check(request, function):
    """Check if user has sufficient rights for performing ``request``."""
    authorization = request.headers.get("Authorization", None)
    if authorization:
        challenge = authorization.lstrip("Basic").strip().encode("ascii")
        # ``_check`` decorator can access ``request`` protected functions
        # pylint: disable-msg=W0212
        plain = request._decode(base64.b64decode(challenge))
        # pylint: enable-msg=W0212
        user, password = plain.split(":")
    else:
        user = password = None

    if request.server.acl.has_right(user, password):
        function(request)
    else:
        request.send_response(client.UNAUTHORIZED)
        request.send_header(
            "WWW-Authenticate",
            "Basic realm=\"Radicale Server - Password Required\"")
        request.end_headers()


class HTTPServer(server.HTTPServer):
    """HTTP server."""
    # Maybe a Pylint bug, ``__init__`` calls ``server.HTTPServer.__init__``
    # pylint: disable-msg=W0231
    def __init__(self, address, handler):
        """Create server."""
        server.HTTPServer.__init__(self, address, handler)
        self.acl = acl.load()
    # pylint: enable-msg=W0231


class HTTPSServer(HTTPServer):
    """HTTPS server."""
    def __init__(self, address, handler):
        """Create server by wrapping HTTP socket in an SSL socket."""
        # Fails with Python 2.5, import if needed
        # pylint: disable-msg=F0401
        import ssl
        # pylint: enable-msg=F0401

        HTTPServer.__init__(self, address, handler)
        self.socket = ssl.wrap_socket(
            socket.socket(self.address_family, self.socket_type),
            server_side=True,
            certfile=config.get("server", "certificate"),
            keyfile=config.get("server", "key"),
            ssl_version=ssl.PROTOCOL_SSLv23)
        self.server_bind()
        self.server_activate()


class CalendarHTTPHandler(server.BaseHTTPRequestHandler):
    """HTTP requests handler for calendars."""
    _encoding = config.get("encoding", "request")

    # Decorator checking rights before performing request
    check_rights = lambda function: lambda request: _check(request, function)

    @property
    def _calendar(self):
        """The ``ical.Calendar`` object corresponding to the given path."""
        # ``self.path`` must be something like a posix path
        # ``normpath`` should clean malformed and malicious request paths
        attributes = posixpath.normpath(self.path.strip("/")).split("/")
        if len(attributes) >= 2:
            path = "%s/%s" % (attributes[0], attributes[1])
            return ical.Calendar(path)

    def _decode(self, text):
        """Try to decode text according to various parameters."""
        # List of charsets to try
        charsets = []

        # First append content charset given in the request
        content_type = self.headers.get("Content-Type", None)
        if content_type and "charset=" in content_type:
            charsets.append(content_type.split("charset=")[1].strip())
        # Then append default Radicale charset
        charsets.append(self._encoding)
        # Then append various fallbacks
        charsets.append("utf-8")
        charsets.append("iso8859-1")

        # Try to decode
        for charset in charsets:
            try:
                return text.decode(charset)
            except UnicodeDecodeError:
                pass
        raise UnicodeDecodeError

    # Naming methods ``do_*`` is OK here
    # pylint: disable-msg=C0103

    @check_rights
    def do_GET(self):
        """Manage GET request."""
        answer = self._calendar.text.encode(self._encoding)

        self.send_response(client.OK)
        self.send_header("Content-Length", len(answer))
        self.end_headers()
        self.wfile.write(answer)

    @check_rights
    def do_DELETE(self):
        """Manage DELETE request."""
        item = self._calendar.get_item(xmlutils.name_from_path(self.path))
        if item and self.headers.get("If-Match", item.etag) == item.etag:
            # No ETag precondition or precondition verified, delete item
            answer = xmlutils.delete(self.path, self._calendar)

            self.send_response(client.NO_CONTENT)
            self.send_header("Content-Length", len(answer))
            self.end_headers()
            self.wfile.write(answer)
        else:
            # No item or ETag precondition not verified, do not delete item
            self.send_response(client.PRECONDITION_FAILED)

    def do_OPTIONS(self):
        """Manage OPTIONS request."""
        self.send_response(client.OK)
        self.send_header("Allow", "DELETE, GET, OPTIONS, PROPFIND, PUT, REPORT")
        self.send_header("DAV", "1, calendar-access")
        self.end_headers()

    def do_PROPFIND(self):
        """Manage PROPFIND request."""
        xml_request = self.rfile.read(int(self.headers["Content-Length"]))
        answer = xmlutils.propfind(self.path, xml_request, self._calendar)

        self.send_response(client.MULTI_STATUS)
        self.send_header("DAV", "1, calendar-access")
        self.send_header("Content-Length", len(answer))
        self.end_headers()
        self.wfile.write(answer)

    @check_rights
    def do_PUT(self):
        """Manage PUT request."""
        item = self._calendar.get_item(xmlutils.name_from_path(self.path))
        if (not item and not self.headers.get("If-Match")) or \
                (item and self.headers.get("If-Match", item.etag) == item.etag):
            # PUT allowed in 3 cases
            # Case 1: No item and no ETag precondition: Add new item
            # Case 2: Item and ETag precondition verified: Modify item
            # Case 3: Item and no Etag precondition: Force modifying item
            ical_request = self._decode(
                self.rfile.read(int(self.headers["Content-Length"])))
            xmlutils.put(self.path, ical_request, self._calendar)

            self.send_response(client.CREATED)
        else:
            # PUT rejected in all other cases
            self.send_response(client.PRECONDITION_FAILED)

    @check_rights
    def do_REPORT(self):
        """Manage REPORT request."""
        xml_request = self.rfile.read(int(self.headers["Content-Length"]))
        answer = xmlutils.report(self.path, xml_request, self._calendar)

        self.send_response(client.MULTI_STATUS)
        self.send_header("Content-Length", len(answer))
        self.end_headers()
        self.wfile.write(answer)

    # pylint: enable-msg=C0103
