# This file is part of Radicale Server - Calendar Server
# Copyright © 2008 Nicolas Kandel
# Copyright © 2008 Pascal Halter
# Copyright © 2008-2017 Guillaume Ayoub
# Copyright © 2017-2019 Unrud <unrud@outlook.com>
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
Authentication backend that checks credentials with a htpasswd file.

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

from radicale import auth


class Auth(auth.BaseAuth):
    def __init__(self, configuration):
        super().__init__(configuration)
        self._filename = configuration.get("auth", "htpasswd_filename")
        encryption = configuration.get("auth", "htpasswd_encryption")

        if encryption == "ssha":
            self._verify = self._ssha
        elif encryption == "sha1":
            self._verify = self._sha1
        elif encryption == "plain":
            self._verify = self._plain
        elif encryption == "md5":
            try:
                from passlib.hash import apr_md5_crypt
            except ImportError as e:
                raise RuntimeError(
                    "The htpasswd encryption method 'md5' requires "
                    "the passlib module.") from e
            self._verify = functools.partial(self._md5apr1, apr_md5_crypt)
        elif encryption == "bcrypt":
            try:
                from passlib.hash import bcrypt
            except ImportError as e:
                raise RuntimeError(
                    "The htpasswd encryption method 'bcrypt' requires "
                    "the passlib module with bcrypt support.") from e
            # A call to `encrypt` raises passlib.exc.MissingBackendError with a
            # good error message if bcrypt backend is not available. Trigger
            # this here.
            bcrypt.hash("test-bcrypt-backend")
            self._verify = functools.partial(self._bcrypt, bcrypt)
        elif encryption == "crypt":
            try:
                import crypt
            except ImportError as e:
                raise RuntimeError(
                    "The htpasswd encryption method 'crypt' requires "
                    "the crypt() system support.") from e
            self._verify = functools.partial(self._crypt, crypt)
        else:
            raise RuntimeError("The htpasswd encryption method %r is not "
                               "supported." % encryption)

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

    def login(self, login, password):
        """Validate credentials.

        Iterate through htpasswd credential file until login matches, extract
        hash (encrypted password) and check hash against password,
        using the method specified in the Radicale config.

        The content of the file is not cached because reading is generally a
        very cheap operation, and it's useful to get live updates of the
        htpasswd file.

        """
        try:
            with open(self._filename) as f:
                for line in f:
                    line = line.rstrip("\n")
                    if line.lstrip() and not line.lstrip().startswith("#"):
                        try:
                            hash_login, hash_value = line.split(
                                ":", maxsplit=1)
                            # Always compare both login and password to avoid
                            # timing attacks, see #591.
                            login_ok = hmac.compare_digest(hash_login, login)
                            password_ok = self._verify(hash_value, password)
                            if login_ok and password_ok:
                                return login
                        except ValueError as e:
                            raise RuntimeError("Invalid htpasswd file %r: %s" %
                                               (self._filename, e)) from e
        except OSError as e:
            raise RuntimeError("Failed to load htpasswd file %r: %s" %
                               (self._filename, e)) from e
        return ""
