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

import radicale.rights.authenticated as authenticated
from radicale import pathutils, rights


class Rights(authenticated.Rights):
    def authorized(self, user, path, permissions):
        if self._verify_user and not user:
            return ""
        sane_path = pathutils.strip_path(path)
        if not sane_path:
            return rights.intersect_permissions(permissions, "R")
        if self._verify_user:
            owned = user == sane_path.split("/", maxsplit=1)[0]
        else:
            owned = True
        if "/" not in sane_path:
            return rights.intersect_permissions(permissions,
                                                "RW" if owned else "R")
        if sane_path.count("/") == 1:
            return rights.intersect_permissions(permissions,
                                                "rw" if owned else "r")
        return ""
