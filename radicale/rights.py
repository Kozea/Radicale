# This file is part of Radicale Server - Calendar Server
# Copyright © 2012-2017 Guillaume Ayoub
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
Rights backends.

This module loads the rights backend, according to the rights
configuration.

Default rights are based on a regex-based file whose name is specified in the
config (section "right", key "file").

Authentication login is matched against the "user" key, and collection's path
is matched against the "collection" key. You can use Python's ConfigParser
interpolation values %(login)s and %(path)s. You can also get groups from the
user regex in the collection with {0}, {1}, etc.

For example, for the "user" key, ".+" means "authenticated user" and ".*"
means "anybody" (including anonymous users).

Section names are only used for naming the rule.

Leading or ending slashes are trimmed from collection's path.

"""

import os.path
import re
from configparser import ConfigParser
from importlib import import_module
from io import StringIO

from . import storage


def load(configuration, logger):
    """Load the rights manager chosen in configuration."""
    auth_type = configuration.get("auth", "type")
    rights_type = configuration.get("rights", "type")
    if auth_type == "None" or rights_type == "None":
        return lambda user, collection, permission: True
    elif rights_type in DEFINED_RIGHTS or rights_type == "from_file":
        return Rights(configuration, logger).authorized
    else:
        module = import_module(rights_type)
        return module.Rights(configuration, logger).authorized


DEFINED_RIGHTS = {
    "authenticated": """
[rw]
user:.+
collection:.*
permission:rw
    """,
    "owner_write": """
[w]
user:.+
collection:%(login)s(/.*)?
permission:rw
[r]
user:.+
collection:.*
permission:r
    """,
    "owner_only": """
[rw]
user:.+
collection:%(login)s(/.*)?
permission:rw
[r]
user:.+
collection:
permission:r
    """}


class BaseRights:
    def __init__(self, configuration, logger):
        self.configuration = configuration
        self.logger = logger

    def authorized(self, user, collection, permission):
        """Check if the user is allowed to read or write the collection.

        If the user is empty, check for anonymous rights.

        """
        raise NotImplementedError


class Rights(BaseRights):
    def __init__(self, configuration, logger):
        super().__init__(configuration, logger)
        self.filename = os.path.expanduser(configuration.get("rights", "file"))
        self.rights_type = configuration.get("rights", "type").lower()

    def authorized(self, user, path, permission):
        user = user or ""
        if user and not storage.is_safe_path_component(user):
            # Prevent usernames like "user/calendar.ics"
            raise ValueError("Refused unsafe username: %s", user)
        sane_path = storage.sanitize_path(path).strip("/")
        # Prevent "regex injection"
        user_escaped = re.escape(user)
        sane_path_escaped = re.escape(sane_path)
        regex = ConfigParser(
            {"login": user_escaped, "path": sane_path_escaped})
        if self.rights_type in DEFINED_RIGHTS:
            self.logger.debug("Rights type '%s'", self.rights_type)
            regex.readfp(StringIO(DEFINED_RIGHTS[self.rights_type]))
        else:
            self.logger.debug("Reading rights from file '%s'", self.filename)
            if not regex.read(self.filename):
                self.logger.error(
                    "File '%s' not found for rights", self.filename)
                return False

        for section in regex.sections():
            re_user = regex.get(section, "user")
            re_collection = regex.get(section, "collection")
            self.logger.debug(
                "Test if '%s:%s' matches against '%s:%s' from section '%s'",
                user, sane_path, re_user, re_collection, section)
            # Emulate fullmatch
            user_match = re.match(r"(?:%s)\Z" % re_user, user)
            if user_match:
                re_collection = re_collection.format(*user_match.groups())
                # Emulate fullmatch
                if re.match(r"(?:%s)\Z" % re_collection, sane_path):
                    self.logger.debug("Section '%s' matches", section)
                    return permission in regex.get(section, "permission")
                else:
                    self.logger.debug("Section '%s' does not match", section)
        return False
