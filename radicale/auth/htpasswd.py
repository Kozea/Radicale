# This file is part of Radicale - CalDAV and CardDAV server
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
different the methods BCRYPT or MD5-APR1 (a version of MD5 modified for
Apache). MD5-APR1 provides medium security as of 2015. Only BCRYPT can be
considered secure by current standards.

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
    - MD5-APR1   (htpasswd -m...) -- htpasswd's default method

When passlib[bcrypt] is installed:

    - BCRYPT     (htpasswd -B...) -- Requires htpasswd 2.4.x

"""

import functools
import hmac
from typing import Any

from passlib.hash import apr_md5_crypt

from radicale import auth, config


class Auth(auth.BaseAuth):

    _filename: str
    _encoding: str

    def __init__(self, configuration: config.Configuration) -> None:
        super().__init__(configuration)
        self._filename = configuration.get("auth", "htpasswd_filename")
        self._encoding = configuration.get("encoding", "stock")
        encryption: str = configuration.get("auth", "htpasswd_encryption")

        if encryption == "plain":
            self._verify = self._plain
        elif encryption == "md5":
            self._verify = self._md5apr1
        elif encryption == "bcrypt":
            try:
                from passlib.hash import bcrypt
            except ImportError as e:
                raise RuntimeError(
                    "The htpasswd encryption method 'bcrypt' requires "
                    "the passlib[bcrypt] module.") from e
            # A call to `encrypt` raises passlib.exc.MissingBackendError with a
            # good error message if bcrypt backend is not available. Trigger
            # this here.
            bcrypt.hash("test-bcrypt-backend")
            self._verify = functools.partial(self._bcrypt, bcrypt)
        else:
            raise RuntimeError("The htpasswd encryption method %r is not "
                               "supported." % encryption)

    def _plain(self, hash_value: str, password: str) -> bool:
        """Check if ``hash_value`` and ``password`` match, plain method."""
        return hmac.compare_digest(hash_value.encode(), password.encode())

    def _bcrypt(self, bcrypt: Any, hash_value: str, password: str) -> bool:
        return bcrypt.verify(password, hash_value.strip())

    def _md5apr1(self, hash_value: str, password: str) -> bool:
        return apr_md5_crypt.verify(password, hash_value.strip())

    def login(self, login: str, password: str) -> str:
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
