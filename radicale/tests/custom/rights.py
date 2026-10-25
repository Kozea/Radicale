# This file is part of Radicale - CalDAV and CardDAV server
# Copyright © 2017-2021 Unrud <unrud@outlook.com>
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
Custom rights management.

"""

from radicale import pathutils, rights


class Rights(rights.BaseRights):

    def authorization(self, user: str, user_groups: set, path: str) -> str:
        sane_path = pathutils.strip_path(path)
        if sane_path not in ("tmp", "other"):
            return ""
        return "RrWw"
