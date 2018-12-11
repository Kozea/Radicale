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

    name = "Read"
    uuid = "0d41f7f1-4d93-41e7-98ce-0f2069d6773a"
    group = ""

    tags = ("VADDRESSBOOK", "VCALENDAR")
    item_writethrough = False

    def get(self, item):
        return item

    def get_meta(self, props, base_props):
        return base_props

    def set_meta(self, props, old_props, old_base_props):
        return old_props, old_base_props
