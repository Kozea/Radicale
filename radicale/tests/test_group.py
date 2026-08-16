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

import base64
import logging
import os
import sys

import pytest

import radicale
from radicale.tests import BaseTest
from radicale.tests.helpers import get_file_content


class TestBaseGroupRequests(BaseTest):
    """Tests basic requests with group lookup."""
    def setup_method(self) -> None:
        BaseTest.setup_method(self)
        self.htpasswd_file_path = os.path.join(self.colpath, ".htpasswd")
        self.htgroup_file_path = os.path.join(self.colpath, ".htgroup")
        htpasswd = ["owner:ownerpw",
                    "user1:user1pw",
                    "user2:user2pw",
                    ]
        htgroup = ["group1:user1",
                   "group2:user2",
                   "admins:owner",
                   ]
        htpasswd_content = "\n".join(htpasswd)
        htgroup_content = "\n".join(htgroup)
        with open(self.htpasswd_file_path, "w") as f:
            f.write(htpasswd_content)
        with open(self.htgroup_file_path, "w") as f:
            f.write(htgroup_content)
        self.rights_file_path = os.path.join(self.colpath, "rights")
        with open(self.rights_file_path, "w") as f:
            f.write("""\
# let user create its own base folder
[principal]
user: .+
collection: {user}
permissions: RW

# let user create its own collections
[collections]
user: .+
collection: {user}/[^/]+
permissions: rw

[calendarsWriter]
groups: admins
collection: GROUPS/[^/]+
permissions: rw

[calendarsReader]
user: .+
collection: GROUPS/[^/]+
permissions: r

[calendarsWriterCustom]
groups: admins
collection: MYGROUPS/[^/]+
permissions: rw

[calendarsReaderCustom]
user: .+
collection: MYGROUPS/[^/]+
permissions: r
""")

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

    @pytest.mark.skipif(sys.platform == "darwin" or sys.platform == 'win32', reason="not supported on MacOS or Windows")
    def test_incompatible_group_from_auth(self) -> None:
        for auth_type in ["dovecot", "imap", "remote_user", "http_remote_user", "htpasswd", "oauth2"]:
            logging.info("\n*** test: auth_type=%r, group_type=%r", "dovecot", auth_type)
            try:
                self.configure(
                        {"auth": {
                            "type": auth_type,
                            "oauth2_token": "dummy",
                            },
                         "group": {"type": "from_auth"}
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
                         "group": {"type": "from_auth"}
                         })
            except RuntimeError:
                raise
            else:
                pass

    def test_static_group_collection_discovery_by_user_group_missing_base_folder(self) -> None:
        """static group collection discovery by user group (base64 encoded) where base folder is missing."""
        self.configure({"auth": {"type": "htpasswd",
                                 "htpasswd_filename": self.htpasswd_file_path,
                                 "htpasswd_encryption": "plain"},
                        "group": {"type": "htgroup",
                                  "htgroup_filename": self.htgroup_file_path},
                        "logging": {"request_header_on_debug": "False",
                                    "response_content_on_debug": "True",
                                    "request_content_on_debug": "True"},
                        "rights": {"type": "from_file",
                                   "file": self.rights_file_path,
                                   }})

        logging.info("\n*** prepare GROUPS folder")

        path_static_group1 = "/GROUPS/" + base64.b64encode("group1".encode('utf-8')).decode('ascii') + "/"

        logging.info("\n*** prepare user folder")
        path_user1 = "/user1/calendarU1.ics/"
        self.mkcalendar(path_user1, login="user1:user1pw")

        # verify PROPFIND as user1 in list
        logging.info("\n*** PROPFIND collection DEPTH=1 user1")
        _, responses = self.propfind("/user1/", """\
<?xml version="1.0" encoding="utf-8"?>
<propfind xmlns="DAV:">
<calendar-home-set xmlns="urn:ietf:params:xml:ns:caldav" />
</propfind>""", login="user1:user1pw", HTTP_DEPTH="1")
        assert path_user1 in responses
        assert path_static_group1 not in responses

    def test_static_group_collection_discovery_by_user_group_success(self) -> None:
        """static group collection discovery by user group (base64 encoded)."""
        self.configure({"auth": {"type": "htpasswd",
                                 "htpasswd_filename": self.htpasswd_file_path,
                                 "htpasswd_encryption": "plain"},
                        "group": {"type": "htgroup",
                                  "htgroup_filename": self.htgroup_file_path},
                        "logging": {"request_header_on_debug": "False",
                                    "response_content_on_debug": "True",
                                    "request_content_on_debug": "True"},
                        "rights": {"type": "from_file",
                                   "file": self.rights_file_path,
                                   }})

        logging.info("\n*** prepare GROUPS folder")
        path_static_group1 = "/GROUPS/" + base64.b64encode("group1".encode('utf-8')).decode('ascii') + "/"
        self.mkcalendar(path_static_group1, login="owner:ownerpw", check=409)

        # create GROUPS folder
        os.mkdir(os.path.join(self.colpath, "collection-root", "GROUPS"))

        # try again
        self.mkcalendar(path_static_group1, login="owner:ownerpw")

        logging.info("\n*** prepare user folder")
        path_user1 = "/user1/calendarU1.ics/"
        self.mkcalendar(path_user1, login="user1:user1pw")

        # try upload item as owner -> ok (w permission defined)
        logging.info("\n*** PUT to path as owner -> 201")
        event = get_file_content("event1.ics")
        self.put(path_static_group1, event, login="owner:ownerpw")

        # verify PROPFIND as user1 in list
        logging.info("\n*** PROPFIND collection DEPTH=1 user1")
        _, responses = self.propfind("/user1/", """\
<?xml version="1.0" encoding="utf-8"?>
<propfind xmlns="DAV:">
<calendar-home-set xmlns="urn:ietf:params:xml:ns:caldav" />
</propfind>""", login="user1:user1pw", HTTP_DEPTH="1")
        assert path_user1 in responses
        assert path_static_group1 in responses

        # try upload item as user1 -> fail (w permission missing)
        logging.info("\n*** PUT to group collection as user1 -> 403")
        event = get_file_content("event1.ics")
        self.put(path_static_group1, event, login="user1:user1pw", check=403)

        # get item as user1 -> success
        logging.info("\n*** GET from group collection as user1")
        self.get(path_static_group1 + "event1.ics", login="user1:user1pw")

    def test_static_group_collection_discovery_by_user_group_custom_folder(self) -> None:
        """static group collection discovery by user group (base64 encoded)."""
        self.configure({"auth": {"type": "htpasswd",
                                 "htpasswd_filename": self.htpasswd_file_path,
                                 "htpasswd_encryption": "plain"},
                        "group": {"type": "htgroup",
                                  "htgroup_filename": self.htgroup_file_path,
                                  "group_collections_folder": "MYGROUPS",
                                  },
                        "logging": {"request_header_on_debug": "False",
                                    "response_content_on_debug": "True",
                                    "request_content_on_debug": "True"},
                        "rights": {"type": "from_file",
                                   "file": self.rights_file_path,
                                   }})

        logging.info("\n*** prepare MYGROUPS folder")
        path_static_group1 = "/MYGROUPS/" + base64.b64encode("group1".encode('utf-8')).decode('ascii') + "/"
        self.mkcalendar(path_static_group1, login="owner:ownerpw", check=409)

        # create GROUPS folder
        os.mkdir(os.path.join(self.colpath, "collection-root", "MYGROUPS"))

        # try again
        self.mkcalendar(path_static_group1, login="owner:ownerpw")

        logging.info("\n*** prepare user folder")
        path_user1 = "/user1/calendarU1.ics/"
        self.mkcalendar(path_user1, login="user1:user1pw")

        # try upload item as owner -> ok (w permission defined)
        logging.info("\n*** PUT to path as owner -> 201")
        event = get_file_content("event1.ics")
        self.put(path_static_group1, event, login="owner:ownerpw")

        # verify PROPFIND as user1 in list
        logging.info("\n*** PROPFIND collection DEPTH=1 user1")
        _, responses = self.propfind("/user1/", """\
<?xml version="1.0" encoding="utf-8"?>
<propfind xmlns="DAV:">
<calendar-home-set xmlns="urn:ietf:params:xml:ns:caldav" />
</propfind>""", login="user1:user1pw", HTTP_DEPTH="1")
        assert path_user1 in responses
        assert path_static_group1 in responses

        # try upload item as user1 -> fail (w permission missing)
        logging.info("\n*** PUT to group collection as user1 -> 403")
        event = get_file_content("event1.ics")
        self.put(path_static_group1, event, login="user1:user1pw", check=403)

        # get item as user1 -> success
        logging.info("\n*** GET from group collection as user1")
        self.get(path_static_group1 + "event1.ics", login="user1:user1pw")

    def test_static_group_collection_discovery_by_user_group_disabled_folder(self) -> None:
        """static group collection discovery by user group (base64 encoded)."""
        self.configure({"auth": {"type": "htpasswd",
                                 "htpasswd_filename": self.htpasswd_file_path,
                                 "htpasswd_encryption": "plain"},
                        "group": {"type": "htgroup",
                                  "htgroup_filename": self.htgroup_file_path,
                                  "group_collections_folder": "",
                                  },
                        "logging": {"request_header_on_debug": "False",
                                    "response_content_on_debug": "True",
                                    "request_content_on_debug": "True"},
                        "rights": {"type": "from_file",
                                   "file": self.rights_file_path,
                                   }})

        path_static_group1 = "/GROUPS/" + base64.b64encode("group1".encode('utf-8')).decode('ascii') + "/"

        logging.info("\n*** prepare user folder")
        path_user1 = "/user1/calendarU1.ics/"
        self.mkcalendar(path_user1, login="user1:user1pw")

        # verify PROPFIND as user1 in list
        logging.info("\n*** PROPFIND collection DEPTH=1 user1")
        _, responses = self.propfind("/user1/", """\
<?xml version="1.0" encoding="utf-8"?>
<propfind xmlns="DAV:">
<calendar-home-set xmlns="urn:ietf:params:xml:ns:caldav" />
</propfind>""", login="user1:user1pw", HTTP_DEPTH="1")
        assert path_user1 in responses
        assert path_static_group1 not in responses

        # get item as user1 -> not found
        logging.info("\n*** GET from group collection as user1")
        self.get(path_static_group1 + "event1.ics", login="user1:user1pw", check=404)
