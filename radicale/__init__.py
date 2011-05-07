# -*- coding: utf-8 -*-
#
# This file is part of Radicale Server - Calendar Server
# Copyright © 2008-2011 Guillaume Ayoub
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

This module offers a WSGI application class.

To use this module, you should take a look at the file ``radicale.py`` that
should have been included in this package.

"""

import os
import posixpath
import base64
import socket
import wsgiref.simple_server
# Manage Python2/3 different modules
# pylint: disable=F0401
try:
    from http import client, server
except ImportError:
    import httplib as client
    import BaseHTTPServer as server
# pylint: enable=F0401

from radicale import acl, config, ical, log, xmlutils


VERSION = "git"


class HTTPServer(wsgiref.simple_server.WSGIServer, object):
    """HTTP server."""
    def __init__(self, address, handler, bind_and_activate=True):
        """Create server."""
        ipv6 = ":" in address[0]

        if ipv6:
            self.address_family = socket.AF_INET6

        # Do not bind and activate, as we might change socket options
        super(HTTPServer, self).__init__(address, handler, False)

        if ipv6:
            # Only allow IPv6 connections to the IPv6 socket
            self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)

        if bind_and_activate:
            self.server_bind()
            self.server_activate()


class HTTPSServer(HTTPServer):
    """HTTPS server."""
    def __init__(self, address, handler):
        """Create server by wrapping HTTP socket in an SSL socket."""
        # Fails with Python 2.5, import if needed
        # pylint: disable=F0401
        import ssl
        # pylint: enable=F0401

        super(HTTPSServer, self).__init__(address, handler, False)

        self.socket = ssl.wrap_socket(
            self.socket,
            server_side=True,
            certfile=config.get("server", "certificate"),
            keyfile=config.get("server", "key"),
            ssl_version=ssl.PROTOCOL_SSLv23)

        self.server_bind()
        self.server_activate()


class RequestHandler(wsgiref.simple_server.WSGIRequestHandler):
    """HTTP requests handler."""
    def log_message(self, *args, **kwargs):
        """Disable inner logging management."""


class Application(object):
    """WSGI application managing calendars."""
    def __init__(self):
        """Initialize application."""
        super(Application, self).__init__()
        self.acl = acl.load()
        self.encoding = config.get("encoding", "request")

    def decode(self, text, environ):
        """Try to magically decode ``text`` according to given ``environ``."""
        # List of charsets to try
        charsets = []

        # First append content charset given in the request
        content_type = environ.get("CONTENT_TYPE")
        if content_type and "charset=" in content_type:
            charsets.append(content_type.split("charset=")[1].strip())
        # Then append default Radicale charset
        charsets.append(self.encoding)
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

    def __call__(self, environ, start_response):
        """Manage a request."""
        log.LOGGER.info("%s request at %s received" % (
                environ["REQUEST_METHOD"], environ["PATH_INFO"]))
        log.LOGGER.debug("Request headers:\n%s" % environ.items())

        # Get content
        content_length = int(environ.get("CONTENT_LENGTH") or 0)
        if content_length:
            content = self.decode(
                environ["wsgi.input"].read(content_length), environ)
            log.LOGGER.debug("Request content:\n%s" % content)
        else:
            content = None

        # Find calendar
        attributes = posixpath.normpath(
            environ["PATH_INFO"].strip("/")).split("/")
        if attributes:
            if attributes[-1].endswith(".ics"):
                attributes.pop()
            path = "/".join(attributes[:min(len(attributes), 2)])
            calendar = ical.Calendar(path)
        else:
            calendar = None

        # Get function corresponding to method
        function = getattr(self, environ["REQUEST_METHOD"].lower())

        # Check rights
        if not calendar or not self.acl:
            # No calendar or no acl, don't check rights
            status, headers, answer = function(environ, calendar, content)
        elif calendar.owner is None and config.getboolean("acl", "personal"):
            # No owner and personal calendars, don't check rights
            status, headers, answer = function(environ, calendar, content)
        else:
            # Ask authentication backend to check rights
            log.LOGGER.info(
                "Checking rights for calendar owned by %s" % calendar.owner)
            authorization = environ.get("HTTP_AUTHORIZATION", None)

            if authorization:
                auth = authorization.lstrip("Basic").strip().encode("ascii")
                user, password = self.decode(
                    base64.b64decode(auth), environ).split(":")
            else:
                user = password = None

            if self.acl.has_right(calendar.owner, user, password):
                log.LOGGER.info("%s allowed" % calendar.owner)
                status, headers, answer = function(environ, calendar, content)
            else:
                log.LOGGER.info("%s refused" % calendar.owner)
                status = client.UNAUTHORIZED
                headers = {
                    "WWW-Authenticate":
                    "Basic realm=\"Radicale Server - Password Required\""}
                answer = None

        # Set content length
        if answer:
            log.LOGGER.debug("Response content:\n%s" % answer)
            headers["Content-Length"] = "%i" % len(answer)

        # Start response
        status = "%i %s" % (status, client.responses.get(status, ""))
        start_response(status, list(headers.items()))

        # Return response content
        return [answer] if answer else []

    # All these functions must have the same parameters, some are useless
    # pylint: disable=W0612,W0613,R0201

    def get(self, environ, calendar, content):
        """Manage GET request."""
        item_name = xmlutils.name_from_path(environ["PATH_INFO"], calendar)
        if item_name:
            # Get calendar item
            item = calendar.get_item(item_name)
            if item:
                items = calendar.timezones
                items.append(item)
                answer_text = ical.serialize(
                    headers=calendar.headers, items=items)
                etag = item.etag
            else:
                return client.GONE, {}, None
        else:
            # Get whole calendar
            answer_text = calendar.text
            etag = calendar.etag

        headers = {
            "Content-Type": "text/calendar",
            "Last-Modified": calendar.last_modified,
            "ETag": etag}
        answer = answer_text.encode(self.encoding)
        return client.OK, headers, answer

    def head(self, environ, calendar, content):
        """Manage HEAD request."""
        status, headers, answer = self.get(environ, calendar, content)
        return status, headers, None

    def delete(self, environ, calendar, content):
        """Manage DELETE request."""
        item = calendar.get_item(
            xmlutils.name_from_path(environ["PATH_INFO"], calendar))
        if item and environ.get("HTTP_IF_MATCH", item.etag) == item.etag:
            # No ETag precondition or precondition verified, delete item
            answer = xmlutils.delete(environ["PATH_INFO"], calendar)
            status = client.NO_CONTENT
        else:
            # No item or ETag precondition not verified, do not delete item
            answer = None
            status = client.PRECONDITION_FAILED
        return status, {}, answer

    def mkcalendar(self, environ, calendar, content):
        """Manage MKCALENDAR request."""
        return client.CREATED, {}, None

    def options(self, environ, calendar, content):
        """Manage OPTIONS request."""
        headers = {
            "Allow": "DELETE, HEAD, GET, MKCALENDAR, " \
                "OPTIONS, PROPFIND, PROPPATCH, PUT, REPORT",
            "DAV": "1, calendar-access"}
        return client.OK, headers, None

    def propfind(self, environ, calendar, content):
        """Manage PROPFIND request."""
        headers = {
            "DAV": "1, calendar-access",
            "Content-Type": "text/xml"}
        answer = xmlutils.propfind(
            environ["PATH_INFO"], content, calendar,
            environ.get("HTTP_DEPTH", "infinity"))
        return client.MULTI_STATUS, headers, answer

    def proppatch(self, environ, calendar, content):
        """Manage PROPPATCH request."""
        xmlutils.proppatch(environ["PATH_INFO"], content, calendar)
        headers = {
            "DAV": "1, calendar-access",
            "Content-Type": "text/xml"}
        return client.MULTI_STATUS, headers, None

    def put(self, environ, calendar, content):
        """Manage PUT request."""
        headers = {}
        item_name = xmlutils.name_from_path(environ["PATH_INFO"], calendar)
        item = calendar.get_item(item_name)
        if (not item and not environ.get("HTTP_IF_MATCH")) or (
            item and environ.get("HTTP_IF_MATCH", item.etag) == item.etag):
            # PUT allowed in 3 cases
            # Case 1: No item and no ETag precondition: Add new item
            # Case 2: Item and ETag precondition verified: Modify item
            # Case 3: Item and no Etag precondition: Force modifying item
            xmlutils.put(environ["PATH_INFO"], content, calendar)
            status = client.CREATED
            headers["ETag"] = calendar.get_item(item_name).etag
        else:
            # PUT rejected in all other cases
            status = client.PRECONDITION_FAILED
        return status, headers, None

    def report(self, environ, calendar, content):
        """Manage REPORT request."""
        answer = xmlutils.report(environ["PATH_INFO"], content, calendar)
        return client.MULTI_STATUS, {}, answer

    # pylint: enable=W0612,W0613,R0201
