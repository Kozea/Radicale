# This file is part of Radicale - CalDAV and CardDAV server
# Copyright © 2022-2024 Peter Varkoly
# Copyright © 2024-2024 Peter Bieringer <pb@bieringer.de>
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
Authentication backend that checks credentials with a ldap server.
Following parameters are needed in the configuration:
   ldap_uri         The ldap url to the server like ldap://localhost
   ldap_base        The baseDN of the ldap server
   ldap_reader_dn   The DN of a ldap user with read access to get the user accounts
   ldap_secret      The password of the ldap_reader_dn
   ldap_secret_file The path of the file containing the password of the ldap_reader_dn
   ldap_filter      The search filter to find the user to authenticate by the username
   ldap_load_groups If the groups of the authenticated users need to be loaded
Following parameters controls SSL connections:
   ldap_use_ssl   If the connection
   ldap_ssl_verify_mode The certificate verification mode. NONE, OPTIONAL, default is REQUIRED
   ldap_ssl_ca_file

"""
import ssl

from radicale import auth, config
from radicale.log import logger


class Auth(auth.BaseAuth):
    _ldap_uri: str
    _ldap_base: str
    _ldap_reader_dn: str
    _ldap_secret: str
    _ldap_filter: str
    _ldap_load_groups: bool
    _ldap_version: int = 3
    _ldap_use_ssl: bool = False
    _ldap_ssl_verify_mode: int = ssl.CERT_REQUIRED
    _ldap_ssl_ca_file: str = ""

    def __init__(self, configuration: config.Configuration) -> None:
        super().__init__(configuration)
        try:
            import ldap3
            self.ldap3 = ldap3
        except ImportError:
            try:
                import ldap
                self._ldap_version = 2
                self.ldap = ldap
            except ImportError as e:
                raise RuntimeError("LDAP authentication requires the ldap3 module") from e
        self._ldap_uri = configuration.get("auth", "ldap_uri")
        self._ldap_base = configuration.get("auth", "ldap_base")
        self._ldap_reader_dn = configuration.get("auth", "ldap_reader_dn")
        self._ldap_load_groups = configuration.get("auth", "ldap_load_groups")
        self._ldap_secret = configuration.get("auth", "ldap_secret")
        self._ldap_filter = configuration.get("auth", "ldap_filter")
        ldap_secret_file_path = configuration.get("auth", "ldap_secret_file")
        if ldap_secret_file_path:
            with open(ldap_secret_file_path, 'r') as file:
                self._ldap_secret = file.read().rstrip('\n')
        if self._ldap_version == 3:
            self._ldap_use_ssl = configuration.get("auth", "ldap_use_ssl")
            if self._ldap_use_ssl:
                self._ldap_ssl_ca_file = configuration.get("auth", "ldap_ssl_ca_file")
                tmp = configuration.get("auth", "ldap_ssl_verify_mode")
                if tmp == "NONE":
                    self._ldap_ssl_verify_mode = ssl.CERT_NONE
                elif tmp == "OPTIONAL":
                    self._ldap_ssl_verify_mode = ssl.CERT_OPTIONAL
        logger.info("auth.ldap_uri             : %r" % self._ldap_uri)
        logger.info("auth.ldap_base            : %r" % self._ldap_base)
        logger.info("auth.ldap_reader_dn       : %r" % self._ldap_reader_dn)
        logger.info("auth.ldap_load_groups     : %s" % self._ldap_load_groups)
        logger.info("auth.ldap_filter          : %r" % self._ldap_filter)
        if ldap_secret_file_path:
            logger.info("auth.ldap_secret_file_path: %r" % ldap_secret_file_path)
            if self._ldap_secret:
                logger.info("auth.ldap_secret          : (from file)")
        else:
            logger.info("auth.ldap_secret_file_path: (not provided)")
            if self._ldap_secret:
                logger.info("auth.ldap_secret          : (from config)")
        if self._ldap_reader_dn and not self._ldap_secret:
            logger.error("auth.ldap_secret         : (not provided)")
            raise RuntimeError("LDAP authentication requires ldap_secret for reader_dn")
        logger.info("auth.ldap_use_ssl         : %s" % self._ldap_use_ssl)
        if self._ldap_use_ssl is True:
            logger.info("auth.ldap_ssl_verify_mode : %s" % self._ldap_ssl_verify_mode)
            if self._ldap_ssl_ca_file:
                logger.info("auth.ldap_ssl_ca_file     : %r" % self._ldap_ssl_ca_file)
            else:
                logger.info("auth.ldap_ssl_ca_file     : (not provided)")

    def _login2(self, login: str, password: str) -> str:
        try:
            """Bind as reader dn"""
            logger.debug(f"_login2 {self._ldap_uri}, {self._ldap_reader_dn}")
            conn = self.ldap.initialize(self._ldap_uri)
            conn.protocol_version = 3
            conn.set_option(self.ldap.OPT_REFERRALS, 0)
            conn.simple_bind_s(self._ldap_reader_dn, self._ldap_secret)
            """Search for the dn of user to authenticate"""
            res = conn.search_s(self._ldap_base, self.ldap.SCOPE_SUBTREE, filterstr=self._ldap_filter.format(login), attrlist=['memberOf'])
            if len(res) == 0:
                """User could not be find"""
                return ""
            user_dn = res[0][0]
            logger.debug("LDAP Auth user: %s", user_dn)
            """Close ldap connection"""
            conn.unbind()
        except Exception as e:
            raise RuntimeError(f"Invalid ldap configuration:{e}")

        try:
            """Bind as user to authenticate"""
            conn = self.ldap.initialize(self._ldap_uri)
            conn.protocol_version = 3
            conn.set_option(self.ldap.OPT_REFERRALS, 0)
            conn.simple_bind_s(user_dn, password)
            tmp: list[str] = []
            if self._ldap_load_groups:
                tmp = []
                for t in res[0][1]['memberOf']:
                    tmp.append(t.decode('utf-8').split(',')[0][3:])
                self._ldap_groups = set(tmp)
                logger.debug("LDAP Auth groups of user: %s", ",".join(self._ldap_groups))
            conn.unbind()
            return login
        except self.ldap.INVALID_CREDENTIALS:
            return ""

    def _login3(self, login: str, password: str) -> str:
        """Connect the server"""
        try:
            logger.debug(f"_login3 {self._ldap_uri}, {self._ldap_reader_dn}")
            if self._ldap_use_ssl:
                tls = self.ldap3.Tls(validate=self._ldap_ssl_verify_mode)
                if self._ldap_ssl_ca_file != "":
                    tls = self.ldap3.Tls(
                        validate=self._ldap_ssl_verify_mode,
                        ca_certs_file=self._ldap_ssl_ca_file
                        )
                server = self.ldap3.Server(self._ldap_uri, use_ssl=True, tls=tls)
            else:
                server = self.ldap3.Server(self._ldap_uri)
            conn = self.ldap3.Connection(server, self._ldap_reader_dn, password=self._ldap_secret)
        except self.ldap3.core.exceptions.LDAPSocketOpenError:
            raise RuntimeError("Unable to reach ldap server")
        except Exception as e:
            logger.debug(f"_login3 error 1 {e}")
            pass

        if not conn.bind():
            logger.debug("_login3 can not bind")
            raise RuntimeError("Unable to read from ldap server")

        logger.debug(f"_login3 bind as {self._ldap_reader_dn}")
        """Search the user dn"""
        conn.search(
            search_base=self._ldap_base,
            search_filter=self._ldap_filter.format(login),
            search_scope=self.ldap3.SUBTREE,
            attributes=['memberOf']
        )
        if len(conn.entries) == 0:
            logger.debug(f"_login3 user '{login}' can not be find")
            """User could not be find"""
            return ""

        user_entry = conn.response[0]
        conn.unbind()
        user_dn = user_entry['dn']
        logger.debug(f"_login3 found user_dn {user_dn}")
        try:
            """Try to bind as the user itself"""
            conn = self.ldap3.Connection(server, user_dn, password=password)
            if not conn.bind():
                logger.debug(f"_login3 user '{login}' can not be find")
                return ""
            if self._ldap_load_groups:
                tmp = []
                for g in user_entry['attributes']['memberOf']:
                    tmp.append(g.split(',')[0][3:])
                self._ldap_groups = set(tmp)
            conn.unbind()
            logger.debug(f"_login3 {login} successfully authorized")
            return login
        except Exception as e:
            logger.debug(f"_login3 error 2 {e}")
            pass
        return ""

    def _login(self, login: str, password: str) -> str:
        """Validate credentials.
        In first step we make a connection to the ldap server with the ldap_reader_dn credential.
        In next step the DN of the user to authenticate will be searched.
        In the last step the authentication of the user will be proceeded.
        """
        if self._ldap_version == 2:
            return self._login2(login, password)
        return self._login3(login, password)
