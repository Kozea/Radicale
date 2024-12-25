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
        logger.info("auth.strip_domain: %s", self._strip_domain)
        logger.info("auth.lc_username: %s", self._lc_username)
        logger.info("auth.uc_username: %s", self._uc_username)
        if self._lc_username is True and self._uc_username is True:
            raise RuntimeError("auth.lc_username and auth.uc_username cannot be enabled together")

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
        return self._login(login, password)
