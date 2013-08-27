# -*- coding: utf-8 -*-
#
# This file is part of Radicale Server - Calendar Server
# Copyright © 2008 Nicolas Kandel
# Copyright © 2008 Pascal Halter
# Copyright © 2008-2013 Guillaume Ayoub
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
Rights management.

Rights are based on a regex-based file whose name is specified in the config
(section "right", key "file").

Authentication login is matched against the "user" key, and collection's path
is matched against the "collection" key. You can use Python's ConfigParser
interpolation values %(login)s and %(path)s. You can also get groups from the
user regex in the collection with {0}, {1}, etc.

Section names are only used for naming the rule.

Leading or ending slashes are trimmed from collection's path.

"""

import re
import io
import os.path

from . import config, log

# Manage Python2/3 different modules
# pylint: disable=F0401
try:
    from configparser import ConfigParser
except ImportError:
    from ConfigParser import ConfigParser
# pylint: enable=F0401


FILENAME = os.path.expanduser(config.get("rights", "file"))
TYPE = config.get("rights", "type").lower()
DEFINED_RIGHTS = {
    "owner_write": "[r]\nuser:.*\ncollection:.*\npermission:r\n"
                   "[w]\nuser:.*\ncollection:^%(login)s/.+$\npermission:w",
    "owner_only": "[rw]\nuser:.*\ncollection:^%(login)s/.+$\npermission:rw"}


def _read_from_sections(user, collection, permission):
    """Get regex sections."""
    regex = ConfigParser({"login": user, "path": collection})
    if TYPE in DEFINED_RIGHTS:
        log.LOGGER.debug("Rights type '%s'" % TYPE)
        regex.readfp(io.BytesIO(DEFINED_RIGHTS[TYPE]))
    elif TYPE == "from_file":
        log.LOGGER.debug("Reading rights from file %s" % FILENAME)
        if not regex.read(FILENAME):
            log.LOGGER.error("File '%s' not found for rights" % FILENAME)
            return False
    else:
        log.LOGGER.error("Unknown rights type '%s'" % TYPE)
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


def authorized(user, collection, right):
    """Check if the user is allowed to read or write the collection."""
    return TYPE == "none" or (user and _read_from_sections(
        user, collection.url.rstrip("/") or "/", right))
