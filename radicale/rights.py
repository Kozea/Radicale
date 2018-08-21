# This file is part of Radicale Server - Calendar Server
# Copyright © 2012-2017 Guillaume Ayoub
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
Rights backends.

This module loads the rights backend, according to the rights
configuration.

Default rights are based on a regex-based file whose name is specified in the
config (section "right", key "file").

Authentication login is matched against the "user" key, and collection's path
is matched against the "collection" key. You can use Python's ConfigParser
interpolation values %(login)s and %(path)s. You can also get groups from the
user regex in the collection with {0}, {1}, etc.

For example, for the "user" key, ".+" means "authenticated user" and ".*"
means "anybody" (including anonymous users).

Section names are only used for naming the rule.

Leading or ending slashes are trimmed from collection's path.

"""

import configparser
import os.path
import re
from importlib import import_module

from radicale import storage
from radicale.log import logger

INTERNAL_TYPES = ("none", "authenticated", "owner_write", "owner_only",
                  "from_file")


def load(configuration):
    """Load the rights manager chosen in configuration."""
    rights_type = configuration.get("rights", "type")
    if rights_type == "authenticated":
        rights_class = AuthenticatedRights
    elif rights_type == "owner_write":
        rights_class = OwnerWriteRights
    elif rights_type == "owner_only":
        rights_class = OwnerOnlyRights
    elif rights_type == "from_file":
        rights_class = Rights
    else:
        try:
            rights_class = import_module(rights_type).Rights
        except Exception as e:
            raise RuntimeError("Failed to load rights module %r: %s" %
                               (rights_type, e)) from e
    logger.info("Rights type is %r", rights_type)
    return rights_class(configuration)


def intersect_permissions(a, b="RrWw"):
    return "".join(set(a).intersection(set(b)))


class BaseRights:
    def __init__(self, configuration):
        self.configuration = configuration

    def authorized(self, user, path, permissions):
        """Check if the user is allowed to read or write the collection.

        If ``user`` is empty, check for anonymous rights.

        ``path`` is sanitized.

        ``permissions`` can include "R", "r", "W", "w"

        Returns granted rights.

        """
        raise NotImplementedError


class AuthenticatedRights(BaseRights):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._verify_user = self.configuration.get("auth", "type") != "none"

    def authorized(self, user, path, permissions):
        if self._verify_user and not user:
            return ""
        sane_path = storage.sanitize_path(path).strip("/")
        if "/" not in sane_path:
            return intersect_permissions(permissions, "RW")
        if sane_path.count("/") == 1:
            return intersect_permissions(permissions, "rw")
        return ""


class OwnerWriteRights(AuthenticatedRights):
    def authorized(self, user, path, permissions):
        if self._verify_user and not user:
            return ""
        sane_path = storage.sanitize_path(path).strip("/")
        if not sane_path:
            return intersect_permissions(permissions, "R")
        if self._verify_user:
            owned = user == sane_path.split("/", maxsplit=1)[0]
        else:
            owned = True
        if "/" not in sane_path:
            return intersect_permissions(permissions, "RW" if owned else "R")
        if sane_path.count("/") == 1:
            return intersect_permissions(permissions, "rw" if owned else "r")
        return ""


class OwnerOnlyRights(AuthenticatedRights):
    def authorized(self, user, path, permissions):
        if self._verify_user and not user:
            return ""
        sane_path = storage.sanitize_path(path).strip("/")
        if not sane_path:
            return intersect_permissions(permissions, "R")
        if self._verify_user and user != sane_path.split("/", maxsplit=1)[0]:
            return ""
        if "/" not in sane_path:
            return intersect_permissions(permissions, "RW")
        if sane_path.count("/") == 1:
            return intersect_permissions(permissions, "rw")
        return ""


class Rights(BaseRights):
    def __init__(self, configuration):
        super().__init__(configuration)
        self.filename = os.path.expanduser(configuration.get("rights", "file"))

    def authorized(self, user, path, permissions):
        user = user or ""
        sane_path = storage.sanitize_path(path).strip("/")
        # Prevent "regex injection"
        user_escaped = re.escape(user)
        sane_path_escaped = re.escape(sane_path)
        rights_config = configparser.ConfigParser(
            {"login": user_escaped, "path": sane_path_escaped})
        try:
            if not rights_config.read(self.filename):
                raise RuntimeError("No such file: %r" %
                                   self.filename)
        except Exception as e:
            raise RuntimeError("Failed to load rights file %r: %s" %
                               (self.filename, e)) from e
        for section in rights_config.sections():
            try:
                user_pattern = rights_config.get(section, "user")
                collection_pattern = rights_config.get(section, "collection")
                user_match = re.fullmatch(user_pattern, user)
                collection_match = user_match and re.fullmatch(
                    collection_pattern.format(
                        *map(re.escape, user_match.groups())), sane_path)
            except Exception as e:
                raise RuntimeError("Error in section %r of rights file %r: "
                                   "%s" % (section, self.filename, e)) from e
            if user_match and collection_match:
                logger.debug("Rule %r:%r matches %r:%r from section %r",
                             user, sane_path, user_pattern,
                             collection_pattern, section)
                return intersect_permissions(
                    permissions, rights_config.get(section, "permissions"))
            else:
                logger.debug("Rule %r:%r doesn't match %r:%r from section %r",
                             user, sane_path, user_pattern,
                             collection_pattern, section)
        logger.info("Rights: %r:%r doesn't match any section", user, sane_path)
        return ""
