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
Radicale tests related to group lookup.

"""

import logging
import os

import pytest

import radicale
from radicale.tests import BaseTest


class TestBaseGroupRequests(BaseTest):
    """Tests basic requests with group lookup.

    We should setup auth for each type before creating the Application object.

    """

    def _test_htgroup(self, htpasswd_content: str, htgroup_content, check: int = 207) -> None:
        """Test htpasswd authentication with user "tmp" and password "bepo" for
        """
        htpasswd_file_path = os.path.join(self.colpath, ".htpasswd")
        htgroup_file_path = os.path.join(self.colpath, ".htgroup")
        encoding: str = self.configuration.get("encoding", "stock")
        with open(htpasswd_file_path, "w", encoding=encoding) as f:
            f.write(htpasswd_content)
        with open(htgroup_file_path, "w", encoding=encoding) as f:
            f.write(htgroup_content)
        self.configure({"auth": {"type": "htpasswd",
                                 "delay": 0,
                                 "htpasswd_filename": htpasswd_file_path,
                                 "htpasswd_encryption": "autodetect"},
                        "group": {"type": "htgroup",
                                  "htgroup_filename": htgroup_file_path},
                        "server": {"delay_on_error": 0}})
        self.propfind("/", check=check,
                      login="%s:%s" % ("tmp", "bepo"))

    @pytest.mark.skipif(radicale.log.logger.getEffectiveLevel() == logging.INFO, reason="requires loglevel DEBUG")
    def test_htgroup_simple(self, caplog) -> None:
        caplog.set_level(logging.DEBUG)
        self._test_htgroup(htpasswd_content="tmp:bepo",
                           htgroup_content="group:tmp")
        logs = caplog.messages
        assert len([log for log in logs if "Group memberships (htgroup) for user 'tmp': {'group'}" in log]) == 1

    @pytest.mark.skipif(radicale.log.logger.getEffectiveLevel() == logging.INFO, reason="requires loglevel DEBUG")
    def test_htgroup_more_groups(self, caplog) -> None:
        caplog.set_level(logging.DEBUG)
        self._test_htgroup(htpasswd_content="tmp:bepo",
                           htgroup_content="group1:tmp\ngroup2:tmp\ngroup3:user")
        logs = caplog.messages
        assert len([log for log in logs
                    if "Group memberships (htgroup) for user 'tmp': {'group2', 'group1'}" in log
                    or "Group memberships (htgroup) for user 'tmp': {'group1', 'group2'}" in log
                    ]) == 1

    @pytest.mark.skipif(radicale.log.logger.getEffectiveLevel() == logging.INFO, reason="requires loglevel DEBUG")
    def test_htgroup_more_empty_groups(self, caplog) -> None:
        caplog.set_level(logging.DEBUG)
        self._test_htgroup(htpasswd_content="tmp:bepo",
                           htgroup_content="group1:tmp\ngroup2:tmp\ngroup3:user\ngroup4:")
        logs = caplog.messages
        assert len([log for log in logs
                    if "Group memberships (htgroup) for user 'tmp': {'group2', 'group1'}" in log
                    or "Group memberships (htgroup) for user 'tmp': {'group1', 'group2'}" in log
                    ]) == 1

    @pytest.mark.skipif(radicale.log.logger.getEffectiveLevel() == logging.INFO, reason="requires loglevel DEBUG")
    def test_htgroup_more_users(self, caplog) -> None:
        caplog.set_level(logging.DEBUG)
        self._test_htgroup(htpasswd_content="tmp:bepo",
                           htgroup_content="group1:tmp user1\ngroup2:tmp user2\ngroup3:user3 user2")
        logs = caplog.messages
        assert len([log for log in logs
                    if "Group memberships (htgroup) for user 'tmp': {'group2', 'group1'}" in log
                    or "Group memberships (htgroup) for user 'tmp': {'group1', 'group2'}" in log
                    ]) == 1

    @pytest.mark.skipif(radicale.log.logger.getEffectiveLevel() == logging.INFO, reason="requires loglevel DEBUG")
    def test_htgroup_unauthenticated_user(self, caplog) -> None:
        caplog.set_level(logging.DEBUG)
        self._test_htgroup(htpasswd_content="tmp:bepo1",
                           htgroup_content="group1:tmp user1\ngroup2:tmp user2\ngroup3:user3 user2", check=401)
        logs = caplog.messages
        assert len([log for log in logs
                    if "Group memberships (htgroup) for user 'tmp': {'group2', 'group1'}" in log
                    or "Group memberships (htgroup) for user 'tmp': {'group1', 'group2'}" in log
                    ]) == 0

    def test_incompatible_group_auth_type(self) -> None:
        for auth_type in ["dovecot", "imap", "remote_user", "http_remote_user", "htpasswd", "oauth2"]:
            logging.info("\n*** test: auth_type=%r, group_type=%r", "dovecot", auth_type)
            try:
                self.configure(
                        {"auth": {
                            "type": auth_type,
                            "oauth2_token": "dummy",
                            },
                         "group": {"type": "auth_type"}
                         })
            except RuntimeError:
                pass
            else:
                raise

        for auth_type in ["pam", "ldap"]:
            logging.info("\n*** test: auth_type=%r, group_type=%r", "dovecot", auth_type)
            try:
                self.configure(
                        {"auth": {
                            "type": auth_type,
                            },
                         "group": {"type": "auth_type"}
                         })
            except RuntimeError:
                raise
            else:
                pass
