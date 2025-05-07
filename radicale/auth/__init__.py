# This file is part of Radicale - CalDAV and CardDAV server
# Copyright © 2008 Nicolas Kandel
# Copyright © 2008 Pascal Halter
# Copyright © 2008-2017 Guillaume Ayoub
# Copyright © 2017-2022 Unrud <unrud@outlook.com>
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
Authentication module.

Authentication is based on usernames and passwords. If something more
advanced is needed an external WSGI server or reverse proxy can be used
(see ``remote_user`` or ``http_x_remote_user`` backend).

Take a look at the class ``BaseAuth`` if you want to implement your own.

"""

import hashlib
import os
import threading
import time
from typing import List, Sequence, Set, Tuple, Union, final
from urllib.parse import unquote

from radicale import config, types, utils
from radicale.log import logger

INTERNAL_TYPES: Sequence[str] = ("none", "remote_user", "http_x_remote_user",
                                 "denyall",
                                 "htpasswd",
                                 "ldap",
                                 "imap",
                                 "oauth2",
                                 "pam",
                                 "dovecot")

CACHE_LOGIN_TYPES: Sequence[str] = (
                                    "dovecot",
                                    "ldap",
                                    "htpasswd",
                                    "imap",
                                    "oauth2",
                                    "pam",
                                   )

INSECURE_IF_NO_LOOPBACK_TYPES: Sequence[str] = (
                                    "remote_user",
                                    "http_x_remote_user",
                                   )

AUTH_SOCKET_FAMILY: Sequence[str] = ("AF_UNIX", "AF_INET", "AF_INET6")


def load(configuration: "config.Configuration") -> "BaseAuth":
    """Load the authentication module chosen in configuration."""
    _type = configuration.get("auth", "type")
    if _type == "none":
        logger.warning("No user authentication is selected: '[auth] type=none' (INSECURE)")
    elif _type == "denyall":
        logger.warning("All user authentication is blocked by: '[auth] type=denyall'")
    elif _type in INSECURE_IF_NO_LOOPBACK_TYPES:
        sgi = os.environ.get('SERVER_GATEWAY_INTERFACE') or None
        if not sgi:
            hosts: List[Tuple[str, int]] = configuration.get("server", "hosts")
            localhost_only = True
            address_lo = []
            address = []
            for address_port in hosts:
                if address_port[0] in ["localhost", "localhost6", "127.0.0.1", "::1"]:
                    address_lo.append(utils.format_address(address_port))
                else:
                    address.append(utils.format_address(address_port))
                    localhost_only = False
            if localhost_only is False:
                logger.warning("User authentication '[auth] type=%s' is selected but server is not only listen on loopback address (potentially INSECURE): %s", _type, " ".join(address))
    return utils.load_plugin(INTERNAL_TYPES, "auth", "Auth", BaseAuth,
                             configuration)


class BaseAuth:

    _ldap_groups: Set[str] = set([])
    _urldecode_username: bool
    _lc_username: bool
    _uc_username: bool
    _strip_domain: bool
    _auth_delay: float
    _failed_auth_delay: float
    _type: str
    _cache_logins: bool
    _cache_successful: dict                 # login -> (digest, time_ns)
    _cache_successful_logins_expiry: int
    _cache_failed: dict                     # digest_failed -> (time_ns, login)
    _cache_failed_logins_expiry: int
    _cache_failed_logins_salt_ns: int       # persistent over runtime
    _lock: threading.Lock

    def __init__(self, configuration: "config.Configuration") -> None:
        """Initialize BaseAuth.

        ``configuration`` see ``radicale.config`` module.
        The ``configuration`` must not change during the lifetime of
        this object, it is kept as an internal reference.

        """
        self.configuration = configuration
        self._lc_username = configuration.get("auth", "lc_username")
        self._uc_username = configuration.get("auth", "uc_username")
        self._strip_domain = configuration.get("auth", "strip_domain")
        self._urldecode_username = configuration.get("auth", "urldecode_username")
        logger.info("auth.strip_domain: %s", self._strip_domain)
        logger.info("auth.lc_username: %s", self._lc_username)
        logger.info("auth.uc_username: %s", self._uc_username)
        logger.info("auth.urldecode_username: %s", self._urldecode_username)
        if self._lc_username is True and self._uc_username is True:
            raise RuntimeError("auth.lc_username and auth.uc_username cannot be enabled together")
        self._auth_delay = configuration.get("auth", "delay")
        logger.info("auth.delay: %f", self._auth_delay)
        self._failed_auth_delay = 0
        self._lock = threading.Lock()
        # cache_successful_logins
        self._cache_logins = configuration.get("auth", "cache_logins")
        self._type = configuration.get("auth", "type")
        if (self._type in CACHE_LOGIN_TYPES) or (self._cache_logins is False):
            logger.info("auth.cache_logins: %s", self._cache_logins)
        else:
            logger.info("auth.cache_logins: %s (but not required for type '%s' and disabled therefore)", self._cache_logins, self._type)
            self._cache_logins = False
        if self._cache_logins is True:
            self._cache_successful_logins_expiry = configuration.get("auth", "cache_successful_logins_expiry")
            if self._cache_successful_logins_expiry < 0:
                raise RuntimeError("self._cache_successful_logins_expiry cannot be < 0")
            self._cache_failed_logins_expiry = configuration.get("auth", "cache_failed_logins_expiry")
            if self._cache_failed_logins_expiry < 0:
                raise RuntimeError("self._cache_failed_logins_expiry cannot be < 0")
            logger.info("auth.cache_successful_logins_expiry: %s seconds", self._cache_successful_logins_expiry)
            logger.info("auth.cache_failed_logins_expiry: %s seconds", self._cache_failed_logins_expiry)
            # cache init
            self._cache_successful = dict()
            self._cache_failed = dict()
            self._cache_failed_logins_salt_ns = time.time_ns()

    def _cache_digest(self, login: str, password: str, salt: str) -> str:
        h = hashlib.sha3_512()
        h.update(salt.encode())
        h.update(login.encode())
        h.update(password.encode())
        return str(h.digest())

    def get_external_login(self, environ: types.WSGIEnviron) -> Union[
            Tuple[()], Tuple[str, str]]:
        """Optionally provide the login and password externally.

        ``environ`` a dict with the WSGI environment

        If ``()`` is returned, Radicale handles HTTP authentication.
        Otherwise, returns a tuple ``(login, password)``. For anonymous users
        ``login`` must be ``""``.

        """
        return ()

    def _login(self, login: str, password: str) -> str:
        """Check credentials and map login to internal user

        ``login`` the login name

        ``password`` the password

        Returns the username or ``""`` for invalid credentials.

        """

        raise NotImplementedError

    def _sleep_for_constant_exec_time(self, time_ns_begin: int):
        """Sleep some time to reach a constant execution time for failed logins

        Independent of time required by external backend or used digest methods

        Increase final execution time in case initial limit exceeded

        See also issue 591

        """
        time_delta = (time.time_ns() - time_ns_begin) / 1000 / 1000 / 1000
        with self._lock:
            # avoid that another thread is changing global value at the same time
            failed_auth_delay = self._failed_auth_delay
            failed_auth_delay_old = failed_auth_delay
            if time_delta > failed_auth_delay:
                # set new
                failed_auth_delay = time_delta
                # store globally
                self._failed_auth_delay = failed_auth_delay
        if (failed_auth_delay_old != failed_auth_delay):
            logger.debug("Failed login constant execution time need increase of failed_auth_delay: %.9f -> %.9f sec", failed_auth_delay_old, failed_auth_delay)
            # sleep == 0
        else:
            sleep = failed_auth_delay - time_delta
            logger.debug("Failed login constant exection time alignment, sleeping: %.9f sec", sleep)
            time.sleep(sleep)

    @final
    def login(self, login: str, password: str) -> Tuple[str, str]:
        time_ns_begin = time.time_ns()
        result_from_cache = False
        if self._lc_username:
            login = login.lower()
        if self._uc_username:
            login = login.upper()
        if self._urldecode_username:
            login = unquote(login)
        if self._strip_domain:
            login = login.split('@')[0]
        if self._cache_logins is True:
            # time_ns is also used as salt
            result = ""
            digest = ""
            time_ns = time.time_ns()
            # cleanup failed login cache to avoid out-of-memory
            cache_failed_entries = len(self._cache_failed)
            if cache_failed_entries > 0:
                logger.debug("Login failed cache investigation start (entries: %d)", cache_failed_entries)
                self._lock.acquire()
                cache_failed_cleanup = dict()
                for digest in self._cache_failed:
                    (time_ns_cache, login_cache) = self._cache_failed[digest]
                    age_failed = int((time_ns - time_ns_cache) / 1000 / 1000 / 1000)
                    if age_failed > self._cache_failed_logins_expiry:
                        cache_failed_cleanup[digest] = (login_cache, age_failed)
                cache_failed_cleanup_entries = len(cache_failed_cleanup)
                logger.debug("Login failed cache cleanup start (entries: %d)", cache_failed_cleanup_entries)
                if cache_failed_cleanup_entries > 0:
                    for digest in cache_failed_cleanup:
                        (login, age_failed) = cache_failed_cleanup[digest]
                        logger.debug("Login failed cache entry for user+password expired: '%s' (age: %d > %d sec)", login_cache, age_failed, self._cache_failed_logins_expiry)
                        del self._cache_failed[digest]
                self._lock.release()
                logger.debug("Login failed cache investigation finished")
            # check for cache failed login
            digest_failed = login + ":" + self._cache_digest(login, password, str(self._cache_failed_logins_salt_ns))
            if self._cache_failed.get(digest_failed):
                # login+password found in cache "failed" -> shortcut return
                (time_ns_cache, login_cache) = self._cache_failed[digest]
                age_failed = int((time_ns - time_ns_cache) / 1000 / 1000 / 1000)
                logger.debug("Login failed cache entry for user+password found: '%s' (age: %d sec)", login_cache, age_failed)
                self._sleep_for_constant_exec_time(time_ns_begin)
                return ("", self._type + " / cached")
            if self._cache_successful.get(login):
                # login found in cache "successful"
                (digest_cache, time_ns_cache) = self._cache_successful[login]
                digest = self._cache_digest(login, password, str(time_ns_cache))
                if digest == digest_cache:
                    age_success = int((time_ns - time_ns_cache) / 1000 / 1000 / 1000)
                    if age_success > self._cache_successful_logins_expiry:
                        logger.debug("Login successful cache entry for user+password found but expired: '%s' (age: %d > %d sec)", login, age_success, self._cache_successful_logins_expiry)
                        # delete expired success from cache
                        del self._cache_successful[login]
                        digest = ""
                    else:
                        logger.debug("Login successful cache entry for user+password found: '%s' (age: %d sec)", login, age_success)
                        result = login
                        result_from_cache = True
                else:
                    logger.debug("Login successful cache entry for user+password not matching: '%s'", login)
            else:
                # login not found in cache, caculate always to avoid timing attacks
                digest = self._cache_digest(login, password, str(time_ns))
            if result == "":
                # verify login+password via configured backend
                logger.debug("Login verification for user+password via backend: '%s'", login)
                result = self._login(login, password)
                if result != "":
                    logger.debug("Login successful for user+password via backend: '%s'", login)
                    if digest == "":
                        # successful login, but expired, digest must be recalculated
                        digest = self._cache_digest(login, password, str(time_ns))
                    # store successful login in cache
                    self._lock.acquire()
                    self._cache_successful[login] = (digest, time_ns)
                    self._lock.release()
                    logger.debug("Login successful cache for user set: '%s'", login)
                    if self._cache_failed.get(digest_failed):
                        logger.debug("Login failed cache for user cleared: '%s'", login)
                        del self._cache_failed[digest_failed]
                else:
                    logger.debug("Login failed for user+password via backend: '%s'", login)
                    self._lock.acquire()
                    self._cache_failed[digest_failed] = (time_ns, login)
                    self._lock.release()
                    logger.debug("Login failed cache for user set: '%s'", login)
            if result_from_cache is True:
                if result == "":
                    self._sleep_for_constant_exec_time(time_ns_begin)
                return (result, self._type + " / cached")
            else:
                if result == "":
                    self._sleep_for_constant_exec_time(time_ns_begin)
                return (result, self._type)
        else:
            # self._cache_logins is False
            result = self._login(login, password)
            if result == "":
                self._sleep_for_constant_exec_time(time_ns_begin)
            return (result, self._type)
