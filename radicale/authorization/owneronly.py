# -*- coding: utf-8 -*-
#
# This file is part of Radicale Server - Calendar Server
# Copyright © 2011-2012 Guillaume Ayoub
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
Radicale authorization module.

Manages who is authorized to access a collection.

The policy here is that owners have read and write access
to their own collections.

"""

import os
import sys

from radicale import authorization, config, log




def read_authorized(user, collection):
    """Check if the user is allowed to read the collection"""
    log.LOGGER.debug("read_authorized '" + user + "' in '" + collection.owner + "/" + collection.name + "'");
    
    return user == collection.owner


def write_authorized(user, collection):
    """Check if the user is allowed to write the collection"""
    log.LOGGER.debug("write_authorized '" + user + "' in '" + collection.owner + "/" + collection.name + "'");

    return user == collection.owner
    
