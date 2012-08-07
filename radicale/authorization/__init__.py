# -*- coding: utf-8 -*-
#
# This file is part of Radicale Server - Calendar Server
# Copyright © 2008-2012 Guillaume Ayoub
# Copyright © 2008 Nicolas Kandel
# Copyright © 2008 Pascal Halter
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
Users and rights management.

This module loads a list of users with access rights, according to the acl
configuration.

"""

from radicale import config, log


AUTHORIZATION_PREFIX = "authorization"

PUBLIC_USERS = []
PRIVATE_USERS = []



def _config_users(name):
    """Get an iterable of strings from the configuraton string [acl] ``name``.

    The values must be separated by a comma. The whitespace characters are
    stripped at the beginning and at the end of the values.

    """
    for user in config.get(AUTHORIZATION_PREFIX, name).split(","):
        user = user.strip()
        yield None if user == "None" else user


def load():
    """Load list of available ACL managers."""
    
    PUBLIC_USERS.extend(_config_users("public_users"))
    PRIVATE_USERS.extend(_config_users("private_users"))
    
    authorization_type = config.get(AUTHORIZATION_PREFIX, "type")
    log.LOGGER.debug("auth type = " + authorization_type)
    if authorization_type == "None":
        return None
    else:
        module = __import__("authorization.%s" % authorization_type, globals=globals(), level=2)
        return getattr(module, authorization_type)


def may_read(user, collection):
    if (collection.owner not in PRIVATE_USERS and user != collection.owner):
        # owner is not private and is not user, forbidden
        return False

    return read_authorized(user, collection)
    
def may_write(user, collection):
    return write_authorized(user, collection)
    
    