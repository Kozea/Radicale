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
The rights module used to determine if a user can read and/or write
collections and entries.

Permissions:

  - R: read a collection (excluding address book or calendar collections)
  - r: read an address book or calendar collection
  - W: write a collection (excluding address book or calendar collections)
  - w: write an address book or calendar collection

Take a look at the class ``BaseRights`` if you want to implement your own.

"""

from radicale import utils

INTERNAL_TYPES = ("authenticated", "owner_write", "owner_only", "from_file")


def load(configuration):
    """Load the rights module chosen in configuration."""
    return utils.load_plugin(INTERNAL_TYPES, "rights", "Rights", configuration)


def intersect_permissions(a, b="RrWw"):
    return "".join(set(a).intersection(set(b)))


class BaseRights:
    def __init__(self, configuration):
        """Initialize BaseRights.

        ``configuration`` see ``radicale.config`` module.
        The ``configuration`` must not change during the lifetime of
        this object, it is kept as an internal reference.

        """
        self.configuration = configuration

    def authorized(self, user, path, permissions):
        """Check if the user is allowed to read or write the collection.

        If ``user`` is empty, check for anonymous rights.

        ``path`` is sanitized.

        ``permissions`` can include "R", "r", "W", "w"

        Returns granted rights.

        """
        raise NotImplementedError
