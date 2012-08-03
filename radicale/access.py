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
Radicale access module.

Manages access to collections.

"""

import os
import sys

from radicale import acl, authorization, log



def load():
    log.LOGGER.debug("access.load()")
    global aacl ; aacl = acl.load()
    global aauthorization ; aauthorization = authorization.load()



def is_authenticated(user, password):
    if (not user): 
        # No user given
        return False

    return aacl.is_authenticated(user, password)
     



def may_read(user, collection):
    """Check if the user is allowed to read the collection"""
    
    user_authorized = aauthorization.read_authorized(user, collection)

    log.LOGGER.debug("read %s %s -- %i" % (user, collection.owner, user_authorized))
    return user_authorized




def may_write(user, collection):
    """Check if the user is allowed to write the collection"""
    
    user_authorized = aauthorization.write_authorized(user, collection)
    
    log.LOGGER.debug("write %s %s -- %i" % (user, collection.owner, user_authorized))
    return user_authorized
