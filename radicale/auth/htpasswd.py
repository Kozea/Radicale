# -*- coding: utf-8 -*-
#
# This file is part of Radicale Server - Calendar Server
# Copyright © 2008 Nicolas Kandel
# Copyright © 2008 Pascal Halter
# Copyright © 2008-2013 Guillaume Ayoub
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
Implement htpasswd authentication.

Apache's htpasswd command (httpd.apache.org/docs/programs/htpasswd.html) manages
a file for storing user credentials. It can encrypt passwords using different
methods, e.g. BCRYPT, MD5-APR1 (a version of MD5 modified for Apache), SHA1, or
by using the system's CRYPT routine. The CRYPT and SHA1 encryption methods
implemented by htpasswd are considered as insecure. MD5-APR1 provides medium
security as of 2015. Only BCRYPT can be considered secure by current standards.

MD5-APR1-encrypted credentials can be written by all versions of htpasswd (its
the default, in fact), whereas BCRYPT requires htpasswd 2.4.x or newer.

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
import hashlib
import os
import random
import time

from .. import config


FILENAME = os.path.expanduser(config.get("auth", "htpasswd_filename"))
ENCRYPTION = config.get("auth", "htpasswd_encryption")


def _plain(hash_value, password):
    """Check if ``hash_value`` and ``password`` match, using plain method."""
    return hash_value == password


def _crypt(hash_value, password):
    """Check if ``hash_value`` and ``password`` match, using crypt method."""
    return crypt.crypt(password, hash_value) == hash_value


def _sha1(hash_value, password):
    """Check if ``hash_value`` and ``password`` match, using sha1 method."""
    hash_value = hash_value.replace("{SHA}", "").encode("ascii")
    password = password.encode(config.get("encoding", "stock"))
    sha1 = hashlib.sha1()  # pylint: disable=E1101
    sha1.update(password)
    return sha1.digest() == base64.b64decode(hash_value)


def _ssha(hash_salt_value, password):
    """Check if ``hash_salt_value`` and ``password`` match, using salted sha1
    method. This method is not directly supported by htpasswd, but it can be
    written with e.g. openssl, and nginx can parse it."""
    hash_salt_value = base64.b64decode(hash_salt_value.replace("{SSHA}", ""))
    password = password.encode(config.get("encoding", "stock"))
    hash_value = hash_salt_value[:20]
    salt_value = hash_salt_value[20:]
    sha1 = hashlib.sha1()  # pylint: disable=E1101
    sha1.update(password)
    sha1.update(salt_value)
    return sha1.digest() == hash_value


def _bcrypt(hash_value, password):
    return _passlib_bcrypt.verify(password, hash_value)


def _md5apr1(hash_value, password):
    return _passlib_md5apr1.verify(password, hash_value)


# Prepare mapping between encryption names and verification functions.
# Pre-fill with methods that do not have external dependencies.
_verifuncs = {
    "ssha": _ssha,
    "sha1": _sha1,
    "plain": _plain}


# Conditionally attempt to import external dependencies.
if ENCRYPTION == "md5":
    try:
        from passlib.hash import apr_md5_crypt as _passlib_md5apr1
    except ImportError:
        raise RuntimeError(("The htpasswd_encryption method 'md5' requires "
            "availability of the passlib module."))
    _verifuncs["md5"] = _md5apr1
elif ENCRYPTION == "bcrypt":
    try:
        from passlib.hash import bcrypt as _passlib_bcrypt
    except ImportError:
        raise RuntimeError(("The htpasswd_encryption method 'bcrypt' requires "
            "availability of the passlib module with bcrypt support."))
    # A call to `encrypt` raises passlib.exc.MissingBackendError with a good
    # error message if bcrypt backend is not available. Trigger this here.
    _passlib_bcrypt.encrypt("test-bcrypt-backend")
    _verifuncs["bcrypt"] = _bcrypt
elif ENCRYPTION == "crypt":
    try:
        import crypt
    except ImportError:
        raise RuntimeError(("The htpasswd_encryption method 'crypt' requires "
            "crypt() system support."))
    _verifuncs["crypt"] = _crypt


# Validate initial configuration.
if ENCRYPTION not in _verifuncs:
    raise RuntimeError(("The htpasswd encryption method '%s' is not "
        "supported." % ENCRYPTION))
 

def is_authenticated(user, password):
    """Validate credentials.

    Iterate through htpasswd credential file until user matches, extract hash
    (encrypted password) and check hash against user-given password, using the
    method specified in the Radicale config.

    """
    with open(FILENAME) as f:
        for line in f:
            strippedline = line.strip()
            if strippedline:
                login, hash_value = strippedline.split(":")
                if login == user:
                    if _verifuncs[ENCRYPTION](hash_value, password):
                        # Allow encryption method to be overridden at runtime.
                        return True
    # Random timer to avoid timing oracles and simple bruteforce attacks
    time.sleep(1 + random.random())
    return False

