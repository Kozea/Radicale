# -*- coding: utf-8 -*-
#
# This file is part of Radicale Server - Calendar Server
# Copyright © 2008 Nicolas Kandel
# Copyright © 2008 Pascal Halter
# Copyright © 2008-2013 Guillaume Ayoub
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
Authentication management.

"""

import sys

from .. import config, log


def load():
    """Load list of available authentication managers."""
    auth_type = config.get("auth", "type")
    log.LOGGER.debug("Authentication type is %s" % auth_type)
    if auth_type == "None":
        return None
    elif auth_type == 'custom':
        auth_module = config.get("auth", "custom_handler")
        __import__(auth_module)
        module = sys.modules[auth_module]
    else:
        root_module = __import__(
            "auth.%s" % auth_type, globals=globals(), level=2)
        module = getattr(root_module, auth_type)
    # Override auth.is_authenticated
    sys.modules[__name__].is_authenticated = module.is_authenticated
    return module


def is_authenticated(user, password):
    """Check if the user is authenticated.

    This method is overriden if an auth module is loaded.

    """
    return True  # Default is always True: no authentication
