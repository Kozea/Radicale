# This file is part of Radicale - CalDAV and CardDAV server
# Copyright © 2026-2026 Peter Bieringer <pb@bieringer.de>
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
Backend that retrieves groups of a user from htgroups file.

Apache's htgroup format (https://httpd.apache.org/docs/2.4/mod/mod_authz_groupfile.html)
"""

import os
import threading
import time
from typing import Set, Tuple

from radicale import config, group, logger


class Group(group.BaseGroup):

    _filename: str
    _encoding: str
    _htgroup_by_member: dict[str, Set]   # member -> groups (set)
    _htgroup_mtime_ns: int
    _htgroup_size: int
    _htgroup_ok: bool
    _htgroup_not_ok_time: float
    _htgroup_not_ok_reminder_seconds: int
    _htgroup_cache: bool
    _lock: threading.Lock

    def __init__(self, configuration: config.Configuration) -> None:
        super().__init__(configuration)
        self._filename = configuration.get("group", "htgroup_filename")
        logger.info("group htgroup file: %r", self._filename)
        self._encoding = configuration.get("encoding", "stock")
        logger.info("group htgroup file encoding: %r", self._encoding)
        self._htgroup_cache = configuration.get("group", "htgroup_cache")
        logger.info("group htgroup cache: %s", self._htgroup_cache)

        self._htgroup_ok = False
        self._htgroup_not_ok_reminder_seconds = 60  # currently hardcoded
        (self._htgroup_ok, self._htgroup_by_member, self._htgroup_size, self._htgroup_mtime_ns) = self._read_htgroup(True, False)
        self._lock = threading.Lock()

    def _read_htgroup(self, init: bool, suppress: bool) -> Tuple[bool, dict, int, int]:
        """Read htgroup file

        init == True: stop on error
        init == False: warn/skip on error and set mark to log reminder every interval
        suppress == True: suppress warnings, change info to debug (used in non-caching mode)
        suppress == False: do not suppress warnings (used in caching mode)

        """
        htgroup_ok = True
        if (init is True) or (suppress is True):
            info = "Read"
        else:
            info = "Re-read"
        if suppress is False:
            logger.info("%s content of htgroup file start: %r", info, self._filename)
        else:
            logger.debug("%s content of htgroup file start: %r", info, self._filename)
        htgroup: dict[str, str] = dict()
        htgroup_by_member: dict[str, Set[str]] = dict()
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
                            group, members = line.split(":", maxsplit=1)
                            skip = False
                            if group == "":
                                if init is True:
                                    raise ValueError("htgroup file contains problematic line not matching <group>:<members> in line: %d" % line_num)
                                else:
                                    errors += 1
                                    logger.warning("htgroup file contains problematic line not matching <group>:<members> in line: %d (ignored)", line_num)
                                    htgroup_ok = False
                                    skip = True
                            else:
                                if htgroup.get(group):
                                    duplicates += 1
                                    if init is True:
                                        raise ValueError("htgroup file contains duplicate group: '%s'", group, line_num)
                                    else:
                                        logger.warning("htgroup file contains duplicate group: '%s' (line: %d / ignored)", group, line_num)
                                        htgroup_ok = False
                                        skip = True
                            if skip is False:
                                htgroup[group] = members
                                entries += 1
                        except ValueError as e:
                            if init is True:
                                raise RuntimeError("Invalid htgroup file %r: %s" % (self._filename, e)) from e
        except OSError as e:
            if init is True:
                raise RuntimeError("Failed to load htgroup file %r: %s" % (self._filename, e)) from e
            else:
                logger.warning("Failed to load htgroup file on re-read: %r" % self._filename)
                htgroup_ok = False
        htgroup_size = os.stat(self._filename).st_size
        htgroup_mtime_ns = os.stat(self._filename).st_mtime_ns
        if suppress is False:
            logger.info("%s content of htgroup file done: %r (entries: %d, duplicates: %d, errors: %d)", info, self._filename, entries, duplicates, errors)
        else:
            logger.debug("%s content of htgroup file done: %r (entries: %d, duplicates: %d, errors: %d)", info, self._filename, entries, duplicates, errors)
        if htgroup_ok is True:
            self._htgroup_not_ok_time = 0
        else:
            self._htgroup_not_ok_time = time.time()
        # convert mapping
        for group in htgroup:
            for member in htgroup[group].split(' '):
                if member not in htgroup_by_member:
                    htgroup_by_member[member] = set([group])
                else:
                    htgroup_by_member[member].add(group)
        return (htgroup_ok, htgroup_by_member, htgroup_size, htgroup_mtime_ns)

    def _groups(self, login: str) -> Set[str]:
        """Get list of groups of login

        Optional: the content of the file is cached and live updates will be detected by
        comparing mtime_ns and size
        """
        logger.trace("Group memberships (htgroup) lookup for user %r", login)
        group_ok = False
        groups: Set[str]
        if self._htgroup_cache is True:
            # check and re-read file if required
            with self._lock:
                htgroup_size = os.stat(self._filename).st_size
                htgroup_mtime_ns = os.stat(self._filename).st_mtime_ns
                if (htgroup_size != self._htgroup_size) or (htgroup_mtime_ns != self._htgroup_mtime_ns):
                    (self._htgroup_ok, self._htgroup, self._htgroup_size, self._htgroup_mtime_ns) = self._read_htgroup(False, False)
                    self._htgroup_not_ok_time = 0

            # log reminder of problemantic file every interval
            current_time = time.time()
            if (self._htgroup_ok is False):
                if (self._htgroup_not_ok_time > 0):
                    if (current_time - self._htgroup_not_ok_time) > self._htgroup_not_ok_reminder_seconds:
                        logger.warning("htgroup file still contains issues (REMINDER, check warnings in the past): %r" % self._filename)
                        self._htgroup_not_ok_time = current_time
                else:
                    self._htgroup_not_ok_time = current_time

            if self._htgroup_by_member.get(login):
                groups = self._htgroup_by_member[login]
                group_ok = True
        else:
            # read file on every request
            (htgroup_ok, htgroup_by_member, htgroup_size, htgroup_mtime_ns) = self._read_htgroup(False, True)
            if htgroup_by_member.get(login):
                groups = htgroup_by_member[login]
                group_ok = True

        if group_ok is True:
            logger.debug("Group memberships (htgroup) for user %r: %r", login, groups)
            return groups
        else:
            logger.debug("Group memberships (htgroup) for user %r not found", login)
        return set([])
