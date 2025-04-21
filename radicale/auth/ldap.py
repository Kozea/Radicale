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
Authentication backend that checks credentials with a LDAP server.
Following parameters are needed in the configuration:
   ldap_uri            The LDAP URL to the server like ldap://localhost
   ldap_base           The baseDN of the LDAP server
   ldap_reader_dn      The DN of a LDAP user with read access to get the user accounts
   ldap_secret         The password of the ldap_reader_dn
   ldap_secret_file    The path of the file containing the password of the ldap_reader_dn
   ldap_filter         The search filter to find the user to authenticate by the username
   ldap_user_attribute The attribute to be used as username after authentication
   ldap_groups_attribute The attribute containing group memberships in the LDAP user entry
Following parameters controls SSL connections:
   ldap_use_ssl        If ssl encryption should be used (to be deprecated)
   ldap_security    The encryption mode to be used: *none*|tls|starttls
   ldap_ssl_verify_mode The certificate verification mode. Works for tls and starttls. NONE, OPTIONAL, default is REQUIRED
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
    _ldap_attributes: list[str] = []
    _ldap_user_attr: str
    _ldap_groups_attr: str
    _ldap_module_version: int = 3
    _ldap_use_ssl: bool = False
    _ldap_security: str = "none"
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
                self._ldap_module_version = 2
                self.ldap = ldap
            except ImportError as e:
                raise RuntimeError("LDAP authentication requires the ldap3 module") from e

        self._ldap_ignore_attribute_create_modify_timestamp = configuration.get("auth", "ldap_ignore_attribute_create_modify_timestamp")
        if self._ldap_ignore_attribute_create_modify_timestamp:
            self.ldap3.utils.config._ATTRIBUTES_EXCLUDED_FROM_CHECK.extend(['createTimestamp', 'modifyTimestamp'])
            logger.info("auth.ldap_ignore_attribute_create_modify_timestamp applied")

        self._ldap_uri = configuration.get("auth", "ldap_uri")
        self._ldap_base = configuration.get("auth", "ldap_base")
        self._ldap_reader_dn = configuration.get("auth", "ldap_reader_dn")
        self._ldap_secret = configuration.get("auth", "ldap_secret")
        self._ldap_filter = configuration.get("auth", "ldap_filter")
        self._ldap_user_attr = configuration.get("auth", "ldap_user_attribute")
        self._ldap_groups_attr = configuration.get("auth", "ldap_groups_attribute")
        ldap_secret_file_path = configuration.get("auth", "ldap_secret_file")
        if ldap_secret_file_path:
            with open(ldap_secret_file_path, 'r') as file:
                self._ldap_secret = file.read().rstrip('\n')
        if self._ldap_module_version == 3:
            self._ldap_use_ssl = configuration.get("auth", "ldap_use_ssl")
            self._ldap_security = configuration.get("auth", "ldap_security")
            self._use_encryption = self._ldap_use_ssl or self._ldap_security in ("tls", "starttls")
            if self._ldap_use_ssl and self._ldap_security == "starttls":
                raise RuntimeError("Cannot set both 'ldap_use_ssl = True' and 'ldap_security' = 'starttls'")
            if self._ldap_use_ssl:
                logger.warning("Configuration uses soon to be deprecated 'ldap_use_ssl', use 'ldap_security' ('none', 'tls', 'starttls') instead.")
            if self._use_encryption:
                self._ldap_ssl_ca_file = configuration.get("auth", "ldap_ssl_ca_file")
                tmp = configuration.get("auth", "ldap_ssl_verify_mode")
                if tmp == "NONE":
                    self._ldap_ssl_verify_mode = ssl.CERT_NONE
                elif tmp == "OPTIONAL":
                    self._ldap_ssl_verify_mode = ssl.CERT_OPTIONAL

        logger.info("auth.ldap_uri             : %r" % self._ldap_uri)
        logger.info("auth.ldap_base            : %r" % self._ldap_base)
        logger.info("auth.ldap_reader_dn       : %r" % self._ldap_reader_dn)
        logger.info("auth.ldap_filter          : %r" % self._ldap_filter)
        if self._ldap_user_attr:
            logger.info("auth.ldap_user_attribute  : %r" % self._ldap_user_attr)
        else:
            logger.info("auth.ldap_user_attribute  : (not provided)")
        if self._ldap_groups_attr:
            logger.info("auth.ldap_groups_attribute: %r" % self._ldap_groups_attr)
        else:
            logger.info("auth.ldap_groups_attribute: (not provided)")
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
            raise RuntimeError("LDAP authentication requires ldap_secret for ldap_reader_dn")
        logger.info("auth.ldap_use_ssl         : %s" % self._ldap_use_ssl)
        logger.info("auth.ldap_security      : %s" % self._ldap_security)
        if self._use_encryption:
            logger.info("auth.ldap_ssl_verify_mode : %s" % self._ldap_ssl_verify_mode)
            if self._ldap_ssl_ca_file:
                logger.info("auth.ldap_ssl_ca_file     : %r" % self._ldap_ssl_ca_file)
            else:
                logger.info("auth.ldap_ssl_ca_file     : (not provided)")
        """Extend attributes to to be returned in the user query"""
        if self._ldap_groups_attr:
            self._ldap_attributes.append(self._ldap_groups_attr)
        if self._ldap_user_attr:
            self._ldap_attributes.append(self._ldap_user_attr)
        logger.info("ldap_attributes           : %r" % self._ldap_attributes)

    def _login2(self, login: str, password: str) -> str:
        try:
            """Bind as reader dn"""
            logger.debug(f"_login2 {self._ldap_uri}, {self._ldap_reader_dn}")
            conn = self.ldap.initialize(self._ldap_uri)
            conn.protocol_version = 3
            conn.set_option(self.ldap.OPT_REFERRALS, 0)
            conn.simple_bind_s(self._ldap_reader_dn, self._ldap_secret)
            """Search for the dn of user to authenticate"""
            escaped_login = self.ldap.filter.escape_filter_chars(login)
            logger.debug(f"_login2 login escaped for LDAP filters: {escaped_login}")
            res = conn.search_s(
                self._ldap_base,
                self.ldap.SCOPE_SUBTREE,
                filterstr=self._ldap_filter.format(escaped_login),
                attrlist=self._ldap_attributes
            )
            if len(res) != 1:
                """User could not be found unambiguously"""
                logger.debug(f"_login2 no unique DN found for '{login}'")
                return ""
            user_entry = res[0]
            user_dn = user_entry[0]
            logger.debug(f"_login2 found LDAP user DN {user_dn}")
            """Close LDAP connection"""
            conn.unbind()
        except Exception as e:
            raise RuntimeError(f"Invalid LDAP configuration:{e}")

        try:
            """Bind as user to authenticate"""
            conn = self.ldap.initialize(self._ldap_uri)
            conn.protocol_version = 3
            conn.set_option(self.ldap.OPT_REFERRALS, 0)
            conn.simple_bind_s(user_dn, password)
            tmp: list[str] = []
            if self._ldap_groups_attr:
                tmp = []
                for g in user_entry[1][self._ldap_groups_attr]:
                    """Get group g's RDN's attribute value"""
                    try:
                        rdns = self.ldap.dn.explode_dn(g, notypes=True)
                        tmp.append(rdns[0])
                    except Exception:
                        tmp.append(g.decode('utf8'))
                self._ldap_groups = set(tmp)
                logger.debug("_login2 LDAP groups of user: %s", ",".join(self._ldap_groups))
            if self._ldap_user_attr:
                if user_entry[1][self._ldap_user_attr]:
                    tmplogin = user_entry[1][self._ldap_user_attr][0]
                    login = tmplogin.decode('utf-8')
                    logger.debug(f"_login2 user set to: '{login}'")
            conn.unbind()
            logger.debug(f"_login2 {login} successfully authenticated")
            return login
        except self.ldap.INVALID_CREDENTIALS:
            return ""

    def _login3(self, login: str, password: str) -> str:
        """Connect the server"""
        try:
            logger.debug(f"_login3 {self._ldap_uri}, {self._ldap_reader_dn}")
            if self._use_encryption:
                logger.debug("_login3 using encryption (reader)")
                tls = self.ldap3.Tls(validate=self._ldap_ssl_verify_mode)
                if self._ldap_ssl_ca_file != "":
                    tls = self.ldap3.Tls(
                        validate=self._ldap_ssl_verify_mode,
                        ca_certs_file=self._ldap_ssl_ca_file
                        )
                if self._ldap_use_ssl or self._ldap_security == "tls":
                    logger.debug("_login3 using ssl (reader)")
                    server = self.ldap3.Server(self._ldap_uri, use_ssl=True, tls=tls)
                else:
                    server = self.ldap3.Server(self._ldap_uri, use_ssl=False, tls=tls)
            else:
                logger.debug("_login3 not using encryption (reader)")
                server = self.ldap3.Server(self._ldap_uri)
            try:
                conn = self.ldap3.Connection(server, self._ldap_reader_dn, password=self._ldap_secret, auto_bind=False, raise_exceptions=True)
                if self._ldap_security == "starttls":
                    logger.debug("_login3 using starttls (reader)")
                    conn.start_tls()
            except self.ldap3.core.exceptions.LDAPStartTLSError as e:
                raise RuntimeError(f"_login3 StartTLS Error: {e}")
        except self.ldap3.core.exceptions.LDAPSocketOpenError:
            raise RuntimeError("Unable to reach LDAP server")
        except Exception as e:
            logger.debug(f"_login3 error 1 {e} (reader)")
            pass
        if not conn.bind():
            logger.debug("_login3 cannot bind (reader)")
            raise RuntimeError("Unable to read from LDAP server")
        logger.debug(f"_login3 bind as {self._ldap_reader_dn}")
        """Search the user dn"""
        escaped_login = self.ldap3.utils.conv.escape_filter_chars(login)
        logger.debug(f"_login3 login escaped for LDAP filters: {escaped_login}")
        conn.search(
            search_base=self._ldap_base,
            search_filter=self._ldap_filter.format(escaped_login),
            search_scope=self.ldap3.SUBTREE,
            attributes=self._ldap_attributes
        )
        if len(conn.entries) != 1:
            """User could not be found unambiguously"""
            logger.debug(f"_login3 no unique DN found for '{login}'")
            return ""

        user_entry = conn.response[0]
        conn.unbind()
        user_dn = user_entry['dn']
        logger.debug(f"_login3 found LDAP user DN {user_dn}")
        try:
            """Try to bind as the user itself"""
            try:
                conn = self.ldap3.Connection(server, user_dn, password=password, auto_bind=False)
                if self._ldap_security == "starttls":
                    logger.debug("_login3 using starttls (user)")
                    conn.start_tls()
            except self.ldap3.core.exceptions.LDAPStartTLSError as e:
                raise RuntimeError(f"_login3 StartTLS Error: {e}")
            if not conn.bind():
                logger.debug(f"_login3 user '{login}' cannot be found")
                return ""
            tmp: list[str] = []
            if self._ldap_groups_attr:
                tmp = []
                for g in user_entry['attributes'][self._ldap_groups_attr]:
                    """Get group g's RDN's attribute value"""
                    try:
                        rdns = self.ldap3.utils.dn.parse_dn(g)
                        tmp.append(rdns[0][1])
                    except Exception:
                        tmp.append(g)
                self._ldap_groups = set(tmp)
                logger.debug("_login3 LDAP groups of user: %s", ",".join(self._ldap_groups))
            if self._ldap_user_attr:
                if user_entry['attributes'][self._ldap_user_attr]:
                    if isinstance(user_entry['attributes'][self._ldap_user_attr], list):
                        login = user_entry['attributes'][self._ldap_user_attr][0]
                    else:
                        login = user_entry['attributes'][self._ldap_user_attr]
                    logger.debug(f"_login3 user set to: '{login}'")
            conn.unbind()
            logger.debug(f"_login3 {login} successfully authenticated")
            return login
        except Exception as e:
            logger.debug(f"_login3 error 2 {e}")
            pass
        return ""

    def _login(self, login: str, password: str) -> str:
        """Validate credentials.
        In first step we make a connection to the LDAP server with the ldap_reader_dn credential.
        In next step the DN of the user to authenticate will be searched.
        In the last step the authentication of the user will be proceeded.
        """
        if self._ldap_module_version == 2:
            return self._login2(login, password)
        return self._login3(login, password)
