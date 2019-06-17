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

import base64
import functools
import hashlib
import hmac

from radicale import auth


class Auth(auth.BaseAuth):
    def __init__(self, configuration):
        super().__init__(configuration)
        self.filename = configuration.get("auth", "htpasswd_filename")
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
            bcrypt.hash("test-bcrypt-backend")
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
            with open(self.filename) as f:
                for line in f:
                    line = line.rstrip("\n")
                    if line.lstrip() and not line.lstrip().startswith("#"):
                        try:
                            hash_login, hash_value = line.split(
                                ":", maxsplit=1)
                            # Always compare both login and password to avoid
                            # timing attacks, see #591.
                            login_ok = hmac.compare_digest(hash_login, login)
                            password_ok = self.verify(hash_value, password)
                            if login_ok and password_ok:
                                return login
                        except ValueError as e:
                            raise RuntimeError("Invalid htpasswd file %r: %s" %
                                               (self.filename, e)) from e
        except OSError as e:
            raise RuntimeError("Failed to load htpasswd file %r: %s" %
                               (self.filename, e)) from e
        return ""
