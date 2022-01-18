# This file is part of Radicale - CalDAV and CardDAV server
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

"""
A dummy web backend that shows a simple message.

"""

from http import client

from radicale import httputils, pathutils, types, web


class Web(web.BaseWeb):

    def get(self, environ: types.WSGIEnviron, base_prefix: str, path: str,
            user: str) -> types.WSGIResponse:
        assert path == "/.web" or path.startswith("/.web/")
        assert pathutils.sanitize_path(path) == path
        if path != "/.web":
            return httputils.redirect(base_prefix + "/.web")
        return client.OK, {"Content-Type": "text/plain"}, "Radicale works!"
