# This file is part of Radicale - CalDAV and CardDAV server
# Copyright © 2008 Nicolas Kandel
# Copyright © 2008 Pascal Halter
# Copyright © 2008-2017 Guillaume Ayoub
# Copyright © 2017-2019 Unrud <unrud@outlook.com>
# Copyright © 2024-2025 Peter Bieringer <pb@bieringer.de>
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

When argon2 is installed:
    - ARGON2     (python -c 'from passlib.hash import argon2; print(argon2.using(type="ID").hash("password"))')

"""

import functools
import hmac
import os
import re
import threading
import time
from typing import Any, Tuple

from passlib.hash import apr_md5_crypt, sha256_crypt, sha512_crypt

from radicale import auth, config, logger


class Auth(auth.BaseAuth):

    _filename: str
    _encoding: str
    _htpasswd: dict             # login -> digest
    _htpasswd_mtime_ns: int
    _htpasswd_size: int
    _htpasswd_ok: bool
    _htpasswd_not_ok_time: float
    _htpasswd_not_ok_reminder_seconds: int
    _htpasswd_bcrypt_use: int
    _htpasswd_argon2_use: int
    _htpasswd_cache: bool
    _has_bcrypt: bool
    _has_argon2: bool
    _encryption: str
    _lock: threading.Lock

    def __init__(self, configuration: config.Configuration) -> None:
        super().__init__(configuration)
        self._filename = configuration.get("auth", "htpasswd_filename")
        logger.info("auth htpasswd file: %r", self._filename)
        self._encoding = configuration.get("encoding", "stock")
        logger.info("auth htpasswd file encoding: %r", self._encoding)
        self._htpasswd_cache = configuration.get("auth", "htpasswd_cache")
        logger.info("auth htpasswd cache: %s", self._htpasswd_cache)
        self._encryption: str = configuration.get("auth", "htpasswd_encryption")
        logger.info("auth htpasswd encryption is 'radicale.auth.htpasswd_encryption.%s'", self._encryption)

        self._has_bcrypt = False
        self._has_argon2 = False
        self._htpasswd_ok = False
        self._htpasswd_not_ok_reminder_seconds = 60 # currently hardcoded
        (self._htpasswd_ok, self._htpasswd_bcrypt_use, self._htpasswd_argon2_use, self._htpasswd, self._htpasswd_size, self._htpasswd_mtime_ns) = self._read_htpasswd(True, False)
        self._lock = threading.Lock()

        if self._encryption == "plain":
            self._verify = self._plain
        elif self._encryption == "md5":
            self._verify = self._md5apr1
        elif self._encryption == "sha256":
            self._verify = self._sha256
        elif self._encryption == "sha512":
            self._verify = self._sha512

        if self._encryption == "bcrypt" or self._encryption == "autodetect":
            try:
                import bcrypt
            except ImportError as e:
                if (self._encryption == "autodetect") and (self._htpasswd_bcrypt_use == 0):
                    logger.warning("auth htpasswd encryption is 'radicale.auth.htpasswd_encryption.%s' which can require bycrypt module, but currently no entries found", self._encryption)
                else:
                    raise RuntimeError(
                        "The htpasswd encryption method 'bcrypt' or 'autodetect' requires "
                        "the bcrypt module (entries found: %d)." % self._htpasswd_bcrypt_use) from e
            else:
                self._has_bcrypt = True
                if self._encryption == "autodetect":
                    if self._htpasswd_bcrypt_use == 0:
                        logger.info("auth htpasswd encryption is 'radicale.auth.htpasswd_encryption.%s' and bycrypt module found, but currently not required", self._encryption)
                    else:
                        logger.info("auth htpasswd encryption is 'radicale.auth.htpasswd_encryption.%s' and bycrypt module found (bcrypt entries found: %d)", self._encryption, self._htpasswd_bcrypt_use)
            if self._encryption == "bcrypt":
                self._verify = functools.partial(self._bcrypt, bcrypt)
            else:
                self._verify = self._autodetect
                if self._htpasswd_bcrypt_use:
                    self._verify_bcrypt = functools.partial(self._bcrypt, bcrypt)

        if self._encryption == "argon2" or self._encryption == "autodetect":
            try:
                import argon2
                from passlib.hash import argon2  # noqa: F811
            except ImportError as e:
                if (self._encryption == "autodetect") and (self._htpasswd_argon2_use == 0):
                    logger.warning("auth htpasswd encryption is 'radicale.auth.htpasswd_encryption.%s' which can require argon2 module, but currently no entries found", self._encryption)
                else:
                    raise RuntimeError(
                        "The htpasswd encryption method 'argon2' or 'autodetect' requires "
                        "the argon2 module (entries found: %d)." % self._htpasswd_argon2_use) from e
            else:
                self._has_argon2 = True
                if self._encryption == "autodetect":
                    if self._htpasswd_argon2_use == 0:
                        logger.info("auth htpasswd encryption is 'radicale.auth.htpasswd_encryption.%s' and argon2 module found, but currently not required", self._encryption)
                    else:
                        logger.info("auth htpasswd encryption is 'radicale.auth.htpasswd_encryption.%s' and argon2 module found (argon2 entries found: %d)", self._encryption, self._htpasswd_argon2_use)
            if self._encryption == "argon2":
                self._verify = functools.partial(self._argon2, argon2)
            else:
                self._verify = self._autodetect
                if self._htpasswd_argon2_use:
                    self._verify_argon2 = functools.partial(self._argon2, argon2)

        if not hasattr(self, '_verify'):
            raise RuntimeError("The htpasswd encryption method %r is not "
                               "supported." % self._encryption)

    def _plain(self, hash_value: str, password: str) -> tuple[str, bool]:
        """Check if ``hash_value`` and ``password`` match, plain method."""
        return ("PLAIN", hmac.compare_digest(hash_value.encode(), password.encode()))

    def _plain_fallback(self, method_orig, hash_value: str, password: str) -> tuple[str, bool]:
        """Check if ``hash_value`` and ``password`` match, plain method / fallback in case of hash length is not matching on autodetection."""
        info = "PLAIN/fallback as hash length not matching for " + method_orig + ": " + str(len(hash_value))
        return (info, hmac.compare_digest(hash_value.encode(), password.encode()))

    def _bcrypt(self, bcrypt: Any, hash_value: str, password: str) -> tuple[str, bool]:
        if self._encryption == "autodetect" and len(hash_value) != 60:
            return self._plain_fallback("BCRYPT", hash_value, password)
        else:
            return ("BCRYPT", bcrypt.checkpw(password=password.encode('utf-8'), hashed_password=hash_value.encode()))

    def _argon2(self, argon2: Any, hash_value: str, password: str) -> tuple[str, bool]:
        return ("ARGON2", argon2.verify(password, hash_value.strip()))

    def _md5apr1(self, hash_value: str, password: str) -> tuple[str, bool]:
        if self._encryption == "autodetect" and len(hash_value) != 37:
            return self._plain_fallback("MD5-APR1", hash_value, password)
        else:
            return ("MD5-APR1", apr_md5_crypt.verify(password, hash_value.strip()))

    def _sha256(self, hash_value: str, password: str) -> tuple[str, bool]:
        if self._encryption == "autodetect" and len(hash_value) != 63:
            return self._plain_fallback("SHA-256", hash_value, password)
        else:
            return ("SHA-256", sha256_crypt.verify(password, hash_value.strip()))

    def _sha512(self, hash_value: str, password: str) -> tuple[str, bool]:
        if self._encryption == "autodetect" and len(hash_value) != 106:
            return self._plain_fallback("SHA-512", hash_value, password)
        else:
            return ("SHA-512", sha512_crypt.verify(password, hash_value.strip()))

    def _autodetect(self, hash_value: str, password: str) -> tuple[str, bool]:
        if hash_value.startswith("$apr1$", 0, 6):
            # MD5-APR1
            return self._md5apr1(hash_value, password)
        elif re.match(r"^\$2(a|b|x|y)?\$", hash_value):
            # BCRYPT
            return self._verify_bcrypt(hash_value, password)
        elif re.match(r"^\$argon2(i|d|id)\$", hash_value):
            # ARGON2
            return self._verify_argon2(hash_value, password)
        elif hash_value.startswith("$5$", 0, 3):
            # SHA-256
            return self._sha256(hash_value, password)
        elif hash_value.startswith("$6$", 0, 3):
            # SHA-512
            return self._sha512(hash_value, password)
        else:
            return self._plain(hash_value, password)

    def _read_htpasswd(self, init: bool, suppress: bool) -> Tuple[bool, int, int, dict, int, int]:
        """Read htpasswd file

        init == True: stop on error
        init == False: warn/skip on error and set mark to log reminder every interval
        suppress == True: suppress warnings, change info to debug (used in non-caching mode)
        suppress == False: do not suppress warnings (used in caching mode)

        """
        htpasswd_ok = True
        bcrypt_use = 0
        argon2_use = 0
        if (init is True) or (suppress is True):
            info = "Read"
        else:
            info = "Re-read"
        if suppress is False:
            logger.info("%s content of htpasswd file start: %r", info, self._filename)
        else:
            logger.debug("%s content of htpasswd file start: %r", info, self._filename)
        htpasswd: dict[str, str] = dict()
        entries = 0
        duplicates = 0
        errors = 0
        try:
            with open(self._filename, encoding=self._encoding) as f:
                line_num = 0
                for line in f:
                    line_num += 1
                    line = line.rstrip("\n")
                    if line.lstrip() and not line.lstrip().startswith("#"):
                        try:
                            login, digest = line.split(":", maxsplit=1)
                            skip = False
                            if login == "" or digest == "":
                                if init is True:
                                    raise ValueError("htpasswd file contains problematic line not matching <login>:<digest> in line: %d" % line_num)
                                else:
                                    errors += 1
                                    logger.warning("htpasswd file contains problematic line not matching <login>:<digest> in line: %d (ignored)", line_num)
                                    htpasswd_ok = False
                                    skip = True
                            else:
                                if htpasswd.get(login):
                                    duplicates += 1
                                    if init is True:
                                        raise ValueError("htpasswd file contains duplicate login: '%s'", login, line_num)
                                    else:
                                        logger.warning("htpasswd file contains duplicate login: '%s' (line: %d / ignored)", login, line_num)
                                        htpasswd_ok = False
                                        skip = True
                                else:
                                    if re.match(r"^\$2(a|b|x|y)?\$", digest) and len(digest) == 60:
                                        if init is True:
                                            bcrypt_use += 1
                                        else:
                                            if self._has_bcrypt is False:
                                                logger.warning("htpasswd file contains bcrypt digest login: '%s' (line: %d / ignored because module is not loaded)", login, line_num)
                                                skip = True
                                                htpasswd_ok = False
                                    if re.match(r"^\$argon2(i|d|id)\$", digest):
                                        if init is True:
                                            argon2_use += 1
                                        else:
                                            if self._has_argon2 is False:
                                                logger.warning("htpasswd file contains argon2 digest login: '%s' (line: %d / ignored because module is not loaded)", login, line_num)
                                                skip = True
                                                htpasswd_ok = False
                            if skip is False:
                                htpasswd[login] = digest
                                entries += 1
                        except ValueError as e:
                            if init is True:
                                raise RuntimeError("Invalid htpasswd file %r: %s" % (self._filename, e)) from e
        except OSError as e:
            if init is True:
                raise RuntimeError("Failed to load htpasswd file %r: %s" % (self._filename, e)) from e
            else:
                logger.warning("Failed to load htpasswd file on re-read: %r" % self._filename)
                htpasswd_ok = False
        htpasswd_size = os.stat(self._filename).st_size
        htpasswd_mtime_ns = os.stat(self._filename).st_mtime_ns
        if suppress is False:
            logger.info("%s content of htpasswd file done: %r (entries: %d, duplicates: %d, errors: %d)", info, self._filename, entries, duplicates, errors)
        else:
            logger.debug("%s content of htpasswd file done: %r (entries: %d, duplicates: %d, errors: %d)", info, self._filename, entries, duplicates, errors)
        if htpasswd_ok is True:
            self._htpasswd_not_ok_time = 0
        else:
            self._htpasswd_not_ok_time = time.time()
        return (htpasswd_ok, bcrypt_use, argon2_use, htpasswd, htpasswd_size, htpasswd_mtime_ns)

    def _login(self, login: str, password: str) -> str:
        """Validate credentials.

        Iterate through htpasswd credential file until login matches, extract
        hash (encrypted password) and check hash against password,
        using the method specified in the Radicale config.

        Optional: the content of the file is cached and live updates will be detected by
        comparing mtime_ns and size

        """
        login_ok = False
        digest: str
        if self._htpasswd_cache is True:
            # check and re-read file if required
            with self._lock:
                htpasswd_size = os.stat(self._filename).st_size
                htpasswd_mtime_ns = os.stat(self._filename).st_mtime_ns
                if (htpasswd_size != self._htpasswd_size) or (htpasswd_mtime_ns != self._htpasswd_mtime_ns):
                    (self._htpasswd_ok, self._htpasswd_bcrypt_use, self._htpasswd_argon2_use, self._htpasswd, self._htpasswd_size, self._htpasswd_mtime_ns) = self._read_htpasswd(False, False)
                    self._htpasswd_not_ok_time = 0

            # log reminder of problemantic file every interval
            current_time = time.time()
            if (self._htpasswd_ok is False):
                if (self._htpasswd_not_ok_time > 0):
                    if (current_time - self._htpasswd_not_ok_time) > self._htpasswd_not_ok_reminder_seconds:
                        logger.warning("htpasswd file still contains issues (REMINDER, check warnings in the past): %r" % self._filename)
                        self._htpasswd_not_ok_time = current_time
                else:
                    self._htpasswd_not_ok_time = current_time

            if self._htpasswd.get(login):
                digest = self._htpasswd[login]
                login_ok = True
        else:
            # read file on every request
            (htpasswd_ok, htpasswd_bcrypt_use, htpasswd_argon2_use, htpasswd, htpasswd_size, htpasswd_mtime_ns) = self._read_htpasswd(False, True)
            if htpasswd.get(login):
                digest = htpasswd[login]
                login_ok = True

        if login_ok is True:
            try:
                (method, password_ok) = self._verify(digest, password)
            except ValueError as e:
                logger.error("Login verification failed for user: '%s' (htpasswd/%s) with error '%s'", login, self._encryption, e)
                return ""
            if password_ok:
                logger.debug("Login verification successful for user: '%s' (htpasswd/%s/%s)", login, self._encryption, method)
                return login
            else:
                logger.warning("Login verification failed for user: '%s' (htpasswd/%s/%s)", login, self._encryption, method)
        else:
            logger.warning("Login verification user not found (htpasswd): '%s'", login)
        return ""
