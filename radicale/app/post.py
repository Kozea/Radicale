# This file is part of Radicale - CalDAV and CardDAV server
# Copyright © 2008 Nicolas Kandel
# Copyright © 2008 Pascal Halter
# Copyright © 2008-2017 Guillaume Ayoub
# Copyright © 2017-2018 Unrud <unrud@outlook.com>
# Copyright © 2020 Tom Hacohen <tom@stosb.com>
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

from radicale import httputils, types
from radicale.app.base import ApplicationBase


class ApplicationPartPost(ApplicationBase):

    def do_POST(self, environ: types.WSGIEnviron, base_prefix: str,
                path: str, user: str) -> types.WSGIResponse:
        """Manage POST request."""
        if path == "/.web" or path.startswith("/.web/"):
            return self._web.post(environ, base_prefix, path, user)
        return httputils.METHOD_NOT_ALLOWED
