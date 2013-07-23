# -*- coding: utf-8 -*-
#
# This file is part of Radicale Server - Calendar Server
# Copyright © 2013 Guillaume Ayoub
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
Regex-based rights.

Regexes are read from a file whose name is specified in the config (section
"right", key "file").

Authentication login is matched against the "user" key, and collection's path
is matched against the "collection" key. You can use Python's ConfigParser
interpolation values %(login)s and %(path)s. You can also get groups from the
user regex in the collection with {0}, {1}, etc.

Section names are only used for naming the rule.

Leading or ending slashes are trimmed from collection's path.

Examples:

# This means all users starting with "admin" may read any collection
[admin]
user: ^admin.*\|.+?$
collection: .*
permission: r

# This means all users may read and write any collection starting with public.
# We do so by just not testing against the user string.
[public]
user: .*
collection: ^public(/.+)?$
permission: rw

# A little more complex: give read access to users from a domain for all
# collections of all the users (ie. user@domain.tld can read domain/*).
[domain-wide-access]
user: ^.+@(.+)\..+$
collection: ^{0}/.+$
permission: r

# Allow authenticated user to read all collections
[allow-everyone-read]
user: .*
collection: .*
permission: r

# Give write access to owners
[owner-write]
user: .*
collection: ^%(login)s/.+$
permission: w

"""

import os.path
import re

from radicale import config, log

# Manage Python2/3 different modules
# pylint: disable=F0401
try:
    from configparser import ConfigParser
except ImportError:
    from ConfigParser import ConfigParser
# pylint: enable=F0401


FILENAME = (
    os.path.expanduser(config.get("rights", "file")) or
    log.LOGGER.error("No file name configured for rights type 'regex'"))


def _read_from_sections(user, collection, permission):
    """Get regex sections."""
    log.LOGGER.debug("Reading regex from file %s" % FILENAME)
    regex = ConfigParser({"login": user, "path": collection})
    if not regex.read(FILENAME):
        log.LOGGER.error(
            "File '%s' not found for rights management type 'regex'" %
            FILENAME)
        return False

    for section in regex.sections():
        re_user = regex.get(section, "user")
        re_collection = regex.get(section, "collection")
        log.LOGGER.debug(
            "Test if '%s:%s' matches against '%s:%s' from section '%s'" % (
                user, collection, re_user, re_collection, section))
        user_match = re.match(re_user, user)
        if user_match:
            re_collection = re_collection.format(*user_match.groups())
            if re.match(re_collection, collection):
                log.LOGGER.debug("Section '%s' matches" % section)
                if permission in regex.get(section, "permission"):
                    return True
        log.LOGGER.debug("Section '%s' does not match" % section)

    return False


def read_authorized(user, collection):
    """Check if the user is allowed to read the collection."""
    return user and _read_from_sections(
        user, collection.url.rstrip("/") or "/", "r")


def write_authorized(user, collection):
    """Check if the user is allowed to write the collection."""
    return user and _read_from_sections(
        user, collection.url.rstrip("/") or "/", "w")
