# This file is part of Radicale Server - Calendar Server
# Copyright © 2008 Nicolas Kandel
# Copyright © 2008 Pascal Halter
# Copyright © 2008-2016 Guillaume Ayoub
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
import contextlib
import shlex
import socket
import socketserver
import ssl
import threading
import subprocess
import wsgiref.simple_server
import zlib
from http import client
from urllib.parse import unquote, urlparse

import vobject

from . import auth, rights, storage, xmlutils


VERSION = "2.0.0rc0"

# Standard "not allowed" response that is returned when an authenticated user
# tries to access information they don't have rights to
NOT_ALLOWED = (client.FORBIDDEN, {}, None)


class HTTPServer(wsgiref.simple_server.WSGIServer):
    """HTTP server."""

    # These class attributes must be set before creating instance
    client_timeout = None
    max_connections = None

    def __init__(self, address, handler, bind_and_activate=True):
        """Create server."""
        ipv6 = ":" in address[0]

        if ipv6:
            self.address_family = socket.AF_INET6

        # Do not bind and activate, as we might change socket options
        super().__init__(address, handler, False)

        if ipv6:
            # Only allow IPv6 connections to the IPv6 socket
            self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)

        if bind_and_activate:
            self.server_bind()
            self.server_activate()

        if self.max_connections:
            self.connections_guard = threading.BoundedSemaphore(
                self.max_connections)
        else:
            # use dummy context manager
            self.connections_guard = contextlib.suppress()

    def get_request(self):
        # Set timeout for client
        _socket, address = super().get_request()
        if self.client_timeout:
            _socket.settimeout(self.client_timeout)
        return _socket, address


class HTTPSServer(HTTPServer):
    """HTTPS server."""

    # These class attributes must be set before creating instance
    certificate = None
    key = None
    protocol = None
    cyphers = None

    def __init__(self, address, handler):
        """Create server by wrapping HTTP socket in an SSL socket."""
        super().__init__(address, handler, bind_and_activate=False)

        self.socket = ssl.wrap_socket(
            self.socket, self.key, self.certificate, server_side=True,
            ssl_version=self.protocol, cyphers=self.cyphers)

        self.server_bind()
        self.server_activate()


class ThreadedHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    def process_request_thread(self, request, client_address):
        with self.connections_guard:
            return super().process_request_thread(request, client_address)


class ThreadedHTTPSServer(socketserver.ThreadingMixIn, HTTPSServer):
    def process_request_thread(self, request, client_address):
        with self.connections_guard:
            return super().process_request_thread(request, client_address)


class RequestHandler(wsgiref.simple_server.WSGIRequestHandler):
    """HTTP requests handler."""
    def log_message(self, *args, **kwargs):
        """Disable inner logging management."""


