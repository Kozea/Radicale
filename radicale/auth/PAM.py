# -*- coding: utf-8 -*-
#
# This file is part of Radicale Server - Calendar Server
# Copyright © 2011 Henry-Nicolas Tourneur
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

Authentication based on the ``pam-python`` module.

"""

import grp
import pam
import pwd

from .. import config, log


GROUP_MEMBERSHIP = config.get("auth", "pam_group_membership")


def is_authenticated(user, password):
    """Check if ``user``/``password`` couple is valid."""
    if user is None or password is None:
        return False

    # Check whether the user exists in the PAM system
    try:
        pwd.getpwnam(user).pw_uid
    except KeyError:
        log.LOGGER.debug("User %s not found" % user)
        return False
    else:
        log.LOGGER.debug("User %s found" % user)

    # Check whether the group exists
    try:
        # Obtain supplementary groups
        members = grp.getgrnam(GROUP_MEMBERSHIP).gr_mem
    except KeyError:
        log.LOGGER.debug(
            "The PAM membership required group (%s) doesn't exist" %
            GROUP_MEMBERSHIP)
        return False

    # Check whether the user exists
    try:
        # Get user primary group
        primary_group = grp.getgrgid(pwd.getpwnam(user).pw_gid).gr_name
    except KeyError:
        log.LOGGER.debug("The PAM user (%s) doesn't exist" % user)
        return False

    # Check whether the user belongs to the required group
    # (primary or supplementary)
    if primary_group == GROUP_MEMBERSHIP or user in members:
        log.LOGGER.debug(
            "The PAM user belongs to the required group (%s)" %
            GROUP_MEMBERSHIP)
        # Check the password
        if pam.authenticate(user, password):
            return True
        else:
            log.LOGGER.debug("Wrong PAM password")
    else:
        log.LOGGER.debug(
            "The PAM user doesn't belong to the required group (%s)" %
            GROUP_MEMBERSHIP)

    return False
