# This file is part of Radicale - CalDAV and CardDAV server
# Copyright © 2012-2017 Guillaume Ayoub
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
Rights backend based on a regex-based file whose name is specified in the
config (section "rights", key "file").

The login is matched against the "user" key, and the collection path
is matched against the "collection" key. In the "collection" regex you can use
`{user}` and get groups from the "user" regex with `{0}`, `{1}`, etc.
In consequence of the parameter substitution you have to write `{{` and `}}`
if you want to use regular curly braces in the "user" and "collection" regexes.

For example, for the "user" key, ".+" means "authenticated user" and ".*"
means "anybody" (including anonymous users).

Section names are only used for naming the rule.

Leading or ending slashes are trimmed from collection's path.

"""

from configparser import ConfigParser
import re

from radicale import config, pathutils, rights
from radicale.log import logger


class Rights(rights.BaseRights):

    _filename: str
    _rights_config: ConfigParser
    _user_groups: set

    def __init__(self, configuration: config.Configuration) -> None:
        super().__init__(configuration)
        self._filename = configuration.get("rights", "file")
        self._rights_config = ConfigParser()
        try:
            with open(self._filename, "r") as f:
                self._rights_config.read_file(f)
                logger.debug("Rights were read")
        except Exception as e:
            raise RuntimeError("Failed to load rights file %r: %s" %
                               (self._filename, e)) from e

    def authorization(self, user: str, path: str) -> str:
        user = user or ""
        sane_path = pathutils.strip_path(path)
        # Prevent "regex injection"
        escaped_user = re.escape(user)
        logger.debug("authorization called %r %r",user,path)

        for section in self._rights_config.sections():
            group_match      = []
            try:
                collection_pattern = self._rights_config.get(section, "collection")
                user_pattern   = self._rights_config.get(section, "user", fallback = "")
                allowed_groups = self._rights_config.get(section, "groups", fallback = "").split(",")
                try:
                    group_match = self._user_groups.intersection(allowed_groups)
                    logger.debug("Groups %r, %r",",".join(group_match),";".join(groups))
                except:
                    pass

                # Use empty format() for harmonized handling of curly braces
                user_match = re.fullmatch(user_pattern.format(), user)
                u_collection_match = user_match and re.fullmatch(
                    collection_pattern.format(
                        *(re.escape(s) for s in user_match.groups()),
                        user=escaped_user), sane_path)
                g_collection_match = re.fullmatch( collection_pattern.format(user=escaped_user), sane_path)
            except Exception as e:
                raise RuntimeError("Error in section %r of rights file %r: "
                                   "%s" % (section, self._filename, e)) from e
            if user_match and u_collection_match:
                logger.debug("User rule %r:%r matches %r:%r from section %r",
                             user, sane_path, user_pattern,
                             collection_pattern, section)
                return self._rights_config.get(section, "permissions")
            if len(group_match) > 0 and g_collection_match:
                logger.debug("Group rule %r:%r matches %r from section %r",
                             group_match, sane_path,
                             collection_pattern, section)
                return self._rights_config.get(section, "permissions")
#if user_match and collection_match:
#    permission = rights_config.get(section, "permissions")
#    logger.debug("Rule %r:%r matches %r:%r from section %r permission %r",
#                 user, sane_path, user_pattern,
#                 collection_pattern, section, permission)
#    return permission
            logger.debug("Rule %r:%r doesn't match %r:%r from section %r",
                         user, sane_path, user_pattern, collection_pattern,
                         section)
        logger.info("Rights: %r:%r doesn't match any section", user, sane_path)
        return ""
