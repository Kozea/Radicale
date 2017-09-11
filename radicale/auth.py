# This file is part of Radicale Server - Calendar Server
# Copyright © 2008 Nicolas Kandel
# Copyright © 2008 Pascal Halter
# Copyright © 2008-2017 Guillaume Ayoub
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
Authentication management.

Default is htpasswd authentication.

Apache's htpasswd command (httpd.apache.org/docs/programs/htpasswd.html)
manages a file for storing user credentials. It can encrypt passwords using
different methods, e.g. BCRYPT, MD5-APR1 (a version of MD5 modified for
Apache), SHA1, or by using the system's CRYPT routine. The CRYPT and SHA1
encryption methods implemented by htpasswd are considered as insecure. MD5-APR1
provides medium security as of 2015. Only BCRYPT can be considered secure by
current standards.

MD5-APR1-encrypted credentials can be written by all versions of htpasswd (it
is the default, in fact), whereas BCRYPT requires htpasswd 2.4.x or newer.

The `is_authenticated(user, password)` function provided by this module
verifies the user-given credentials by parsing the htpasswd credential file
pointed to by the ``htpasswd_filename`` configuration value while assuming
the password encryption method specified via the ``htpasswd_encryption``
configuration value.

The following htpasswd password encrpytion methods are supported by Radicale
out-of-the-box:

    - plain-text (created by htpasswd -p...) -- INSECURE
    - CRYPT      (created by htpasswd -d...) -- INSECURE
    - SHA1       (created by htpasswd -s...) -- INSECURE

