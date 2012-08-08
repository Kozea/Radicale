# -*- coding: utf-8 -*-
#
# This file is part of Radicale Server - Calendar Server
# Copyright © 2011-2012 Guillaume Ayoub
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
Radicale access module.

Manage access to collections.

"""

from radicale import auth, rights, log

AUTH = None
RIGHTS = None


def load():
    """Load authentication and rights modules."""
    global AUTH, RIGHTS
    AUTH = auth.load()
    RIGHTS = rights.load()


def is_authenticated(user, password):
    """Check if the user is authenticated."""
    if AUTH is None:
        return True
    return AUTH.is_authenticated(user, password) if user else False


def read_authorized(user, collection):
    """Check if the user is allowed to read the collection."""
    if RIGHTS is None:
        return True
    user_authorized = RIGHTS.read_authorized(user, collection)
    log.LOGGER.debug(
        "Read %s %s -- %i" % (user, collection.owner, user_authorized))
    return user_authorized


def write_authorized(user, collection):
    """Check if the user is allowed to write the collection."""
    if RIGHTS is None:
        return True
    user_authorized = RIGHTS.write_authorized(user, collection)
    log.LOGGER.debug(
        "Write %s %s -- %i" % (user, collection.owner, user_authorized))
    return user_authorized
