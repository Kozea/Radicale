# -*- coding: utf-8 -*-
#
# This file is part of Radicale Server - Calendar Server
# Copyright © 2011 Moritz Kornher
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
Htpasswd ACL.

Load the list of login/password couples according a the configuration file
created by Apache ``htpasswd`` command. Plain-text, crypt and sha1 are
supported, but md5 is not (see ``htpasswd`` man page to understand why).

"""

from radicale import acl, config

def has_right(owner, user, password):
    """Check owner and username"""
    return (owner in acl.PRIVATE_USERS or owner == user)
