# -*- coding: utf-8 -*-
#
# This file is part of Radicale Server - Calendar Server
# Copyright © 2011 Henry-Nicolas Tourneur
# Copyright © 2021-2021 Unrud <unrud@outlook.com>
# Copyright © 2025-2025 Peter Bieringer <pb@bieringer.de>
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
PAM authentication.

Authentication using the ``pam-python`` module.

Important: radicale user need access to /etc/shadow by e.g.
    chgrp radicale /etc/shadow
    chmod g+r
"""

import grp
import pwd

from radicale import auth
from radicale.log import logger


class Auth(auth.BaseAuth):
    def __init__(self, configuration) -> None:
        super().__init__(configuration)
        try:
            import pam
            self.pam = pam
        except ImportError as e:
            raise RuntimeError("PAM authentication requires the Python pam module") from e
        self._service = configuration.get("auth", "pam_service")
        logger.info("auth.pam_service: %s" % self._service)
        self._group_membership = configuration.get("auth", "pam_group_membership")
        if (self._group_membership):
            logger.info("auth.pam_group_membership: %s" % self._group_membership)
        else:
            logger.warning("auth.pam_group_membership: (empty, nothing to check / INSECURE)")

    def pam_authenticate(self, *args, **kwargs):
        return self.pam.authenticate(*args, **kwargs)

    def _login(self, login: str, password: str) -> str:
        """Check if ``user``/``password`` couple is valid."""
        if login is None or password is None:
            return ""

        # Check whether the user exists in the PAM system
        try:
            pwd.getpwnam(login).pw_uid
        except KeyError:
            logger.debug("PAM user not found: %r" % login)
            return ""
        else:
            logger.debug("PAM user found: %r" % login)

        # Check whether the user has a primary group (mandatory)
        try:
            # Get user primary group
            primary_group = grp.getgrgid(pwd.getpwnam(login).pw_gid).gr_name
            logger.debug("PAM user %r has primary group: %r" % (login, primary_group))
        except KeyError:
            logger.debug("PAM user has no primary group: %r" % login)
            return ""

        # Obtain supplementary groups
        members = []
        if (self._group_membership):
            try:
                members = grp.getgrnam(self._group_membership).gr_mem
            except KeyError:
                logger.debug(
                    "PAM membership required group doesn't exist: %r" %
                    self._group_membership)
                return ""

        # Check whether the user belongs to the required group
        # (primary or supplementary)
        if (self._group_membership):
            if (primary_group != self._group_membership) and (login not in members):
                logger.warning("PAM user %r belongs not to the required group: %r" % (login, self._group_membership))
                return ""
            else:
                logger.debug("PAM user %r belongs to the required group: %r" % (login, self._group_membership))

        # Check the password
        if self.pam_authenticate(login, password, service=self._service):
            return login
        else:
            logger.debug("PAM authentication not successful for user: %r (service %r)" % (login, self._service))
            return ""
