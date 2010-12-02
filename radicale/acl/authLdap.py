# -*- coding: utf-8 -*-

import sys, ldap, syslog

from radicale import config, log

def has_right(owner, user, password):
	if user == None:
		user=""
	if password == None:
		password=""
	if owner != user:
		return False
	try:
		l=ldap.open(LDAPSERVER, 389)
		dn="%s%s,%s" % (LDAPPREPEND, user, LDAPAPPEND)
		l.simple_bind_s(dn, password);
		return True
	except:
		log.error(sys.exc_info()[0])
		return False

LDAPSERVER = config.get("authLdap", "LDAPServer")
LDAPPREPEND = config.get("authLdap", "LDAPPrepend")
LDAPAPPEND = config.get("authLdap", "LDAPAppend")
