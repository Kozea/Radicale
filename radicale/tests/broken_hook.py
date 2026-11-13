# This file is part of Radicale - CalDAV and CardDAV server
# Copyright © 2017-2022 Unrud <unrud@outlook.com>
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

"""Hook plugin whose constructor fails, used to exercise the load fallback."""


class Hook:
    constructed = 0
    notifications: list = []

    def __init__(self, configuration):
        type(self).constructed += 1
        raise RuntimeError("broken hook constructor")

    def notify(self, notification_item):
        type(self).notifications.append(notification_item)
