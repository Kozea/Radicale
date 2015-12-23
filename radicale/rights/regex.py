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

For example, for the "user" key, ".+" means "authenticated user" and ".*"
means "anybody" (including anonymous users).

Section names are only used for naming the rule.

Leading or ending slashes are trimmed from collection's path.

"""

import re
import sys
import os.path

from .. import config, log

# Manage Python2/3 different modules
if sys.version_info[0] == 2:
    from ConfigParser import ConfigParser
    from StringIO import StringIO
else:
    from configparser import ConfigParser
    from io import StringIO


DEFINED_RIGHTS = {
    "authenticated": "[rw]\nuser:.+\ncollection:.*\npermission:rw",
    "owner_write": "[r]\nuser:.+\ncollection:.*\npermission:r\n"
                   "[w]\nuser:.+\ncollection:^%(login)s(/.*)?$\npermission:w",
    "owner_only": "[rw]\nuser:.+\ncollection:^%(login)s(/.*)?$\npermission:rw",
}


def _read_from_sections(user, collection_url, permission):
    """Get regex sections."""
    filename = os.path.expanduser(config.get("rights", "file"))
    rights_type = config.get("rights", "type").lower()
    # Prevent "regex injection"
    user_escaped = re.escape(user)
    collection_url_escaped = re.escape(collection_url)
    regex = ConfigParser({"login": user_escaped, "path": collection_url_escaped})
    if rights_type in DEFINED_RIGHTS:
        log.LOGGER.debug("Rights type '%s'" % rights_type)
        regex.readfp(StringIO(DEFINED_RIGHTS[rights_type]))
    elif rights_type == "from_file":
        log.LOGGER.debug("Reading rights from file %s" % filename)
        if not regex.read(filename):
            log.LOGGER.error("File '%s' not found for rights" % filename)
            return False
    else:
        log.LOGGER.error("Unknown rights type '%s'" % rights_type)
        return False

    for section in regex.sections():
        re_user = regex.get(section, "user")
        re_collection = regex.get(section, "collection")
        log.LOGGER.debug(
            "Test if '%s:%s' matches against '%s:%s' from section '%s'" % (
                user, collection_url, re_user, re_collection, section))
        user_match = re.match(re_user, user)
        if user_match:
            re_collection = re_collection.format(*user_match.groups())
            if re.match(re_collection, collection_url):
                log.LOGGER.debug("Section '%s' matches" % section)
                if permission in regex.get(section, "permission"):
                    return True
            else:
                log.LOGGER.debug("Section '%s' does not match" % section)
    return False


def authorized(user, collection, permission):
    """Check if the user is allowed to read or write the collection.

       If the user is empty it checks for anonymous rights
    """
    collection_url = collection.url.rstrip("/") or "/"
    if collection_url in (".well-known/carddav", ".well-known/caldav"):
        return permission == "r"
    rights_type = config.get("rights", "type").lower()
    return (
        rights_type == "none" or
        _read_from_sections(user or "", collection_url, permission))
