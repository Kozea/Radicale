# This file is part of Radicale - CalDAV and CardDAV server
# Copyright © 2026-2026 oliviasculley <olivia@sculley.dev>
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

"""An LDAP reader setup error is reported instead of crashing."""

import logging
from unittest.mock import patch

import pytest

from radicale.tests import BaseTest


class TestLdapReaderSetup(BaseTest):

    def test_ldap3_reader_setup_error_is_unable_to_read(self, caplog):
        """Server or TLS setup failed before a reader connection existed."""
        ldap3 = pytest.importorskip("ldap3")
        from radicale.auth import ldap as ldap_auth

        caplog.set_level(logging.DEBUG)
        ldap_auth.Auth._ldap_attributes = []
        opened = []
        try:
            self.configure({"auth": {
                "type": "ldap",
                "delay": "0",
                "ldap_uri": "ldap://ldap.example",
                "ldap_base": "ou=people,dc=example,dc=com",
                "ldap_reader_dn": "cn=reader,dc=example,dc=com",
                "ldap_secret": "reader-secret",
                "ldap_filter": "(uid={0})",
            }})

            def refuse_connection(*_args, **_kwargs):
                opened.append(True)
                raise AssertionError("reader connection opened")

            def server_boom(*_args, **_kwargs):
                raise ValueError("server boom")

            with patch.object(ldap3, "Server", server_boom), \
                    patch.object(ldap3, "Connection", refuse_connection):
                with pytest.raises(RuntimeError, match="Unable to read from LDAP server") as caught:
                    self.application._auth._login_ext_with_groups("owner", "secret", None)
            assert str(caught.value) == "Unable to read from LDAP server"
            assert isinstance(caught.value.__cause__, ValueError)
            assert str(caught.value.__cause__) == "server boom"
            assert opened == []
            assert "server boom" in caplog.text

            caplog.clear()
            opened.clear()
            ldap_auth.Auth._ldap_attributes = []
            self.configure({"auth": {
                "type": "ldap",
                "delay": "0",
                "ldap_uri": "ldap://ldap.example",
                "ldap_base": "ou=people,dc=example,dc=com",
                "ldap_reader_dn": "cn=reader,dc=example,dc=com",
                "ldap_secret": "reader-secret",
                "ldap_filter": "(uid={0})",
                "ldap_security": "starttls",
            }})

            def tls_boom(*_args, **_kwargs):
                raise ValueError("tls setup boom")

            with patch.object(ldap3, "Tls", tls_boom), \
                    patch.object(ldap3, "Server", server_boom), \
                    patch.object(ldap3, "Connection", refuse_connection):
                with pytest.raises(RuntimeError, match="Unable to read from LDAP server") as caught:
                    self.application._auth._login_ext_with_groups("owner", "secret", None)
            assert str(caught.value) == "Unable to read from LDAP server"
            assert str(caught.value.__cause__) == "tls setup boom"
            assert opened == []
            assert "tls setup boom" in caplog.text
            assert "server boom" not in caplog.text
        finally:
            ldap_auth.Auth._ldap_attributes = []
