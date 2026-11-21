# This file is part of Radicale - CalDAV and CardDAV server
# Copyright © 2008 Nicolas Kandel
# Copyright © 2008 Pascal Halter
# Copyright © 2008-2017 Guillaume Ayoub
# Copyright © 2017-2022 Unrud <unrud@outlook.com>
# Copyright © 2024-2026 Peter Bieringer <pb@bieringer.de>
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
(see ``remote_user``, ``http_remote_user`` or ``http_x_remote_user`` backend).

Take a look at the class ``BaseAuth`` if you want to implement your own.

"""

import hashlib
import os
import threading
import time
import secrets
from typing import Optional
from collections import OrderedDict
from typing import List, Sequence, Tuple, Union, final
from urllib.parse import unquote

from radicale import config, types, utils
from radicale.log import logger

INTERNAL_TYPES: Sequence[str] = ("none", "remote_user", "http_x_remote_user",
                                 "http_remote_user",
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
                                    "http_remote_user",
                                    "http_x_remote_user",
                                   )

AUTH_SOCKET_FAMILY: Sequence[str] = ("AF_UNIX", "AF_INET", "AF_INET6")

REMOTE_ADDR_SOURCE: Sequence[str] = ("REMOTE_ADDR", "X-Remote-Addr")

NO_LOGIN_NO_GROUPS: Tuple[str, set] = ("", set([]))
NO_LOGIN: str = ""


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


class AuthContext:
    remote_addr: str
    x_remote_addr: str

    def __init__(self):
        self.remote_addr = None
        self.x_remote_addr = None


class _AuthCacheEntry:
    _expiry_ns: int
    _login: str
    _groups: Optional[frozenset] # only needed for successful cache

    def __init__(self, expiry_ns: int, login: str, groups: Optional[tuple] = None):
        self._expiry_ns = expiry_ns
        self._login = login
        self._groups = groups


class AuthCache:
    
    _name: str                                # only used for logging ("successful" or "failed")
    _items: OrderedDict[str, _AuthCacheEntry] # first item = oldest
    _max_item_count: int
    _ttl_ns: int
    _lock: threading.RLock
    
    def __init__(self, name, max_items, ttl) -> None:
        self._name = name
        self._items = OrderedDict()
        self._max_item_count = max_items
        self._ttl_ns = ttl * 10**9
        self._lock = threading.RLock()
    
    def set_or_refresh(self, digest: str, login: str, groups: Optional[set] = None) -> None:
        with self._lock:
            now_ns = time.monotonic_ns()
            new_expiry_ns = now_ns + self._ttl_ns
            self._items[digest] = _AuthCacheEntry(new_expiry_ns, login,
                                                  frozenset(groups) if groups is not None else None)
            self._items.move_to_end(digest)
            self.cleanup(now_ns)
            if len (self._items) > self._max_item_count:
                self._items.popitem(last=False)
    
    def get(self, digest: str) -> Optional[tuple]:
        logger.trace("Entering AuthCache.get() for digest %s...", digest)
        with self._lock:
            now_ns = time.monotonic_ns()
            cache_entry = self._items.get(digest)
            self.cleanup(now_ns)
            cache_found = cache_entry is not None
            cache_hit = cache_found and digest in self._items
        # other methods will not change the contents of an _AuthCacheEntry, so we can evaluate after lock release
        if cache_found:
            age_s = (now_ns - (cache_entry._expiry_ns - self._ttl_ns)) / 10**9
            logger.debug("Login %s cache %s for %r (age: %.3f sec, TTL: %d sec)",
                self._name, "hit" if cache_hit else "expired", cache_entry._login, age_s, self._ttl_ns // 10**9)
            if cache_hit:
                cache_groups = set(cache_entry._groups) if cache_entry._groups is not None else None
                return cache_entry._expiry_ns, cache_entry._login, cache_groups
        logger.trace("Exiting AuthCache.get() for digest %s... without hit", digest)
        return None
    
    def clear(self, digest: str) -> bool:
        with self._lock:
            return self._items.pop(digest, None) is not None
    
    def cleanup(self, now_ns: Optional[int] = None) -> None:
        logger.debug("Login %s cache cleanup start (entries: %d)",
            self._name, len(self._items))
        with self._lock:
            if now_ns is None:
                now_ns = time.monotonic_ns()
            while self._items:
                oldest_entry = next(iter(self._items.values()))
                oldest_entry_expired_for_ns = now_ns - oldest_entry._expiry_ns
                if oldest_entry_expired_for_ns < 0:
                    break
                logger.trace("Login %s cache entry for user+password expired: %r (age over ttl: %.3f sec)",
                    self._name, oldest_entry, oldest_entry_expired_for_ns / 10**9)
                self._items.popitem(last=False)
        logger.debug("Login %s cache investigation finished (remaining entries: %d)",
            self._name, len(self._items))


class BaseAuth:

    _urldecode_username: bool
    _lc_username: bool
    _uc_username: bool
    _strip_domain: bool
    _auth_delay: float
    _failed_auth_delay: float
    _type: str
    _cache_logins: bool
    _cache_successful: AuthCache
    _cache_successful_logins_expiry: int
    _cache_successful_logins_max_count: int
    _cache_failed: AuthCache
    _cache_failed_logins_expiry: int
    _cache_failed_logins_max_count: int
    _cache_secret_salt: str                 # persistent over runtime
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
        logger.info("auth.delay: %f seconds", self._auth_delay)
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
            self._cache_successful_logins_max_count = configuration.get("auth", "cache_successful_logins_max_count")
            if self._cache_successful_logins_max_count < 0:
                raise RuntimeError("self._cache_successful_logins_max_count cannot be < 0")
            self._cache_failed_logins_max_count = configuration.get("auth", "cache_failed_logins_max_count")
            if self._cache_failed_logins_max_count < 0:
                raise RuntimeError("self._cache_failed_logins_max_count cannot be < 0")
            logger.info("auth.cache_successful_logins_expiry: %s seconds", self._cache_successful_logins_expiry)
            logger.info("auth.cache_failed_logins_expiry: %s seconds", self._cache_failed_logins_expiry)
            logger.info("auth.cache_successful_logins_max_count: %s", self._cache_successful_logins_max_count)
            logger.info("auth.cache_failed_logins_max_count: %s", self._cache_failed_logins_max_count)
            if ((self._cache_successful_logins_max_count == 0 or self._cache_successful_logins_expiry == 0)
                and (self._cache_failed_logins_max_count == 0 or self._cache_failed_logins_expiry == 0)):
                logger.notice("Both successful and failed login cache have TTL = 0 and/or max_count = 0; therefore disabling cache")
                self._cache_logins = False
        if self._cache_logins is True:
            # cache init
            self._cache_successful = AuthCache("successful", self._cache_successful_logins_max_count, self._cache_successful_logins_expiry)
            logger.trace("BaseAuth._cache_successful = %r", self._cache_successful)
            self._cache_failed = AuthCache("failed", self._cache_failed_logins_max_count, self._cache_failed_logins_expiry)
            logger.trace("BaseAuth._cache_failed = %r", self._cache_failed)
            self._cache_secret_salt = secrets.token_urlsafe()

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

    def _login_ext(self, login: str, password: str, context: AuthContext) -> str:
        """Check credentials and map login to internal user

        ``login`` the login name

        ``password`` the password

        ``context`` additional data for the login, e.g. IP address used

        Returns the username or ``""`` for invalid credentials.

        No support of ``user_groups``
        """

        # override this method instead of _login() if you want the context
        return self._login(login, password)

    def _login_ext_with_groups(self, login: str, password: str, context: AuthContext) -> Tuple[str, set]:
        """Check credentials and map login to internal user

        ``login`` the login name

        ``password`` the password

        Returns the username or ``""`` for invalid credentials

        Returns ``user_groups`` or ``set([])`` if invalid or no groups are supplied

        """

        # override this method instead of _login() if user_groups is supported
        return (self._login_ext(login, password, context), set([]))

    def _sleep_for_constant_exec_time(self, monotonic_ns_begin: int):
        """Sleep some time to reach a constant execution time for failed logins

        Independent of time required by external backend or used digest methods

        Increase final execution time in case initial limit exceeded

        See also issue 591

        """
        time_delta = (time.monotonic_ns() - monotonic_ns_begin) / 10**9
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
    def login(self, login: str, password: str, context: AuthContext) -> Tuple[str, set, str]:
        """
        Returns the
         - ``login`` or ``""`` for invalid credentials
         - authentication type
         - ``user_groups`` (if supported by authentication type) or ``set([])`` if invalid or no groups are supplied
        """
        monotonic_ns_begin = time.monotonic_ns()
        _type: str = self._type
        (result, groups) = NO_LOGIN_NO_GROUPS
        login_orig: str = login
        if self._lc_username:
            login = login.lower()
        if self._uc_username:
            login = login.upper()
        if self._urldecode_username:
            login = unquote(login)
        if self._strip_domain:
            login = login.split('@')[0]
        if len(login) == 0:
            if len(login_orig) > 0:
                logger.warning("Login verification impossible as turned empty: %r -> %r", login_orig, login)
            else:
                logger.warning("Login verification impossible as is empty: %r", login)
            self._sleep_for_constant_exec_time(monotonic_ns_begin)
            if self._cache_logins is True:
                self._cache_successful.cleanup()
                self._cache_failed.cleanup()
            return (result, groups, _type)  # NO_LOGIN_NO_GROUPS

        if self._cache_logins is True:
            login_digest = login + ":" + self._cache_digest(login, password, self._cache_secret_salt)
            now_ns = time.monotonic_ns()

            # check for cache failed login
            cache_failed_entry = self._cache_failed.get(login_digest)
            if cache_failed_entry:
                # login+password found in cache "failed" -> shortcut return
                _type = _type + "/cached"
                self._cache_successful.cleanup()
                return (result, groups, _type)  # NO_LOGIN_NO_GROUPS

            cache_successful_entry = self._cache_successful.get(login_digest)
            if cache_successful_entry:
                # login found in cache "successful"
                (expiry_ns_cache, login_cache, groups_cache) = cache_successful_entry
                result = login_cache
                groups = groups_cache
                _type = _type + "/cached"

            if result == "":
                # verify login+password via configured backend
                logger.debug("Login verification for user+password via backend %r: %r", _type, login)
                (result, groups) = self._login_ext_with_groups(login, password, context)
                if result != "":
                    logger.debug("Login successful for user+password via backend %r: %r -> %r; groups: %r", _type, login, result, groups)
                    self._cache_successful.set_or_refresh(login_digest, result, groups)
                    logger.debug("Login successful cache for user set: %r -> %r", login, result)
                    if self._cache_failed.clear(login_digest):
                        logger.debug("Login failed cache for user cleared: %r", login)
                else:
                    logger.debug("Login failed for user+password via backend: %r", login)
                    self._cache_failed.set_or_refresh(login_digest, login)
                    logger.debug("Login failed cache for user set: %r", login)
        else:
            # self._cache_logins is False
            logger.debug("Login verification for user+password via backend %r: %r", _type, login)
            (result, groups) = self._login_ext_with_groups(login, password, context)
            if result != "":
                logger.debug("Login successful for user+password via backend %r: %r -> %r; groups: %r", _type, login, result, groups)
        # finally
        if result == "":
            self._sleep_for_constant_exec_time(monotonic_ns_begin)
        return (result, groups, _type)
