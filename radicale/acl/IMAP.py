# -*- coding: utf-8 -*-
#
# This file is part of Radicale Server - Calendar Server
# Copyright © 2012 Daniel Aleksandersen
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

def has_right(owner, user, password):
    """Check if ``user``/``password`` couple is valid."""

    if not user or (owner not in acl.PRIVATE_USERS and user != owner):
        # No user given, or owner is not private and is not user, forbidden
        return False

    log.LOGGER.debug("[IMAP ACL] Connecting to %s:%s." % (IMAP_SERVER, IMAP_SERVER_PORT,))
    connection = imaplib.IMAP4(host=IMAP_SERVER, port=IMAP_SERVER_PORT)

    def secure_connection():
        try:
            connection.starttls()
            log.LOGGER.debug("[IMAP ACL] Server connection changed to TLS.")
            return True
        except (IMAP4.error, IAMP4.abort) as err:
            import sys
            PY_MIN = float(3.2)
            PY_SYS = float("%s.%s" % (sys.version_info.major, sys.version_info.minor))
            if PY_SYS < PY_MIN:
                log.LOGGER.error("[IMAP ACL] Python 3.2 or newer is required for TLS.")
            log.LOGGER.warning("[IMAP ACL] Server at %s failed to accept TLS connection because of: %s" % (IMAP_SERVER, str(err)))
        return False # server is not secure

    def server_is_local():
        if IMAP_HOST == "localhost":
            log.LOGGER.warning("[IMAP ACL] Server is local. Will allow transmitting unencrypted credentials.")
            return True
        return False # server is not local

    """Enforcing security policy of only transmitting credentials over TLS or to local server."""
    if secure_connection() or server_is_local():
        try:
            connection.login( user, password )
            connection.logout()
            log.LOGGER.debug("[IMAP ACL] Authenticated user %s via %s." % (user, IMAP_SERVER))
            return True
        except ( imaplib.IMAP4.error, imaplib.IMAP4.abort, Exception ) as err:
            log.LOGGER.error("[IMAP ACL] Server could not authenticate user %s because of: %s" % (user, str(err)))
    else:
        log.LOGGER.critical("[IMAP ACL] Server did not support TLS and is not ``localhost``. Refusing to transmit passwords under these conditions. Authentication attempt aborted.")
    return False # authentication failed
