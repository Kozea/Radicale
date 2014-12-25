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
Storage backends.

This module loads the storage backend, according to the storage
configuration.

"""
import imp
from .. import config, ical


def load():
    """Load list of available storage managers."""
    storage_type = config.get("storage", "type")
    if storage_type == "custom":
        storage_module = config.get("storage", "custom_handler")
        module = imp.load_source('storage.Custom', storage_module)
    else:
        root_module = __import__(
            "storage.%s" % storage_type, globals=globals(), level=2)
        module = getattr(root_module, storage_type)
    ical.Collection = module.Collection
    return module
