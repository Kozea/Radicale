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
LDAP ACL.

Authentication based on the ``python-ldap`` module
(http://www.python-ldap.org/).

"""

import ldap
from radicale import acl, config, log


BASE = config.get("acl", "ldap_base")
ATTRIBUTE = config.get("acl", "ldap_attribute")
CONNEXION = ldap.initialize(config.get("acl", "ldap_url"))
BINDDN = config.get("acl", "ldap_binddn")
PASSWORD = config.get("acl", "ldap_password")


def has_right(owner, user, password):
    """Check if ``user``/``password`` couple is valid."""
    if not user or (owner not in acl.PRIVATE_USERS and user != owner):
        # No user given, or owner is not private and is not user, forbidden
        return False

    if BINDDN and PASSWORD:
        log.LOGGER.debug("Initial LDAP bind as %s" % BINDDN)
        CONNEXION.simple_bind_s(BINDDN, PASSWORD)

    distinguished_name = "%s=%s" % (ATTRIBUTE, ldap.dn.escape_dn_chars(user))
    log.LOGGER.debug(
        "LDAP bind for %s in base %s" % (distinguished_name, BASE))

    users = CONNEXION.search_s(BASE, ldap.SCOPE_ONELEVEL, distinguished_name)
    if users:
        log.LOGGER.debug("User %s found" % user)
        try:
            CONNEXION.simple_bind_s(users[0][0], password or "")
        except ldap.LDAPError:
            log.LOGGER.debug("Invalid credentials")
        else:
            log.LOGGER.debug("LDAP bind OK")
            return True
    else:
        log.LOGGER.debug("User %s not found" % user)

    log.LOGGER.debug("LDAP bind failed")
    return False
