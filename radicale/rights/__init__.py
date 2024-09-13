# This file is part of Radicale - CalDAV and CardDAV server
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

  - R: read collections (excluding address books and calendars)
  - r: read address book and calendar collections
  - i: subset of **r** that only allows direct access via HTTP method GET
       (CalDAV/CardDAV is susceptible to expensive search requests)
  - W: write collections (excluding address books and calendars)
  - w: write address book and calendar collections

Take a look at the class ``BaseRights`` if you want to implement your own.

"""

from typing import Sequence, Set

from radicale import config, utils

INTERNAL_TYPES: Sequence[str] = ("authenticated", "owner_write", "owner_only",
                                 "from_file")


def load(configuration: "config.Configuration") -> "BaseRights":
    """Load the rights module chosen in configuration."""
    return utils.load_plugin(INTERNAL_TYPES, "rights", "Rights", BaseRights,
                             configuration)


def intersect(a: str, b: str) -> str:
    """Intersect two lists of rights.

    Returns all rights that are both in ``a`` and ``b``.

    """
    return "".join(set(a).intersection(set(b)))


class BaseRights:

    _user_groups: Set[str] = set([])

    def __init__(self, configuration: "config.Configuration") -> None:
        """Initialize BaseRights.

        ``configuration`` see ``radicale.config`` module.
        The ``configuration`` must not change during the lifetime of
        this object, it is kept as an internal reference.

        """
        self.configuration = configuration

    def authorization(self, user: str, path: str) -> str:
        """Get granted rights of ``user`` for the collection ``path``.

        If ``user`` is empty, check for anonymous rights.

        ``path`` is sanitized.

        Returns granted rights (e.g. ``"RW"``).

        """
        raise NotImplementedError
