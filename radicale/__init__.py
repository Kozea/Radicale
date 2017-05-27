# This file is part of Radicale Server - Calendar Server
# Copyright © 2008 Nicolas Kandel
# Copyright © 2008 Pascal Halter
# Copyright © 2008-2017 Guillaume Ayoub
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
import datetime
import io
import itertools
import os
import posixpath
import pprint
import random
import socket
import socketserver
import ssl
import sys
import threading
import time
import traceback
import wsgiref.simple_server
import zlib
from http import client
from urllib.parse import unquote, urlparse

import vobject

from . import auth, rights, storage, xmlutils

VERSION = "2.0.0"

NOT_ALLOWED = (
    client.FORBIDDEN, (("Content-Type", "text/plain"),),
    "Access to the requested resource forbidden.")
NOT_FOUND = (
    client.NOT_FOUND, (("Content-Type", "text/plain"),),
    "The requested resource could not be found.")
WEBDAV_PRECONDITION_FAILED = (
    client.CONFLICT, (("Content-Type", "text/plain"),),
    "WebDAV precondition failed.")
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

DAV_HEADERS = "1, 2, 3, calendar-access, addressbook, extended-mkcol"


class HTTPServer(wsgiref.simple_server.WSGIServer):
    """HTTP server."""

    # These class attributes must be set before creating instance
    client_timeout = None
    max_connections = None
    logger = None

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

    def handle_error(self, request, client_address):
        if issubclass(sys.exc_info()[0], socket.timeout):
            self.logger.error("connection timeout")
        else:
            self.logger.error(
                "An exception occurred during request:\n%s",
                traceback.format_exc())


class HTTPSServer(HTTPServer):
    """HTTPS server."""

    # These class attributes must be set before creating instance
    certificate = None
    key = None
    protocol = None
    ciphers = None

    def __init__(self, address, handler):
        """Create server by wrapping HTTP socket in an SSL socket."""
        super().__init__(address, handler, bind_and_activate=False)

        self.socket = ssl.wrap_socket(
            self.socket, self.key, self.certificate, server_side=True,
            ssl_version=self.protocol, ciphers=self.ciphers)

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

    # These class attributes must be set before creating instance
    logger = None

    def __init__(self, *args, **kwargs):
        # Store exception for logging
        self.error_stream = io.StringIO()
        super().__init__(*args, **kwargs)

    def get_stderr(self):
        return self.error_stream

    def log_message(self, *args, **kwargs):
        """Disable inner logging management."""

    def get_environ(self):
        env = super().get_environ()
        # Parent class only tries latin1 encoding
        env["PATH_INFO"] = unquote(self.path.split("?", 1)[0])
        return env

    def handle(self):
        super().handle()
        # Log exception
        error = self.error_stream.getvalue().strip("\n")
        if error:
            self.logger.error(
                "An exception occurred during request:\n%s" % error)


