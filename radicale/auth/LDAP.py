# -*- coding: utf-8 -*-
#
# This file is part of Radicale Server - Calendar Server
# Copyright © 2011 Corentin Le Bail
# Copyright © 2011-2013 Guillaume Ayoub
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
LDAP authentication.

Authentication based on the ``python-ldap`` module
(http://www.python-ldap.org/).

"""

import ldap

from .. import config, log


BASE = config.get("auth", "ldap_base")
ATTRIBUTE = config.get("auth", "ldap_attribute")
FILTER = config.get("auth", "ldap_filter")
CONNEXION = ldap.initialize(config.get("auth", "ldap_url"))
BINDDN = config.get("auth", "ldap_binddn")
PASSWORD = config.get("auth", "ldap_password")
SCOPE = getattr(ldap, "SCOPE_%s" % config.get("auth", "ldap_scope").upper())


def is_authenticated(user, password):
    """Check if ``user``/``password`` couple is valid."""
    global CONNEXION

    try:
        CONNEXION.whoami_s()
    except:
        log.LOGGER.debug("Reconnecting the LDAP server")
        CONNEXION = ldap.initialize(config.get("auth", "ldap_url"))

    if BINDDN and PASSWORD:
        log.LOGGER.debug("Initial LDAP bind as %s" % BINDDN)
        CONNEXION.simple_bind_s(BINDDN, PASSWORD)

    distinguished_name = "%s=%s" % (ATTRIBUTE, ldap.dn.escape_dn_chars(user))
    log.LOGGER.debug(
        "LDAP bind for %s in base %s" % (distinguished_name, BASE))

    if FILTER:
        filter_string = "(&(%s)%s)" % (distinguished_name, FILTER)
    else:
        filter_string = distinguished_name
    log.LOGGER.debug("Used LDAP filter: %s" % filter_string)

    users = CONNEXION.search_s(BASE, SCOPE, filter_string)
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
