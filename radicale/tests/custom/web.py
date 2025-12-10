# This file is part of Radicale - CalDAV and CardDAV server
# Copyright © 2017-2021 Unrud <unrud@outlook.com>
# Copyright © 2025-2025 Peter Bieringer <pb@bieringer.de>
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
Custom web plugin.

"""

from http import client

from radicale import httputils, types, web


class Web(web.BaseWeb):

    def get(self, environ: types.WSGIEnviron, base_prefix: str, path: str,
            user: str) -> types.WSGIResponse:
        return client.OK, {"Content-Type": "text/plain"}, "custom", None

    def post(self, environ: types.WSGIEnviron, base_prefix: str, path: str,
             user: str) -> types.WSGIResponse:
        content = httputils.read_request_body(self.configuration, environ)
        return client.OK, {"Content-Type": "text/plain"}, "echo:" + content, None
