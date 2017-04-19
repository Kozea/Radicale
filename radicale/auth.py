# This file is part of Radicale Server - Calendar Server
# Copyright © 2008 Nicolas Kandel
# Copyright © 2008 Pascal Halter
# Copyright © 2008-2016 Guillaume Ayoub
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
import os
import random
import time
from importlib import import_module


def load(configuration, logger):
    """Load the authentication manager chosen in configuration."""
    auth_type = configuration.get("auth", "type")
    logger.debug("Authentication type is %s", auth_type)
    if auth_type == "None":
        class_ = NoneAuth
    elif auth_type == "htpasswd":
        class_ = Auth
    else:
        class_ = import_module(auth_type).Auth
    return class_(configuration, logger)


class BaseAuth:
    def __init__(self, configuration, logger):
        self.configuration = configuration
        self.logger = logger

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
            except ImportError:
                raise RuntimeError(
                    "The htpasswd encryption method 'md5' requires "
                    "the passlib module.")
            self.verify = functools.partial(self._md5apr1, apr_md5_crypt)
        elif self.encryption == "bcrypt":
            try:
                from passlib.hash import bcrypt
            except ImportError:
                raise RuntimeError(
                    "The htpasswd encryption method 'bcrypt' requires "
                    "the passlib module with bcrypt support.")
            # A call to `encrypt` raises passlib.exc.MissingBackendError with a
            # good error message if bcrypt backend is not available. Trigger
            # this here.
            bcrypt.encrypt("test-bcrypt-backend")
            self.verify = functools.partial(self._bcrypt, bcrypt)
        elif self.encryption == "crypt":
            try:
                import crypt
            except ImportError:
                raise RuntimeError(
                    "The htpasswd encryption method 'crypt' requires "
                    "the crypt() system support.")
            self.verify = functools.partial(self._crypt, crypt)
        else:
            raise RuntimeError(
                "The htpasswd encryption method '%s' is not "
                "supported." % self.encryption)

    def _plain(self, hash_value, password):
        """Check if ``hash_value`` and ``password`` match, plain method."""
        return hash_value == password

    def _crypt(self, crypt, hash_value, password):
        """Check if ``hash_value`` and ``password`` match, crypt method."""
        return crypt.crypt(password, hash_value) == hash_value

    def _sha1(self, hash_value, password):
        """Check if ``hash_value`` and ``password`` match, sha1 method."""
        hash_value = hash_value.replace("{SHA}", "").encode("ascii")
        password = password.encode(self.configuration.get("encoding", "stock"))
        sha1 = hashlib.sha1()
        sha1.update(password)
        return sha1.digest() == base64.b64decode(hash_value)

    def _ssha(self, hash_value, password):
        """Check if ``hash_value`` and ``password`` match, salted sha1 method.

        This method is not directly supported by htpasswd, but it can be
        written with e.g. openssl, and nginx can parse it.

        """
        hash_value = hash_value.replace(
            "{SSHA}", "").encode("ascii").decode("base64")
        password = password.encode(self.configuration.get("encoding", "stock"))
        hash_value = hash_value[:20]
        salt_value = hash_value[20:]
        sha1 = hashlib.sha1()
        sha1.update(password)
        sha1.update(salt_value)
        return sha1.digest() == hash_value

    def _bcrypt(self, bcrypt, hash_value, password):
        return bcrypt.verify(password, hash_value)

    def _md5apr1(self, md5_apr1, hash_value, password):
        return md5_apr1.verify(password, hash_value)

    def is_authenticated(self, user, password):
        # The content of the file is not cached because reading is generally a
        # very cheap operation, and it's useful to get live updates of the
        # htpasswd file.
        with open(self.filename) as fd:
            for line in fd:
                line = line.strip()
                if line:
                    login, hash_value = line.split(":")
                    if login == user and self.verify(hash_value, password):
                        return True
        # Random timer to avoid timing oracles and simple bruteforce attacks
        time.sleep(1 + random.random())
        return False
