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

from radicale import config


PUBLIC_USERS = []
PRIVATE_USERS = []


def _config_users(name):
    """Get an iterable of strings from the configuraton string [acl] ``name``.

    The values must be separated by a comma. The whitespace characters are
    stripped at the beginning and at the end of the values.

    """
    for user in config.get("acl", name).split(","):
        user = user.strip()
        yield None if user == "None" else user


def load():
    """Load list of available ACL managers."""
    acl_type = config.get("acl", "type")
    if acl_type == "None":
        return None
    else:
        PUBLIC_USERS.extend(_config_users("public_users"))
        PRIVATE_USERS.extend(_config_users("private_users"))
        module = __import__("acl.%s" % acl_type, globals=globals(), level=2)
        return getattr(module, acl_type)
