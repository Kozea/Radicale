# This file is part of Radicale - CalDAV and CardDAV server
# Copyright © 2026-2026 Peter Bieringer <pb@bieringer.de>
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
Group membership module.

Enrich user with group membership

Take a look at the class ``BaseGroup`` if you want to implement your own.

"""

from typing import Sequence, Set, final

from radicale import config, utils
from radicale.log import logger

INTERNAL_TYPES: Sequence[str] = ("none",
                                 "auth_type",
                                 "htgroup",
                                 )


def load(configuration: "config.Configuration") -> "BaseGroup":
    """Load the group module chosen in configuration."""
    _type = configuration.get("group", "type")
    if _type == "none":
        logger.info("No user groups lookup method is selected")
    else:
        logger.info("User groups lookup method: %r", _type)
    return utils.load_plugin(INTERNAL_TYPES, "group", "Group", BaseGroup,
                             configuration)


class BaseGroup:

    def __init__(self, configuration: "config.Configuration") -> None:
        """Initialize BaseGroup.

        ``configuration`` see ``radicale.config`` module.
        The ``configuration`` must not change during the lifetime of
        this object, it is kept as an internal reference.

        """
        self.configuration = configuration
        self._type = configuration.get("group", "type")

    def _groups(self, login: str) -> Set[str]:
        """Retrieve set of groups of a user

        ``login`` the login name

        """

        raise NotImplementedError

    @final
    def groups(self, login: str) -> Set[str]:
        return self._groups(login)
