# This file is part of Radicale - CalDAV and CardDAV server
# Copyright © 2012-2016 Jean-Marc Martins
# Copyright © 2012-2017 Guillaume Ayoub
# Copyright © 2017-2022 Unrud <unrud@outlook.com>
# Copyright © 2024-2025 Peter Bieringer <pb@bieringer.de>
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
Radicale tests with simple requests and authentication.

"""

import base64
import logging
import os
import sys
from typing import Iterable, Tuple, Union

import pytest

from radicale import xmlutils
from radicale.tests import BaseTest


class TestBaseAuthRequests(BaseTest):
    """Tests basic requests with auth.

    We should setup auth for each type before creating the Application object.

    """

    # test for available bcrypt module
    try:
        import bcrypt
    except ImportError:
        has_bcrypt = 0
    else:
        has_bcrypt = 1

    # test for available argon2 module
    try:
        import argon2
        from passlib.hash import argon2  # noqa: F811
    except ImportError:
        has_argon2 = 0
    else:
        has_argon2 = 1

    def _test_htpasswd(self, htpasswd_encryption: str, htpasswd_content: str,
                       test_matrix: Union[str, Iterable[Tuple[str, str, bool]]]
                       = "ascii") -> None:
        """Test htpasswd authentication with user "tmp" and password "bepo" for
           ``test_matrix`` "ascii" or user "😀" and password "🔑" for
           ``test_matrix`` "unicode"."""
        htpasswd_file_path = os.path.join(self.colpath, ".htpasswd")
        encoding: str = self.configuration.get("encoding", "stock")
        with open(htpasswd_file_path, "w", encoding=encoding) as f:
            f.write(htpasswd_content)
        self.configure({"auth": {"type": "htpasswd",
                                 "htpasswd_filename": htpasswd_file_path,
                                 "htpasswd_encryption": htpasswd_encryption}})
        if test_matrix == "ascii":
            test_matrix = (("tmp", "bepo", True), ("tmp", "tmp", False),
                           ("tmp", "", False), ("unk", "unk", False),
                           ("unk", "", False), ("", "", False))
        elif test_matrix == "unicode":
            test_matrix = (("😀", "🔑", True), ("😀", "🌹", False),
                           ("😁", "🔑", False), ("😀", "", False),
                           ("", "🔑", False), ("", "", False))
        elif isinstance(test_matrix, str):
            raise ValueError("Unknown test matrix %r" % test_matrix)
        for user, password, valid in test_matrix:
            self.propfind("/", check=207 if valid else 401,
                          login="%s:%s" % (user, password))

    def test_htpasswd_plain(self) -> None:
        self._test_htpasswd("plain", "tmp:bepo")

    def test_htpasswd_plain_autodetect(self) -> None:
        self._test_htpasswd("autodetect", "tmp:bepo")

    def test_htpasswd_plain_password_split(self) -> None:
        self._test_htpasswd("plain", "tmp:be:po", (
            ("tmp", "be:po", True), ("tmp", "bepo", False)))

    def test_htpasswd_plain_unicode(self) -> None:
        self._test_htpasswd("plain", "😀:🔑", "unicode")

    def test_htpasswd_md5(self) -> None:
        self._test_htpasswd("md5", "tmp:$apr1$BI7VKCZh$GKW4vq2hqDINMr8uv7lDY/")

    def test_htpasswd_md5_autodetect(self) -> None:
        self._test_htpasswd("autodetect", "tmp:$apr1$BI7VKCZh$GKW4vq2hqDINMr8uv7lDY/")

    def test_htpasswd_md5_unicode(self):
        self._test_htpasswd(
            "md5", "😀:$apr1$w4ev89r1$29xO8EvJmS2HEAadQ5qy11", "unicode")

    def test_htpasswd_sha256(self) -> None:
        self._test_htpasswd("sha256", "tmp:$5$i4Ni4TQq6L5FKss5$ilpTjkmnxkwZeV35GB9cYSsDXTALBn6KtWRJAzNlCL/")

    def test_htpasswd_sha256_autodetect(self) -> None:
        self._test_htpasswd("autodetect", "tmp:$5$i4Ni4TQq6L5FKss5$ilpTjkmnxkwZeV35GB9cYSsDXTALBn6KtWRJAzNlCL/")

    def test_htpasswd_sha512(self) -> None:
        self._test_htpasswd("sha512", "tmp:$6$3Qhl8r6FLagYdHYa$UCH9yXCed4A.J9FQsFPYAOXImzZUMfvLa0lwcWOxWYLOF5sE/lF99auQ4jKvHY2vijxmefl7G6kMqZ8JPdhIJ/")

    def test_htpasswd_sha512_autodetect(self) -> None:
        self._test_htpasswd("autodetect", "tmp:$6$3Qhl8r6FLagYdHYa$UCH9yXCed4A.J9FQsFPYAOXImzZUMfvLa0lwcWOxWYLOF5sE/lF99auQ4jKvHY2vijxmefl7G6kMqZ8JPdhIJ/")

    @pytest.mark.skipif(has_bcrypt == 0, reason="No bcrypt module installed")
    def test_htpasswd_bcrypt_2a(self) -> None:
        self._test_htpasswd("bcrypt", "tmp:$2a$10$Mj4A9vMecAp/K7.0fMKoVOk1SjgR.RBhl06a52nvzXhxlT3HB7Reu")

    @pytest.mark.skipif(has_bcrypt == 0, reason="No bcrypt module installed")
    def test_htpasswd_bcrypt_2a_autodetect(self) -> None:
        self._test_htpasswd("autodetect", "tmp:$2a$10$Mj4A9vMecAp/K7.0fMKoVOk1SjgR.RBhl06a52nvzXhxlT3HB7Reu")

    @pytest.mark.skipif(has_bcrypt == 0, reason="No bcrypt module installed")
    def test_htpasswd_bcrypt_2b(self) -> None:
        self._test_htpasswd("bcrypt", "tmp:$2b$12$7a4z/fdmXlBIfkz0smvzW.1Nds8wpgC/bo2DVOb4OSQKWCDL1A1wu")

    @pytest.mark.skipif(has_bcrypt == 0, reason="No bcrypt module installed")
    def test_htpasswd_bcrypt_2b_autodetect(self) -> None:
        self._test_htpasswd("autodetect", "tmp:$2b$12$7a4z/fdmXlBIfkz0smvzW.1Nds8wpgC/bo2DVOb4OSQKWCDL1A1wu")

    @pytest.mark.skipif(has_bcrypt == 0, reason="No bcrypt module installed")
    def test_htpasswd_bcrypt_2y(self) -> None:
        self._test_htpasswd("bcrypt", "tmp:$2y$05$oD7hbiQFQlvCM7zoalo/T.MssV3VNTRI3w5KDnj8NTUKJNWfVpvRq")

    @pytest.mark.skipif(has_bcrypt == 0, reason="No bcrypt module installed")
    def test_htpasswd_bcrypt_2y_autodetect(self) -> None:
        self._test_htpasswd("autodetect", "tmp:$2y$05$oD7hbiQFQlvCM7zoalo/T.MssV3VNTRI3w5KDnj8NTUKJNWfVpvRq")

    @pytest.mark.skipif(has_bcrypt == 0, reason="No bcrypt module installed")
    def test_htpasswd_bcrypt_C10(self) -> None:
        self._test_htpasswd("bcrypt", "tmp:$2y$10$bZsWq06ECzxqi7RmulQvC.T1YHUnLW2E3jn.MU2pvVTGn1dfORt2a")

    @pytest.mark.skipif(has_bcrypt == 0, reason="No bcrypt module installed")
    def test_htpasswd_bcrypt_C10_autodetect(self) -> None:
        self._test_htpasswd("bcrypt", "tmp:$2y$10$bZsWq06ECzxqi7RmulQvC.T1YHUnLW2E3jn.MU2pvVTGn1dfORt2a")

    @pytest.mark.skipif(has_bcrypt == 0, reason="No bcrypt module installed")
    def test_htpasswd_bcrypt_unicode(self) -> None:
        self._test_htpasswd("bcrypt", "😀:$2y$10$Oyz5aHV4MD9eQJbk6GPemOs4T6edK6U9Sqlzr.W1mMVCS8wJUftnW", "unicode")

    @pytest.mark.skipif(has_argon2 == 0, reason="No argon2 module installed")
    def test_htpasswd_argon2_i(self) -> None:
        self._test_htpasswd("argon2", "tmp:$argon2i$v=19$m=65536,t=3,p=4$NgZg7F1rzRkDoNSaMwag9A$qmsvMKEn5zOXHm8e3O5fKzzcRo0UESwaDr/cETe5YPI")

    @pytest.mark.skipif(has_argon2 == 0, reason="No argon2 module installed")
    def test_htpasswd_argon2_d(self) -> None:
        self._test_htpasswd("argon2", "tmp:$argon2d$v=19$m=65536,t=3,p=4$ufe+txYiJKR0zlkLwVirVQ$MjGqRyVLes38hA6CEOkloMcTYCuLjxCKgIjtfYZ3iSM")

    @pytest.mark.skipif(has_argon2 == 0, reason="No argon2 module installed")
    def test_htpasswd_argon2_id(self) -> None:
        self._test_htpasswd("argon2", "tmp:$argon2id$v=19$m=65536,t=3,p=4$t7bWuneOkdIa45xTqjXGmA$ORnRJyz9kHogJs6bDgZrTBPlzi4+p023PSEABb3xX1g")

    def test_htpasswd_multi(self) -> None:
        self._test_htpasswd("plain", "ign:ign\ntmp:bepo")

    # login cache successful
    def test_htpasswd_login_cache_successful_plain(self, caplog) -> None:
        caplog.set_level(logging.INFO)
        self.configure({"auth": {"cache_logins": "True"}})
        self._test_htpasswd("plain", "tmp:bepo", (("tmp", "bepo", True), ("tmp", "bepo", True)))
        htpasswd_found = False
        htpasswd_cached_found = False
        for line in caplog.messages:
            if line == "Successful login: 'tmp' (htpasswd)":
                htpasswd_found = True
            elif line == "Successful login: 'tmp' (htpasswd / cached)":
                htpasswd_cached_found = True
        if (htpasswd_found is False) or (htpasswd_cached_found is False):
            raise ValueError("Logging misses expected log lines")

    # login cache failed
    def test_htpasswd_login_cache_failed_plain(self, caplog) -> None:
        caplog.set_level(logging.INFO)
        self.configure({"auth": {"cache_logins": "True"}})
        self._test_htpasswd("plain", "tmp:bepo", (("tmp", "bepo1", False), ("tmp", "bepo1", False)))
        htpasswd_found = False
        htpasswd_cached_found = False
        for line in caplog.messages:
            if line == "Failed login attempt from unknown: 'tmp' (htpasswd)":
                htpasswd_found = True
            elif line == "Failed login attempt from unknown: 'tmp' (htpasswd / cached)":
                htpasswd_cached_found = True
        if (htpasswd_found is False) or (htpasswd_cached_found is False):
            raise ValueError("Logging misses expected log lines")

    # htpasswd file cache
    def test_htpasswd_file_cache(self, caplog) -> None:
        self.configure({"auth": {"htpasswd_cache": "True"}})
        self._test_htpasswd("plain", "tmp:bepo")

    # detection of broken htpasswd file entries
    def test_htpasswd_broken(self) -> None:
        for userpass in ["tmp:", ":tmp"]:
            try:
                self._test_htpasswd("plain", userpass)
            except RuntimeError:
                pass
            else:
                raise

    @pytest.mark.skipif(sys.platform == "win32", reason="leading and trailing "
                        "whitespaces not allowed in file names")
    def test_htpasswd_whitespace_user(self) -> None:
        for user in (" tmp", "tmp ", " tmp "):
            self._test_htpasswd("plain", "%s:bepo" % user, (
                (user, "bepo", True), ("tmp", "bepo", False)))

    def test_htpasswd_whitespace_password(self) -> None:
        for password in (" bepo", "bepo ", " bepo "):
            self._test_htpasswd("plain", "tmp:%s" % password, (
                ("tmp", password, True), ("tmp", "bepo", False)))

    def test_htpasswd_comment(self) -> None:
        self._test_htpasswd("plain", "#comment\n #comment\n \ntmp:bepo\n\n")

    def test_htpasswd_lc_username(self) -> None:
        self.configure({"auth": {"lc_username": "True"}})
        self._test_htpasswd("plain", "tmp:bepo", (
            ("tmp", "bepo", True), ("TMP", "bepo", True), ("tmp1", "bepo", False)))

    def test_htpasswd_uc_username(self) -> None:
        self.configure({"auth": {"uc_username": "True"}})
        self._test_htpasswd("plain", "TMP:bepo", (
            ("tmp", "bepo", True), ("TMP", "bepo", True), ("TMP1", "bepo", False)))

    def test_htpasswd_strip_domain(self) -> None:
        self.configure({"auth": {"strip_domain": "True"}})
        self._test_htpasswd("plain", "tmp:bepo", (
            ("tmp", "bepo", True), ("tmp@domain.example", "bepo", True), ("tmp1", "bepo", False)))

    def test_remote_user(self) -> None:
        self.configure({"auth": {"type": "remote_user"}})
        _, responses = self.propfind("/", """\
