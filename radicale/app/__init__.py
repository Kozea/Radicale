# This file is part of Radicale - CalDAV and CardDAV server
# Copyright © 2008 Nicolas Kandel
# Copyright © 2008 Pascal Halter
# Copyright © 2008-2017 Guillaume Ayoub
# Copyright © 2017-2019 Unrud <unrud@outlook.com>
# Copyright © 2024-2025 Peter Bieringer <pb@bieringer.de>
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

Can be used with an external WSGI server (see ``radicale.application()``) or
the built-in server (see ``radicale.server`` module).

"""

import base64
import datetime
import pprint
import random
import time
import zlib
from http import client
from typing import Iterable, List, Mapping, Tuple, Union

from radicale import config, httputils, log, pathutils, types
from radicale.app.base import ApplicationBase
from radicale.app.delete import ApplicationPartDelete
from radicale.app.get import ApplicationPartGet
from radicale.app.head import ApplicationPartHead
from radicale.app.mkcalendar import ApplicationPartMkcalendar
from radicale.app.mkcol import ApplicationPartMkcol
from radicale.app.move import ApplicationPartMove
from radicale.app.options import ApplicationPartOptions
from radicale.app.post import ApplicationPartPost
from radicale.app.propfind import ApplicationPartPropfind
from radicale.app.proppatch import ApplicationPartProppatch
from radicale.app.put import ApplicationPartPut
from radicale.app.report import ApplicationPartReport
from radicale.auth import AuthContext
from radicale.log import logger

# Combination of types.WSGIStartResponse and WSGI application return value
_IntermediateResponse = Tuple[str, List[Tuple[str, str]], Iterable[bytes]]


class Application(ApplicationPartDelete, ApplicationPartHead,
                  ApplicationPartGet, ApplicationPartMkcalendar,
                  ApplicationPartMkcol, ApplicationPartMove,
                  ApplicationPartOptions, ApplicationPartPropfind,
                  ApplicationPartProppatch, ApplicationPartPost,
                  ApplicationPartPut, ApplicationPartReport, ApplicationBase):
    """WSGI application."""

    _mask_passwords: bool
    _auth_delay: float
    _internal_server: bool
    _max_content_length: int
    _auth_realm: str
    _auth_type: str
    _web_type: str
    _script_name: str
    _extra_headers: Mapping[str, str]

    def __init__(self, configuration: config.Configuration) -> None:
        """Initialize Application.

        ``configuration`` see ``radicale.config`` module.
        The ``configuration`` must not change during the lifetime of
        this object, it is kept as an internal reference.

        """
        super().__init__(configuration)
        self._mask_passwords = configuration.get("logging", "mask_passwords")
        self._bad_put_request_content = configuration.get("logging", "bad_put_request_content")
        self._request_header_on_debug = configuration.get("logging", "request_header_on_debug")
        self._response_content_on_debug = configuration.get("logging", "response_content_on_debug")
        self._auth_delay = configuration.get("auth", "delay")
        self._auth_type = configuration.get("auth", "type")
        self._web_type = configuration.get("web", "type")
        self._internal_server = configuration.get("server", "_internal_server")
        self._script_name = configuration.get("server", "script_name")
        if self._script_name:
            if self._script_name[0] != "/":
                logger.error("server.script_name must start with '/': %r", self._script_name)
                raise RuntimeError("server.script_name option has to start with '/'")
            else:
                if self._script_name.endswith("/"):
                    logger.error("server.script_name must not end with '/': %r", self._script_name)
                    raise RuntimeError("server.script_name option must not end with '/'")
                else:
                    logger.info("Provided script name to strip from URI if called by reverse proxy: %r", self._script_name)
        else:
            logger.info("Default script name to strip from URI if called by reverse proxy is taken from HTTP_X_SCRIPT_NAME or SCRIPT_NAME")
        self._max_content_length = configuration.get(
            "server", "max_content_length")
        self._auth_realm = configuration.get("auth", "realm")
        self._permit_delete_collection = configuration.get("rights", "permit_delete_collection")
        logger.info("permit delete of collection: %s", self._permit_delete_collection)
        self._permit_overwrite_collection = configuration.get("rights", "permit_overwrite_collection")
        logger.info("permit overwrite of collection: %s", self._permit_overwrite_collection)
        self._extra_headers = dict()
        for key in self.configuration.options("headers"):
            self._extra_headers[key] = configuration.get("headers", key)
        self._strict_preconditions = configuration.get("storage", "strict_preconditions")
        logger.info("strict preconditions check: %s", self._strict_preconditions)

    def _scrub_headers(self, environ: types.WSGIEnviron) -> types.WSGIEnviron:
        """Mask passwords and cookies."""
        headers = dict(environ)
        if (self._mask_passwords and
                headers.get("HTTP_AUTHORIZATION", "").startswith("Basic")):
            headers["HTTP_AUTHORIZATION"] = "Basic **masked**"
        if headers.get("HTTP_COOKIE"):
            headers["HTTP_COOKIE"] = "**masked**"
        return headers

    def __call__(self, environ: types.WSGIEnviron, start_response:
                 types.WSGIStartResponse) -> Iterable[bytes]:
        with log.register_stream(environ["wsgi.errors"]):
            try:
                status_text, headers, answers = self._handle_request(environ)
            except Exception as e:
                logger.error("An exception occurred during %s request on %r: "
                             "%s", environ.get("REQUEST_METHOD", "unknown"),
                             environ.get("PATH_INFO", ""), e, exc_info=True)
                # Make minimal response
                status, raw_headers, raw_answer = (
                    httputils.INTERNAL_SERVER_ERROR)
                assert isinstance(raw_answer, str)
                answer = raw_answer.encode("ascii")
                status_text = "%d %s" % (
                    status, client.responses.get(status, "Unknown"))
                headers = [*raw_headers, ("Content-Length", str(len(answer)))]
                answers = [answer]
            start_response(status_text, headers)
        if environ.get("REQUEST_METHOD") == "HEAD":
            return []
        return answers

    def _handle_request(self, environ: types.WSGIEnviron
                        ) -> _IntermediateResponse:
        time_begin = datetime.datetime.now()
        request_method = environ["REQUEST_METHOD"].upper()
        unsafe_path = environ.get("PATH_INFO", "")
        https = environ.get("HTTPS", "")

        context = AuthContext()

        """Manage a request."""
        def response(status: int, headers: types.WSGIResponseHeaders,
                     answer: Union[None, str, bytes]) -> _IntermediateResponse:
            """Helper to create response from internal types.WSGIResponse"""
            headers = dict(headers)
            content_encoding = "plain"
            # Set content length
            answers = []
            if answer is not None:
                if isinstance(answer, str):
                    if self._response_content_on_debug:
                        logger.debug("Response content:\n%s", answer)
                    else:
                        logger.debug("Response content: suppressed by config/option [logging] response_content_on_debug")
                    headers["Content-Type"] += "; charset=%s" % self._encoding
                    answer = answer.encode(self._encoding)
                accept_encoding = [
                    encoding.strip() for encoding in
                    environ.get("HTTP_ACCEPT_ENCODING", "").split(",")
                    if encoding.strip()]

                if "gzip" in accept_encoding:
                    zcomp = zlib.compressobj(wbits=16 + zlib.MAX_WBITS)
                    answer = zcomp.compress(answer) + zcomp.flush()
                    headers["Content-Encoding"] = "gzip"
                    content_encoding = "gzip"

                headers["Content-Length"] = str(len(answer))
                answers.append(answer)

            # Add extra headers set in configuration
            headers.update(self._extra_headers)

            # Start response
            time_end = datetime.datetime.now()
            status_text = "%d %s" % (
                status, client.responses.get(status, "Unknown"))
            if answer is not None:
                logger.info("%s response status for %r%s in %.3f seconds %s %s bytes: %s",
                            request_method, unsafe_path, depthinfo,
                            (time_end - time_begin).total_seconds(), content_encoding, str(len(answer)), status_text)
            else:
                logger.info("%s response status for %r%s in %.3f seconds: %s",
                            request_method, unsafe_path, depthinfo,
                            (time_end - time_begin).total_seconds(), status_text)
            # Return response content
            return status_text, list(headers.items()), answers

        reverse_proxy = False
        remote_host = "unknown"
        if environ.get("REMOTE_HOST"):
            remote_host = repr(environ["REMOTE_HOST"])
        if environ.get("REMOTE_ADDR"):
            if remote_host == 'unknown':
                remote_host = environ["REMOTE_ADDR"]
            context.remote_addr = environ["REMOTE_ADDR"]
        if environ.get("HTTP_X_FORWARDED_FOR"):
            reverse_proxy = True
            remote_host = "%s (forwarded for %r)" % (
                remote_host, environ["HTTP_X_FORWARDED_FOR"])
        if environ.get("HTTP_X_REMOTE_ADDR"):
            context.x_remote_addr = environ["HTTP_X_REMOTE_ADDR"]
        if environ.get("HTTP_X_FORWARDED_HOST") or environ.get("HTTP_X_FORWARDED_PROTO") or environ.get("HTTP_X_FORWARDED_SERVER"):
            reverse_proxy = True
        remote_useragent = ""
        if environ.get("HTTP_USER_AGENT"):
            remote_useragent = " using %r" % environ["HTTP_USER_AGENT"]
        depthinfo = ""
        if environ.get("HTTP_DEPTH"):
            depthinfo = " with depth %r" % environ["HTTP_DEPTH"]
        if https:
            https_info = " " + environ.get("SSL_PROTOCOL", "") + " " + environ.get("SSL_CIPHER", "")
        else:
            https_info = ""
        logger.info("%s request for %r%s received from %s%s%s",
                    request_method, unsafe_path, depthinfo,
                    remote_host, remote_useragent, https_info)
        if self._request_header_on_debug:
            logger.debug("Request header:\n%s",
                         pprint.pformat(self._scrub_headers(environ)))
        else:
            logger.debug("Request header: suppressed by config/option [logging] request_header_on_debug")

        # SCRIPT_NAME is already removed from PATH_INFO, according to the
        # WSGI specification.
        # Reverse proxies can overwrite SCRIPT_NAME with X-SCRIPT-NAME header
        if self._script_name and (reverse_proxy is True):
            base_prefix_src = "config"
            base_prefix = self._script_name
        else:
            base_prefix_src = ("HTTP_X_SCRIPT_NAME" if "HTTP_X_SCRIPT_NAME" in
                               environ else "SCRIPT_NAME")
            base_prefix = environ.get(base_prefix_src, "")
            if base_prefix and base_prefix[0] != "/":
                logger.error("Base prefix (from %s) must start with '/': %r",
                             base_prefix_src, base_prefix)
                if base_prefix_src == "HTTP_X_SCRIPT_NAME":
                    return response(*httputils.BAD_REQUEST)
                return response(*httputils.INTERNAL_SERVER_ERROR)
            if base_prefix.endswith("/"):
                logger.warning("Base prefix (from %s) must not end with '/': %r",
                               base_prefix_src, base_prefix)
                base_prefix = base_prefix.rstrip("/")
        if base_prefix:
            logger.debug("Base prefix (from %s): %r", base_prefix_src, base_prefix)

        # Sanitize request URI (a WSGI server indicates with an empty path,
        # that the URL targets the application root without a trailing slash)
        path = pathutils.sanitize_path(unsafe_path)
        logger.debug("Sanitized path: %r", path)
        if (reverse_proxy is True) and (len(base_prefix) > 0):
            if path.startswith(base_prefix):
                path_new = path.removeprefix(base_prefix)
                logger.debug("Called by reverse proxy, remove base prefix %r from path: %r => %r", base_prefix, path, path_new)
                path = path_new
            else:
                if self._auth_type in ['remote_user', 'http_remote_user', 'http_x_remote_user'] and self._web_type == 'internal':
                    logger.warning("Called by reverse proxy, cannot remove base prefix %r from path: %r as not matching (may cause authentication issues using internal WebUI)", base_prefix, path)
                else:
                    logger.debug("Called by reverse proxy, cannot remove base prefix %r from path: %r as not matching", base_prefix, path)

        # Get function corresponding to method
        function = getattr(self, "do_%s" % request_method, None)
        if not function:
            return response(*httputils.METHOD_NOT_ALLOWED)

        # Redirect all "…/.well-known/{caldav,carddav}" paths to "/".
        # This shouldn't be necessary but some clients like TbSync require it.
        # Status must be MOVED PERMANENTLY using FOUND causes problems
        if (path.rstrip("/").endswith("/.well-known/caldav") or
                path.rstrip("/").endswith("/.well-known/carddav")):
            return response(*httputils.redirect(
                base_prefix + "/", client.MOVED_PERMANENTLY))
        # Return NOT FOUND for all other paths containing ".well-known"
        if path.endswith("/.well-known") or "/.well-known/" in path:
            return response(*httputils.NOT_FOUND)

        # Ask authentication backend to check rights
        login = password = ""
        external_login = self._auth.get_external_login(environ)
        authorization = environ.get("HTTP_AUTHORIZATION", "")
        if external_login:
            login, password = external_login
            login, password = login or "", password or ""
        elif authorization.startswith("Basic"):
            authorization = authorization[len("Basic"):].strip()
            login, password = httputils.decode_request(
                self.configuration, environ, base64.b64decode(
                    authorization.encode("ascii"))).split(":", 1)

        (user, info) = self._auth.login(login, password, context) or ("", "") if login else ("", "")
        if self.configuration.get("auth", "type") == "ldap":
            try:
                logger.debug("Groups received from LDAP: %r", ",".join(self._auth._ldap_groups))
                self._rights._user_groups = self._auth._ldap_groups
            except AttributeError:
                pass
        if user and login == user:
            logger.info("Successful login: %r (%s)", user, info)
        elif user:
            logger.info("Successful login: %r -> %r (%s)", login, user, info)
        elif login:
            logger.warning("Failed login attempt from %s: %r (%s)",
                           remote_host, login, info)
            # Random delay to avoid timing oracles and bruteforce attacks
            if self._auth_delay > 0:
                random_delay = self._auth_delay * (0.5 + random.random())
                logger.debug("Failed login, sleeping random: %.3f sec", random_delay)
                time.sleep(random_delay)

        if user and not pathutils.is_safe_path_component(user):
            # Prevent usernames like "user/calendar.ics"
            logger.info("Refused unsafe username: %r", user)
            user = ""

        # Create principal collection
        if user:
            principal_path = "/%s/" % user
            with self._storage.acquire_lock("r", user):
                principal = next(iter(self._storage.discover(
                    principal_path, depth="1")), None)
            if not principal:
                if "W" in self._rights.authorization(user, principal_path):
                    with self._storage.acquire_lock("w", user):
                        try:
                            new_coll, _, _ = self._storage.create_collection(principal_path)
                            if new_coll:
                                jsn_coll = self.configuration.get("storage", "predefined_collections")
                                for (name_coll, props) in jsn_coll.items():
                                    try:
                                        self._storage.create_collection(principal_path + name_coll, props=props)
                                    except ValueError as e:
                                        logger.warning("Failed to create predefined collection %r: %s", name_coll, e)
                        except ValueError as e:
                            logger.warning("Failed to create principal "
                                           "collection %r: %s", user, e)
                            user = ""
                else:
                    logger.warning("Access to principal path %r denied by "
                                   "rights backend", principal_path)

        if self._internal_server:
            # Verify content length
            content_length = int(environ.get("CONTENT_LENGTH") or 0)
            if content_length:
                if (self._max_content_length > 0 and
                        content_length > self._max_content_length):
                    logger.info("Request body too large: %d", content_length)
                    return response(*httputils.REQUEST_ENTITY_TOO_LARGE)

        if not login or user:
            status, headers, answer = function(
                environ, base_prefix, path, user, remote_host, remote_useragent)
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
            headers = dict(headers)
            headers.update({
                "WWW-Authenticate":
                "Basic realm=\"%s\"" % self._auth_realm})

        return response(status, headers, answer)
