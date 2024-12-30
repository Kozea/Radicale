# This file is part of Radicale - CalDAV and CardDAV server
# Copyright © 2008 Nicolas Kandel
# Copyright © 2008 Pascal Halter
# Copyright © 2008-2017 Guillaume Ayoub
# Copyright © 2017-2022 Unrud <unrud@outlook.com>
# Copyright © 2024-2024 Peter Bieringer <pb@bieringer.de>
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
import time
from typing import Sequence, Set, Tuple, Union, final

from radicale import config, types, utils
from radicale.log import logger

INTERNAL_TYPES: Sequence[str] = ("none", "remote_user", "http_x_remote_user",
                                 "denyall",
                                 "htpasswd",
                                 "ldap",
                                 "dovecot")


def load(configuration: "config.Configuration") -> "BaseAuth":
    """Load the authentication module chosen in configuration."""
    if configuration.get("auth", "type") == "none":
        logger.warning("No user authentication is selected: '[auth] type=none' (insecure)")
    if configuration.get("auth", "type") == "denyall":
        logger.warning("All access is blocked by: '[auth] type=denyall'")
    return utils.load_plugin(INTERNAL_TYPES, "auth", "Auth", BaseAuth,
                             configuration)


class BaseAuth:

    _ldap_groups: Set[str] = set([])
    _lc_username: bool
    _uc_username: bool
    _strip_domain: bool
    _cache: dict
    _cache_logins: bool
    _cache_logins_expiry: int
    _cache_logins_expiry_ns: int

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
        self._cache_logins = configuration.get("auth", "cache_logins")
        self._cache_logins_expiry = configuration.get("auth", "cache_logins_expiry")
        if self._cache_logins_expiry < 0:
            raise RuntimeError("self._cache_logins_expiry cannot be < 0")
        logger.info("auth.strip_domain: %s", self._strip_domain)
        logger.info("auth.lc_username: %s", self._lc_username)
        logger.info("auth.uc_username: %s", self._uc_username)
        if self._lc_username is True and self._uc_username is True:
            raise RuntimeError("auth.lc_username and auth.uc_username cannot be enabled together")
        logger.info("auth.cache_logins: %s", self._cache_logins)
        if self._cache_logins is True:
            logger.info("auth.cache_logins_expiry: %s seconds", self._cache_logins_expiry)
            self._cache_logins_expiry_ns = self._cache_logins_expiry * 1000 * 1000 * 1000
        self._cache = dict()

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

    @final
    def login(self, login: str, password: str) -> str:
        if self._lc_username:
            login = login.lower()
        if self._uc_username:
            login = login.upper()
        if self._strip_domain:
            login = login.split('@')[0]
        if self._cache_logins is True:
            # time_ns is also used as salt
            result = ""
            digest = ""
            time_ns = time.time_ns()
            if self._cache.get(login):
                # entry found in cache
                (digest_cache, time_ns_cache) = self._cache[login]
                digest = self._cache_digest(login, password, str(time_ns_cache))
                if digest == digest_cache:
                    if (time_ns - time_ns_cache) > self._cache_logins_expiry_ns:
                        logger.debug("Login cache entry for user found but expired: '%s'", login)
                        digest = ""
                    else:
                        logger.debug("Login cache entry for user found: '%s'", login)
                        result = login
                else:
                    logger.debug("Login cache entry for user not matching: '%s'", login)
            else:
                # entry not found in cache, caculate always to avoid timing attacks
                digest = self._cache_digest(login, password, str(time_ns))
            if result == "":
                result = self._login(login, password)
                if result != "":
                    if digest == "":
                        # successful login, but expired, digest must be recalculated
                        digest = self._cache_digest(login, password, str(time_ns))
                    # store successful login in cache
                    self._cache[login] = (digest, time_ns)
                    logger.debug("Login cache for user set: '%s'", login)
            return result
        else:
            return self._login(login, password)
