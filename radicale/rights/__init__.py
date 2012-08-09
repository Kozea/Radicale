# -*- coding: utf-8 -*-
#
# This file is part of Radicale Server - Calendar Server
# Copyright © 2008-2012 Guillaume Ayoub
# Copyright © 2008 Nicolas Kandel
# Copyright © 2008 Pascal Halter
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
Rights management.

"""

import sys

from radicale import config, log


def load():
    """Load list of available ACL managers."""
    rights_type = config.get("rights", "type")
    log.LOGGER.debug("Rights type is %s" % rights_type)
    if rights_type == "None":
        return None
    else:
        root_module = __import__(
            "rights.%s" % rights_type, globals=globals(), level=2)
        module = getattr(root_module, rights_type)
        # Override rights.[read|write]_authorized
        sys.modules[__name__].read_authorized = module.read_authorized
        sys.modules[__name__].write_authorized = module.write_authorized
        return module


def read_authorized(user, collection):
    """Check if the user is allowed to read the collection.

    This method is overriden if an auth module is loaded.

    """
    return True


def write_authorized(user, collection):
    """Check if the user is allowed to write the collection.

    This method is overriden if an auth module is loaded.

    """
    return True
