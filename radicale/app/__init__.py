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
import cProfile
import datetime
import io
import logging
import pprint
import pstats
import random
import time
import zlib
from http import client
from typing import Iterable, List, Mapping, Tuple, Union

from radicale import config, httputils, log, pathutils, types, utils
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

REQUEST_METHODS = ["DELETE", "GET", "HEAD", "MKCALENDAR", "MKCOL", "MOVE", "OPTIONS", "POST", "PROPFIND", "PROPPATCH", "PUT", "REPORT"]


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
    _max_resource_size: int
    _auth_realm: str
    _auth_type: str
    _web_type: str
    _script_name: str
    _extra_headers: Mapping[str, str]
    _profiling_per_request: bool = False
    _profiling_per_request_method: bool = False
    profiler_per_request_method: dict[str, cProfile.Profile] = {}
    profiler_per_request_method_counter: dict[str, int] = {}
    profiler_per_request_method_starttime: datetime.datetime
    profiler_per_request_method_logtime: datetime.datetime

    def __init__(self, configuration: config.Configuration) -> None:
        """Initialize Application.

        ``configuration`` see ``radicale.config`` module.
        The ``configuration`` must not change during the lifetime of
        this object, it is kept as an internal reference.

        """
        super().__init__(configuration)
        self._mask_passwords = configuration.get("logging", "mask_passwords")
        self._max_content_length = configuration.get("server", "max_content_length")
        self._max_resource_size = configuration.get("server", "max_resource_size")
        logger.info("max_content_length set to: %d bytes (%sbytes)", self._max_content_length, utils.format_unit(self._max_content_length, binary=True))
        if (self._max_resource_size > (self._max_content_length * 0.8)):
            max_resource_size_limited = int(self._max_content_length * 0.8)
            logger.warning("max_resource_size set to: %d bytes (%sbytes) (capped from %d to 80%% of max_content_length)", max_resource_size_limited, utils.format_unit(max_resource_size_limited, binary=True), self._max_resource_size)
            self._max_resource_size = max_resource_size_limited
        else:
            logger.info("max_resource_size  set to: %d bytes (%sbytes)", self._max_resource_size, utils.format_unit(self._max_resource_size, binary=True))
        self._bad_put_request_content = configuration.get("logging", "bad_put_request_content")
        logger.info("log bad put request content: %s", self._bad_put_request_content)
        self._request_header_on_debug = configuration.get("logging", "request_header_on_debug")
        self._request_content_on_debug = configuration.get("logging", "request_content_on_debug")
        self._response_header_on_debug = configuration.get("logging", "response_header_on_debug")
        self._response_content_on_debug = configuration.get("logging", "response_content_on_debug")
        logger.debug("log request  header  on debug: %s", self._request_header_on_debug)
        logger.debug("log request  content on debug: %s", self._request_content_on_debug)
        logger.debug("log response header  on debug: %s", self._response_header_on_debug)
        logger.debug("log response content on debug: %s", self._response_content_on_debug)
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
        # Profiling options
        self._profiling = configuration.get("logging", "profiling")
        self._profiling_per_request_min_duration = configuration.get("logging", "profiling_per_request_min_duration")
        self._profiling_per_request_header = configuration.get("logging", "profiling_per_request_header")
        self._profiling_per_request_xml = configuration.get("logging", "profiling_per_request_xml")
        self._profiling_per_request_method_interval = configuration.get("logging", "profiling_per_request_method_interval")
        self._profiling_top_x_functions = configuration.get("logging", "profiling_top_x_functions")
        if self._profiling in config.PROFILING:
            logger.info("profiling: %r", self._profiling)
            if self._profiling == "per_request":
                self._profiling_per_request = True
            elif self._profiling == "per_request_method":
                self._profiling_per_request_method = True
        if self._profiling_per_request or self._profiling_per_request_method:
            logger.info("profiling top X functions: %d", self._profiling_top_x_functions)
        if self._profiling_per_request:
            logger.info("profiling per request minimum duration: %d (below are skipped)", self._profiling_per_request_min_duration)
            logger.info("profiling per request header: %s", self._profiling_per_request_header)
            logger.info("profiling per request xml   : %s", self._profiling_per_request_xml)
        if self._profiling_per_request_method:
            logger.info("profiling per request method interval: %d seconds", self._profiling_per_request_method_interval)
        # Profiling per request method initialization
        if self._profiling_per_request_method:
            for method in REQUEST_METHODS:
                self.profiler_per_request_method[method] = cProfile.Profile()
                self.profiler_per_request_method_counter[method] = False
        self.profiler_per_request_method_starttime = datetime.datetime.now()
        self.profiler_per_request_method_logtime = self.profiler_per_request_method_starttime

    def __del__(self) -> None:
        """Shutdown application."""
        if self._profiling_per_request_method:
            # Profiling since startup
            self._profiler_per_request_method(True)

    def _profiler_per_request_method(self, shutdown: bool = False) -> None:
        """Display profiler data per method."""
        profiler_timedelta_start = (datetime.datetime.now() - self.profiler_per_request_method_starttime).total_seconds()
        for method in REQUEST_METHODS:
            if self.profiler_per_request_method_counter[method] > 0:
                s = io.StringIO()
                s.write("**Profiling statistics BEGIN**\n")
                stats = pstats.Stats(self.profiler_per_request_method[method], stream=s).sort_stats('cumulative')
                stats.print_stats(self._profiling_top_x_functions)  # Print top X functions
                s.write("**Profiling statistics END**\n")
                logger.info("Profiling data per request method %s after %d seconds and %d requests:\n%s", method, profiler_timedelta_start, self.profiler_per_request_method_counter[method], utils.textwrap_str(s.getvalue(), -1))
            else:
                if shutdown:
                    logger.info("Profiling data per request method %s after %d seconds: (no request seen so far)", method, profiler_timedelta_start)
                else:
                    logger.debug("Profiling data per request method %s after %d seconds: (no request seen so far)", method, profiler_timedelta_start)

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
                status, raw_headers, raw_answer, xml_request = (
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
        profiler = None
        profiler_active = False
        xml_request = None

        context = AuthContext()

        """Manage a request."""
        def response(status: int, headers: types.WSGIResponseHeaders,
                     answer: Union[None, str, bytes],
                     xml_request: Union[None, str] = None) -> _IntermediateResponse:
            """Helper to create response from internal types.WSGIResponse"""
            headers = dict(headers)
            content_encoding = "plain"
            # Set content length
            answers = []
            if answer is not None:
                if isinstance(answer, str):
                    if self._response_content_on_debug:
                        if logger.isEnabledFor(logging.DEBUG):
                            logger.debug("Response content (nonXML):\n%s", utils.textwrap_str(answer))
                    else:
                        if logger.isEnabledFor(logging.DEBUG):
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

            if self._response_header_on_debug:
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug("Response header:\n%s", utils.textwrap_str(pprint.pformat(headers)))
            else:
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug("Response header: suppressed by config/option [logging] response_header_on_debug")

            # Start response
            time_end = datetime.datetime.now()
            time_delta_seconds = (time_end - time_begin).total_seconds()
            status_text = "%d %s" % (
                status, client.responses.get(status, "Unknown"))
            flags = []
            if xml_request is not None:
                if "<sync-token />" in xml_request:
                    flags.append("sync-token")
                if "<getetag />" in xml_request:
                    flags.append("getetag")
                if "<CS:getctag />" in xml_request:
                    flags.append("getctag")
                if "<sync-collection " in xml_request:
                    flags.append("sync-collection")
            if flags:
                flags_text = " (" + " ".join(flags) + ")"
            else:
                flags_text = ""
            if answer is not None:
                logger.info("%s response status for %r%s in %.3f seconds %s %s bytes%s: %s",
                            request_method, unsafe_path, depthinfo,
                            (time_end - time_begin).total_seconds(), content_encoding, str(len(answer)),
                            flags_text,
                            status_text)
            else:
                logger.info("%s response status for %r%s in %.3f seconds: %s",
                            request_method, unsafe_path, depthinfo,
                            time_delta_seconds, status_text)

            # Profiling end
            if self._profiling_per_request:
                if profiler_active is True:
                    if profiler is not None:
                        # Profiling per request
                        if time_delta_seconds < self._profiling_per_request_min_duration:
                            logger.debug("Profiling data per request %s for %r%s: (suppressed because duration below minimum %.3f < %.3f)", request_method, unsafe_path, depthinfo, time_delta_seconds, self._profiling_per_request_min_duration)
                        else:
                            s = io.StringIO()
                            s.write("**Profiling statistics BEGIN**\n")
                            stats = pstats.Stats(profiler, stream=s).sort_stats('cumulative')
                            stats.print_stats(self._profiling_top_x_functions)  # Print top X functions
                            s.write("**Profiling statistics END**\n")
                            if self._profiling_per_request_header:
                                s.write("**Profiling request header BEGIN**\n")
                                s.write(pprint.pformat(self._scrub_headers(environ)))
                                s.write("\n**Profiling request header END**")
                            if self._profiling_per_request_xml:
                                if xml_request is not None:
                                    s.write("\n**Profiling request content (XML) BEGIN**\n")
                                    if xml_request is not None:
                                        s.write(xml_request)
                                    s.write("**Profiling request content (XML) END**")
                            logger.info("Profiling data per request %s for %r%s:\n%s", request_method, unsafe_path, depthinfo, utils.textwrap_str(s.getvalue(), -1))
                    else:
                        logger.debug("Profiling data per request %s for %r%s: (suppressed because of no data)", request_method, unsafe_path, depthinfo)
                else:
                    logger.info("Profiling data per request %s for %r%s: (not available because of concurrent running profiling request)", request_method, unsafe_path, depthinfo)
            elif self._profiling_per_request_method:
                self.profiler_per_request_method[request_method].disable()
                self.profiler_per_request_method_counter[request_method] += 1
                profiler_timedelta = (datetime.datetime.now() - self.profiler_per_request_method_logtime).total_seconds()
                if profiler_timedelta > self._profiling_per_request_method_interval:
                    self._profiler_per_request_method()
                    self.profiler_per_request_method_logtime = datetime.datetime.now()

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
                         utils.textwrap_str(pprint.pformat(self._scrub_headers(environ))))
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
            # Profiling
            if self._profiling_per_request:
                profiler = cProfile.Profile()
                try:
                    profiler.enable()
                except ValueError:
                    profiler_active = False
                else:
                    profiler_active = True
            elif self._profiling_per_request_method:
                try:
                    self.profiler_per_request_method[request_method].enable()
                except ValueError:
                    profiler_active = False
                else:
                    profiler_active = True

            status, headers, answer, xml_request = function(
                environ, base_prefix, path, user, remote_host, remote_useragent)

            # Profiling
            if self._profiling_per_request:
                if profiler is not None:
                    if profiler_active is True:
                        profiler.disable()
            elif self._profiling_per_request_method:
                if profiler_active is True:
                    self.profiler_per_request_method[request_method].disable()

            if (status, headers, answer, xml_request) == httputils.NOT_ALLOWED:
                logger.info("Access to %r denied for %s", path,
                            repr(user) if user else "anonymous user")
        else:
            status, headers, answer, xml_request = httputils.NOT_ALLOWED

        if ((status, headers, answer, xml_request) == httputils.NOT_ALLOWED and not user and
                not external_login):
            # Unknown or unauthorized user
            logger.debug("Asking client for authentication")
            status = client.UNAUTHORIZED
            headers = dict(headers)
            headers.update({
                "WWW-Authenticate":
                "Basic realm=\"%s\"" % self._auth_realm})

        return response(status, headers, answer, xml_request)