class Application:
    """WSGI application managing collections."""
    def __init__(self, configuration, logger):
        """Initialize application."""
        super().__init__()
        self.configuration = configuration
        self.logger = logger
        self.is_authenticated = auth.load(configuration, logger)
        self.Collection = storage.load(configuration, logger)
        self.authorized = rights.load(configuration, logger)
        self.encoding = configuration.get("encoding", "request")

    def headers_log(self, environ):
        """Sanitize headers for logging."""
        request_environ = dict(environ)
        # Remove environment variables
        if not self.configuration.getboolean("logging", "full_environment"):
            for shell_variable in os.environ:
                request_environ.pop(shell_variable, None)
        # Mask credentials
        if (self.configuration.getboolean("logging", "mask_passwords") and
                request_environ.get("HTTP_AUTHORIZATION",
                                    "").startswith("Basic")):
            request_environ["HTTP_AUTHORIZATION"] = "Basic **masked**"
        return request_environ

    def decode(self, text, environ):
        """Try to magically decode ``text`` according to given ``environ``."""
        # List of charsets to try
        charsets = []

        # First append content charset given in the request
        content_type = environ.get("CONTENT_TYPE")
        if content_type and "charset=" in content_type:
            charsets.append(
                content_type.split("charset=")[1].split(";")[0].strip())
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

    def collect_allowed_items(self, items, user):
        """Get items from request that user is allowed to access."""
        read_last_collection_allowed = None
        write_last_collection_allowed = None
        read_allowed_items = []
        write_allowed_items = []

        for item in items:
            if isinstance(item, self.Collection):
                if self.authorized(user, item, "r"):
                    self.logger.debug(
                        "%s has read access to collection %s" %
                        (user or "Anonymous", item.path or "/"))
                    read_last_collection_allowed = True
                    read_allowed_items.append(item)
                else:
                    self.logger.debug(
                        "%s has NO read access to collection %s" %
                        (user or "Anonymous", item.path or "/"))
                    read_last_collection_allowed = False

                if self.authorized(user, item, "w"):
                    self.logger.debug(
                        "%s has write access to collection %s" %
                        (user or "Anonymous", item.path or "/"))
                    write_last_collection_allowed = True
                    write_allowed_items.append(item)
                else:
                    self.logger.debug(
                        "%s has NO write access to collection %s" %
                        (user or "Anonymous", item.path or "/"))
                    write_last_collection_allowed = False
            else:
                # item is not a collection, it's the child of the last
                # collection we've met in the loop. Only add this item
                # if this last collection was allowed.
                if read_last_collection_allowed:
                    self.logger.debug(
                        "%s has read access to item %s" %
                        (user or "Anonymous", item.href))
                    read_allowed_items.append(item)
                else:
                    self.logger.debug(
                        "%s has NO read access to item %s" %
                        (user or "Anonymous", item.href))

                if write_last_collection_allowed:
                    self.logger.debug(
                        "%s has write access to item %s" %
                        (user or "Anonymous", item.href))
                    write_allowed_items.append(item)
                else:
                    self.logger.debug(
                        "%s has NO write access to item %s" %
                        (user or "Anonymous", item.href))

        return read_allowed_items, write_allowed_items

    def __call__(self, environ, start_response):
        """Manage a request."""
        def response(status, headers={}, answer=None):
            # Start response
            status = "%i %s" % (status,
                                client.responses.get(status, "Unknown"))
            self.logger.debug("Answer status: %s" % status)
            start_response(status, list(headers.items()))
            # Return response content
            return [answer] if answer else []

        self.logger.info("%s request at %s received" % (
            environ["REQUEST_METHOD"], environ["PATH_INFO"]))
        headers = pprint.pformat(self.headers_log(environ))
        self.logger.debug("Request headers:\n%s" % headers)

        # Strip base_prefix from request URI
        base_prefix = self.configuration.get("server", "base_prefix")
        if environ["PATH_INFO"].startswith(base_prefix):
            environ["PATH_INFO"] = environ["PATH_INFO"][len(base_prefix):]
        elif self.configuration.get("server", "can_skip_base_prefix"):
            self.logger.debug(
                "Prefix already stripped from path: %s", environ["PATH_INFO"])
        else:
            # Request path not starting with base_prefix, not allowed
            self.logger.debug(
                "Path not starting with prefix: %s", environ["PATH_INFO"])
            return response(*NOT_ALLOWED)

        # Sanitize request URI
        environ["PATH_INFO"] = storage.sanitize_path(
            unquote(environ["PATH_INFO"]))
        self.logger.debug("Sanitized path: %s", environ["PATH_INFO"])

        path = environ["PATH_INFO"]

        # Get function corresponding to method
        function = getattr(self, "do_%s" % environ["REQUEST_METHOD"].upper())

        # Ask authentication backend to check rights
        authorization = environ.get("HTTP_AUTHORIZATION", None)

        if authorization and authorization.startswith("Basic"):
            authorization = authorization[len("Basic"):].strip()
            user, password = self.decode(base64.b64decode(
                authorization.encode("ascii")), environ).split(":", 1)
        else:
            user = environ.get("REMOTE_USER")
            password = None

        # If /.well-known is not available, clients query /
        if path == "/.well-known" or path.startswith("/.well-known/"):
            return response(client.NOT_FOUND, {})

        if user and not storage.is_safe_path_component(user):
            # Prevent usernames like "user/calendar.ics"
            self.logger.info("Refused unsafe username: %s", user)
            is_authenticated = False
        else:
            is_authenticated = self.is_authenticated(user, password)
        is_valid_user = is_authenticated or not user

        # Create principal collection
        if user and is_authenticated:
            principal_path = "/%s/" % user
            collection = self.Collection(principal_path, True)
            if self.authorized(user, collection, "w"):
                with self.Collection.acquire_lock("r"):
                    principal = next(
                        self.Collection.discover(principal_path), None)
                if not principal or principal.path != user:
                    with self.Collection.acquire_lock("w"):
                        self.Collection.create_collection(principal_path)

        # Get content
        content_length = int(environ.get("CONTENT_LENGTH") or 0)
        if content_length:
            max_content_length = self.configuration.getint(
                "server", "max_content_length")
            if max_content_length and content_length > max_content_length:
                self.logger.debug(
                    "Request body too large: %d", content_length)
                return response(client.REQUEST_ENTITY_TOO_LARGE)
            try:
                content = self.decode(
                    environ["wsgi.input"].read(content_length), environ)
            except socket.timeout:
                return response(client.REQUEST_TIMEOUT)
            self.logger.debug("Request content:\n%s" % content)
        else:
            content = None

        if is_valid_user:
            if function in (
                    self.do_GET, self.do_HEAD, self.do_OPTIONS,
                    self.do_PROPFIND, self.do_REPORT):
                lock_mode = "r"
            else:
                lock_mode = "w"
            with self.Collection.acquire_lock(lock_mode):
                items = self.Collection.discover(
                    path, environ.get("HTTP_DEPTH", "0"))
                read_allowed_items, write_allowed_items = (
                    self.collect_allowed_items(items, user))
                if (read_allowed_items or write_allowed_items or
                        is_authenticated and function == self.do_PROPFIND or
                        function == self.do_OPTIONS):
                    status, headers, answer = function(
                        environ, read_allowed_items, write_allowed_items,
                        content, user)
                    hook = self.configuration.get("storage", "hook")
                    if lock_mode == "w" and hook:
                        self.logger.debug("Running hook")
                        folder = os.path.expanduser(
                            self.configuration.get("storage",
                                                   "filesystem_folder"))
                        subprocess.check_call(
                            hook % {"user": shlex.quote(user or "Anonymous")},
                            shell=True, cwd=folder)
                else:
                    status, headers, answer = NOT_ALLOWED
        else:
            status, headers, answer = NOT_ALLOWED

        if (status, headers, answer) == NOT_ALLOWED and not is_authenticated:
            # Unknown or unauthorized user
            self.logger.info("%s refused" % (user or "Anonymous user"))
            status = client.UNAUTHORIZED
            realm = self.configuration.get("server", "realm")
            headers = {
                "WWW-Authenticate":
                "Basic realm=\"%s\"" % realm}
            answer = None

        # Set content length
        if answer:
            self.logger.debug("Response content:\n%s" % answer, environ)
            answer = answer.encode(self.encoding)
            accept_encoding = [
                encoding.strip() for encoding in
                environ.get("HTTP_ACCEPT_ENCODING", "").split(",")
                if encoding.strip()]

            if "gzip" in accept_encoding:
                zcomp = zlib.compressobj(wbits=16 + zlib.MAX_WBITS)
                answer = zcomp.compress(answer) + zcomp.flush()
                headers["Content-Encoding"] = "gzip"

            headers["Content-Length"] = str(len(answer))

        if self.configuration.has_section("headers"):
            for key in self.configuration.options("headers"):
                headers[key] = self.configuration.get("headers", key)

        return response(status, headers, answer)

    # All these functions must have the same parameters, some are useless
    # pylint: disable=W0612,W0613,R0201

    def do_DELETE(self, environ, read_collections, write_collections, content,
                  user):
        """Manage DELETE request."""
        if not write_collections:
            return NOT_ALLOWED

        collection = write_collections[0]

        if collection.path == environ["PATH_INFO"].strip("/"):
            # Path matching the collection, the collection must be deleted
            item = collection
        else:
            # Try to get an item matching the path
            name = xmlutils.name_from_path(environ["PATH_INFO"], collection)
            item = collection.get(name)

        if item:
            if_match = environ.get("HTTP_IF_MATCH", "*")
            if if_match in ("*", item.etag):
                # No ETag precondition or precondition verified, delete item
                answer = xmlutils.delete(environ["PATH_INFO"], collection)
                return client.OK, {}, answer

        # No item or ETag precondition not verified, do not delete item
        return client.PRECONDITION_FAILED, {}, None

    def do_GET(self, environ, read_collections, write_collections, content,
               user):
        """Manage GET request."""
        # Display a "Radicale works!" message if the root URL is requested
        if environ["PATH_INFO"] == "/":
            headers = {"Content-type": "text/html"}
            answer = "<!DOCTYPE html>\n<title>Radicale</title>Radicale works!"
            return client.OK, headers, answer

        if not read_collections:
            return NOT_ALLOWED

        collection = read_collections[0]

        item_name = xmlutils.name_from_path(environ["PATH_INFO"], collection)

        if item_name:
            # Get collection item
            item = collection.get(item_name)
            if item:
                answer = item.serialize()
                etag = item.etag
            else:
                return client.NOT_FOUND, {}, None
        else:
            # Get whole collection
            answer = collection.serialize()
            if answer is None:
                return client.NOT_FOUND, {}, None
            else:
                etag = collection.etag

        if answer:
            headers = {
                "Content-Type": storage.MIMETYPES[collection.get_meta("tag")],
                "Last-Modified": collection.last_modified,
                "ETag": etag}
        else:
            headers = {}
        return client.OK, headers, answer

    def do_HEAD(self, environ, read_collections, write_collections, content,
                user):
        """Manage HEAD request."""
        status, headers, answer = self.do_GET(
            environ, read_collections, write_collections, content, user)
        return status, headers, None

    def do_MKCALENDAR(self, environ, read_collections, write_collections,
                      content, user):
        """Manage MKCALENDAR request."""
        if not write_collections:
            return NOT_ALLOWED

        collection = write_collections[0]

        props = xmlutils.props_from_request(content)
        # TODO: use this?
        # timezone = props.get("C:calendar-timezone")
        collection = self.Collection.create_collection(
            environ["PATH_INFO"], tag="VCALENDAR")
        for key, value in props.items():
            collection.set_meta(key, value)
        return client.CREATED, {}, None

    def do_MKCOL(self, environ, read_collections, write_collections, content,
                 user):
        """Manage MKCOL request."""
        if not write_collections:
            return NOT_ALLOWED

        collection = write_collections[0]

        props = xmlutils.props_from_request(content)
        collection = self.Collection.create_collection(environ["PATH_INFO"])
        for key, value in props.items():
            collection.set_meta(key, value)
        return client.CREATED, {}, None

    def do_MOVE(self, environ, read_collections, write_collections, content,
                user):
        """Manage MOVE request."""
        if not write_collections:
            return NOT_ALLOWED

        from_collection = write_collections[0]
        from_name = xmlutils.name_from_path(
            environ["PATH_INFO"], from_collection)
        item = from_collection.get(from_name)
        if item:
            # Move the item
            to_url_parts = urlparse(environ["HTTP_DESTINATION"])
            if to_url_parts.netloc == environ["HTTP_HOST"]:
                to_url = to_url_parts.path
                to_path, to_name = to_url.rstrip("/").rsplit("/", 1)
                for to_collection in self.Collection.discover(
                        to_path, depth="0"):
                    if to_collection in write_collections:
                        to_collection.upload(to_name, item)
                        from_collection.delete(from_name)
                        return client.CREATED, {}, None
                    else:
                        return NOT_ALLOWED
            else:
                # Remote destination server, not supported
                return client.BAD_GATEWAY, {}, None
        else:
            # No item found
            return client.GONE, {}, None

    def do_OPTIONS(self, environ, read_collections, write_collections,
                   content, user):
        """Manage OPTIONS request."""
        headers = {
            "Allow": ("DELETE, HEAD, GET, MKCALENDAR, MKCOL, MOVE, "
                      "OPTIONS, PROPFIND, PROPPATCH, PUT, REPORT"),
            "DAV": "1, 2, 3, calendar-access, addressbook, extended-mkcol"}
        return client.OK, headers, None

    def do_PROPFIND(self, environ, read_collections, write_collections,
                    content, user):
        """Manage PROPFIND request."""
        if not read_collections:
            return client.NOT_FOUND, {}, None
        headers = {
            "DAV": "1, 2, 3, calendar-access, addressbook, extended-mkcol",
            "Content-Type": "text/xml"}
        answer = xmlutils.propfind(
            environ["PATH_INFO"], content, read_collections, write_collections,
            user)
        return client.MULTI_STATUS, headers, answer

    def do_PROPPATCH(self, environ, read_collections, write_collections,
                     content, user):
        """Manage PROPPATCH request."""
        if not write_collections:
            return NOT_ALLOWED

        collection = write_collections[0]

        answer = xmlutils.proppatch(environ["PATH_INFO"], content, collection)
        headers = {
            "DAV": "1, 2, 3, calendar-access, addressbook, extended-mkcol",
            "Content-Type": "text/xml"}
        return client.MULTI_STATUS, headers, answer

    def do_PUT(self, environ, read_collections, write_collections, content,
               user):
        """Manage PUT request."""
        if not write_collections:
            return NOT_ALLOWED

        collection = write_collections[0]

        content_type = environ.get("CONTENT_TYPE")
        if content_type:
            tags = {value: key for key, value in storage.MIMETYPES.items()}
            tag = tags.get(content_type.split(";")[0])
            if tag:
                collection.set_meta("tag", tag)
        headers = {}
        item_name = xmlutils.name_from_path(environ["PATH_INFO"], collection)
        item = collection.get(item_name)

        etag = environ.get("HTTP_IF_MATCH", "")
        match = environ.get("HTTP_IF_NONE_MATCH", "") == "*"
        if (not item and not etag) or (
                item and ((etag or item.etag) == item.etag) and not match):
            # PUT allowed in 3 cases
            # Case 1: No item and no ETag precondition: Add new item
            # Case 2: Item and ETag precondition verified: Modify item
            # Case 3: Item and no Etag precondition: Force modifying item
            items = list(vobject.readComponents(content or ""))
            if item:
                # PUT is modifying an existing item
                if items:
                    new_item = collection.update(item_name, items[0])
                else:
                    new_item = None
            elif item_name:
                # PUT is adding a new item
                if items:
                    new_item = collection.upload(item_name, items[0])
                else:
                    new_item = None
            else:
                # PUT is replacing the whole collection
                collection.delete()
                new_item = self.Collection.create_collection(
                    environ["PATH_INFO"], items)
            if new_item:
                headers["ETag"] = new_item.etag
            status = client.CREATED
        else:
            # PUT rejected in all other cases
            status = client.PRECONDITION_FAILED
        return status, headers, None

    def do_REPORT(self, environ, read_collections, write_collections, content,
                  user):
        """Manage REPORT request."""
        if not read_collections:
            return NOT_ALLOWED

        collection = read_collections[0]

        headers = {"Content-Type": "text/xml"}

        answer = xmlutils.report(environ["PATH_INFO"], content, collection)
        return client.MULTI_STATUS, headers, answer

    # pylint: enable=W0612,W0613,R0201
