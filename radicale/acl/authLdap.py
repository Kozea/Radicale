# -*- coding: utf-8 -*-

import sys, ldap

from radicale import config

def has_right(owner, user, password):
	if user == None:
		user=""
	if password == None:
		password=""
	if owner != user:
		return False
	try:
		l=ldap.open(LDAPSERVER, 389)
		cn="%s%s,%s" % (LDAPPREPEND, user, LDAPAPPEND)
		l.simple_bind_s(cn, password);
		return True
	except:
		return False

LDAPSERVER = config.get("authLdap", "LDAPServer")
LDAPPREPEND = config.get("authLdap", "LDAPPrepend")
LDAPAPPEND = config.get("authLdap", "LDAPAppend")
