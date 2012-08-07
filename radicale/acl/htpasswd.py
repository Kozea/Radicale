# -*- coding: utf-8 -*-
#
# This file is part of Radicale Server - Calendar Server
# Copyright © 2008-2012 Guillaume Ayoub
# Copyright © 2008 Nicolas Kandel
# Copyright © 2008 Pascal Halter
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
Htpasswd ACL.

Load the list of login/password couples according a the configuration file
created by Apache ``htpasswd`` command. Plain-text, crypt and sha1 are
supported, but md5 is not (see ``htpasswd`` man page to understand why).

"""

import base64
import hashlib

from radicale import acl, config


FILENAME = config.get("acl", "htpasswd_filename")
ENCRYPTION = config.get("acl", "htpasswd_encryption")


def _plain(hash_value, password):
    """Check if ``hash_value`` and ``password`` match using plain method."""
    return hash_value == password


def _crypt(hash_value, password):
    """Check if ``hash_value`` and ``password`` match using crypt method."""
    # The ``crypt`` module is only present on Unix, import if needed
    import crypt
    return crypt.crypt(password, hash_value) == hash_value


def _sha1(hash_value, password):
    """Check if ``hash_value`` and ``password`` match using sha1 method."""
    hash_value = hash_value.replace("{SHA}", "").encode("ascii")
    password = password.encode(config.get("encoding", "stock"))
    sha1 = hashlib.sha1()  # pylint: disable=E1101
    sha1.update(password)
    return sha1.digest() == base64.b64decode(hash_value)


def is_authenticated(user, password):
    """Check if ``user``/``password`` couple is valid."""
    for line in open(FILENAME).readlines():
        if line.strip():
            login, hash_value = line.strip().split(":")
            if login == user:
                return globals()["_%s" % ENCRYPTION](hash_value, password)
    return False
