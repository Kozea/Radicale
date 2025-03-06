# RadicaleIMAP IMAP authentication plugin for Radicale.
# Copyright © 2017, 2020 Unrud <unrud@outlook.com>
# Copyright © 2025-2025 Peter Bieringer <pb@bieringer.de>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import imaplib
import ssl

from radicale import auth
from radicale.log import logger


class Auth(auth.BaseAuth):
    """Authenticate user with IMAP."""

    def __init__(self, configuration) -> None:
        super().__init__(configuration)
        self._host, self._port = self.configuration.get("auth", "imap_host")
        logger.info("auth imap host: %r", self._host)
        self._security = self.configuration.get("auth", "imap_security")
        if self._security == "none":
            logger.warning("auth imap security: %s (INSECURE, credentials are transmitted in clear text)", self._security)
        else:
            logger.info("auth imap security: %s", self._security)
        if self._security == "tls":
            if self._port is None:
                self._port = 993
                logger.info("auth imap port (autoselected): %d", self._port)
            else:
                logger.info("auth imap port: %d", self._port)
        else:
            if self._port is None:
                self._port = 143
                logger.info("auth imap port (autoselected): %d", self._port)
            else:
                logger.info("auth imap port: %d", self._port)

    def _login(self, login, password) -> str:
        try:
            connection: imaplib.IMAP4 | imaplib.IMAP4_SSL
            if self._security == "tls":
                connection = imaplib.IMAP4_SSL(
                    host=self._host, port=self._port,
                    ssl_context=ssl.create_default_context())
            else:
                connection = imaplib.IMAP4(host=self._host, port=self._port)
                if self._security == "starttls":
                    connection.starttls(ssl.create_default_context())
            try:
                connection.authenticate(
                    "PLAIN",
                    lambda _: "{0}\x00{0}\x00{1}".format(login, password).encode(),
                )
            except imaplib.IMAP4.error as e:
                logger.warning("IMAP authentication failed for user %r: %s", login, e, exc_info=False)
                return ""
            connection.logout()
            return login
        except (OSError, imaplib.IMAP4.error) as e:
            logger.error("Failed to communicate with IMAP server %r: %s" % ("[%s]:%d" % (self._host, self._port), e))
            return ""
