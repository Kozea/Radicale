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
A dummy backend that returns no group but check whether authentication type supports it.

"""
from typing import Set

from radicale import config, group


class Group(group.BaseGroup):

    def __init__(self, configuration: config.Configuration) -> None:
        super().__init__(configuration)
        auth_type = configuration.get("auth", "type")
        if auth_type not in ["ldap", "pam"]:
            raise RuntimeError("group-type 'auth_type' is not supported by auth/type %r" % auth_type)

    def _groups(self, login: str) -> Set[str]:
        return set([])
