# -*- coding: utf-8 -*-
#
# This file is part of Radicale Server - Calendar Server
# Copyright © 2008 Nicolas Kandel
# Copyright © 2008 Pascal Halter
# Copyright © 2008-2013 Guillaume Ayoub
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
import sys
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
    from urllib.parse import unquote, urlparse
except ImportError:
    import httplib as client
    from urllib import unquote
    from urlparse import urlparse
# pylint: enable=F0401,E0611

from . import auth, config, ical, log, rights, storage, xmlutils


VERSION = "0.9b1"

# Standard "not allowed" response that is returned when an authenticated user
# tries to access information they don't have rights to
NOT_ALLOWED = (client.FORBIDDEN, {}, None)


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

        ssl_kwargs = dict(
            server_side=True,
            certfile=config.get("server", "certificate"),
            keyfile=config.get("server", "key"),
            ssl_version=getattr(ssl, config.get("server", "protocol"),
                                ssl.PROTOCOL_SSLv23)
        )
        # add ciphers argument only if supported (Python 2.7+)
        if sys.version_info >= (2, 7):
            ssl_kwargs["ciphers"] = config.get("server", "ciphers") or None

        self.socket = ssl.wrap_socket(self.socket, **ssl_kwargs)

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
        auth.load()
        storage.load()
        rights.load()
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

    def collect_allowed_items(self, items, user):
        """Get items from request that user is allowed to access."""
        read_last_collection_allowed = None
        write_last_collection_allowed = None
        read_allowed_items = []
        write_allowed_items = []

        for item in items:
            if isinstance(item, ical.Collection):
                if rights.authorized(user, item, "r"):
                    log.LOGGER.debug(
                        "%s has read access to collection %s" %
                        (user or "Anonymous", item.url or "/"))
                    read_last_collection_allowed = True
                    read_allowed_items.append(item)
                else:
                    log.LOGGER.debug(
                        "%s has NO read access to collection %s" %
                        (user or "Anonymous", item.url or "/"))
                    read_last_collection_allowed = False

                if rights.authorized(user, item, "w"):
                    log.LOGGER.debug(
                        "%s has write access to collection %s" %
                        (user or "Anonymous", item.url or "/"))
                    write_last_collection_allowed = True
                    write_allowed_items.append(item)
                else:
                    log.LOGGER.debug(
                        "%s has NO write access to collection %s" %
                        (user or "Anonymous", item.url or "/"))
                    write_last_collection_allowed = False
            else:
                # item is not a collection, it's the child of the last
                # collection we've met in the loop. Only add this item
                # if this last collection was allowed.
                if read_last_collection_allowed:
                    log.LOGGER.debug(
                        "%s has read access to item %s" %
                        (user or "Anonymous", item.name))
                    read_allowed_items.append(item)
                else:
                    log.LOGGER.debug(
                        "%s has NO read access to item %s" %
                        (user or "Anonymous", item.name))

                if write_last_collection_allowed:
                    log.LOGGER.debug(
                        "%s has write access to item %s" %
                        (user or "Anonymous", item.name))
                    write_allowed_items.append(item)
                else:
                    log.LOGGER.debug(
                        "%s has NO write access to item %s" %
                        (user or "Anonymous", item.name))

        return read_allowed_items, write_allowed_items

    def __call__(self, environ, start_response):
        """Manage a request."""
        log.LOGGER.info("%s request at %s received" % (
            environ["REQUEST_METHOD"], environ["PATH_INFO"]))
        headers = pprint.pformat(self.headers_log(environ))
        log.LOGGER.debug("Request headers:\n%s" % headers)

        base_prefix = config.get("server", "base_prefix")
        if environ["PATH_INFO"].startswith(base_prefix):
            # Sanitize request URI
            environ["PATH_INFO"] = self.sanitize_uri(
                "/%s" % environ["PATH_INFO"][len(base_prefix):])
            log.LOGGER.debug("Sanitized path: %s", environ["PATH_INFO"])
        else:
            # Request path not starting with base_prefix, not allowed
            log.LOGGER.debug(
                "Path not starting with prefix: %s", environ["PATH_INFO"])
            environ["PATH_INFO"] = None

        # Get content
        content_length = int(environ.get("CONTENT_LENGTH") or 0)
        if content_length:
            content = self.decode(
                environ["wsgi.input"].read(content_length), environ)
            log.LOGGER.debug("Request content:\n%s" % content)
        else:
            content = None

        path = environ["PATH_INFO"]

        # Get function corresponding to method
        function = getattr(self, environ["REQUEST_METHOD"].lower())

        # Ask authentication backend to check rights
        authorization = environ.get("HTTP_AUTHORIZATION", None)

        if authorization:
            authorization = authorization.lstrip("Basic").strip()
            user, password = self.decode(base64.b64decode(
                authorization.encode("ascii")), environ).split(":", 1)
        else:
            user = environ.get("REMOTE_USER")
            password = None

        is_authenticated = auth.is_authenticated(user, password)
        is_valid_user = is_authenticated or not user

        if is_valid_user:
            items = ical.Collection.from_path(
                path, environ.get("HTTP_DEPTH", "0"))
            read_allowed_items, write_allowed_items = \
                self.collect_allowed_items(items, user)
        else:
            read_allowed_items, write_allowed_items = None, None

        if is_valid_user and (
                (read_allowed_items or write_allowed_items) or
                (is_authenticated and function == self.propfind) or
                function == self.options):
            status, headers, answer = function(
                environ, read_allowed_items, write_allowed_items, content,
                user)
        else:
            status, headers, answer = NOT_ALLOWED

        if ((status, headers, answer) == NOT_ALLOWED and
                not is_authenticated and
                config.get("auth", "type") != "None"):
            # Unknown or unauthorized user
            log.LOGGER.info("%s refused" % (user or "Anonymous user"))
            status = client.UNAUTHORIZED
            headers = {
                "WWW-Authenticate":
                "Basic realm=\"%s\"" % config.get("server", "realm")}
            answer = None

        # Set content length
        if answer:
            log.LOGGER.debug(
                "Response content:\n%s" % self.decode(answer, environ))
            headers["Content-Length"] = str(len(answer))

        if config.has_section("headers"):
            for key in config.options("headers"):
                headers[key] = config.get("headers", key)

        # Start response
        status = "%i %s" % (status, client.responses.get(status, "Unknown"))
        log.LOGGER.debug("Answer status: %s" % status)
        start_response(status, list(headers.items()))

        # Return response content
        return [answer] if answer else []

    # All these functions must have the same parameters, some are useless
    # pylint: disable=W0612,W0613,R0201

    def delete(self, environ, read_collections, write_collections, content,
               user):
        """Manage DELETE request."""
        if not len(write_collections):
            return client.PRECONDITION_FAILED, {}, None

        collection = write_collections[0]

        if collection.path == environ["PATH_INFO"].strip("/"):
            # Path matching the collection, the collection must be deleted
            item = collection
        else:
            # Try to get an item matching the path
            item = collection.get_item(
                xmlutils.name_from_path(environ["PATH_INFO"], collection))

        if item:
            # Evolution bug workaround
            etag = environ.get("HTTP_IF_MATCH", item.etag).replace("\\", "")
            if etag == item.etag:
                # No ETag precondition or precondition verified, delete item
                answer = xmlutils.delete(environ["PATH_INFO"], collection)
                return client.OK, {}, answer

        # No item or ETag precondition not verified, do not delete item
        return client.PRECONDITION_FAILED, {}, None

    def get(self, environ, read_collections, write_collections, content, user):
        """Manage GET request.

        In Radicale, GET requests create collections when the URL is not
        available. This is useful for clients with no MKCOL or MKCALENDAR
        support.

        """
        # Display a "Radicale works!" message if the root URL is requested
        if environ["PATH_INFO"] == "/":
            headers = {"Content-type": "text/html"}
            answer = b"<!DOCTYPE html>\n<title>Radicale</title>Radicale works!"
            return client.OK, headers, answer

        if not len(read_collections):
            return NOT_ALLOWED

        collection = read_collections[0]

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
                if collection in write_collections:
                    log.LOGGER.debug(
                        "Creating collection %s" % collection.name)
                    collection.write()
                else:
                    log.LOGGER.debug(
                        "Collection %s not available and could not be created "
                        "due to missing write rights" % collection.name)
                    return NOT_ALLOWED

            # Get whole collection
            answer_text = collection.text
            etag = collection.etag

        headers = {
            "Content-Type": collection.mimetype,
            "Last-Modified": collection.last_modified,
            "ETag": etag}
        answer = answer_text.encode(self.encoding)
        return client.OK, headers, answer

    def head(self, environ, read_collections, write_collections, content,
             user):
        """Manage HEAD request."""
        status, headers, answer = self.get(
            environ, read_collections, write_collections, content, user)
        return status, headers, None

    def mkcalendar(self, environ, read_collections, write_collections, content,
                   user):
        """Manage MKCALENDAR request."""
        if not len(write_collections):
            return NOT_ALLOWED

        collection = write_collections[0]

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

    def mkcol(self, environ, read_collections, write_collections, content,
              user):
        """Manage MKCOL request."""
        if not len(write_collections):
            return NOT_ALLOWED

        collection = write_collections[0]

        props = xmlutils.props_from_request(content)
        with collection.props as collection_props:
            for key, value in props.items():
                collection_props[key] = value
        collection.write()
        return client.CREATED, {}, None

    def move(self, environ, read_collections, write_collections, content,
             user):
        """Manage MOVE request."""
        if not len(write_collections):
            return NOT_ALLOWED

        from_collection = write_collections[0]

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
                    if to_collection in write_collections:
                        to_collection.append(to_name, item.text)
                        from_collection.remove(from_name)
                        return client.CREATED, {}, None
                    else:
                        return NOT_ALLOWED
                else:
                    # Remote destination server, not supported
                    return client.BAD_GATEWAY, {}, None
            else:
                # No item found
                return client.GONE, {}, None
        else:
            # Moving collections, not supported
            return client.FORBIDDEN, {}, None

    def options(self, environ, read_collections, write_collections, content,
                user):
        """Manage OPTIONS request."""
        headers = {
            "Allow": ("DELETE, HEAD, GET, MKCALENDAR, MKCOL, MOVE, "
                      "OPTIONS, PROPFIND, PROPPATCH, PUT, REPORT"),
            "DAV": "1, 2, 3, calendar-access, addressbook, extended-mkcol"}
        return client.OK, headers, None

    def propfind(self, environ, read_collections, write_collections, content,
                 user):
        """Manage PROPFIND request."""
        # Rights is handled by collection in xmlutils.propfind
        headers = {
            "DAV": "1, 2, 3, calendar-access, addressbook, extended-mkcol",
            "Content-Type": "text/xml"}
        collections = set(read_collections + write_collections)
        answer = xmlutils.propfind(
            environ["PATH_INFO"], content, collections, user)
        return client.MULTI_STATUS, headers, answer

    def proppatch(self, environ, read_collections, write_collections, content,
                  user):
        """Manage PROPPATCH request."""
        if not len(write_collections):
            return NOT_ALLOWED

        collection = write_collections[0]

        answer = xmlutils.proppatch(
            environ["PATH_INFO"], content, collection)
        headers = {
            "DAV": "1, 2, 3, calendar-access, addressbook, extended-mkcol",
            "Content-Type": "text/xml"}
        return client.MULTI_STATUS, headers, answer

    def put(self, environ, read_collections, write_collections, content, user):
        """Manage PUT request."""
        if not len(write_collections):
            return NOT_ALLOWED

        collection = write_collections[0]

        collection.set_mimetype(environ.get("CONTENT_TYPE"))
        headers = {}
        item_name = xmlutils.name_from_path(environ["PATH_INFO"], collection)
        item = collection.get_item(item_name)

        # Evolution bug workaround
        etag = environ.get("HTTP_IF_MATCH", "").replace("\\", "")
        match = environ.get("HTTP_IF_NONE_MATCH", "") == "*"
        if (not item and not etag) or (
                item and ((etag or item.etag) == item.etag) and not match):
            # PUT allowed in 3 cases
            # Case 1: No item and no ETag precondition: Add new item
            # Case 2: Item and ETag precondition verified: Modify item
            # Case 3: Item and no Etag precondition: Force modifying item
            xmlutils.put(environ["PATH_INFO"], content, collection)
            status = client.CREATED
            # Try to return the etag in the header.
            # If the added item doesn't have the same name as the one given
            # by the client, then there's no obvious way to generate an
            # etag, we can safely ignore it.
            new_item = collection.get_item(item_name)
            if new_item:
                headers["ETag"] = new_item.etag
        else:
            # PUT rejected in all other cases
            status = client.PRECONDITION_FAILED
        return status, headers, None

    def report(self, environ, read_collections, write_collections, content,
               user):
        """Manage REPORT request."""
        if not len(read_collections):
            return NOT_ALLOWED

        collection = read_collections[0]

        headers = {"Content-Type": "text/xml"}

        answer = xmlutils.report(environ["PATH_INFO"], content, collection)
        return client.MULTI_STATUS, headers, answer

    # pylint: enable=W0612,W0613,R0201
