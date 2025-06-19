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

from http import client
from typing import TYPE_CHECKING

from radicale import httputils, types
from radicale.app.base import ApplicationBase

if TYPE_CHECKING:
    from radicale.privacy.http import PrivacyHTTP


class ApplicationPartOptions(ApplicationBase):
    _privacy_http: "PrivacyHTTP"

    def do_OPTIONS(self, environ: types.WSGIEnviron, base_prefix: str,
                   path: str, user: str) -> types.WSGIResponse:
        """Manage OPTIONS request."""
        # Handle privacy-specific paths for CORS preflight
        if path.startswith("/privacy/"):
            headers = {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, Authorization",
                "Access-Control-Max-Age": "86400"
            }
            return client.OK, headers, None
        headers = {
            "Allow": ", ".join(
                name[3:] for name in dir(self) if name.startswith("do_")),
            "DAV": httputils.DAV_HEADERS}
        return client.OK, headers, None
