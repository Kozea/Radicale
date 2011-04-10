# -*- coding: utf-8 -*-

import sys
import ldap
import radicale

LDAPSERVER = config.get("authLdap", "LDAPServer")
LDAPPREPEND = config.get("authLdap", "LDAPPrepend")
LDAPAPPEND = config.get("authLdap", "LDAPAppend")

def has_right(owner, user, password):
    if user == None:
        user=""
    if password == None:
        password=""
    if owner != user:
        return False
    try:
		radicale.log.LOGGER.info("Open LDAP server connexion")
        l=ldap.open(LDAPSERVER, 389)
        cn="%s%s,%s" % (LDAPPREPEND, user, LDAPAPPEND)
		radicale.log.LOGGER.info("LDAP bind with dn: %s" % (cn))
        l.simple_bind_s(cn, password);
		radicale.log.LOGGER.info("LDAP bind ok")
        return True
    except:
		radicale.log.LOGGER.info("Nu such credential")
    return False
