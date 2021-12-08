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

"""
Authentication backend that takes the username from the ``REMOTE_USER``
WSGI environment variable.

It's intended for use with an external WSGI server.

"""

from typing import Tuple, Union

from radicale import types
from radicale.auth import none


class Auth(none.Auth):

    def get_external_login(self, environ: types.WSGIEnviron
                           ) -> Union[Tuple[()], Tuple[str, str]]:
        return environ.get("REMOTE_USER", ""), ""
