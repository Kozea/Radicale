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
The web module for the website at ``/.web``.

Take a look at the class ``BaseWeb`` if you want to implement your own.

"""

from typing import Sequence

from radicale import config, httputils, types, utils

INTERNAL_TYPES: Sequence[str] = ("none", "internal")


def load(configuration: "config.Configuration") -> "BaseWeb":
    """Load the web module chosen in configuration."""
    return utils.load_plugin(INTERNAL_TYPES, "web", "Web", BaseWeb,
                             configuration)


class BaseWeb:

    configuration: "config.Configuration"

    def __init__(self, configuration: "config.Configuration") -> None:
        """Initialize BaseWeb.

        ``configuration`` see ``radicale.config`` module.
        The ``configuration`` must not change during the lifetime of
        this object, it is kept as an internal reference.

        """
        self.configuration = configuration

    def get(self, environ: types.WSGIEnviron, base_prefix: str, path: str,
            user: str) -> types.WSGIResponse:
        """GET request.

        ``base_prefix`` is sanitized and never ends with "/".

        ``path`` is sanitized and always starts with "/.web"

        ``user`` is empty for anonymous users.

        """
        return httputils.METHOD_NOT_ALLOWED

    def post(self, environ: types.WSGIEnviron, base_prefix: str, path: str,
             user: str) -> types.WSGIResponse:
        """POST request.

        ``base_prefix`` is sanitized and never ends with "/".

        ``path`` is sanitized and always starts with "/.web"

        ``user`` is empty for anonymous users.

        Use ``httputils.read*_request_body(self.configuration, environ)`` to
        read the body.

        """
        return httputils.METHOD_NOT_ALLOWED
