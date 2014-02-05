# -*- coding: utf-8 -*-
#
# This file is part of Radicale Server - Calendar Server
# Copyright © 2012-2013 Guillaume Ayoub
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
Rights backends.

This module loads the rights backend, according to the rights
configuration.

"""
import sys

from .. import config


def load():
    """Load list of available storage managers."""
    storage_type = config.get("rights", "type")
    if storage_type == "custom":
        rights_module = config.get("rights", "custom_handler")
        __import__(rights_module)
        module = sys.modules[rights_module]
    else:
        root_module = __import__("rights.regex", globals=globals(), level=2)
        module = root_module.regex
    sys.modules[__name__].authorized = module.authorized
    return module


def authorized(user, collection, right):
    """ Check when user has rights on collection
    This method is overriden when appropriate rights backend loaded.
    """
    raise NotImplementedError()
