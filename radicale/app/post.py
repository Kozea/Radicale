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

import json
from http import client
from typing import Any, Dict, List, Union

from radicale import httputils, types
from radicale.app.base import ApplicationBase

# Define the possible result types
SettingsResult = Union[Dict[str, bool], Dict[str, str]]
CardsResult = Dict[str, List[Dict[str, Any]]]
StatusResult = Dict[str, Union[str, int, List[str]]]
APIResult = Union[SettingsResult, CardsResult, StatusResult, str]


class ApplicationPartPost(ApplicationBase):

    def do_POST(self, environ: types.WSGIEnviron, base_prefix: str,
                path: str, user: str) -> types.WSGIResponse:
        """Manage POST request."""
        # Handle privacy-specific paths first
        if path.startswith("/privacy/"):
            parts = path.strip("/").split("/")
            if len(parts) < 3:
                return httputils.BAD_REQUEST

            resource_type = parts[1]  # 'settings' or 'cards'
            user_identifier = parts[2]

            # Check if authenticated user matches the requested resource
            if user != user_identifier:
                return httputils.FORBIDDEN

            # Read request body
            try:
                content_length = int(environ.get("CONTENT_LENGTH", 0))
                if content_length > 0:
                    body = environ["wsgi.input"].read(content_length)
                    data = json.loads(body)
                else:
                    data = {}
            except (ValueError, json.JSONDecodeError):
                return httputils.BAD_REQUEST

            success: bool
            result: APIResult

            if resource_type == "settings":
                success, result = self._privacy_core.create_settings(user_identifier, data)
                if success:
                    return client.CREATED, {"Content-Type": "application/json"}, json.dumps(result).encode()
            elif resource_type == "cards" and len(parts) > 3 and parts[3] == "reprocess":
                success, result = self._privacy_core.reprocess_cards(user_identifier)
            else:
                return httputils.BAD_REQUEST

            return self._to_wsgi_response(success, result)

        if path == "/.web" or path.startswith("/.web/"):
            return self._web.post(environ, base_prefix, path, user)
        return httputils.METHOD_NOT_ALLOWED
