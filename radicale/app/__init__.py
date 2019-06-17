# This file is part of Radicale Server - Calendar Server
# Copyright © 2008 Nicolas Kandel
# Copyright © 2008 Pascal Halter
# Copyright © 2008-2017 Guillaume Ayoub
# Copyright © 2017-2019 Unrud <unrud@outlook.com>
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
Radicale WSGI application.

Can be used with an external WSGI server or the built-in server.

"""

import base64
import datetime
import io
import logging
import posixpath
import pprint
import random
import time
import zlib
from http import client
from xml.etree import ElementTree as ET

import pkg_resources

from radicale import (auth, httputils, log, pathutils, rights, storage, web,
                      xmlutils)
from radicale.app.delete import ApplicationDeleteMixin
from radicale.app.get import ApplicationGetMixin
from radicale.app.head import ApplicationHeadMixin
from radicale.app.mkcalendar import ApplicationMkcalendarMixin
from radicale.app.mkcol import ApplicationMkcolMixin
from radicale.app.move import ApplicationMoveMixin
from radicale.app.options import ApplicationOptionsMixin
from radicale.app.propfind import ApplicationPropfindMixin
from radicale.app.proppatch import ApplicationProppatchMixin
from radicale.app.put import ApplicationPutMixin
from radicale.app.report import ApplicationReportMixin
from radicale.log import logger

VERSION = pkg_resources.get_distribution("radicale").version


class Application(
        ApplicationDeleteMixin, ApplicationGetMixin, ApplicationHeadMixin,
        ApplicationMkcalendarMixin, ApplicationMkcolMixin,
        ApplicationMoveMixin, ApplicationOptionsMixin,
        ApplicationPropfindMixin, ApplicationProppatchMixin,
        ApplicationPutMixin, ApplicationReportMixin):

    """WSGI application managing collections."""

    def __init__(self, configuration):
        """Initialize application."""
        super().__init__()
        self.configuration = configuration
        self.Auth = auth.load(configuration)
        self.Collection = storage.load(configuration)
        self.Rights = rights.load(configuration)
        self.Web = web.load(configuration)
        self.encoding = configuration.get("encoding", "request")

    def _headers_log(self, environ):
        """Sanitize headers for logging."""
        request_environ = dict(environ)

        # Mask passwords
        mask_passwords = self.configuration.get("logging", "mask_passwords")
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

    def __call__(self, environ, start_response):
        with log.register_stream(environ["wsgi.errors"]):
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
                logger.error("An exception occurred during %s request on %r: "
                             "%s", method, path, e, exc_info=True)
                status, headers, answer = httputils.INTERNAL_SERVER_ERROR
                answer = answer.encode("ascii")
                status = "%d %s" % (
                    status, client.responses.get(status, "Unknown"))
                headers = [
                    ("Content-Length", str(len(answer)))] + list(headers)
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
                    logger.debug("Response content:\n%s", answer)
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
            for key in self.configuration.options("headers"):
                headers[key] = self.configuration.get("headers", key)

            # Start response
            time_end = datetime.datetime.now()
            status = "%d %s" % (
                status, client.responses.get(status, "Unknown"))
            logger.info(
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
        logger.info(
            "%s request for %r%s received from %s%s",
            environ["REQUEST_METHOD"], environ.get("PATH_INFO", ""), depthinfo,
            remote_host, remote_useragent)
        headers = pprint.pformat(self._headers_log(environ))
        logger.debug("Request headers:\n%s", headers)

        # Let reverse proxies overwrite SCRIPT_NAME
        if "HTTP_X_SCRIPT_NAME" in environ:
            # script_name must be removed from PATH_INFO by the client.
            unsafe_base_prefix = environ["HTTP_X_SCRIPT_NAME"]
            logger.debug("Script name overwritten by client: %r",
                         unsafe_base_prefix)
        else:
            # SCRIPT_NAME is already removed from PATH_INFO, according to the
            # WSGI specification.
            unsafe_base_prefix = environ.get("SCRIPT_NAME", "")
        # Sanitize base prefix
        base_prefix = pathutils.sanitize_path(unsafe_base_prefix).rstrip("/")
        logger.debug("Sanitized script name: %r", base_prefix)
        # Sanitize request URI (a WSGI server indicates with an empty path,
        # that the URL targets the application root without a trailing slash)
        path = pathutils.sanitize_path(environ.get("PATH_INFO", ""))
        logger.debug("Sanitized path: %r", path)

        # Get function corresponding to method
        function = getattr(self, "do_%s" % environ["REQUEST_METHOD"].upper())

        # If "/.well-known" is not available, clients query "/"
        if path == "/.well-known" or path.startswith("/.well-known/"):
            return response(*httputils.NOT_FOUND)

        # Ask authentication backend to check rights
        login = password = ""
        external_login = self.Auth.get_external_login(environ)
        authorization = environ.get("HTTP_AUTHORIZATION", "")
        if external_login:
            login, password = external_login
            login, password = login or "", password or ""
        elif authorization.startswith("Basic"):
            authorization = authorization[len("Basic"):].strip()
            login, password = self.decode(base64.b64decode(
                authorization.encode("ascii")), environ).split(":", 1)

        user = self.Auth.login(login, password) or "" if login else ""
        if user and login == user:
            logger.info("Successful login: %r", user)
        elif user:
            logger.info("Successful login: %r -> %r", login, user)
        elif login:
            logger.info("Failed login attempt: %r", login)
            # Random delay to avoid timing oracles and bruteforce attacks
            delay = self.configuration.get("auth", "delay")
            if delay > 0:
                random_delay = delay * (0.5 + random.random())
                logger.debug("Sleeping %.3f seconds", random_delay)
                time.sleep(random_delay)

        if user and not pathutils.is_safe_path_component(user):
            # Prevent usernames like "user/calendar.ics"
            logger.info("Refused unsafe username: %r", user)
            user = ""

        # Create principal collection
        if user:
            principal_path = "/%s/" % user
            if self.Rights.authorized(user, principal_path, "W"):
                with self.Collection.acquire_lock("r", user):
                    principal = next(
                        self.Collection.discover(principal_path, depth="1"),
                        None)
                if not principal:
                    with self.Collection.acquire_lock("w", user):
                        try:
                            self.Collection.create_collection(principal_path)
                        except ValueError as e:
                            logger.warning("Failed to create principal "
                                           "collection %r: %s", user, e)
                            user = ""
            else:
                logger.warning("Access to principal path %r denied by "
                               "rights backend", principal_path)

        if self.configuration.get("internal", "internal_server"):
            # Verify content length
            content_length = int(environ.get("CONTENT_LENGTH") or 0)
            if content_length:
                max_content_length = self.configuration.get(
                    "server", "max_content_length")
                if max_content_length and content_length > max_content_length:
                    logger.info("Request body too large: %d", content_length)
                    return response(*httputils.REQUEST_ENTITY_TOO_LARGE)

        if not login or user:
            status, headers, answer = function(
                environ, base_prefix, path, user)
            if (status, headers, answer) == httputils.NOT_ALLOWED:
                logger.info("Access to %r denied for %s", path,
                            repr(user) if user else "anonymous user")
        else:
            status, headers, answer = httputils.NOT_ALLOWED

        if ((status, headers, answer) == httputils.NOT_ALLOWED and not user and
                not external_login):
            # Unknown or unauthorized user
            logger.debug("Asking client for authentication")
            status = client.UNAUTHORIZED
            realm = self.configuration.get("auth", "realm")
            headers = dict(headers)
            headers.update({
                "WWW-Authenticate":
                "Basic realm=\"%s\"" % realm})

        return response(status, headers, answer)

    def access(self, user, path, permission, item=None):
        if permission not in "rw":
            raise ValueError("Invalid permission argument: %r" % permission)
        if not item:
            permissions = permission + permission.upper()
            parent_permissions = permission
        elif isinstance(item, storage.BaseCollection):
            if item.get_meta("tag"):
                permissions = permission
            else:
                permissions = permission.upper()
            parent_permissions = ""
        else:
            permissions = ""
            parent_permissions = permission
        if permissions and self.Rights.authorized(user, path, permissions):
            return True
        if parent_permissions:
            parent_path = pathutils.unstrip_path(
                posixpath.dirname(pathutils.strip_path(path)), True)
            if self.Rights.authorized(user, parent_path, parent_permissions):
                return True
        return False

    def read_raw_content(self, environ):
        content_length = int(environ.get("CONTENT_LENGTH") or 0)
        if not content_length:
            return b""
        content = environ["wsgi.input"].read(content_length)
        if len(content) < content_length:
            raise RuntimeError("Request body too short: %d" % len(content))
        return content

    def read_content(self, environ):
        content = self.decode(self.read_raw_content(environ), environ)
        logger.debug("Request content:\n%s", content)
        return content

    def read_xml_content(self, environ):
        content = self.decode(self.read_raw_content(environ), environ)
        if not content:
            return None
        try:
            xml_content = ET.fromstring(content)
        except ET.ParseError as e:
            logger.debug("Request content (Invalid XML):\n%s", content)
            raise RuntimeError("Failed to parse XML: %s" % e) from e
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("Request content:\n%s",
                         xmlutils.pretty_xml(xml_content))
        return xml_content

    def write_xml_content(self, xml_content):
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("Response content:\n%s",
                         xmlutils.pretty_xml(xml_content))
        f = io.BytesIO()
        ET.ElementTree(xml_content).write(f, encoding=self.encoding,
                                          xml_declaration=True)
        return f.getvalue()

    def webdav_error_response(self, namespace, name,
                              status=httputils.WEBDAV_PRECONDITION_FAILED[0]):
        """Generate XML error response."""
        headers = {"Content-Type": "text/xml; charset=%s" % self.encoding}
        content = self.write_xml_content(
            xmlutils.webdav_error(namespace, name))
        return status, headers, content
