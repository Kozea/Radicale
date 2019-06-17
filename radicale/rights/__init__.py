# This file is part of Radicale Server - Calendar Server
# Copyright © 2012-2017 Guillaume Ayoub
# Copyright © 2017-2018 Unrud <unrud@outlook.com>
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

from importlib import import_module

from radicale.log import logger

INTERNAL_TYPES = ("authenticated", "owner_write", "owner_only", "from_file")


def load(configuration):
    """Load the rights manager chosen in configuration."""
    rights_type = configuration.get("rights", "type")
    if rights_type in INTERNAL_TYPES:
        module = "radicale.rights.%s" % rights_type
    else:
        module = rights_type
    try:
        class_ = import_module(module).Rights
    except Exception as e:
        raise RuntimeError("Failed to load rights module %r: %s" %
                           (module, e)) from e
    logger.info("Rights type is %r", rights_type)
    return class_(configuration)


def intersect_permissions(a, b="RrWw"):
    return "".join(set(a).intersection(set(b)))


class BaseRights:
    def __init__(self, configuration):
        self.configuration = configuration

    def authorized(self, user, path, permissions):
        """Check if the user is allowed to read or write the collection.

        If ``user`` is empty, check for anonymous rights.

        ``path`` is sanitized.

        ``permissions`` can include "R", "r", "W", "w"

        Returns granted rights.

        """
        raise NotImplementedError
