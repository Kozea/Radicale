# This file is part of Radicale Server - Calendar Server
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

import configparser
import re

from radicale import pathutils, rights
from radicale.log import logger


class Rights(rights.BaseRights):
    def __init__(self, configuration):
        super().__init__(configuration)
        self.filename = configuration.get("rights", "file")

    def authorized(self, user, path, permissions):
        user = user or ""
        sane_path = pathutils.strip_path(path)
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
                return rights.intersect_permissions(
                    permissions, rights_config.get(section, "permissions"))
            else:
                logger.debug("Rule %r:%r doesn't match %r:%r from section %r",
                             user, sane_path, user_pattern,
                             collection_pattern, section)
        logger.info("Rights: %r:%r doesn't match any section", user, sane_path)
        return ""