class Application:
    """WSGI application managing collections."""

    def __init__(self, configuration, logger):
        """Initialize application."""
        super().__init__()
        self.configuration = configuration
        self.logger = logger
        self.Auth = auth.load(configuration, logger)
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
            if not item:
                continue
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

        def response(status, headers=(), answer=None):
            headers = dict(headers)
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
                headers["Content-Type"] += "; charset=%s" % self.encoding

            # Add extra headers set in configuration
            if self.configuration.has_section("headers"):
                for key in self.configuration.options("headers"):
                    headers[key] = self.configuration.get("headers", key)

            # Start response
            time_end = datetime.datetime.now()
            status = "%i %s" % (
                status, client.responses.get(status, "Unknown"))
            self.logger.info(
                "%s answer status for %s in %.3f seconds: %s",
                environ["REQUEST_METHOD"], environ["PATH_INFO"] + depthinfo,
                (time_end - time_begin).total_seconds(), status)
            start_response(status, list(headers.items()))
            # Return response content
            return [answer] if answer else []

        remote_host = "UNKNOWN"
        if environ.get("REMOTE_HOST"):
            remote_host = environ["REMOTE_HOST"]
        elif environ.get("REMOTE_ADDR"):
            remote_host = environ["REMOTE_ADDR"]
        if environ.get("HTTP_X_FORWARDED_FOR"):
            remote_host = "%s (forwarded by %s)" % (
                environ["HTTP_X_FORWARDED_FOR"], remote_host)
        remote_useragent = "UNKNOWN"
        if environ.get("HTTP_USER_AGENT"):
            remote_useragent = environ["HTTP_USER_AGENT"]
        depthinfo = ""
        if environ.get("HTTP_DEPTH"):
            depthinfo = " with depth " + environ["HTTP_DEPTH"]
        time_begin = datetime.datetime.now()
        self.logger.info(
            "%s request for %s received from %s using \"%s\"",
            environ["REQUEST_METHOD"], environ["PATH_INFO"] + depthinfo,
            remote_host, remote_useragent)
        headers = pprint.pformat(self.headers_log(environ))
        self.logger.debug("Request headers:\n%s", headers)

        # Let reverse proxies overwrite SCRIPT_NAME
        if "HTTP_X_SCRIPT_NAME" in environ:
            environ["SCRIPT_NAME"] = environ["HTTP_X_SCRIPT_NAME"]
            self.logger.debug(
                "Script name overwritten by client: %s",
                environ["SCRIPT_NAME"])
        # Sanitize base prefix
        environ["SCRIPT_NAME"] = storage.sanitize_path(
            environ.get("SCRIPT_NAME", "")).rstrip("/")
        self.logger.debug("Sanitized script name: %s", environ["SCRIPT_NAME"])
        base_prefix = environ["SCRIPT_NAME"]
        # Sanitize request URI
        environ["PATH_INFO"] = storage.sanitize_path(environ["PATH_INFO"])
        self.logger.debug("Sanitized path: %s", environ["PATH_INFO"])
        path = environ["PATH_INFO"]
        if base_prefix and path.startswith(base_prefix):
            path = path[len(base_prefix):]
            self.logger.debug("Stripped script name from path: %s", path)

        # Get function corresponding to method
        function = getattr(self, "do_%s" % environ["REQUEST_METHOD"].upper())

        # Ask authentication backend to check rights
        authorization = environ.get("HTTP_AUTHORIZATION", None)
        if authorization and authorization.startswith("Basic"):
            authorization = authorization[len("Basic"):].strip()
            login, password = self.decode(base64.b64decode(
                authorization.encode("ascii")), environ).split(":", 1)
            user = self.Auth.map_login_to_user(login)
        else:
            user = self.Auth.map_login_to_user(environ.get("REMOTE_USER", ""))
            password = ""

        # If "/.well-known" is not available, clients query "/"
        if path == "/.well-known" or path.startswith("/.well-known/"):
            return response(*NOT_FOUND)

        if not user:
            is_authenticated = True
        elif not storage.is_safe_path_component(user):
            # Prevent usernames like "user/calendar.ics"
            self.logger.info("Refused unsafe username: %s", user)
            is_authenticated = False
        else:
            is_authenticated = self.Auth.is_authenticated(user, password)
            if not is_authenticated:
                self.logger.info("Failed login attempt: %s", user)
                # Random delay to avoid timing oracles and bruteforce attacks
                delay = self.configuration.getfloat("auth", "delay")
                if delay > 0:
                    random_delay = delay * (0.5 + random.random())
                    self.logger.debug("Sleeping %.3f seconds", random_delay)
                    time.sleep(random_delay)

        # Create principal collection
        if user and is_authenticated:
            principal_path = "/%s/" % user
            if self.authorized(user, principal_path, "w"):
                with self.Collection.acquire_lock("r", user):
                    principal = next(
                        self.Collection.discover(principal_path, depth="1"),
                        None)
                if not principal:
                    with self.Collection.acquire_lock("w", user):
                        self.Collection.create_collection(principal_path)

        # Verify content length
        content_length = int(environ.get("CONTENT_LENGTH") or 0)
        if content_length:
            max_content_length = self.configuration.getint(
                "server", "max_content_length")
            if max_content_length and content_length > max_content_length:
                self.logger.debug(
                    "Request body too large: %d", content_length)
                return response(*REQUEST_ENTITY_TOO_LARGE)

        if is_authenticated:
            try:
                status, headers, answer = function(
                    environ, base_prefix, path, user)
            except socket.timeout:
                return response(*REQUEST_TIMEOUT)
            if (status, headers, answer) == NOT_ALLOWED:
                self.logger.info("Access denied for %s",
                                 "'%s'" % user if user else "anonymous user")
        else:
            status, headers, answer = NOT_ALLOWED

        if (status, headers, answer) == NOT_ALLOWED and not (
                user and is_authenticated):
            # Unknown or unauthorized user
            self.logger.debug("Asking client for authentication")
            status = client.UNAUTHORIZED
            realm = self.configuration.get("server", "realm")
            headers = dict(headers)
            headers.update({
                "WWW-Authenticate":
                "Basic realm=\"%s\"" % realm})

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

    def _read_content(self, environ):
        content_length = int(environ.get("CONTENT_LENGTH") or 0)
        if content_length > 0:
            content = self.decode(
                environ["wsgi.input"].read(content_length), environ)
            self.logger.debug("Request content:\n%s", content.strip())
        else:
            content = None
        return content

    def do_DELETE(self, environ, base_prefix, path, user):
        """Manage DELETE request."""
        if not self._access(user, path, "w"):
            return NOT_ALLOWED
        with self.Collection.acquire_lock("w", user):
            item = next(self.Collection.discover(path), None)
            if not self._access(user, path, "w", item):
                return NOT_ALLOWED
            if not item:
                return NOT_FOUND
            if_match = environ.get("HTTP_IF_MATCH", "*")
            if if_match not in ("*", item.etag):
                # ETag precondition not verified, do not delete item
                return PRECONDITION_FAILED
            if isinstance(item, self.Collection):
                answer = xmlutils.delete(base_prefix, path, item)
            else:
                answer = xmlutils.delete(
                    base_prefix, path, item.collection, item.href)
            return client.OK, {"Content-Type": "text/xml"}, answer

    def do_GET(self, environ, base_prefix, path, user):
        """Manage GET request."""
        # Display a "Radicale works!" message if the root URL is requested
        if not path.strip("/"):
            return client.OK, {"Content-Type": "text/plain"}, "Radicale works!"
        if not self._access(user, path, "r"):
            return NOT_ALLOWED
        with self.Collection.acquire_lock("r", user):
            item = next(self.Collection.discover(path), None)
            if not self._access(user, path, "r", item):
                return NOT_ALLOWED
            if not item:
                return NOT_FOUND
            if isinstance(item, self.Collection):
                collection = item
                if collection.get_meta("tag") not in (
                        "VADDRESSBOOK", "VCALENDAR"):
                    return DIRECTORY_LISTING
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

    def do_HEAD(self, environ, base_prefix, path, user):
        """Manage HEAD request."""
        status, headers, answer = self.do_GET(
            environ, base_prefix, path, user)
        return status, headers, None

    def do_MKCALENDAR(self, environ, base_prefix, path, user):
        """Manage MKCALENDAR request."""
        if not self.authorized(user, path, "w"):
            return NOT_ALLOWED
        content = self._read_content(environ)
        with self.Collection.acquire_lock("w", user):
            item = next(self.Collection.discover(path), None)
            if item:
                return WEBDAV_PRECONDITION_FAILED
            props = xmlutils.props_from_request(content)
            props["tag"] = "VCALENDAR"
            # TODO: use this?
            # timezone = props.get("C:calendar-timezone")
            self.Collection.create_collection(path, props=props)
            return client.CREATED, {}, None

    def do_MKCOL(self, environ, base_prefix, path, user):
        """Manage MKCOL request."""
        if not self.authorized(user, path, "w"):
            return NOT_ALLOWED
        content = self._read_content(environ)
        with self.Collection.acquire_lock("w", user):
            item = next(self.Collection.discover(path), None)
            if item:
                return WEBDAV_PRECONDITION_FAILED
            props = xmlutils.props_from_request(content)
            self.Collection.create_collection(path, props=props)
            return client.CREATED, {}, None

    def do_MOVE(self, environ, base_prefix, path, user):
        """Manage MOVE request."""
        to_url = urlparse(environ["HTTP_DESTINATION"])
        if to_url.netloc != environ["HTTP_HOST"]:
            # Remote destination server, not supported
            return REMOTE_DESTINATION
        if not self._access(user, path, "w"):
            return NOT_ALLOWED
        to_path = storage.sanitize_path(to_url.path)
        if not self._access(user, to_path, "w"):
            return NOT_ALLOWED

        with self.Collection.acquire_lock("w", user):
            item = next(self.Collection.discover(path), None)
            if not self._access(user, path, "w", item):
                return NOT_ALLOWED
            if not self._access(user, to_path, "w", item):
                return NOT_ALLOWED
            if not item:
                return NOT_FOUND
            if isinstance(item, self.Collection):
                return WEBDAV_PRECONDITION_FAILED

            to_item = next(self.Collection.discover(to_path), None)
            if (isinstance(to_item, self.Collection) or
                    to_item and environ.get("HTTP_OVERWRITE", "F") != "T"):
                return WEBDAV_PRECONDITION_FAILED
            to_parent_path = storage.sanitize_path(
                "/%s/" % posixpath.dirname(to_path.strip("/")))
            to_collection = next(
                self.Collection.discover(to_parent_path), None)
            if not to_collection:
                return WEBDAV_PRECONDITION_FAILED
            to_href = posixpath.basename(to_path.strip("/"))
            self.Collection.move(item, to_collection, to_href)
            return client.CREATED, {}, None

    def do_OPTIONS(self, environ, base_prefix, path, user):
        """Manage OPTIONS request."""
        headers = {
            "Allow": ", ".join(
                name[3:] for name in dir(self) if name.startswith("do_")),
            "DAV": DAV_HEADERS}
        return client.OK, headers, None

    def do_PROPFIND(self, environ, base_prefix, path, user):
        """Manage PROPFIND request."""
        if not self._access(user, path, "r"):
            return NOT_ALLOWED
        content = self._read_content(environ)
        with self.Collection.acquire_lock("r", user):
            items = self.Collection.discover(
                path, environ.get("HTTP_DEPTH", "0"))
            # take root item for rights checking
            item = next(items, None)
            if not self._access(user, path, "r", item):
                return NOT_ALLOWED
            if not item:
                return NOT_FOUND
            # put item back
            items = itertools.chain([item], items)
            read_items, write_items = self.collect_allowed_items(items, user)
            headers = {"DAV": DAV_HEADERS, "Content-Type": "text/xml"}
            status, answer = xmlutils.propfind(
                base_prefix, path, content, read_items, write_items, user)
            if status == client.FORBIDDEN:
                return NOT_ALLOWED
            else:
                return status, headers, answer

    def do_PROPPATCH(self, environ, base_prefix, path, user):
        """Manage PROPPATCH request."""
        if not self.authorized(user, path, "w"):
            return NOT_ALLOWED
        content = self._read_content(environ)
        with self.Collection.acquire_lock("w", user):
            item = next(self.Collection.discover(path), None)
            if not isinstance(item, self.Collection):
                return WEBDAV_PRECONDITION_FAILED
            headers = {"DAV": DAV_HEADERS, "Content-Type": "text/xml"}
            answer = xmlutils.proppatch(base_prefix, path, content, item)
            return client.MULTI_STATUS, headers, answer

    def do_PUT(self, environ, base_prefix, path, user):
        """Manage PUT request."""
        if not self._access(user, path, "w"):
            return NOT_ALLOWED
        content = self._read_content(environ)
        with self.Collection.acquire_lock("w", user):
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
                return PRECONDITION_FAILED
            if item and etag and item.etag != etag:
                # Etag asked but item not matching: item has changed
                return PRECONDITION_FAILED

            match = environ.get("HTTP_IF_NONE_MATCH", "") == "*"
            if item and match:
                # Creation asked but item found: item can't be replaced
                return PRECONDITION_FAILED

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
                new_item = parent_item.upload(href, items[0])
            headers = {"ETag": new_item.etag}
            return client.CREATED, headers, None

    def do_REPORT(self, environ, base_prefix, path, user):
        """Manage REPORT request."""
        if not self._access(user, path, "r"):
            return NOT_ALLOWED
        content = self._read_content(environ)
        with self.Collection.acquire_lock("r", user):
            item = next(self.Collection.discover(path), None)
            if not self._access(user, path, "r", item):
                return NOT_ALLOWED
            if not item:
                return NOT_FOUND
            if isinstance(item, self.Collection):
                collection = item
            else:
                collection = item.collection
            headers = {"Content-Type": "text/xml"}
            answer = xmlutils.report(base_prefix, path, content, collection)
            return client.MULTI_STATUS, headers, answer
