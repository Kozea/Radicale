# -*- coding: utf-8 -*-
#
# This file is part of Radicale Server - Calendar Server
# Copyright © 2008-2012 Guillaume Ayoub
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

from radicale import acl, config, ical, log, storage, xmlutils


VERSION = "0.7"


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

        # Test if the SSL files can be read
        for name in ("certificate", "key"):
            filename = config.get("server", name)
            try:
                open(filename, "r").close()
            except IOError as exception:
                log.LOGGER.warn(
                    "Error while reading SSL %s %r: %s" % (
                        name, filename, exception))

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

    def address_string(self):
        """Client address, formatted for logging."""
        if config.getboolean("server", "dns_lookup"):
            return \
                wsgiref.simple_server.WSGIRequestHandler.address_string(self)
        else:
            return self.client_address[0]


class Application(object):
    """WSGI application managing collections."""
    def __init__(self):
        """Initialize application."""
        super(Application, self).__init__()
        self.acl = acl.load()
        storage.load()
        self.encoding = config.get("encoding", "request")
        if config.getboolean("logging", "full_environment"):
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

        # Find collection(s)
        items = ical.Collection.from_path(
            environ["PATH_INFO"], environ.get("HTTP_DEPTH", "0"))

        # Get function corresponding to method
        function = getattr(self, environ["REQUEST_METHOD"].lower())

        # Check rights
        if not items or not self.acl or function == self.options:
            # No collection, or no acl, or OPTIONS request: don't check rights
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
            collections = []
            for collection in items:
                if not isinstance(collection, ical.Collection):
                    if last_allowed:
                        collections.append(collection)
                    continue

                if collection.owner in acl.PUBLIC_USERS:
                    log.LOGGER.info("Public collection")
                    collections.append(collection)
                    last_allowed = True
                else:
                    log.LOGGER.info(
                        "Checking rights for collection owned by %s" % (
                            collection.owner or "nobody"))
                    if self.acl.has_right(collection.owner, user, password):
                        log.LOGGER.info(
                            "%s allowed" % (user or "Anonymous user"))
                        collections.append(collection)
                        last_allowed = True
                    else:
                        log.LOGGER.info(
                            "%s refused" % (user or "Anonymous user"))
                        last_allowed = False

            if collections:
                # Collections found
                status, headers, answer = function(
                    environ, collections, content, user)
            elif user and last_allowed is None:
                # Good user and no collections found, redirect user to home
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
        log.LOGGER.debug("Answer status: %s" % status)
        start_response(status, list(headers.items()))

        # Return response content
        return [answer] if answer else []

    # All these functions must have the same parameters, some are useless
    # pylint: disable=W0612,W0613,R0201

    def delete(self, environ, collections, content, user):
        """Manage DELETE request."""
        collection = collections[0]

        if collection.path == environ["PATH_INFO"].strip("/"):
            # Path matching the collection, the collection must be deleted
            item = collection
        else:
            # Try to get an item matching the path
            item = collection.get_item(
                xmlutils.name_from_path(environ["PATH_INFO"], collection))

        # Evolution bug workaround
        etag = environ.get("HTTP_IF_MATCH", item.etag).replace("\\", "")
        if item and etag == item.etag:
            # No ETag precondition or precondition verified, delete item
            answer = xmlutils.delete(environ["PATH_INFO"], collection)
            status = client.NO_CONTENT
        else:
            # No item or ETag precondition not verified, do not delete item
            answer = None
            status = client.PRECONDITION_FAILED
        return status, {}, answer

    def get(self, environ, collections, content, user):
        """Manage GET request.

        In Radicale, GET requests create collections when the URL is not
        available. This is useful for clients with no MKCOL or MKCALENDAR
        support.

        """
        # Display a "Radicale works!" message if the root URL is requested
        if environ["PATH_INFO"] == "/":
            headers = {"Content-type": "text/html"}
            answer = "<!DOCTYPE html>\n<title>Radicale</title>Radicale works!"
            return client.OK, headers, answer

        collection = collections[0]
        item_name = xmlutils.name_from_path(environ["PATH_INFO"], collection)

        if item_name:
            # Get collection item
            item = collection.get_item(item_name)
            if item:
                items = collection.timezones
                items.append(item)
                answer_text = ical.serialize(
                    collection.tag, collection.headers, items)
                etag = item.etag
            else:
                return client.GONE, {}, None
        else:
            # Create the collection if it does not exist
            if not collection.exists:
                collection.write()

            # Get whole collection
            answer_text = collection.text
            etag = collection.etag

        headers = {
            "Content-Type": collection.mimetype,
            "Last-Modified": collection.last_modified,
            "ETag": etag}
        answer = answer_text.encode(self.encoding)
        return client.OK, headers, answer

    def head(self, environ, collections, content, user):
        """Manage HEAD request."""
        status, headers, answer = self.get(environ, collections, content, user)
        return status, headers, None

    def mkcalendar(self, environ, collections, content, user):
        """Manage MKCALENDAR request."""
        collection = collections[0]
        props = xmlutils.props_from_request(content)
        timezone = props.get("C:calendar-timezone")
        if timezone:
            collection.replace("", timezone)
            del props["C:calendar-timezone"]
        with collection.props as collection_props:
            for key, value in props.items():
                collection_props[key] = value
        collection.write()
        return client.CREATED, {}, None

    def mkcol(self, environ, collections, content, user):
        """Manage MKCOL request."""
        collection = collections[0]
        props = xmlutils.props_from_request(content)
        with collection.props as collection_props:
            for key, value in props.items():
                collection_props[key] = value
        collection.write()
        return client.CREATED, {}, None

    def move(self, environ, collections, content, user):
        """Manage MOVE request."""
        from_collection = collections[0]
        from_name = xmlutils.name_from_path(
            environ["PATH_INFO"], from_collection)
        if from_name:
            item = from_collection.get_item(from_name)
            if item:
                # Move the item
                to_url_parts = urlparse(environ["HTTP_DESTINATION"])
                if to_url_parts.netloc == environ["HTTP_HOST"]:
                    to_url = to_url_parts.path
                    to_path, to_name = to_url.rstrip("/").rsplit("/", 1)
                    to_collection = ical.Collection.from_path(
                        to_path, depth="0")[0]
                    to_collection.append(to_name, item.text)
                    from_collection.remove(from_name)
                    return client.CREATED, {}, None
                else:
                    # Remote destination server, not supported
                    return client.BAD_GATEWAY, {}, None
            else:
                # No item found
                return client.GONE, {}, None
        else:
            # Moving collections, not supported
            return client.FORBIDDEN, {}, None

    def options(self, environ, collections, content, user):
        """Manage OPTIONS request."""
        headers = {
            "Allow": "DELETE, HEAD, GET, MKCALENDAR, MKCOL, MOVE, " \
                "OPTIONS, PROPFIND, PROPPATCH, PUT, REPORT",
            "DAV": "1, 2, 3, calendar-access, addressbook, extended-mkcol"}
        return client.OK, headers, None

    def propfind(self, environ, collections, content, user):
        """Manage PROPFIND request."""
        headers = {
            "DAV": "1, 2, 3, calendar-access, addressbook, extended-mkcol",
            "Content-Type": "text/xml"}
        answer = xmlutils.propfind(
            environ["PATH_INFO"], content, collections, user)
        return client.MULTI_STATUS, headers, answer

    def proppatch(self, environ, collections, content, user):
        """Manage PROPPATCH request."""
        collection = collections[0]
        answer = xmlutils.proppatch(environ["PATH_INFO"], content, collection)
        headers = {
            "DAV": "1, 2, 3, calendar-access, addressbook, extended-mkcol",
            "Content-Type": "text/xml"}
        return client.MULTI_STATUS, headers, answer

    def put(self, environ, collections, content, user):
        """Manage PUT request."""
        collection = collections[0]
        collection.set_mimetype(environ.get("CONTENT_TYPE"))
        headers = {}
        item_name = xmlutils.name_from_path(environ["PATH_INFO"], collection)
        item = collection.get_item(item_name)

        # Evolution bug workaround
        etag = environ.get("HTTP_IF_MATCH", "").replace("\\", "")
        if (not item and not etag) or (
            item and ((etag or item.etag) == item.etag)):
            # PUT allowed in 3 cases
            # Case 1: No item and no ETag precondition: Add new item
            # Case 2: Item and ETag precondition verified: Modify item
            # Case 3: Item and no Etag precondition: Force modifying item
            xmlutils.put(environ["PATH_INFO"], content, collection)
            status = client.CREATED
            headers["ETag"] = collection.get_item(item_name).etag
        else:
            # PUT rejected in all other cases
            status = client.PRECONDITION_FAILED
        return status, headers, None

    def report(self, environ, collections, content, user):
        """Manage REPORT request."""
        collection = collections[0]
        headers = {"Content-Type": "text/xml"}
        answer = xmlutils.report(environ["PATH_INFO"], content, collection)
        return client.MULTI_STATUS, headers, answer

    # pylint: enable=W0612,W0613,R0201
