# -*- coding: utf-8 -*-
#
# This file is part of Radicale Server - Calendar Server
# Copyright © 2011 Corentin Le Bail
# Copyright © 2011-2013 Guillaume Ayoub
# Copyright © 2015 Raoul Thill
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

Authentication based on the ``ldap3`` module
(https://github.com/cannatag/ldap3/).

"""

import ldap3
import ldap3.utils.dn

from .. import config, log


SERVER = ldap3.Server(config.get("auth", "ldap_url"))
BASE = config.get("auth", "ldap_base")
ATTRIBUTE = config.get("auth", "ldap_attribute")
FILTER = config.get("auth", "ldap_filter")
BINDDN = config.get("auth", "ldap_binddn")
PASSWORD = config.get("auth", "ldap_password")
SCOPE = config.get("auth", "ldap_scope")


def is_authenticated(user, password):
    """Check if ``user``/``password`` couple is valid."""

    if BINDDN and PASSWORD:
        conn = ldap3.Connection(SERVER, BINDDN, PASSWORD)
        conn.bind()
    else:
        conn = ldap3.Connection(SERVER)

    try:
        log.LOGGER.debug("LDAP whoami: %s" % conn.extend.standard.who_am_i())
    except Exception as err:
        log.LOGGER.debug("LDAP error: %s" % err)

    distinguished_name = "%s=%s" % (ATTRIBUTE, ldap3.utils.dn.escape_attribute_value(user))
    log.LOGGER.debug("LDAP bind for %s in base %s" % (distinguished_name, BASE))

    if FILTER:
        filter_string = "(&(%s)%s)" % (distinguished_name, FILTER)
    else:
        filter_string = distinguished_name
    log.LOGGER.debug("LDAP filter: %s" % filter_string)

    conn.search(search_base=BASE,
                search_scope=SCOPE,
                search_filter=filter_string,
                attributes=[ATTRIBUTE])

    users = conn.response

    if users:
        user_dn = users[0]['dn']
        uid = users[0]['attributes'][ATTRIBUTE]
        log.LOGGER.debug("LDAP user %s (%s) found" % (uid, user_dn))
        try:
            conn = ldap3.Connection(SERVER, user_dn, password)
            conn.bind()
            log.LOGGER.debug(conn.result)
            whoami = conn.extend.standard.who_am_i()
            log.LOGGER.debug("LDAP whoami: %s" % whoami)
            if whoami:
                log.LOGGER.debug("LDAP bind OK")
                return True
            else:
                log.LOGGER.debug("LDAP bind failed")
                return False
        except ldap3.LDAPInvalidCredentialsResult:
            log.LOGGER.debug("LDAP invalid credentials")
        except Exception as err:
            log.LOGGER.debug("LDAP error %s" % err)
        return False
    else:
        log.LOGGER.debug("LDAP user %s not found" % user)
        return False