<?xml version="1.0" encoding="utf-8"?>
<propfind xmlns="DAV:">
    <prop>
        <current-user-principal />
    </prop>
</propfind>""", REMOTE_USER="test")
        assert responses is not None
        response = responses["/"]
        assert not isinstance(response, int)
        status, prop = response["D:current-user-principal"]
        assert status == 200
        href_element = prop.find(xmlutils.make_clark("D:href"))
        assert href_element is not None and href_element.text == "/test/"

    def test_http_x_remote_user(self) -> None:
        self.configure({"auth": {"type": "http_x_remote_user"}})
        _, responses = self.propfind("/", """\
<?xml version="1.0" encoding="utf-8"?>
<propfind xmlns="DAV:">
    <prop>
        <current-user-principal />
    </prop>
</propfind>""", HTTP_X_REMOTE_USER="test")
        assert responses is not None
        response = responses["/"]
        assert not isinstance(response, int)
        status, prop = response["D:current-user-principal"]
        assert status == 200
        href_element = prop.find(xmlutils.make_clark("D:href"))
        assert href_element is not None and href_element.text == "/test/"

    @pytest.mark.skipif(sys.platform == 'win32', reason="Not supported on Windows")
    def _test_dovecot(
            self, user, password, expected_status, expected_rip=None,
            response=b'FAIL\t1', mech=[b'PLAIN'], broken=None,
            extra_config=None, extra_env=None):
        import socket
        from unittest.mock import DEFAULT, patch

        if extra_env is None:
            extra_env = {}
        if extra_config is None:
            extra_config = {}

        config = {"auth": {"type": "dovecot",
                           "dovecot_socket": "./dovecot.sock"}}
        for toplvl, entries in extra_config.items():
            for key, val in entries.items():
                config[toplvl][key] = val
        self.configure(config)

        if broken is None:
            broken = []

        handshake = b''
        if "version" not in broken:
            handshake += b'VERSION\t'
            if "incompatible" in broken:
                handshake += b'2'
            else:
                handshake += b'1'
            handshake += b'\t2\n'

        if "mech" not in broken:
            handshake += b'MECH\t%b\n' % b' '.join(mech)

        if "duplicate" in broken:
            handshake += b'VERSION\t1\t2\n'

        if "done" not in broken:
            handshake += b'DONE\n'

        sent_rip = None

        def record_sent_data(s, data, flags=None):
            nonlocal sent_rip
            if b'\trip=' in data:
                sent_rip = data.split(b'\trip=')[1].split(b'\t')[0]
            return len(data)

        with patch.multiple(
                'socket.socket',
                connect=DEFAULT,
                send=record_sent_data,
                recv=DEFAULT
                ) as mock_socket:
            if "socket" in broken:
                mock_socket["connect"].side_effect = socket.error(
                        "Testing error with the socket"
                )
            mock_socket["recv"].side_effect = [handshake, response]
            status, _, answer = self.request(
                "PROPFIND", "/",
                HTTP_AUTHORIZATION="Basic %s" % base64.b64encode(
                    ("%s:%s" % (user, password)).encode()).decode(),
                **extra_env)
            assert sent_rip == expected_rip
            assert status == expected_status

    @pytest.mark.skipif(sys.platform == 'win32', reason="Not supported on Windows")
    def test_dovecot_no_user(self):
        self._test_dovecot("", "", 401)

    @pytest.mark.skipif(sys.platform == 'win32', reason="Not supported on Windows")
    def test_dovecot_no_password(self):
        self._test_dovecot("user", "", 401)

    @pytest.mark.skipif(sys.platform == 'win32', reason="Not supported on Windows")
    def test_dovecot_broken_handshake_no_version(self):
        self._test_dovecot("user", "password", 401, broken=["version"])

    @pytest.mark.skipif(sys.platform == 'win32', reason="Not supported on Windows")
    def test_dovecot_broken_handshake_incompatible(self):
        self._test_dovecot("user", "password", 401, broken=["incompatible"])

    @pytest.mark.skipif(sys.platform == 'win32', reason="Not supported on Windows")
    def test_dovecot_broken_handshake_duplicate(self):
        self._test_dovecot(
                "user", "password", 207, response=b'OK\t1',
                broken=["duplicate"]
        )

    @pytest.mark.skipif(sys.platform == 'win32', reason="Not supported on Windows")
    def test_dovecot_broken_handshake_no_mech(self):
        self._test_dovecot("user", "password", 401, broken=["mech"])

    @pytest.mark.skipif(sys.platform == 'win32', reason="Not supported on Windows")
    def test_dovecot_broken_handshake_unsupported_mech(self):
        self._test_dovecot("user", "password", 401, mech=[b'ONE', b'TWO'])

    @pytest.mark.skipif(sys.platform == 'win32', reason="Not supported on Windows")
    def test_dovecot_broken_handshake_no_done(self):
        self._test_dovecot("user", "password", 401, broken=["done"])

    @pytest.mark.skipif(sys.platform == 'win32', reason="Not supported on Windows")
    def test_dovecot_broken_socket(self):
        self._test_dovecot("user", "password", 401, broken=["socket"])

    @pytest.mark.skipif(sys.platform == 'win32', reason="Not supported on Windows")
    def test_dovecot_auth_good1(self):
        self._test_dovecot("user", "password", 207, response=b'OK\t1')

    @pytest.mark.skipif(sys.platform == 'win32', reason="Not supported on Windows")
    def test_dovecot_auth_good2(self):
        self._test_dovecot(
                "user", "password", 207, response=b'OK\t1',
                mech=[b'PLAIN\nEXTRA\tTERM']
        )

        self._test_dovecot("user", "password", 207, response=b'OK\t1')

    @pytest.mark.skipif(sys.platform == 'win32', reason="Not supported on Windows")
    def test_dovecot_auth_bad1(self):
        self._test_dovecot("user", "password", 401, response=b'FAIL\t1')

    @pytest.mark.skipif(sys.platform == 'win32', reason="Not supported on Windows")
    def test_dovecot_auth_bad2(self):
        self._test_dovecot("user", "password", 401, response=b'CONT\t1')

    @pytest.mark.skipif(sys.platform == 'win32', reason="Not supported on Windows")
    def test_dovecot_auth_id_mismatch(self):
        self._test_dovecot("user", "password", 401, response=b'OK\t2')

    @pytest.mark.skipif(sys.platform == 'win32', reason="Not supported on Windows")
    def test_dovecot_remote_addr(self):
        self._test_dovecot("user", "password", 401, expected_rip=b'172.17.16.15',
                           extra_env={
                               'REMOTE_ADDR': '172.17.16.15',
                               'HTTP_X_REMOTE_ADDR': '127.0.0.1',
                           })

    @pytest.mark.skipif(sys.platform == 'win32', reason="Not supported on Windows")
    def test_dovecot_x_remote_addr(self):
        self._test_dovecot("user", "password", 401, expected_rip=b'172.17.16.15',
                           extra_env={
                               'REMOTE_ADDR': '127.0.0.1',
                               'HTTP_X_REMOTE_ADDR': '172.17.16.15',
                           },
                           extra_config={
                               'auth': {"dovecot_rip_x_remote_addr": "True"},
                           })

    @pytest.mark.skipif(sys.platform == 'win32', reason="Not supported on Windows")
    def test_dovecot_x_remote_addr_whitespace(self):
        self._test_dovecot("user", "password", 401, expected_rip=b'172.17.16.15rip=127.0.0.1',
                           extra_env={
                               'REMOTE_ADDR': '127.0.0.1',
                               'HTTP_X_REMOTE_ADDR': '172.17.16.15\trip=127.0.0.1',
                           },
                           extra_config={
                               'auth': {"dovecot_rip_x_remote_addr": "True"},
                           })

    def test_custom(self) -> None:
        """Custom authentication."""
        self.configure({"auth": {"type": "radicale.tests.custom.auth"}})
        self.propfind("/tmp/", login="tmp:")

    def test_none(self) -> None:
        self.configure({"auth": {"type": "none"}})
        self.propfind("/tmp/", login="tmp:")

    def test_denyall(self) -> None:
        self.configure({"auth": {"type": "denyall"}})
        self.propfind("/tmp/", login="tmp:", check=401)