When passlib (https://pypi.python.org/pypi/passlib) is importable, the
following significantly more secure schemes are parsable by Radicale:

    - MD5-APR1   (htpasswd -m...) -- htpasswd's default method
    - BCRYPT     (htpasswd -B...) -- Requires htpasswd 2.4.x

"""

import base64
import functools
import hashlib
import hmac
import os
from importlib import import_module

import ldap3

INTERNAL_TYPES = ("None", "none", "remote_user", "http_x_remote_user",
                  "htpasswd", "ldap")


def load(configuration, logger):
    """Load the authentication manager chosen in configuration."""
    auth_type = configuration.get("auth", "type")
    if auth_type in ("None", "none"):  # DEPRECATED: use "none"
        class_ = NoneAuth
    elif auth_type == "remote_user":
        class_ = RemoteUserAuth
    elif auth_type == "http_x_remote_user":
        class_ = HttpXRemoteUserAuth
    elif auth_type == "htpasswd":
        class_ = Auth
    elif auth_type == "ldap":
        class_ = LdapAuth
    else:
        try:
            class_ = import_module(auth_type).Auth
        except Exception as e:
            raise RuntimeError("Failed to load authentication module %r: %s" %
                               (auth_type, e)) from e
    logger.info("Authentication type is %r", auth_type)
    return class_(configuration, logger)


class BaseAuth:
    def __init__(self, configuration, logger):
        self.configuration = configuration
        self.logger = logger

    def get_external_login(self, environ):
        """Optionally provide the login and password externally.

        Returns a tuple (login, password) or ().

        """
        return ()

    def is_authenticated(self, user, password):
        """Validate credentials.

        Iterate through htpasswd credential file until user matches, extract
        hash (encrypted password) and check hash against user-given password,
        using the method specified in the Radicale config.

        """
        raise NotImplementedError

    def map_login_to_user(self, login):
        """Map login to internal username."""
        return login


class NoneAuth(BaseAuth):
    def is_authenticated(self, user, password):
        return True


class Auth(BaseAuth):
    def __init__(self, configuration, logger):
        super().__init__(configuration, logger)
        self.filename = os.path.expanduser(
            configuration.get("auth", "htpasswd_filename"))
        self.encryption = configuration.get("auth", "htpasswd_encryption")

        if self.encryption == "ssha":
            self.verify = self._ssha
        elif self.encryption == "sha1":
            self.verify = self._sha1
        elif self.encryption == "plain":
            self.verify = self._plain
        elif self.encryption == "md5":
            try:
                from passlib.hash import apr_md5_crypt
            except ImportError as e:
                raise RuntimeError(
                    "The htpasswd encryption method 'md5' requires "
                    "the passlib module.") from e
            self.verify = functools.partial(self._md5apr1, apr_md5_crypt)
        elif self.encryption == "bcrypt":
            try:
                from passlib.hash import bcrypt
            except ImportError as e:
                raise RuntimeError(
                    "The htpasswd encryption method 'bcrypt' requires "
                    "the passlib module with bcrypt support.") from e
            # A call to `encrypt` raises passlib.exc.MissingBackendError with a
            # good error message if bcrypt backend is not available. Trigger
            # this here.
            bcrypt.encrypt("test-bcrypt-backend")
            self.verify = functools.partial(self._bcrypt, bcrypt)
        elif self.encryption == "crypt":
            try:
                import crypt
            except ImportError as e:
                raise RuntimeError(
                    "The htpasswd encryption method 'crypt' requires "
                    "the crypt() system support.") from e
            self.verify = functools.partial(self._crypt, crypt)
        else:
            raise RuntimeError(
                "The htpasswd encryption method %r is not "
                "supported." % self.encryption)

    def _plain(self, hash_value, password):
        """Check if ``hash_value`` and ``password`` match, plain method."""
        return hmac.compare_digest(hash_value, password)

    def _crypt(self, crypt, hash_value, password):
        """Check if ``hash_value`` and ``password`` match, crypt method."""
        hash_value = hash_value.strip()
        return hmac.compare_digest(crypt.crypt(password, hash_value),
                                   hash_value)

    def _sha1(self, hash_value, password):
        """Check if ``hash_value`` and ``password`` match, sha1 method."""
        hash_value = base64.b64decode(hash_value.strip().replace(
            "{SHA}", "").encode("ascii"))
        password = password.encode(self.configuration.get("encoding", "stock"))
        sha1 = hashlib.sha1()
        sha1.update(password)
        return hmac.compare_digest(sha1.digest(), hash_value)

    def _ssha(self, hash_value, password):
        """Check if ``hash_value`` and ``password`` match, salted sha1 method.

        This method is not directly supported by htpasswd, but it can be
        written with e.g. openssl, and nginx can parse it.

        """
        hash_value = base64.b64decode(hash_value.strip().replace(
            "{SSHA}", "").encode("ascii"))
        password = password.encode(self.configuration.get("encoding", "stock"))
        salt_value = hash_value[20:]
        hash_value = hash_value[:20]
        sha1 = hashlib.sha1()
        sha1.update(password)
        sha1.update(salt_value)
        return hmac.compare_digest(sha1.digest(), hash_value)

    def _bcrypt(self, bcrypt, hash_value, password):
        hash_value = hash_value.strip()
        return bcrypt.verify(password, hash_value)

    def _md5apr1(self, md5_apr1, hash_value, password):
        hash_value = hash_value.strip()
        return md5_apr1.verify(password, hash_value)

    def is_authenticated(self, user, password):
        # The content of the file is not cached because reading is generally a
        # very cheap operation, and it's useful to get live updates of the
        # htpasswd file.
        try:
            with open(self.filename) as f:
                for line in f:
                    line = line.rstrip("\n")
                    if line.lstrip() and not line.lstrip().startswith("#"):
                        try:
                            login, hash_value = line.split(":", maxsplit=1)
                            # Always compare both login and password to avoid
                            # timing attacks, see #591.
                            login_ok = hmac.compare_digest(login, user)
                            password_ok = self.verify(hash_value, password)
                            if login_ok & password_ok:
                                return True
                        except ValueError as e:
                            raise RuntimeError("Invalid htpasswd file %r: %s" %
                                               (self.filename, e)) from e
        except OSError as e:
            raise RuntimeError("Failed to load htpasswd file %r: %s" %
                               (self.filename, e)) from e
        return False


class RemoteUserAuth(NoneAuth):
    def get_external_login(self, environ):
        return environ.get("REMOTE_USER", ""), ""


class HttpXRemoteUserAuth(NoneAuth):
    def get_external_login(self, environ):
        return environ.get("HTTP_X_REMOTE_USER", ""), ""


class LdapAuth(BaseAuth):
    ldap_url = ""
    ldap_base = ""
    ldap_filter = ""
    ldap_attribute = ""
    ldap_binddn = ""
    ldap_password = ""

    def __init__(self, configuration, logger):
        super().__init__(configuration, logger)

        if configuration.has_option("auth", "ldap_url"):
            # also get rid of trailing slashes which are typical for uris
            self.ldap_url = configuration.get("auth", "ldap_url").rstrip("/")
        else:
            raise RuntimeError(
                "The ldap_url configuration for ldap auth is required.")

        if configuration.has_option("auth", "ldap_base"):
            self.ldap_base = configuration.get("auth", "ldap_base")
        else:
            raise RuntimeError(
                "The ldap_base configuration for ldap auth is required.")

        if configuration.has_option("auth", "ldap_filter"):
            self.ldap_filter = configuration.get("auth", "ldap_filter")
        else:
            raise RuntimeError(
                "The ldap_filter configuration for ldap auth is required.")

        if configuration.has_option("auth", "ldap_attribute"):
            self.ldap_attribute = configuration.get("auth", "ldap_attribute")
        else:
            raise RuntimeError(
                "The ldap_attribute configuration for ldap auth is required.")

        if configuration.has_option("auth", "ldap_binddn"):
            self.ldap_binddn = configuration.get("auth", "ldap_binddn")
        else:
            raise RuntimeError(
                "The ldap_binddn configuration for ldap auth is required.")

        if configuration.has_option("auth", "ldap_password"):
            self.ldap_password = configuration.get("auth", "ldap_password")
        else:
            raise RuntimeError(
                "The ldap_password configuration for ldap auth is required.")

        self.logger.info("LDAP auth configuration:")
        self.logger.info("  %r is %r", "ldap_url", self.ldap_url)
        self.logger.info("  %r is %r", "ldap_base", self.ldap_base)
        self.logger.info("  %r is %r", "ldap_filter", self.ldap_filter)
        self.logger.info("  %r is %r", "ldap_attribute", self.ldap_attribute)
        self.logger.info("  %r is %r", "ldap_binddn", self.ldap_binddn)
        self.logger.info("  %r is %r", "ldap_password", self.ldap_password)

    def is_authenticated(self, user, password):
        if user == "" or password == "":
            return False

        server = ldap3.Server(self.ldap_url, get_info=ldap3.ALL)
        conn = ldap3.Connection(server=server, user=self.ldap_binddn,
                                password=self.ldap_password, check_names=True,
                                lazy=False, raise_exceptions=False)
        conn.open()
        conn.bind()

        if conn.result["result"] != 0:
            self.logger.error(conn.result)
            return False

        final_search_filter = self.ldap_filter.replace("%username", user)
        conn.search(search_base=self.ldap_base,
                    search_filter=final_search_filter,
                    attributes=ldap3.ALL_ATTRIBUTES)

        if conn.result["result"] != 0:
            self.logger.error(conn.result)
            return False

        if len(conn.response) == 0:
            return False

        final_user_dn = conn.response[0]["dn"]

        conn.unbind()

        # new connection to check the password as we cannot rebind here
        conn = ldap3.Connection(server=server, user=final_user_dn,
                                password=password, check_names=True,
                                lazy=False, raise_exceptions=False)
        conn.open()
        conn.bind()

        return conn.result["result"] == 0

    def map_login_to_user(self, login):
        if login == "":
            return login

        server = ldap3.Server(self.ldap_url, get_info=ldap3.ALL)
        conn = ldap3.Connection(server=server, user=self.ldap_binddn,
                                password=self.ldap_password, check_names=True,
                                lazy=False, raise_exceptions=False)
        conn.open()
        conn.bind()

        if conn.result["result"] != 0:
            raise RuntimeError(conn.result)

        final_search_filter = self.ldap_filter.replace("%username", login)
        conn.search(search_base=self.ldap_base,
                    search_filter=final_search_filter,
                    attributes=ldap3.ALL_ATTRIBUTES)

        if conn.result["result"] != 0:
            raise RuntimeError(conn.result)

        if len(conn.response) == 0:
            raise RuntimeError("No user found for login name")

        if self.ldap_attribute not in conn.response[0]["attributes"]:
            raise RuntimeError(
                "LDAP record does not contain " + self.ldap_attribute)

        if len(conn.response[0]["attributes"][self.ldap_attribute]) == 0:
            raise RuntimeError(
                "LDAP user has empty attribute " + self.ldap_attribute)

        final_login = conn.response[0]["attributes"][self.ldap_attribute][0]

        conn.unbind()

        return final_login
