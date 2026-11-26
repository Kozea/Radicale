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
import secrets
import threading
import time
from collections import OrderedDict
from typing import List, Optional, Sequence, Tuple, Union, final
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

DIGEST_TRUNCATION = 124


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

    def __init__(self, expiry_ns: int, login: str, groups: Optional[frozenset] = None):
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
            if len(self._items) > self._max_item_count:
                self._items.popitem(last=False)

    def get(self, digest: str) -> Optional[tuple]:
        logger.trace("Entering AuthCache.get() for digest %s...", digest[:-DIGEST_TRUNCATION])
        with self._lock:
            now_ns = time.monotonic_ns()
            cache_entry = self._items.get(digest)
            self.cleanup(now_ns)
            cache_hit = digest in self._items
        # other methods will not change the contents of an _AuthCacheEntry, so we can evaluate after lock release
        if cache_entry is not None:
            age_s = (now_ns - (cache_entry._expiry_ns - self._ttl_ns)) / 10**9
            logger.debug("Login %s cache %s for %r (age: %.3f sec, TTL: %d sec)",
                         self._name, "hit" if cache_hit else "expired", cache_entry._login, age_s, self._ttl_ns // 10**9)
            if cache_hit:
                cache_groups = set(cache_entry._groups) if cache_entry._groups is not None else None
                return cache_entry._login, cache_groups
        logger.trace("Exiting AuthCache.get() for digest %s... without hit", digest[:-DIGEST_TRUNCATION])
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


_LimiterToken = Union[tuple[int], tuple[int, int], tuple[int, int, int, str, str]]


class _AuthLimiter:

    _max_total: int
    _max_active: int
    _max_per_login: int
    _check_per_digest: bool
    _curr_total: int
    _curr_active: int
    _curr_per_login: dict[str, int]
    _curr_per_digest: set[str]
    _condition: threading.Condition
    _release_count: int

    def __init__(self, total_limit: int, active_limit: int, per_login_limit: int, per_digest_check: bool):
        self._max_total = total_limit
        self._max_active = active_limit
        self._max_per_login = per_login_limit
        self._check_per_digest = per_digest_check
        self._curr_total = 0
        self._curr_active = 0
        self._curr_per_login = {}
        self._curr_per_digest = set()
        self._condition = threading.Condition()
        self._release_count = 0

    def try_to_acquire(self, login: str, digest: str, token=None) -> tuple[int, _LimiterToken]:
        reason = 0
        result: _LimiterToken
        with self._condition:
            if token is None or len(token) == 1: # first call or no waiting token
                if self._curr_total >= self._max_total:
                    # no waiting capacity
                    reason += 8
                    result = (self._release_count,)
                else:
                    self._curr_total += 1
            if reason == 0:
                # assuming that either we passed through the else branch above or len(token) == 2
                if self._curr_active >= self._max_active:
                    reason += 4
                if self._curr_per_login.get(login, 0) >= self._max_per_login:
                    reason += 2
                if self._check_per_digest and (digest in self._curr_per_digest):
                    reason += 1
                if reason == 0:
                    self._curr_active += 1
                    self._curr_per_login[login] = self._curr_per_login.get(login, 0) + 1
                    if self._check_per_digest:
                        self._curr_per_digest.add(digest)
                    # capacity available: reserve accordingly and proceed
                    result = (self._release_count, 1, 1, login, digest)
                else:
                    result = (self._release_count, 1)
        if reason == 0:
            logger.trace("auth/login concurrent limiter: slot reserved for login = %r,%r", login, digest[:-DIGEST_TRUNCATION])
            return reason, result
        if reason & 8:
            logger.trace("auth/login concurrent limit reached: %d total (waiting+active) threads", self._max_total)
        if reason & 4:
            logger.trace("auth/login concurrent limit reached: %d active threads", self._max_active)
        if reason & 2:
            logger.trace("auth/login concurrent limit reached: %d threads active for login %r", self._max_per_login, login)
        if reason & 1:
            logger.trace("auth/login concurrent limit reached: another thread is already checking digest %r", digest[:-DIGEST_TRUNCATION])
        return reason, result

    def wait_to_acquire(self, token: tuple, timeout: float) -> bool:
        waiter_release_count = token[0]
        with self._condition:
            return self._condition.wait_for(lambda: self._release_count != waiter_release_count, timeout)

    def release(self, token: tuple) -> None:
        with self._condition:
            # only return what was reserved
            if len(token) >= 2:
                self._curr_total -= 1
                if len(token) == 5:
                    self._curr_active -= 1
                    self._curr_per_login[token[3]] -= 1
                    if self._curr_per_login[token[3]] == 0:
                        del self._curr_per_login[token[3]]
                    if self._check_per_digest:
                        self._curr_per_digest.remove(token[4])
                self._release_count += 1
                self._condition.notify_all()


class BaseAuth:

    _urldecode_username: bool
    _lc_username: bool
    _uc_username: bool
    _strip_domain: bool
    _auth_delay: float
    _failed_auth_delay: float
    _type: str
    _secret_salt: str                 # persistent over runtime
    _cache_logins: bool
    _cache_successful: AuthCache
    _cache_failed: AuthCache
    _limiter: Optional[_AuthLimiter]
    _limiter_max_wait: float
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
            cache_successful_logins_expiry = configuration.get("auth", "cache_successful_logins_expiry")
            if cache_successful_logins_expiry < 0:
                raise RuntimeError("cache_successful_logins_expiry cannot be < 0")
            cache_failed_logins_expiry = configuration.get("auth", "cache_failed_logins_expiry")
            if cache_failed_logins_expiry < 0:
                raise RuntimeError("cache_failed_logins_expiry cannot be < 0")
            cache_successful_logins_max_count = configuration.get("auth", "cache_successful_logins_max_count")
            if cache_successful_logins_max_count < 0:
                raise RuntimeError("cache_successful_logins_max_count cannot be < 0")
            cache_failed_logins_max_count = configuration.get("auth", "cache_failed_logins_max_count")
            if cache_failed_logins_max_count < 0:
                raise RuntimeError("cache_failed_logins_max_count cannot be < 0")
            logger.info("auth.cache_successful_logins_expiry: %s seconds", cache_successful_logins_expiry)
            logger.info("auth.cache_failed_logins_expiry: %s seconds", cache_failed_logins_expiry)
            logger.info("auth.cache_successful_logins_max_count: %s", cache_successful_logins_max_count)
            logger.info("auth.cache_failed_logins_max_count: %s", cache_failed_logins_max_count)
            if ((cache_successful_logins_max_count == 0 or cache_successful_logins_expiry == 0)
                    and (cache_failed_logins_max_count == 0 or cache_failed_logins_expiry == 0)):
                logger.notice("Both successful and failed login cache have TTL = 0 and/or max_count = 0; therefore disabling cache")
                self._cache_logins = False
        if self._cache_logins is True:
            # cache init
            self._cache_successful = AuthCache("successful", cache_successful_logins_max_count, cache_successful_logins_expiry)
            logger.trace("BaseAuth._cache_successful = %r", self._cache_successful)
            self._cache_failed = AuthCache("failed", cache_failed_logins_max_count, cache_failed_logins_expiry)
            logger.trace("BaseAuth._cache_failed = %r", self._cache_failed)
        limiter_enabled = configuration.get("auth", "concurrency_limit_enabled")
        logger.info("auth.concurrency_limit_enabled: %s", limiter_enabled)
        if limiter_enabled:
            self._limiter_max_wait = configuration.get("auth", "concurrency_wait_timeout")
            logger.info("auth.concurrency_wait_timeout: %d", self._limiter_max_wait)
            concurrency_total_limit = configuration.get("auth", "concurrency_total_limit")
            logger.info("auth.concurrency_total_limit: %d", concurrency_total_limit)
            concurrency_active_limit = configuration.get("auth", "concurrency_active_limit")
            logger.info("auth.concurrency_active_limit: %d", concurrency_active_limit)
            concurrency_per_user_limit = configuration.get("auth", "concurrency_per_user_limit")
            logger.info("auth.concurrency_per_user_limit: %d", concurrency_per_user_limit)
            self._limiter_max_wait = configuration.get("auth", "concurrency_wait_timeout")
            logger.info("auth.concurrency_wait_timeout: %.3f seconds", self._limiter_max_wait)
            self._limiter = _AuthLimiter(
                concurrency_total_limit,
                concurrency_active_limit,
                concurrency_per_user_limit,
                self._cache_logins,
            )
        else:
            self._limiter = None

        if self._cache_logins or limiter_enabled:
            self._secret_salt = secrets.token_urlsafe()

    def _cache_digest(self, login: str, password: str, salt: str) -> str:
        h = hashlib.sha3_512()
        h.update(login.encode())
        h.update(salt.encode())
        h.update(password.encode())
        return h.hexdigest()

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

    def _sleep_for_constant_exec_time(self, monotonic_ns_begin: int, admission_wait_ns: int = 0):
        """Sleep some time to reach a constant execution time for failed logins

        Independent of time required by external backend or used digest methods

        Increase final execution time in case initial limit exceeded

        See also issue 591

        """
        total_delta_ns = time.monotonic_ns() - monotonic_ns_begin
        time_delta = (total_delta_ns - admission_wait_ns) / 10**9
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
            sleep = failed_auth_delay - total_delta_ns / 10**9
            if sleep > 0:
                logger.debug("Failed login constant exection time alignment, sleeping: %.9f sec", sleep)
                time.sleep(sleep)

    def _try_login_from_cache(self, login_digest):
        if self._cache_failed.get(login_digest):
            self._cache_successful.cleanup()
            return NO_LOGIN_NO_GROUPS
        return self._cache_successful.get(login_digest)

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

        if (self._type not in CACHE_LOGIN_TYPES):
            # shortcut, no password to authenticate
            (result, groups) = self._login_ext_with_groups(login, password, context)
            return (result, groups, _type)

        # calculate digest from login+password+runtime-salt
        if self._cache_logins or self._limiter:
            login_digest = login + ":" + self._cache_digest(login, password, self._secret_salt)
        else:
            login_digest = ""

        # cached results bypass limiter, so check cache first
        cache_result = None
        if self._cache_logins is True:
            cache_result = self._try_login_from_cache(login_digest)

        try:
            # subject backend call to concurrency limiter if no cache result was found
            admission_wait_ns = 0
            limiter_token = None
            if self._limiter and not cache_result:
                admission_start_ns = time.monotonic_ns()
                limiter_reason, limiter_token = self._limiter.try_to_acquire(login, login_digest)
                if len(limiter_token) == 1:
                    _type = _type + "/error:temp:concurrent-session-limit"
                    # TODO: support HTTP error code 429 in case reason is on client side
                    return (result, groups, _type)  # still NO_LOGIN_NO_GROUPS
                while len(limiter_token) == 2:
                    if self._cache_logins:
                        cache_result = self._try_login_from_cache(login_digest)
                        if cache_result:
                            break
                    timeout = self._limiter_max_wait - (time.monotonic_ns() - monotonic_ns_begin) * 1e-9
                    if (self._limiter.wait_to_acquire(limiter_token, timeout) is False
                            or self._limiter_max_wait - (time.monotonic_ns() - monotonic_ns_begin) * 1e-9 < 0):
                        _type = _type + "/error:temp:concurrent-session-limit"
                        logger.notice("auth/login concurrent limit reached timeout: %.3f seconds", self._limiter_max_wait)
                        return (result, groups, _type)  # still NO_LOGIN_NO_GROUPS
                    limiter_reason, limiter_token = self._limiter.try_to_acquire(login, login_digest, limiter_token)
                admission_wait_ns = time.monotonic_ns() - admission_start_ns

            if self._cache_logins and self._limiter and (cache_result is None):
                # need to check cache again in case it was populated during admission
                cache_result = self._try_login_from_cache(login_digest)
            if cache_result:
                result, groups = cache_result
                _type = _type + "/cached"
            else:
                # common branch for self._cache_logins == False
                #               and (self._cache_logins,cache_result) == (True,None)
                logger.debug("Login verification for user+password via backend %r: %r", _type, login)
                try:
                    (result, groups) = self._login_ext_with_groups(login, password, context)
                except Exception as e:
                    logger.error("auth/login permanent error of backend %r: %r %r", _type, login, e)
                    _type = _type + "/error:perm:backend"
                else:
                    if result != "":
                        logger.debug("Login successful for user+password via backend %r: %r -> %r; groups: %r", _type, login, result, groups)
                        if self._cache_logins:
                            self._cache_successful.set_or_refresh(login_digest, result, groups)
                            logger.debug("Login successful cache for user set: %r -> %r", login, result)
                            if self._cache_failed.clear(login_digest):
                                logger.debug("Login failed cache for user cleared: %r", login)
                    else:
                        logger.debug("Login failed for user+password via backend: %r", login)
                        if self._cache_logins:
                            self._cache_failed.set_or_refresh(login_digest, login)
                            logger.debug("Login failed cache for user set: %r", login)
        finally:
            if self._limiter and limiter_token:
                self._limiter.release(limiter_token)
        if result == "" and (cache_result is None):
            self._sleep_for_constant_exec_time(monotonic_ns_begin, admission_wait_ns)
        return (result, groups, _type)
