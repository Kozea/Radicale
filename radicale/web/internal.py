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
The default web backend.

Features:

  - Create and delete address books and calendars.
  - Edit basic metadata of existing address books and calendars.
  - Upload address books and calendars from files.

"""

from radicale import httputils, types, web

MIMETYPES = httputils.MIMETYPES  # deprecated
FALLBACK_MIMETYPE = httputils.FALLBACK_MIMETYPE  # deprecated


class Web(web.BaseWeb):

    def get(self, environ: types.WSGIEnviron, base_prefix: str, path: str,
            user: str) -> types.WSGIResponse:
        return httputils.serve_resource("radicale.web", "internal_data",
                                        base_prefix, path)
