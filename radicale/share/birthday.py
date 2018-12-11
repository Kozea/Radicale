# This file is part of Radicale Server - Calendar Server
# Copyright © 2018 Unrud<unrud@outlook.com>
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

from radicale.share import BaseShare


class Share(BaseShare):

    name = "Birthday"
    uuid = "a5ee648a-2240-4400-af49-a2f064ec5678"
    group = "birthday"
    tags = ("VCALENDAR",)
    item_writethrough = False

    def get(self, item):
        return None

    def get_meta(self, props, base_props):
        return {
            "tag": "VCALENDAR",
        }

    def set_meta(self, props, old_props, old_base_props):
        return old_props, old_base_props
