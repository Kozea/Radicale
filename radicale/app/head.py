# This file is part of Radicale - CalDAV and CardDAV server
# Copyright © 2008 Nicolas Kandel
# Copyright © 2008 Pascal Halter
# Copyright © 2008-2017 Guillaume Ayoub
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

from radicale import types
from radicale.app.base import ApplicationBase
from radicale.app.get import ApplicationPartGet


class ApplicationPartHead(ApplicationPartGet, ApplicationBase):

    def do_HEAD(self, environ: types.WSGIEnviron, base_prefix: str, path: str,
                user: str) -> types.WSGIResponse:
        """Manage HEAD request."""
        # Body is dropped in `Application.__call__` for HEAD requests
        return self.do_GET(environ, base_prefix, path, user)
