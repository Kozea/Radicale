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
		log.log(10, "Open LDAP server connexion")
		l=ldap.open(LDAPSERVER, 389)
		cn="%s%s,%s" % (LDAPPREPEND, user, LDAPAPPEND)
		log.log(10, "LDAP bind with dn: %s" %(cn))
		l.simple_bind_s(cn, password);
		log.log(20, "LDAP bind Ok")
		return True
	except:
		log.log(40, "LDAP bind error")
		return False

LDAPSERVER = config.get("authLdap", "LDAPServer")
LDAPPREPEND = config.get("authLdap", "LDAPPrepend")
LDAPAPPEND = config.get("authLdap", "LDAPAppend")
