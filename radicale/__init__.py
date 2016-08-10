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

import base64
import contextlib
import os
import posixpath
import pprint
import shlex
import socket
import socketserver
import ssl
import subprocess
import threading
import wsgiref.simple_server
import zlib
from contextlib import contextmanager
from http import client
from urllib.parse import unquote, urlparse

import vobject

from . import auth, rights, storage, xmlutils


VERSION = "2.0.0rc0"

NOT_ALLOWED = (client.FORBIDDEN, {}, None)
DAV_HEADERS = "1, 2, 3, calendar-access, addressbook, extended-mkcol"


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

        # Mask passwords
        mask_passwords = self.configuration.getboolean(
            "logging", "mask_passwords")
        authorization = request_environ.get(
            "HTTP_AUTHORIZATION", "").startswith("Basic")
        if mask_passwords and authorization:
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
        read_allowed_items = []
        write_allowed_items = []
        for item in items:
            if isinstance(item, self.Collection):
                path = item.path
            else:
                path = item.collection.path
            if self.authorized(user, path, "r"):
                self.logger.debug(
                    "%s has read access to collection %s",
                    user or "Anonymous", path or "/")
                read_allowed_items.append(item)
            else:
                self.logger.debug(
                    "%s has NO read access to collection %s",
                    user or "Anonymous", path or "/")
            if self.authorized(user, path, "w"):
                self.logger.debug(
                    "%s has write access to collection %s",
                    user or "Anonymous", path or "/")
                write_allowed_items.append(item)
            else:
                self.logger.debug(
                    "%s has NO write access to collection %s",
                    user or "Anonymous", path or "/")
        return read_allowed_items, write_allowed_items

    def __call__(self, environ, start_response):
        """Manage a request."""

        def response(status, headers={}, answer=None):
            # Start response
            status = "%i %s" % (
                status, client.responses.get(status, "Unknown"))
            self.logger.debug("Answer status: %s", status)
            start_response(status, list(headers.items()))
            # Return response content
            return [answer] if answer else []

        self.logger.debug("\n")  # Add empty lines between requests in debug
        self.logger.info("%s request at %s received",
                         environ["REQUEST_METHOD"], environ["PATH_INFO"])
        headers = pprint.pformat(self.headers_log(environ))
        self.logger.debug("Request headers:\n%s", headers)

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

        # If "/.well-known" is not available, clients query "/"
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
            if self.authorized(user, principal_path, "w"):
                with self._lock_collection("r", user):
                    principal = next(
                        self.Collection.discover(principal_path, depth="1"),
                        None)
                if not principal:
                    with self._lock_collection("w", user):
                        self.Collection.create_collection(principal_path)

        # Verify content length
        content_length = int(environ.get("CONTENT_LENGTH") or 0)
        if content_length:
            max_content_length = self.configuration.getint(
                "server", "max_content_length")
            if max_content_length and content_length > max_content_length:
                self.logger.debug(
                    "Request body too large: %d", content_length)
                return response(client.REQUEST_ENTITY_TOO_LARGE)

        if is_valid_user:
            try:
                status, headers, answer = function(environ, path, user)
            except socket.timeout:
                return response(client.REQUEST_TIMEOUT)
        else:
            status, headers, answer = NOT_ALLOWED

        if (status, headers, answer) == NOT_ALLOWED and not (
                user and is_authenticated):
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
            self.logger.debug("Response content:\n%s", answer)
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

        # Add extra headers set in configuration
        if self.configuration.has_section("headers"):
            for key in self.configuration.options("headers"):
                headers[key] = self.configuration.get("headers", key)

        return response(status, headers, answer)

    def _access(self, user, path, permission, item=None):
        """Check if ``user`` can access ``path`` or the parent collection.

        ``permission`` must either be "r" or "w".

        If ``item`` is given, only access to that class of item is checked.

        """
        path = storage.sanitize_path(path)
        parent_path = storage.sanitize_path(
            "/%s/" % posixpath.dirname(path.strip("/")))
        allowed = False
        if not item or isinstance(item, self.Collection):
            allowed |= self.authorized(user, path, permission)
        if not item or not isinstance(item, self.Collection):
            allowed |= self.authorized(user, parent_path, permission)
        return allowed

    @contextmanager
    def _lock_collection(self, lock_mode, user):
        """Lock the collection with ``permission`` and execute hook."""
        with self.Collection.acquire_lock(lock_mode) as value:
            yield value
            hook = self.configuration.get("storage", "hook")
            if lock_mode == "w" and hook:
                self.logger.debug("Running hook")
                folder = os.path.expanduser(self.configuration.get(
                    "storage", "filesystem_folder"))
                subprocess.check_call(
                    hook % {"user": shlex.quote(user or "Anonymous")},
                    shell=True, cwd=folder)

    def _read_content(self, environ):
        content_length = int(environ.get("CONTENT_LENGTH") or 0)
        if content_length > 0:
            content = self.decode(
                environ["wsgi.input"].read(content_length), environ)
            self.logger.debug("Request content:\n%s", content.strip())
        else:
            content = None
        return content

    def do_DELETE(self, environ, path, user):
        """Manage DELETE request."""
        if not self._access(user, path, "w"):
            return NOT_ALLOWED
        with self._lock_collection("w", user):
            item = next(self.Collection.discover(path), None)
            if not self._access(user, path, "w", item):
                return NOT_ALLOWED
            if not item:
                return client.GONE, {}, None
            if_match = environ.get("HTTP_IF_MATCH", "*")
            if if_match not in ("*", item.etag):
                # ETag precondition not verified, do not delete item
                return client.PRECONDITION_FAILED, {}, None
            if isinstance(item, self.Collection):
                answer = xmlutils.delete(path, item)
            else:
                answer = xmlutils.delete(path, item.collection, item.href)
            return client.OK, {}, answer

    def do_GET(self, environ, path, user):
        """Manage GET request."""
        # Display a "Radicale works!" message if the root URL is requested
        if not path.strip("/"):
            headers = {"Content-type": "text/html"}
            answer = "<!DOCTYPE html>\n<title>Radicale</title>Radicale works!"
            return client.OK, headers, answer
        if not self._access(user, path, "r"):
            return NOT_ALLOWED
        with self._lock_collection("r", user):
            item = next(self.Collection.discover(path), None)
            if not self._access(user, path, "r", item):
                return NOT_ALLOWED
            if not item:
                return client.NOT_FOUND, {}, None
            if isinstance(item, self.Collection):
                collection = item
            else:
                collection = item.collection
            content_type = xmlutils.MIMETYPES.get(
                collection.get_meta("tag"), "text/plain")
            headers = {
                "Content-Type": content_type,
                "Last-Modified": collection.last_modified,
                "ETag": item.etag}
            answer = item.serialize()
            return client.OK, headers, answer

    def do_HEAD(self, environ, path, user):
        """Manage HEAD request."""
        status, headers, answer = self.do_GET(environ, path, user)
        return status, headers, None

    def do_MKCALENDAR(self, environ, path, user):
        """Manage MKCALENDAR request."""
        if not self.authorized(user, path, "w"):
            return NOT_ALLOWED
        content = self._read_content(environ)
        with self._lock_collection("w", user):
            item = next(self.Collection.discover(path), None)
            if item:
                return client.CONFLICT, {}, None
            props = xmlutils.props_from_request(content)
            props["tag"] = "VCALENDAR"
            # TODO: use this?
            # timezone = props.get("C:calendar-timezone")
            self.Collection.create_collection(path, props=props)
            return client.CREATED, {}, None

    def do_MKCOL(self, environ, path, user):
        """Manage MKCOL request."""
        if not self.authorized(user, path, "w"):
            return NOT_ALLOWED
        content = self._read_content(environ)
        with self._lock_collection("w", user):
            item = next(self.Collection.discover(path), None)
            if item:
                return client.CONFLICT, {}, None
            props = xmlutils.props_from_request(content)
            self.Collection.create_collection(path, props=props)
            return client.CREATED, {}, None

    def do_MOVE(self, environ, path, user):
        """Manage MOVE request."""
        to_url = urlparse(environ["HTTP_DESTINATION"])
        if to_url.netloc != environ["HTTP_HOST"]:
            # Remote destination server, not supported
            return client.BAD_GATEWAY, {}, None
        if not self._access(user, path, "w"):
            return NOT_ALLOWED
        to_path = storage.sanitize_path(to_url.path)
        if not self._access(user, to_path, "w"):
            return NOT_ALLOWED

        with self._lock_collection("w", user):
            item = next(self.Collection.discover(path), None)
            if not self._access(user, path, "w", item):
                return NOT_ALLOWED
            if not self._access(user, to_path, "w", item):
                return NOT_ALLOWED
            if not item:
                return client.GONE, {}, None
            if isinstance(item, self.Collection):
                return client.CONFLICT, {}, None

            to_item = next(self.Collection.discover(to_path), None)
            if (isinstance(to_item, self.Collection) or
                    to_item and environ.get("HTTP_OVERWRITE", "F") != "T"):
                return client.CONFLICT, {}, None
            to_parent_path = storage.sanitize_path(
                "/%s/" % posixpath.dirname(to_path.strip("/")))
            to_collection = next(
                self.Collection.discover(to_parent_path), None)
            if not to_collection:
                return client.CONFLICT, {}, None
            to_href = posixpath.basename(to_path.strip("/"))
            self.Collection.move(item, to_collection, to_href)
            return client.CREATED, {}, None

    def do_OPTIONS(self, environ, path, user):
        """Manage OPTIONS request."""
        headers = {
            "Allow": ", ".join(
                name[3:] for name in dir(self) if name.startswith("do_")),
            "DAV": DAV_HEADERS}
        return client.OK, headers, None

    def do_PROPFIND(self, environ, path, user):
        """Manage PROPFIND request."""
        if not self._access(user, path, "r"):
            return NOT_ALLOWED
        content = self._read_content(environ)
        with self._lock_collection("r", user):
            items = self.Collection.discover(
                path, environ.get("HTTP_DEPTH", "0"))
            read_items, write_items = self.collect_allowed_items(items, user)
            if not read_items and not write_items:
                return (client.NOT_FOUND, {}, None) if user else NOT_ALLOWED
            headers = {"DAV": DAV_HEADERS, "Content-Type": "text/xml"}
            answer = xmlutils.propfind(
                path, content, read_items, write_items, user)
            return client.MULTI_STATUS, headers, answer

    def do_PROPPATCH(self, environ, path, user):
        """Manage PROPPATCH request."""
        if not self.authorized(user, path, "w"):
            return NOT_ALLOWED
        content = self._read_content(environ)
        with self._lock_collection("w", user):
            item = next(self.Collection.discover(path), None)
            if not isinstance(item, self.Collection):
                return client.CONFLICT, {}, None
            headers = {"DAV": DAV_HEADERS, "Content-Type": "text/xml"}
            answer = xmlutils.proppatch(path, content, item)
            return client.MULTI_STATUS, headers, answer

    def do_PUT(self, environ, path, user):
        """Manage PUT request."""
        if not self._access(user, path, "w"):
            return NOT_ALLOWED
        content = self._read_content(environ)
        with self._lock_collection("w", user):
            parent_path = storage.sanitize_path(
                "/%s/" % posixpath.dirname(path.strip("/")))
            item = next(self.Collection.discover(path), None)
            parent_item = next(self.Collection.discover(parent_path), None)

            write_whole_collection = (
                isinstance(item, self.Collection) or
                not parent_item or (
                    not next(parent_item.list(), None) and
                    parent_item.get_meta("tag") not in (
                        "VADDRESSBOOK", "VCALENDAR")))
            if write_whole_collection:
                if not self.authorized(user, path, "w"):
                    return NOT_ALLOWED
            elif not self.authorized(user, parent_path, "w"):
                return NOT_ALLOWED

            etag = environ.get("HTTP_IF_MATCH", "")
            if not item and etag:
                # Etag asked but no item found: item has been removed
                return client.PRECONDITION_FAILED, {}, None
            if item and etag and item.etag != etag:
                # Etag asked but item not matching: item has changed
                return client.PRECONDITION_FAILED, {}, None

            match = environ.get("HTTP_IF_NONE_MATCH", "") == "*"
            if item and match:
                # Creation asked but item found: item can't be replaced
                return client.PRECONDITION_FAILED, {}, None

            items = list(vobject.readComponents(content or ""))
            content_type = environ.get("CONTENT_TYPE", "").split(";")[0]
            tags = {value: key for key, value in xmlutils.MIMETYPES.items()}
            tag = tags.get(content_type)

            if write_whole_collection:
                new_item = self.Collection.create_collection(
                    path, items, {"tag": tag})
            else:
                if tag:
                    parent_item.set_meta({"tag": tag})
                href = posixpath.basename(path.strip("/"))
                if item:
                    new_item = parent_item.update(href, items[0])
                else:
                    new_item = parent_item.upload(href, items[0])
            headers = {"ETag": new_item.etag}
            return client.CREATED, headers, None

    def do_REPORT(self, environ, path, user):
        """Manage REPORT request."""
        if not self._access(user, path, "w"):
            return NOT_ALLOWED
        content = self._read_content(environ)
        with self._lock_collection("r", user):
            item = next(self.Collection.discover(path), None)
            if not self._access(user, path, "w", item):
                return NOT_ALLOWED
            if not item:
                return client.NOT_FOUND, {}, None
            if isinstance(item, self.Collection):
                collection = item
            else:
                collection = item.collection
            headers = {"Content-Type": "text/xml"}
            answer = xmlutils.report(path, content, collection)
            return client.MULTI_STATUS, headers, answer
