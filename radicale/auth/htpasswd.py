# This file is part of Radicale - CalDAV and CardDAV server
# Copyright © 2008 Nicolas Kandel
# Copyright © 2008 Pascal Halter
# Copyright © 2008-2017 Guillaume Ayoub
# Copyright © 2017-2019 Unrud <unrud@outlook.com>
# Copyright © 2024 Peter Bieringer <pb@bieringer.de>
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
different the methods BCRYPT/SHA256/SHA512 or MD5-APR1 (a version of MD5 modified for
Apache). MD5-APR1 provides medium security as of 2015. Only BCRYPT/SHA256/SHA512 can be
considered secure by current standards.

MD5-APR1-encrypted credentials can be written by all versions of htpasswd (it
is the default, in fact), whereas BCRYPT/SHA256/SHA512 requires htpasswd 2.4.x or newer.

The `is_authenticated(user, password)` function provided by this module
verifies the user-given credentials by parsing the htpasswd credential file
pointed to by the ``htpasswd_filename`` configuration value while assuming
the password encryption method specified via the ``htpasswd_encryption``
configuration value.

The following htpasswd password encryption methods are supported by Radicale
out-of-the-box:
    - plain-text (created by htpasswd -p ...) -- INSECURE
    - MD5-APR1   (htpasswd -m ...) -- htpasswd's default method, INSECURE
    - SHA256     (htpasswd -2 ...)
    - SHA512     (htpasswd -5 ...)

When bcrypt is installed:
    - BCRYPT     (htpasswd -B ...) -- Requires htpasswd 2.4.x

"""

import functools
import hmac
from typing import Any

from passlib.hash import apr_md5_crypt, sha256_crypt, sha512_crypt

from radicale import auth, config, logger


class Auth(auth.BaseAuth):

    _filename: str
    _encoding: str

    def __init__(self, configuration: config.Configuration) -> None:
        super().__init__(configuration)
        self._filename = configuration.get("auth", "htpasswd_filename")
        self._encoding = configuration.get("encoding", "stock")
        encryption: str = configuration.get("auth", "htpasswd_encryption")

        logger.info("auth htpasswd encryption is 'radicale.auth.htpasswd_encryption.%s'", encryption)

        if encryption == "plain":
            self._verify = self._plain
        elif encryption == "md5":
            self._verify = self._md5apr1
        elif encryption == "sha256":
            self._verify = self._sha256
        elif encryption == "sha512":
            self._verify = self._sha512
        elif encryption == "bcrypt" or encryption == "autodetect":
            try:
                import bcrypt
            except ImportError as e:
                raise RuntimeError(
                    "The htpasswd encryption method 'bcrypt' or 'autodetect' requires "
                    "the bcrypt module.") from e
            if encryption == "bcrypt":
                self._verify = functools.partial(self._bcrypt, bcrypt)
            else:
                self._verify = self._autodetect
                self._verify_bcrypt = functools.partial(self._bcrypt, bcrypt)
        else:
            raise RuntimeError("The htpasswd encryption method %r is not "
                               "supported." % encryption)

    def _plain(self, hash_value: str, password: str) -> bool:
        """Check if ``hash_value`` and ``password`` match, plain method."""
        return hmac.compare_digest(hash_value.encode(), password.encode())

    def _bcrypt(self, bcrypt: Any, hash_value: str, password: str) -> bool:
        return bcrypt.checkpw(password=password.encode('utf-8'), hashed_password=hash_value.encode())

    def _md5apr1(self, hash_value: str, password: str) -> bool:
        return apr_md5_crypt.verify(password, hash_value.strip())

    def _sha256(self, hash_value: str, password: str) -> bool:
        return sha256_crypt.verify(password, hash_value.strip())

    def _sha512(self, hash_value: str, password: str) -> bool:
        return sha512_crypt.verify(password, hash_value.strip())

    def _autodetect(self, hash_value: str, password: str) -> bool:
        if hash_value.startswith("$apr1$", 0, 6) and len(hash_value) == 37:
            # MD5-APR1
            return self._md5apr1(hash_value, password)
        elif hash_value.startswith("$2y$", 0, 4) and len(hash_value) == 60:
            # BCRYPT
            return self._verify_bcrypt(hash_value, password)
        elif hash_value.startswith("$5$", 0, 3) and len(hash_value) == 63:
            # SHA-256
            return self._sha256(hash_value, password)
        elif hash_value.startswith("$6$", 0, 3) and len(hash_value) == 106:
            # SHA-512
            return self._sha512(hash_value, password)
        else:
            # assumed plaintext
            return self._plain(hash_value, password)

    def _login(self, login: str, password: str) -> str:
        """Validate credentials.

        Iterate through htpasswd credential file until login matches, extract
        hash (encrypted password) and check hash against password,
        using the method specified in the Radicale config.

        The content of the file is not cached because reading is generally a
        very cheap operation, and it's useful to get live updates of the
        htpasswd file.

        """
        try:
            with open(self._filename, encoding=self._encoding) as f:
                for line in f:
                    line = line.rstrip("\n")
                    if line.lstrip() and not line.lstrip().startswith("#"):
                        try:
                            hash_login, hash_value = line.split(
                                ":", maxsplit=1)
                            # Always compare both login and password to avoid
                            # timing attacks, see #591.
                            login_ok = hmac.compare_digest(
                                hash_login.encode(), login.encode())
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
