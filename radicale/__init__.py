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
import logging
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
import wsgiref.simple_server
import zlib
from http import client
from urllib.parse import unquote, urlparse
from xml.etree import ElementTree as ET

import vobject

from . import auth, rights, storage, web, xmlutils

VERSION = "2.1.7"

NOT_ALLOWED = (
    client.FORBIDDEN, (("Content-Type", "text/plain"),),
    "Access to the requested resource forbidden.")
BAD_REQUEST = (
    client.BAD_REQUEST, (("Content-Type", "text/plain"),), "Bad Request")
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
INTERNAL_SERVER_ERROR = (
    client.INTERNAL_SERVER_ERROR, (("Content-Type", "text/plain"),),
    "A server error occurred.  Please contact the administrator.")

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

        if self.max_connections:
            self.connections_guard = threading.BoundedSemaphore(
                self.max_connections)
        else:
            # use dummy context manager
            self.connections_guard = contextlib.ExitStack()

        if bind_and_activate:
            try:
                self.server_bind()
                self.server_activate()
            except:
                self.server_close()
                raise

        if self.client_timeout and sys.version_info < (3, 5, 2):
            self.logger.warning("Using server.timeout with Python < 3.5.2 "
                                "can cause network connection failures")

    def get_request(self):
        # Set timeout for client
        _socket, address = super().get_request()
        if self.client_timeout:
            _socket.settimeout(self.client_timeout)
        return _socket, address

    def handle_error(self, request, client_address):
        if issubclass(sys.exc_info()[0], socket.timeout):
            self.logger.info("client timed out", exc_info=True)
        else:
            self.logger.error("An exception occurred during request: %s",
                              sys.exc_info()[1], exc_info=True)


class HTTPSServer(HTTPServer):
    """HTTPS server."""

    # These class attributes must be set before creating instance
    certificate = None
    key = None
    protocol = None
    ciphers = None
    certificate_authority = None

    def __init__(self, address, handler):
        """Create server by wrapping HTTP socket in an SSL socket."""
        super().__init__(address, handler, bind_and_activate=False)

        self.socket = ssl.wrap_socket(
            self.socket, self.key, self.certificate, server_side=True,
            cert_reqs=ssl.CERT_REQUIRED if self.certificate_authority else
            ssl.CERT_NONE,
            ca_certs=self.certificate_authority or None,
            ssl_version=self.protocol, ciphers=self.ciphers,
            do_handshake_on_connect=False)

        self.server_bind()
        self.server_activate()


class ThreadedHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    def process_request_thread(self, request, client_address):
        with self.connections_guard:
            return super().process_request_thread(request, client_address)


class ThreadedHTTPSServer(socketserver.ThreadingMixIn, HTTPSServer):
    def process_request_thread(self, request, client_address):
        try:
            try:
                request.do_handshake()
            except socket.timeout:
                raise
            except Exception as e:
                raise RuntimeError("SSL handshake failed: %s" % e) from e
        except Exception:
            try:
                self.handle_error(request, client_address)
            finally:
                self.shutdown_request(request)
            return
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
        if hasattr(self.connection, "getpeercert"):
            # The certificate can be evaluated by the auth module
            env["REMOTE_CERTIFICATE"] = self.connection.getpeercert()
        # Parent class only tries latin1 encoding
        env["PATH_INFO"] = unquote(self.path.split("?", 1)[0])
        return env

    def handle(self):
        super().handle()
        # Log exception
        error = self.error_stream.getvalue().strip("\n")
        if error:
            self.logger.error(
                "An unhandled exception occurred during request:\n%s" % error)


