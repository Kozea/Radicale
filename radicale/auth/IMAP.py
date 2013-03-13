# -*- coding: utf-8 -*-
#
# This file is part of Radicale Server - Calendar Server
# Copyright © 2012 Daniel Aleksandersen
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
IMAP ACL.

Secure authentication based on the ``imaplib`` module.

Validating users against a modern IMAP4rev1 server that awaits STARTTLS on
port 143. Legacy SSL (often on legacy port 993) is deprecated and thus
unsupported. STARTTLS is enforced except if host is ``localhost`` as
passwords are sent in PLAIN.

Python 3.2 or newer is required for TLS.

"""

import imaplib

from radicale import acl, config, log

IMAP_SERVER = config.get("acl", "imap_auth_host_name")
IMAP_SERVER_PORT = config.get("acl", "imap_auth_host_port")
IMAP_USE_SSL = config.get("acl", "imap_auth_use_ssl")


def has_right(owner, user, password):
    """Check if ``user``/``password`` couple is valid."""
    if not user or (owner not in acl.PRIVATE_USERS and user != owner):
        # No user given, or owner is not private and is not user, forbidden
        return False

    log.LOGGER.debug(
        "[IMAP ACL] Connecting to %s:%s." % (IMAP_SERVER, IMAP_SERVER_PORT,))
    if IMAP_USE_SSL:
	connection = imaplib.IMAP4_SSL(host=IMAP_SERVER, port=IMAP_SERVER_PORT)
  	connection_is_secure = True
    else:
	connection = imaplib.IMAP4(host=IMAP_SERVER, port=IMAP_SERVER_PORT)
    	connection_is_secure = False
        log.LOGGER.debug(
            "[IMAP ACL]" "This connection will allow transmitting unencrypted credentials.")

    if not  connection_is_secure:
    	log.LOGGER.warning(
        	"[IMAP ACL] Sending cleartext password for user %s to server %s." % (user, IMAP_SERVER,))
    try:
	connection.login(user, password)
	connection.logout()
	log.LOGGER.debug("[IMAP ACL] Authenticated user %s via %s." % (user, IMAP_SERVER))
	return True
    except (imaplib.IMAP4.error, imaplib.IMAP4.abort) as exception:
	log.LOGGER.error("[IMAP ACL] Server could not authenticate user %s because of: %s" % (user, exception))
    
    return False  # authentication failed


