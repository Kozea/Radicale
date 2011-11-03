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
import pprint
import base64
import posixpath
import socket
import ssl
import wsgiref.simple_server
# Manage Python2/3 different modules
# pylint: disable=F0401,E0611
try:
    from http import client
    from urllib.parse import quote, unquote, urlparse
except ImportError:
    import httplib as client
    from urllib import quote, unquote
    from urlparse import urlparse
# pylint: enable=F0401,E0611

from radicale import acl, config, ical, log, xmlutils


VERSION = "0.6.3"


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
        if config.getboolean('logging', 'full_environment'):
            self.headers_log = lambda environ: environ

    # This method is overriden in __init__ if full_environment is set
    # pylint: disable=E0202
    @staticmethod
    def headers_log(environ):
        """Remove environment variables from the headers for logging."""
        request_environ = dict(environ)
        for shell_variable in os.environ:
            if shell_variable in request_environ:
                del request_environ[shell_variable]
        return request_environ
    # pylint: enable=E0202

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

    @staticmethod
    def sanitize_uri(uri):
        """Unquote and remove /../ to prevent access to other data."""
        uri = unquote(uri)
        trailing_slash = "/" if uri.endswith("/") else ""
        uri = posixpath.normpath(uri)
        trailing_slash = "" if uri == "/" else trailing_slash
        return uri + trailing_slash

    def __call__(self, environ, start_response):
        """Manage a request."""
        log.LOGGER.info("%s request at %s received" % (
                environ["REQUEST_METHOD"], environ["PATH_INFO"]))
        headers = pprint.pformat(self.headers_log(environ))
        log.LOGGER.debug("Request headers:\n%s" % headers)

        # Sanitize request URI
        environ["PATH_INFO"] = self.sanitize_uri(environ["PATH_INFO"])
        log.LOGGER.debug("Sanitized path: %s", environ["PATH_INFO"])

        # Get content
        content_length = int(environ.get("CONTENT_LENGTH") or 0)
        if content_length:
            content = self.decode(
                environ["wsgi.input"].read(content_length), environ)
            log.LOGGER.debug("Request content:\n%s" % content)
        else:
            content = None

        # Find calendar(s)
        items = ical.Calendar.from_path(
            environ["PATH_INFO"], environ.get("HTTP_DEPTH", "0"))

        # Get function corresponding to method
        function = getattr(self, environ["REQUEST_METHOD"].lower())

        # Check rights
        if not items or not self.acl:
            # No calendar or no acl, don't check rights
            status, headers, answer = function(environ, items, content, None)
        else:
            # Ask authentication backend to check rights
            authorization = environ.get("HTTP_AUTHORIZATION", None)

            if authorization:
                auth = authorization.lstrip("Basic").strip().encode("ascii")
                user, password = self.decode(
                    base64.b64decode(auth), environ).split(":")
            else:
                user = password = None

            last_allowed = None
            calendars = []
            for calendar in items:
                if not isinstance(calendar, ical.Calendar):
                    if last_allowed:
                        calendars.append(calendar)
                    continue

                if calendar.owner in acl.PUBLIC_USERS:
                    log.LOGGER.info("Public calendar")
                    calendars.append(calendar)
                    last_allowed = True
                else:
                    log.LOGGER.info(
                        "Checking rights for calendar owned by %s" % (
                            calendar.owner or "nobody"))
                    if self.acl.has_right(calendar.owner, user, password):
                        log.LOGGER.info(
                            "%s allowed" % (user or "Anonymous user"))
                        calendars.append(calendar)
                        last_allowed = True
                    else:
                        log.LOGGER.info(
                            "%s refused" % (user or "Anonymous user"))
                        last_allowed = False

            if calendars:
                # Calendars found
                status, headers, answer = function(
                    environ, calendars, content, user)
            elif user and last_allowed is None:
                # Good user and no calendars found, redirect user to home
                location = "/%s/" % str(quote(user))
                log.LOGGER.info("redirecting to %s" % location)
                status = client.FOUND
                headers = {"Location": location}
                answer = "Redirecting to %s" % location
            else:
                # Unknown or unauthorized user
                status = client.UNAUTHORIZED
                headers = {
                    "WWW-Authenticate":
                    "Basic realm=\"Radicale Server - Password Required\""}
                answer = None

        # Set content length
        if answer:
            log.LOGGER.debug(
                "Response content:\n%s" % self.decode(answer, environ))
            headers["Content-Length"] = str(len(answer))

        # Start response
        status = "%i %s" % (status, client.responses.get(status, "Unknown"))
        start_response(status, list(headers.items()))

        # Return response content
        return [answer] if answer else []

    # All these functions must have the same parameters, some are useless
    # pylint: disable=W0612,W0613,R0201

    def delete(self, environ, calendars, content, user):
        """Manage DELETE request."""
        calendar = calendars[0]
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

    def get(self, environ, calendars, content, user):
        """Manage GET request."""
        # Display a "Radicale works!" message if the root URL is requested
        if environ["PATH_INFO"] == "/":
            headers = {"Content-type": "text/html"}
            answer = "<!DOCTYPE html>\n<title>Radicale</title>Radicale works!"
            return client.OK, headers, answer

        calendar = calendars[0]
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

    def head(self, environ, calendars, content, user):
        """Manage HEAD request."""
        status, headers, answer = self.get(environ, calendars, content, user)
        return status, headers, None

    def mkcalendar(self, environ, calendars, content, user):
        """Manage MKCALENDAR request."""
        calendar = calendars[0]
        props = xmlutils.props_from_request(content)
        timezone = props.get('C:calendar-timezone')
        if timezone:
            calendar.replace('', timezone)
            del props['C:calendar-timezone']
        with calendar.props as calendar_props:
            for key, value in props.items():
                calendar_props[key] = value
        calendar.write()
        return client.CREATED, {}, None

    def move(self, environ, calendars, content, user):
        """Manage MOVE request."""
        from_calendar = calendars[0]
        from_name = xmlutils.name_from_path(
            environ["PATH_INFO"], from_calendar)
        if from_name:
            item = from_calendar.get_item(from_name)
            if item:
                # Move the item
                to_url_parts = urlparse(environ["HTTP_DESTINATION"])
                if to_url_parts.netloc == environ["HTTP_HOST"]:
                    to_url = to_url_parts.path
                    to_path, to_name = to_url.rstrip("/").rsplit("/", 1)
                    to_calendar = ical.Calendar.from_path(
                        to_path, depth="0")[0]
                    to_calendar.append(to_name, item.text)
                    from_calendar.remove(from_name)
                    return client.CREATED, {}, None
                else:
                    # Remote destination server, not supported
                    return client.BAD_GATEWAY, {}, None
            else:
                # No item found
                return client.GONE, {}, None
        else:
            # Moving calendars, not supported
            return client.FORBIDDEN, {}, None

    def options(self, environ, calendars, content, user):
        """Manage OPTIONS request."""
        headers = {
            "Allow": "DELETE, HEAD, GET, MKCALENDAR, MOVE, " \
                "OPTIONS, PROPFIND, PROPPATCH, PUT, REPORT",
            "DAV": "1, calendar-access"}
        return client.OK, headers, None

    def propfind(self, environ, calendars, content, user):
        """Manage PROPFIND request."""
        headers = {
            "DAV": "1, calendar-access",
            "Content-Type": "text/xml"}
        answer = xmlutils.propfind(
            environ["PATH_INFO"], content, calendars, user)
        return client.MULTI_STATUS, headers, answer

    def proppatch(self, environ, calendars, content, user):
        """Manage PROPPATCH request."""
        calendar = calendars[0]
        answer = xmlutils.proppatch(environ["PATH_INFO"], content, calendar)
        headers = {
            "DAV": "1, calendar-access",
            "Content-Type": "text/xml"}
        return client.MULTI_STATUS, headers, answer

    def put(self, environ, calendars, content, user):
        """Manage PUT request."""
        calendar = calendars[0]
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

    def report(self, environ, calendars, content, user):
        """Manage REPORT request."""
        # TODO: support multiple calendars here
        calendar = calendars[0]
        headers = {'Content-Type': 'text/xml'}
        answer = xmlutils.report(environ["PATH_INFO"], content, calendar)
        return client.MULTI_STATUS, headers, answer

    # pylint: enable=W0612,W0613,R0201