class Application:
    """WSGI application managing collections."""

    def __init__(self, configuration, logger):
        """Initialize application."""
        super().__init__()
        self.configuration = configuration
        self.logger = logger
        self.Auth = auth.load(configuration, logger)
        self.Collection = storage.load(configuration, logger)
        self.Rights = rights.load(configuration, logger)
        self.Web = web.load(configuration, logger)
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
        authorization = request_environ.get("HTTP_AUTHORIZATION", "")
        if mask_passwords and authorization.startswith("Basic"):
            request_environ["HTTP_AUTHORIZATION"] = "Basic **masked**"
        if request_environ.get("HTTP_COOKIE"):
            request_environ["HTTP_COOKIE"] = "**masked**"

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
            if isinstance(item, storage.BaseCollection):
                path = storage.sanitize_path("/%s/" % item.path)
                can_read = self.Rights.authorized(user, path, "r")
                can_write = self.Rights.authorized(user, path, "w")
                target = "collection %r" % item.path
            else:
                path = storage.sanitize_path("/%s/%s" % (item.collection.path,
                                                         item.href))
                can_read = self.Rights.authorized_item(user, path, "r")
                can_write = self.Rights.authorized_item(user, path, "w")
                target = "item %r from %r" % (item.href, item.collection.path)
            text_status = []
            if can_read:
                text_status.append("read")
                read_allowed_items.append(item)
            if can_write:
                text_status.append("write")
                write_allowed_items.append(item)
            self.logger.debug(
                "%s has %s access to %s",
                repr(user) if user else "anonymous user",
                " and ".join(text_status) if text_status else "NO", target)
        return read_allowed_items, write_allowed_items

    def __call__(self, environ, start_response):
        try:
            status, headers, answers = self._handle_request(environ)
        except Exception as e:
            try:
                method = str(environ["REQUEST_METHOD"])
            except Exception:
                method = "unknown"
            try:
                path = str(environ.get("PATH_INFO", ""))
            except Exception:
                path = ""
            self.logger.error("An exception occurred during %s request on %r: "
                              "%s", method, path, e, exc_info=True)
            status, headers, answer = INTERNAL_SERVER_ERROR
            answer = answer.encode("ascii")
            status = "%d %s" % (
                status, client.responses.get(status, "Unknown"))
            headers = [("Content-Length", str(len(answer)))] + list(headers)
            answers = [answer]
        start_response(status, headers)
        return answers

    def _handle_request(self, environ):
        """Manage a request."""
        def response(status, headers=(), answer=None):
            headers = dict(headers)
            # Set content length
            if answer:
                if hasattr(answer, "encode"):
                    self.logger.debug("Response content:\n%s", answer)
                    headers["Content-Type"] += "; charset=%s" % self.encoding
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

            # Start response
            time_end = datetime.datetime.now()
            status = "%d %s" % (
                status, client.responses.get(status, "Unknown"))
            self.logger.info(
                "%s response status for %r%s in %.3f seconds: %s",
                environ["REQUEST_METHOD"], environ.get("PATH_INFO", ""),
                depthinfo, (time_end - time_begin).total_seconds(), status)
            # Return response content
            return status, list(headers.items()), [answer] if answer else []

        remote_host = "unknown"
        if environ.get("REMOTE_HOST"):
            remote_host = repr(environ["REMOTE_HOST"])
        elif environ.get("REMOTE_ADDR"):
            remote_host = environ["REMOTE_ADDR"]
        if environ.get("HTTP_X_FORWARDED_FOR"):
            remote_host = "%r (forwarded by %s)" % (
                environ["HTTP_X_FORWARDED_FOR"], remote_host)
        remote_useragent = ""
        if environ.get("HTTP_USER_AGENT"):
            remote_useragent = " using %r" % environ["HTTP_USER_AGENT"]
        depthinfo = ""
        if environ.get("HTTP_DEPTH"):
            depthinfo = " with depth %r" % environ["HTTP_DEPTH"]
        time_begin = datetime.datetime.now()
        self.logger.info(
            "%s request for %r%s received from %s%s",
            environ["REQUEST_METHOD"], environ.get("PATH_INFO", ""), depthinfo,
            remote_host, remote_useragent)
        headers = pprint.pformat(self.headers_log(environ))
        self.logger.debug("Request headers:\n%s", headers)

        # Let reverse proxies overwrite SCRIPT_NAME
        if "HTTP_X_SCRIPT_NAME" in environ:
            # script_name must be removed from PATH_INFO by the client.
            unsafe_base_prefix = environ["HTTP_X_SCRIPT_NAME"]
            self.logger.debug("Script name overwritten by client: %r",
                              unsafe_base_prefix)
        else:
            # SCRIPT_NAME is already removed from PATH_INFO, according to the
            # WSGI specification.
            unsafe_base_prefix = environ.get("SCRIPT_NAME", "")
        # Sanitize base prefix
        base_prefix = storage.sanitize_path(unsafe_base_prefix).rstrip("/")
        self.logger.debug("Sanitized script name: %r", base_prefix)
        # Sanitize request URI (a WSGI server indicates with an empty path,
        # that the URL targets the application root without a trailing slash)
        path = storage.sanitize_path(environ.get("PATH_INFO", ""))
        self.logger.debug("Sanitized path: %r", path)

        # Get function corresponding to method
        function = getattr(self, "do_%s" % environ["REQUEST_METHOD"].upper())

        # If "/.well-known" is not available, clients query "/"
        if path == "/.well-known" or path.startswith("/.well-known/"):
            return response(*NOT_FOUND)

        # Ask authentication backend to check rights
        external_login = self.Auth.get_external_login(environ)
        authorization = environ.get("HTTP_AUTHORIZATION", "")
        if external_login:
            login, password = external_login
        elif authorization.startswith("Basic"):
            authorization = authorization[len("Basic"):].strip()
            login, password = self.decode(base64.b64decode(
                authorization.encode("ascii")), environ).split(":", 1)
        else:
            # DEPRECATED: use remote_user backend instead
            login = environ.get("REMOTE_USER", "")
            password = ""
        user = self.Auth.map_login_to_user(login)

        if not user:
            is_authenticated = True
        elif not storage.is_safe_path_component(user):
            # Prevent usernames like "user/calendar.ics"
            self.logger.info("Refused unsafe username: %r", user)
            is_authenticated = False
        else:
            is_authenticated = self.Auth.is_authenticated2(login, user,
                                                           password)
            if not is_authenticated:
                self.logger.info("Failed login attempt: %r", user)
                # Random delay to avoid timing oracles and bruteforce attacks
                delay = self.configuration.getfloat("auth", "delay")
                if delay > 0:
                    random_delay = delay * (0.5 + random.random())
                    self.logger.debug("Sleeping %.3f seconds", random_delay)
                    time.sleep(random_delay)
            else:
                self.logger.info("Successful login: %r", user)

        # Create principal collection
        if user and is_authenticated:
            principal_path = "/%s/" % user
            if self.Rights.authorized(user, principal_path, "w"):
                with self.Collection.acquire_lock("r", user):
                    principal = next(
                        self.Collection.discover(principal_path, depth="1"),
                        None)
                if not principal:
                    with self.Collection.acquire_lock("w", user):
                        try:
                            self.Collection.create_collection(principal_path)
                        except ValueError as e:
                            self.logger.warning("Failed to create principal "
                                                "collection %r: %s", user, e)
                            is_authenticated = False
            else:
                self.logger.warning("Access to principal path %r denied by "
                                    "rights backend", principal_path)

        # Verify content length
        content_length = int(environ.get("CONTENT_LENGTH") or 0)
        if content_length:
            max_content_length = self.configuration.getint(
                "server", "max_content_length")
            if max_content_length and content_length > max_content_length:
                self.logger.info(
                    "Request body too large: %d", content_length)
                return response(*REQUEST_ENTITY_TOO_LARGE)

        if is_authenticated:
            status, headers, answer = function(
                environ, base_prefix, path, user)
            if (status, headers, answer) == NOT_ALLOWED:
                self.logger.info("Access to %r denied for %s", path,
                                 repr(user) if user else "anonymous user")
        else:
            status, headers, answer = NOT_ALLOWED

        if (status, headers, answer) == NOT_ALLOWED and not (
                user and is_authenticated) and not external_login:
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
        allowed = False
        if not item or isinstance(item, storage.BaseCollection):
            allowed |= self.Rights.authorized(user, path, permission)
        if not item or not isinstance(item, storage.BaseCollection):
            allowed |= self.Rights.authorized_item(user, path, permission)
        return allowed

    def _read_raw_content(self, environ):
        content_length = int(environ.get("CONTENT_LENGTH") or 0)
        if not content_length:
            return b""
        content = environ["wsgi.input"].read(content_length)
        if len(content) < content_length:
            raise RuntimeError("Request body too short: %d" % len(content))
        return content

    def _read_content(self, environ):
        content = self.decode(self._read_raw_content(environ), environ)
        self.logger.debug("Request content:\n%s", content)
        return content

    def _read_xml_content(self, environ):
        content = self.decode(self._read_raw_content(environ), environ)
        if not content:
            return None
        try:
            xml_content = ET.fromstring(content)
        except ET.ParseError as e:
            self.logger.debug("Request content (Invalid XML):\n%s", content)
            raise RuntimeError("Failed to parse XML: %s" % e) from e
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug("Request content:\n%s",
                              xmlutils.pretty_xml(xml_content))
        return xml_content

    def _write_xml_content(self, xml_content):
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug("Response content:\n%s",
                              xmlutils.pretty_xml(xml_content))
        f = io.BytesIO()
        ET.ElementTree(xml_content).write(f, encoding=self.encoding,
                                          xml_declaration=True)
        return f.getvalue()

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
            if isinstance(item, storage.BaseCollection):
                xml_answer = xmlutils.delete(base_prefix, path, item)
            else:
                xml_answer = xmlutils.delete(
                    base_prefix, path, item.collection, item.href)
            headers = {"Content-Type": "text/xml; charset=%s" % self.encoding}
            return client.OK, headers, self._write_xml_content(xml_answer)

    def do_GET(self, environ, base_prefix, path, user):
        """Manage GET request."""
        # Redirect to .web if the root URL is requested
        if not path.strip("/"):
            web_path = ".web"
            if not environ.get("PATH_INFO"):
                web_path = posixpath.join(posixpath.basename(base_prefix),
                                          web_path)
            return (client.FOUND,
                    {"Location": web_path, "Content-Type": "text/plain"},
                    "Redirected to %s" % web_path)
        # Dispatch .web URL to web module
        if path == "/.web" or path.startswith("/.web/"):
            return self.Web.get(environ, base_prefix, path, user)
        if not self._access(user, path, "r"):
            return NOT_ALLOWED
        with self.Collection.acquire_lock("r", user):
            item = next(self.Collection.discover(path), None)
            if not self._access(user, path, "r", item):
                return NOT_ALLOWED
            if not item:
                return NOT_FOUND
            if isinstance(item, storage.BaseCollection):
                tag = item.get_meta("tag")
                if not tag:
                    return DIRECTORY_LISTING
                content_type = xmlutils.MIMETYPES[tag]
            else:
                content_type = xmlutils.OBJECT_MIMETYPES[item.name]
            headers = {
                "Content-Type": content_type,
                "Last-Modified": item.last_modified,
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
        if not self.Rights.authorized(user, path, "w"):
            return NOT_ALLOWED
        try:
            xml_content = self._read_xml_content(environ)
        except RuntimeError as e:
            self.logger.warning(
                "Bad MKCALENDAR request on %r: %s", path, e, exc_info=True)
            return BAD_REQUEST
        except socket.timeout as e:
            self.logger.debug("client timed out", exc_info=True)
            return REQUEST_TIMEOUT
        with self.Collection.acquire_lock("w", user):
            item = next(self.Collection.discover(path), None)
            if item:
                return WEBDAV_PRECONDITION_FAILED
            props = xmlutils.props_from_request(xml_content)
            props["tag"] = "VCALENDAR"
            # TODO: use this?
            # timezone = props.get("C:calendar-timezone")
            try:
                storage.check_and_sanitize_props(props)
                self.Collection.create_collection(path, props=props)
            except ValueError as e:
                self.logger.warning(
                    "Bad MKCALENDAR request on %r: %s", path, e, exc_info=True)
                return BAD_REQUEST
            return client.CREATED, {}, None

    def do_MKCOL(self, environ, base_prefix, path, user):
        """Manage MKCOL request."""
        if not self.Rights.authorized(user, path, "w"):
            return NOT_ALLOWED
        try:
            xml_content = self._read_xml_content(environ)
        except RuntimeError as e:
            self.logger.warning(
                "Bad MKCOL request on %r: %s", path, e, exc_info=True)
            return BAD_REQUEST
        except socket.timeout as e:
            self.logger.debug("client timed out", exc_info=True)
            return REQUEST_TIMEOUT
        with self.Collection.acquire_lock("w", user):
            item = next(self.Collection.discover(path), None)
            if item:
                return WEBDAV_PRECONDITION_FAILED
            props = xmlutils.props_from_request(xml_content)
            try:
                storage.check_and_sanitize_props(props)
                self.Collection.create_collection(path, props=props)
            except ValueError as e:
                self.logger.warning(
                    "Bad MKCOL request on %r: %s", path, e, exc_info=True)
                return BAD_REQUEST
            return client.CREATED, {}, None

    def do_MOVE(self, environ, base_prefix, path, user):
        """Manage MOVE request."""
        raw_dest = environ.get("HTTP_DESTINATION", "")
        to_url = urlparse(raw_dest)
        if to_url.netloc != environ["HTTP_HOST"]:
            self.logger.info("Unsupported destination address: %r", raw_dest)
            # Remote destination server, not supported
            return REMOTE_DESTINATION
        if not self._access(user, path, "w"):
            return NOT_ALLOWED
        to_path = storage.sanitize_path(to_url.path)
        if not (to_path + "/").startswith(base_prefix + "/"):
            self.logger.warning("Destination %r from MOVE request on %r does"
                                "n't start with base prefix", to_path, path)
            return NOT_ALLOWED
        to_path = to_path[len(base_prefix):]
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
            if isinstance(item, storage.BaseCollection):
                return WEBDAV_PRECONDITION_FAILED

            to_item = next(self.Collection.discover(to_path), None)
            if (isinstance(to_item, storage.BaseCollection) or
                    to_item and environ.get("HTTP_OVERWRITE", "F") != "T"):
                return WEBDAV_PRECONDITION_FAILED
            to_parent_path = storage.sanitize_path(
                "/%s/" % posixpath.dirname(to_path.strip("/")))
            to_collection = next(
                self.Collection.discover(to_parent_path), None)
            if not to_collection:
                return WEBDAV_PRECONDITION_FAILED
            to_href = posixpath.basename(to_path.strip("/"))
            try:
                self.Collection.move(item, to_collection, to_href)
            except ValueError as e:
                self.logger.warning(
                    "Bad MOVE request on %r: %s", path, e, exc_info=True)
                return BAD_REQUEST
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
        try:
            xml_content = self._read_xml_content(environ)
        except RuntimeError as e:
            self.logger.warning(
                "Bad PROPFIND request on %r: %s", path, e, exc_info=True)
            return BAD_REQUEST
        except socket.timeout as e:
            self.logger.debug("client timed out", exc_info=True)
            return REQUEST_TIMEOUT
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
            headers = {"DAV": DAV_HEADERS,
                       "Content-Type": "text/xml; charset=%s" % self.encoding}
            status, xml_answer = xmlutils.propfind(
                base_prefix, path, xml_content, read_items, write_items, user)
            if status == client.FORBIDDEN:
                return NOT_ALLOWED
            else:
                return status, headers, self._write_xml_content(xml_answer)

    def do_PROPPATCH(self, environ, base_prefix, path, user):
        """Manage PROPPATCH request."""
        if not self.Rights.authorized(user, path, "w"):
            return NOT_ALLOWED
        try:
            xml_content = self._read_xml_content(environ)
        except RuntimeError as e:
            self.logger.warning(
                "Bad PROPPATCH request on %r: %s", path, e, exc_info=True)
            return BAD_REQUEST
        except socket.timeout as e:
            self.logger.debug("client timed out", exc_info=True)
            return REQUEST_TIMEOUT
        with self.Collection.acquire_lock("w", user):
            item = next(self.Collection.discover(path), None)
            if not isinstance(item, storage.BaseCollection):
                return WEBDAV_PRECONDITION_FAILED
            headers = {"DAV": DAV_HEADERS,
                       "Content-Type": "text/xml; charset=%s" % self.encoding}
            try:
                xml_answer = xmlutils.proppatch(base_prefix, path, xml_content,
                                                item)
            except ValueError as e:
                self.logger.warning(
                    "Bad PROPPATCH request on %r: %s", path, e, exc_info=True)
                return BAD_REQUEST
            return (client.MULTI_STATUS, headers,
                    self._write_xml_content(xml_answer))

    def do_PUT(self, environ, base_prefix, path, user):
        """Manage PUT request."""
        if not self._access(user, path, "w"):
            return NOT_ALLOWED
        try:
            content = self._read_content(environ)
        except RuntimeError as e:
            self.logger.warning(
                "Bad PUT request on %r: %s", path, e, exc_info=True)
            return BAD_REQUEST
        except socket.timeout as e:
            self.logger.debug("client timed out", exc_info=True)
            return REQUEST_TIMEOUT
        with self.Collection.acquire_lock("w", user):
            parent_path = storage.sanitize_path(
                "/%s/" % posixpath.dirname(path.strip("/")))
            item = next(self.Collection.discover(path), None)
            parent_item = next(self.Collection.discover(parent_path), None)

            write_whole_collection = (
                isinstance(item, storage.BaseCollection) or
                not parent_item or (
                    not next(parent_item.list(), None) and
                    parent_item.get_meta("tag") not in (
                        "VADDRESSBOOK", "VCALENDAR")))
            if write_whole_collection:
                if not self.Rights.authorized(user, path, "w"):
                    return NOT_ALLOWED
            elif not self.Rights.authorized_item(user, path, "w"):
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

            try:
                items = tuple(vobject.readComponents(content or ""))
                if not write_whole_collection and len(items) != 1:
                    raise RuntimeError(
                        "Item contains %d components" % len(items))
                if write_whole_collection or not parent_item.get_meta("tag"):
                    content_type = environ.get("CONTENT_TYPE",
                                               "").split(";")[0]
                    tags = {value: key
                            for key, value in xmlutils.MIMETYPES.items()}
                    tag = tags.get(content_type)
                    if items and items[0].name == "VCALENDAR":
                        tag = "VCALENDAR"
                    elif items and items[0].name in ("VCARD", "VLIST"):
                        tag = "VADDRESSBOOK"
                else:
                    tag = parent_item.get_meta("tag")
                if tag == "VCALENDAR" and len(items) > 1:
                    raise RuntimeError("VCALENDAR collection contains %d "
                                       "components" % len(items))
                for i in items:
                    storage.check_and_sanitize_item(
                        i, is_collection=write_whole_collection, uid=item.uid
                        if not write_whole_collection and item else None,
                        tag=tag)
            except Exception as e:
                self.logger.warning(
                    "Bad PUT request on %r: %s", path, e, exc_info=True)
                return BAD_REQUEST

            if write_whole_collection:
                props = {}
                if tag:
                    props["tag"] = tag
                if tag == "VCALENDAR" and items:
                    if hasattr(items[0], "x_wr_calname"):
                        calname = items[0].x_wr_calname.value
                        if calname:
                            props["D:displayname"] = calname
                    if hasattr(items[0], "x_wr_caldesc"):
                        caldesc = items[0].x_wr_caldesc.value
                        if caldesc:
                            props["C:calendar-description"] = caldesc
                try:
                    storage.check_and_sanitize_props(props)
                    new_item = self.Collection.create_collection(
                        path, items, props)
                except ValueError as e:
                    self.logger.warning(
                        "Bad PUT request on %r: %s", path, e, exc_info=True)
                    return BAD_REQUEST
            else:
                href = posixpath.basename(path.strip("/"))
                try:
                    if tag and not parent_item.get_meta("tag"):
                        new_props = parent_item.get_meta()
                        new_props["tag"] = tag
                        storage.check_and_sanitize_props(new_props)
                        parent_item.set_meta_all(new_props)
                    new_item = parent_item.upload(href, items[0])
                except ValueError as e:
                    self.logger.warning(
                        "Bad PUT request on %r: %s", path, e, exc_info=True)
                    return BAD_REQUEST
            headers = {"ETag": new_item.etag}
            return client.CREATED, headers, None

    def do_REPORT(self, environ, base_prefix, path, user):
        """Manage REPORT request."""
        if not self._access(user, path, "r"):
            return NOT_ALLOWED
        try:
            xml_content = self._read_xml_content(environ)
        except RuntimeError as e:
            self.logger.warning(
                "Bad REPORT request on %r: %s", path, e, exc_info=True)
            return BAD_REQUEST
        except socket.timeout as e:
            self.logger.debug("client timed out", exc_info=True)
            return REQUEST_TIMEOUT
        with self.Collection.acquire_lock("r", user):
            item = next(self.Collection.discover(path), None)
            if not self._access(user, path, "r", item):
                return NOT_ALLOWED
            if not item:
                return NOT_FOUND
            if isinstance(item, storage.BaseCollection):
                collection = item
            else:
                collection = item.collection
            headers = {"Content-Type": "text/xml; charset=%s" % self.encoding}
            try:
                status, xml_answer = xmlutils.report(
                    base_prefix, path, xml_content, collection)
            except ValueError as e:
                self.logger.warning(
                    "Bad REPORT request on %r: %s", path, e, exc_info=True)
                return BAD_REQUEST
            return (status, headers, self._write_xml_content(xml_answer))
