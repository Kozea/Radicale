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

from . import storage


def load(configuration, logger):
    """Load the rights manager chosen in configuration."""
    rights_type = configuration.get("rights", "type")
    if configuration.get("auth", "type") == "None":
        rights_type = "None"
    if rights_type == "None":
        rights_class = NoneRights
    elif rights_type == "authenticated":
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
        except ImportError as e:
            raise RuntimeError("Rights module %r not found" %
                               rights_type) from e
    logger.info("Rights type is %r", rights_type)
    return rights_class(configuration, logger).authorized


class BaseRights:
    def __init__(self, configuration, logger):
        self.configuration = configuration
        self.logger = logger

    def authorized(self, user, collection, permission):
        """Check if the user is allowed to read or write the collection.

        If the user is empty, check for anonymous rights.

        """
        raise NotImplementedError


class NoneRights(BaseRights):
    def authorized(self, user, path, permission):
        return True


class AuthenticatedRights(BaseRights):
    def authorized(self, user, path, permission):
        return bool(user)


class OwnerWriteRights(BaseRights):
    def authorized(self, user, path, permission):
        sane_path = storage.sanitize_path(path).strip("/")
        return bool(user) and (permission == "r" or
                               user == sane_path.split("/", maxsplit=1)[0])


class OwnerOnlyRights(BaseRights):
    def authorized(self, user, path, permission):
        sane_path = storage.sanitize_path(path).strip("/")
        return bool(user) and (
            permission == "r" and not sane_path.strip("/") or
            user == sane_path.split("/", maxsplit=1)[0])


class Rights(BaseRights):
    def __init__(self, configuration, logger):
        super().__init__(configuration, logger)
        self.filename = os.path.expanduser(configuration.get("rights", "file"))

    def authorized(self, user, path, permission):
        user = user or ""
        sane_path = storage.sanitize_path(path).strip("/")
        # Prevent "regex injection"
        user_escaped = re.escape(user)
        sane_path_escaped = re.escape(sane_path)
        regex = configparser.ConfigParser(
            {"login": user_escaped, "path": sane_path_escaped})
        try:
            if not regex.read(self.filename):
                raise RuntimeError("No such file: %r" %
                                   self.filename)
        except Exception as e:
            raise RuntimeError("Failed to load rights file %r: %s" %
                               (self.filename, e)) from e
        for section in regex.sections():
            try:
                re_user_pattern = regex.get(section, "user")
                re_collection_pattern = regex.get(section, "collection")
                # Emulate fullmatch
                user_match = re.match(r"(?:%s)\Z" % re_user_pattern, user)
                collection_match = user_match and re.match(
                    r"(?:%s)\Z" % re_collection_pattern.format(
                        *map(re.escape, user_match.groups())), sane_path)
            except Exception as e:
                raise RuntimeError("Error in section %r of rights file %r: "
                                   "%s" % (section, self.filename, e)) from e
            if user_match and collection_match:
                self.logger.debug("Rule %r:%r matches %r:%r from section %r",
                                  user, sane_path, re_user_pattern,
                                  re_collection_pattern, section)
                return permission in regex.get(section, "permission")
            else:
                self.logger.debug("Rule %r:%r doesn't match %r:%r from section"
                                  " %r", user, sane_path, re_user_pattern,
                                  re_collection_pattern, section)
        self.logger.info(
            "Rights: %r:%r doesn't match any section", user, sane_path)
        return False
