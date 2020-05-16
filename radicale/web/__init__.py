# This file is part of Radicale Server - Calendar Server
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

from radicale import utils

INTERNAL_TYPES = ("none", "internal")


def load(configuration):
    """Load the web module chosen in configuration."""
    return utils.load_plugin(INTERNAL_TYPES, "web", "Web", configuration)


class BaseWeb:
    def get(self, environ, base_prefix, path, user):
        """GET request.

        ``base_prefix`` is sanitized and never ends with "/".

        ``path`` is sanitized and always starts with "/.web"

        ``user`` is empty for anonymous users.

        """
        raise NotImplementedError
