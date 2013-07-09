# -*- coding: utf-8 -*-
#
# This file is part of Radicale Server - Calendar Server
# Copyright © 2012-2013 Guillaume Ayoub
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
File-based rights.

The owners are implied to have all rights on their collections.

Rights are read from a file whose name is specified in the config (section
"right", key "file").

Example:

# This means user1 may read, user2 may write, user3 has full access.
[user0/calendar]
user1: r
user2: w
user3: rw

# user0 can read user1/cal.
[user1/cal]
user0: r

# If a collection a/b is shared and other users than the owner are supposed to
# find the collection in a propfind request, an additional line for a has to
# be in the defintions.
[user0]
user1: r

"""

import os.path

from radicale import config, log
from radicale.rights import owner_only
# Manage Python2/3 different modules
# pylint: disable=F0401
try:
    from configparser import (
        RawConfigParser as ConfigParser, NoSectionError, NoOptionError)
except ImportError:
    from ConfigParser import (
        RawConfigParser as ConfigParser, NoSectionError, NoOptionError)
# pylint: enable=F0401


FILENAME = (
    os.path.expanduser(config.get("rights", "file")) or
    log.LOGGER.error("No file name configured for rights type 'from_file'"))


def _read_rights():
    """Update the rights according to the configuration file."""
    log.LOGGER.debug("Reading rights from file %s" % FILENAME)
    rights = ConfigParser()
    if not rights.read(FILENAME):
        log.LOGGER.error(
            "File '%s' not found for rights management" % FILENAME)
    return rights


def read_authorized(user, collection):
    """Check if the user is allowed to read the collection."""
    if user is None:
        return False
    elif owner_only.read_authorized(user, collection):
        return True
    else:
        try:
            return "r" in _read_rights().get(
                collection.url.rstrip("/") or "/", user)
        except (NoSectionError, NoOptionError):
            return False


def write_authorized(user, collection):
    """Check if the user is allowed to write the collection."""
    if user is None:
        return False
    elif owner_only.write_authorized(user, collection):
        return True
    else:
        try:
            return "w" in _read_rights().get(
                collection.url.rstrip("/") or "/", user)
        except (NoSectionError, NoOptionError):
            return False
