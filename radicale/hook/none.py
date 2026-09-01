# This file is related to Radicale - CalDAV and CardDAV server
# for email notifications
# Copyright © 2020-2020 Tuna Celik <tuna@jakpark.com>
# Copyright © 2025-2025 Nate Harris
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

from radicale import hook


class Hook(hook.BaseHook):
    @property
    def enabled(self) -> bool:
        """Check if this hook is enabled."""
        return False

    def notify(self, notification_item):
        """Notify nothing. Empty hook."""
