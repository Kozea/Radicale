# -*- coding: utf-8 -*-
#
# This file is part of Radicale Server - Calendar Server
# Copyright © 2011 Corentin Le Bail
# Copyright © 2011 Guillaume Ayoub
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
PAM ACL.

Authentication based on the ``python-ldap`` module
(http://www.python-ldap.org/).

"""

import grp
import pam
import pwd
from radicale import acl, config, log


GROUP_MEMBERSHIP = config.get("acl", "group_membership")


def has_right(owner, user, password):
    """Check if ``user``/``password`` couple is valid."""
    if not user or (owner not in acl.PRIVATE_USERS and user != owner):
        # No user given, or owner is not private and is not user, forbidden
        return False
    
    try: # 1 - Does the user exist in the PAM system?
      pwd.getpwnam(user).pw_uid
      log.LOGGER.debug("User %s found" % user)
    except KeyError: # No such user in the PAM system
      log.LOGGER.debug("User %s not found" % user)
      return False
    
    try: # 2 - Does the user belong to the required group?
      for member in grp.getgrnam(GROUP_MEMBERSHIP):
	if member == user:
	  raise Exception()
      log.LOGGER.debug("The user doesn't belong to the required group (%s)" % GROUP_MEMBERSHIP)
      return False
    except KeyError:
      log.LOGGER.debug("The membership required group (%s) doesn't exist" % GROUP_MEMBERSHIP)
      return False
    except Exception:
      log.LOGGER.debug("The user belong to the required group (%s)" % GROUP_MEMBERSHIP)
        
    if pam.authenticate(user, password): # 3 - Does the password match ?
      return True
    return False # Authentication failled
