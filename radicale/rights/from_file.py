# This file is part of Radicale - CalDAV and CardDAV server
# Copyright © 2012-2017 Guillaume Ayoub
# Copyright © 2017-2021 Unrud <unrud@outlook.com>
# Copyright © 2024-2024 Peter Bieringer <pb@bieringer.de>
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
Rights backend based on a regex-based file whose name is specified in the
config (section "rights", key "file").

The login is matched against the "user" and/or "group" key, with the group
teken from the user's groups (currently available only from LDAP), and the
collection path is matched against the "collection" key.
In the "collection" regex you can use `{user}` and `{group}` to match the
respective info. In addition you can get get the matched regex groups from
the "user" regex with `{0}`, `{1}`, etc., as well as `{group}`
In consequence of the parameter substitution you have to write `{{` and `}}`
if you want to use regular curly braces in the "user" and "collection" regexes.

For example, for the "user" key, ".+" means "authenticated user" and ".*"
means "anybody" (including anonymous users).

Section names are only used for naming the rule but need to be unique.

Leading or ending slashes are trimmed from collection's path.

"""

import configparser
import re

from radicale import config, pathutils, rights
from radicale.log import logger


class Rights(rights.BaseRights):

    _filename: str

    def __init__(self, configuration: config.Configuration) -> None:
        super().__init__(configuration)
        self._filename = configuration.get("rights", "file")
        self._log_rights_rule_doesnt_match_on_debug = configuration.get("logging", "rights_rule_doesnt_match_on_debug")
        self._rights_config = configparser.ConfigParser()
        try:
            with open(self._filename, "r") as f:
                self._rights_config.read_file(f)
            logger.debug("Read rights file")
        except Exception as e:
            raise RuntimeError("Failed to load rights file %r: %s" %
                               (self._filename, e)) from e

    def authorization(self, user: str, path: str) -> str:
        user = user or ""
        sane_path = pathutils.strip_path(path)
        # Prevent "regex injection"
        escaped_user = re.escape(user)
        if not self._log_rights_rule_doesnt_match_on_debug:
            logger.debug("logging of rules which doesn't match suppressed by config/option [logging] rights_rule_doesnt_match_on_debug")
        for section in self._rights_config.sections():
            user_match = None
            group_match = None
            collection_match = None
            matched_groups = []
            group = ''
            try:
                # get patterns from rights file
                user_pattern = self._rights_config.get(section, "user", fallback="")
                group_pattern = self._rights_config.get(section, "groups", fallback="")
                collection_pattern = self._rights_config.get(section, "collection")
                # evaluate user_pattern / groups_pattern
                # Use empty format() for harmonized handling of curly braces
                if user_pattern != "":
                    user_match = re.fullmatch(user_pattern.format(), user)
                if group_pattern != "":
                    for g in self._user_groups:
                        if re.fullmatch(group_pattern.format(), g):
                            matched_groups.append(g)
                    group_match = len(matched_groups) > 0
                # ToDo: check when to base64-escape g
                # calculate collection_match depending on user_match & group_match
                if user_match and group_match:               # user matches & matched_groups is not empty
                    for g in matched_groups:
                        collection_match = re.fullmatch(
                            collection_pattern.format(
                                *(re.escape(s) for s in user_match.groups()),
                                user=escaped_user, group=re.escape(g)), sane_path)
                        if collection_match:
                            group = g
                            break
                elif user_match and group_match is None:     # user matches, but no group_pattern
                    collection_match = re.fullmatch(
                        collection_pattern.format(
                            *(re.escape(s) for s in user_match.groups()),
                            user=escaped_user), sane_path)
                elif group_match and user_match is None:     # matched_groups not empty, but no user_pattern
                    for g in matched_groups:
                        collection_match = re.fullmatch(
                            collection_pattern.format(group=re.escape(g)), sane_path)
                else:                                        # user and/or groups don't match
                    collection_match = None
            except Exception as e:
                raise RuntimeError("Error in section %r of rights file %r: "
                                   "%s" % (section, self._filename, e)) from e
            # evaluate permissions
            if collection_match:
                if user_match and group_match:
                    logger.debug("Rule %r:%r:%r matches %r:%r:%r from section %r permission %r",
                                 user, group, sane_path, user_pattern, group_pattern,
                                 collection_pattern, section, permission)
                elif user_match:
                    logger.debug("Rule %r:%r matches %r:%r from section %r permission %r",
                                 user, sane_path, user_pattern,
                                 collection_pattern, section, permission)
                elif group_match:
                    logger.debug("Rule %r:%r matches %r:%r from section %r permission %r",
                                 group, sane_path, group_pattern,
                                 collection_pattern, section, permission)
                permission = self._rights_config.get(section, "permissions")
                return permission
            if self._log_rights_rule_doesnt_match_on_debug:
                logger.debug("Rule %r:%r doesn't match %r:%r from section %r",
                             user, sane_path, user_pattern, collection_pattern,
                             section)
        logger.debug("Rights: %r:%r doesn't match any section", user, sane_path)
        return ""
