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

"""Mocked LDAP, IMAP, OAuth2 and PAM authentication servers.

Covers Kozea/Radicale issue 2259.
"""

import contextlib
import imaplib
import logging
import os
import ssl
import sys
import types
from functools import partial
from typing import Any, Iterator, Optional, Union
from unittest.mock import patch
from urllib.parse import quote

import pytest

from radicale import xmlutils
from radicale.auth import ldap as ldap_auth
from radicale.tests import BaseTest

skip_ldap = False
try:
    import ldap3
except ModuleNotFoundError:
    skip_ldap = True
    pass

skip_pam = False
try:
    import pam
except ModuleNotFoundError:
    skip_pam = True
    pass


def _principal(test: BaseTest, login: str, check: int = 207) -> str:
    _, responses = test.propfind("/", """\
<?xml version="1.0" encoding="utf-8"?>
<propfind xmlns="DAV:">
    <prop>
        <current-user-principal />
    </prop>
</propfind>""", login=login, check=check)
    if check != 207:
        return ""
    response = responses["/"]
    assert not isinstance(response, int)
    status, prop = response["D:current-user-principal"]
    assert status == 200
    href = prop.find(xmlutils.make_clark("D:href"))
    assert href is not None and href.text
    return href.text


OWNER_DN = "uid=owner,ou=people,dc=example,dc=com"


class _MockLdap:
    """In-memory directory served by the ldap3 MOCK_SYNC strategy."""

    reader_dn = "cn=reader,dc=example,dc=com"
    reader_password = "reader-secret"

    def __init__(self, schema: Any = None) -> None:
        self.connection = ldap3.Connection
        self.server = ldap3.Server("mock", get_info=schema)
        self.servers: list = []
        self._seed = self.connection(self.server, client_strategy=ldap3.MOCK_SYNC)
        self.add(self.reader_dn, userPassword=self.reader_password)

    def add(self, dn: str, **attributes: Any) -> None:
        assert self._seed.strategy.add_entry(dn, attributes)

    def _server(self, uri: str, **kwargs: Any) -> Any:
        self.servers.append(kwargs)
        return self.server

    @contextlib.contextmanager
    def patch(self) -> Iterator[Any]:
        connection = partial(self.connection, client_strategy=ldap3.MOCK_SYNC)
        with patch.multiple(ldap3, Server=self._server, Connection=connection), \
                patch.object(self.connection, "start_tls", autospec=True) as start_tls:
            yield start_tls

    def patch_method(self, name: str, side_effect: Any) -> Any:
        return patch.object(self.connection, name, autospec=True, side_effect=side_effect)


def _raise_for_user(error: BaseException) -> Any:
    def side_effect(conn: Any, *args: Any, **kwargs: Any) -> None:
        if conn.user != _MockLdap.reader_dn:
            raise error
    return side_effect


class _Ldap2State:
    def __init__(self) -> None:
        self.reader_dn = "cn=reader,dc=example,dc=com"
        self.reader_password = "reader-secret"
        self.user_filter = "(cn={0})"
        self.group_members_attr = ""
        self.user_results: list = []
        self.group_results: list = []
        self.passwords: dict = {}
        self.duplicate = False
        self.search_error = False
        self.group_search_error = False
        self.connections: list = []


def _install_ldap2(state: _Ldap2State) -> types.ModuleType:
    ldap_mod: Any = types.ModuleType("ldap")
    filt: Any = types.ModuleType("ldap.filter")
    dn_mod: Any = types.ModuleType("ldap.dn")

    def escape(value: str) -> str:
        return (value.replace("\\", "\\5c").replace("(", "\\28")
                .replace(")", "\\29").replace("*", "\\2a"))

    def explode_dn(dn: Union[str, bytes], notypes: bool = True) -> list:
        if isinstance(dn, bytes) or dn == "BAD":
            raise Exception("bad dn")
        return [str(dn).split(",")[0].split("=", 1)[1]]

    class InvalidCredentials(Exception):
        pass

    class Conn:
        def __init__(self) -> None:
            self.protocol_version = None
            self.options: dict = {}
            self.started_tls = False
            self.unbound = False
            state.connections.append(self)

        def set_option(self, key: int, value: object) -> None:
            self.options[key] = value

        def start_tls_s(self) -> None:
            self.started_tls = True

        def simple_bind_s(self, dn: str, secret: str) -> None:
            if dn == state.reader_dn:
                if secret != state.reader_password:
                    raise Exception("reader bind failed")
                return
            if state.passwords.get(dn) != secret:
                raise InvalidCredentials("bad password")

        def search_s(self, base: str, scope: int, filterstr: str = "", attrlist: Optional[list] = None) -> list:
            if state.group_members_attr and ("(%s=" % state.group_members_attr) in filterstr:
                if state.group_search_error:
                    raise Exception("group search failed")
                return list(state.group_results)
            if state.search_error:
                raise Exception("search failed")
            results = []
            for login, entry in state.user_results:
                escaped = escape(login)
                if filterstr == state.user_filter.format(escaped):
                    results.append(entry)
            if state.duplicate and results:
                results.append(results[0])
            return results

        def unbind(self) -> None:
            self.unbound = True

    filt.escape_filter_chars = escape
    dn_mod.explode_dn = explode_dn
    ldap_mod.filter = filt
    ldap_mod.dn = dn_mod
    ldap_mod.VERSION3 = 3
    ldap_mod.OPT_REFERRALS = 0
    ldap_mod.SCOPE_SUBTREE = 2
    ldap_mod.OPT_X_TLS_NEVER = 0
    ldap_mod.OPT_X_TLS_ALLOW = 1
    ldap_mod.OPT_X_TLS_DEMAND = 2
    ldap_mod.OPT_X_TLS_REQUIRE_CERT = 10
    ldap_mod.OPT_X_TLS_CACERTFILE = 11
    ldap_mod.OPT_X_TLS_NEWCTX = 12
    ldap_mod.OPT_ON = 1
    ldap_mod.INVALID_CREDENTIALS = InvalidCredentials
    ldap_mod.initialize = lambda uri: Conn()
    return ldap_mod


class _ImapBox:
    current: "Optional[_ImapBox]" = None

    def __init__(self) -> None:
        self.connections: list = []
        self.capabilities: tuple = ("AUTH=PLAIN",)
        self.auth_error: Optional[BaseException] = None
        self.connect_error: Optional[BaseException] = None
        self.starttls_error: Optional[BaseException] = None
        self.logout_error: Optional[BaseException] = None


class _FakeIMAP:
    # The plugin catches imaplib.IMAP4.error. Patching IMAP4 must keep that class.
    error = imaplib.IMAP4.error

    def __init__(self, host: str, port: int, ssl_context: object = None) -> None:
        box = _ImapBox.current
        assert box is not None
        if box.connect_error is not None:
            raise box.connect_error
        self.host = host
        self.port = port
        self.ssl_context = ssl_context
        self.capabilities = box.capabilities
        self.auth_calls: list = []
        self.login_calls: list = []
        self.starttls_called = False
        self.logout_called = False
        self.secure = ssl_context is not None
        box.connections.append(self)

    def starttls(self, context: object) -> None:
        box = _ImapBox.current
        assert box is not None
        self.starttls_called = True
        self.ssl_context = context
        if box.starttls_error is not None:
            raise box.starttls_error

    def authenticate(self, mechanism: str, authobject: Any) -> None:
        box = _ImapBox.current
        assert box is not None
        payload = authobject(None)
        self.auth_calls.append((mechanism, payload))
        if box.auth_error is not None:
            raise box.auth_error

    def login(self, user: str, password: str) -> None:
        box = _ImapBox.current
        assert box is not None
        self.login_calls.append((user, password))
        if box.auth_error is not None:
            raise box.auth_error

    def logout(self) -> None:
        box = _ImapBox.current
        assert box is not None
        self.logout_called = True
        if box.logout_error is not None:
            raise box.logout_error


class TestAuthServers(BaseTest):
    """Authentication against mocked external servers."""

    def _configure_ldap3(self, **auth: str) -> None:
        # The backend appends to a class-level list. Give each server a fresh one.
        ldap_auth.Auth._ldap_attributes = []
        config = {
            "type": "ldap",
            "delay": "0.001",
            "ldap_uri": "ldap://ldap.example",
            "ldap_base": "ou=people,dc=example,dc=com",
            "ldap_reader_dn": _MockLdap.reader_dn,
            "ldap_secret": _MockLdap.reader_password,
            "ldap_filter": "(uid={0})",
        }
        config.update(auth)
        self.configure({"auth": config, "group": {"type": "from_auth"}})

    @pytest.mark.skipif(skip_ldap is True, reason="No LDAP module found")
    def test_ldap_rejects_bad_config(self) -> None:
        ldap_auth.Auth._ldap_attributes = []
        # configure() keeps earlier values, so each attempt resets the others.
        with pytest.raises(RuntimeError, match="ldap_security"):
            self.configure({"auth": {"type": "ldap", "ldap_security": "bogus",
                                     "ldap_ssl_verify_mode": "REQUIRED"}})
        with pytest.raises(RuntimeError, match="ldap_ssl_verify_mode"):
            self.configure({"auth": {"type": "ldap", "ldap_security": "none",
                                     "ldap_ssl_verify_mode": "SOMETIMES"}})
        with pytest.raises(RuntimeError, match="ldap_secret"):
            self.configure({"auth": {"type": "ldap", "ldap_security": "none",
                                     "ldap_ssl_verify_mode": "REQUIRED",
                                     "ldap_reader_dn": "cn=reader",
                                     "ldap_secret": "",
                                     "ldap_secret_file": ""}})
        secret = os.path.join(self.colpath, "empty.secret")
        with open(secret, "w", encoding="utf-8") as handle:
            handle.write("\n")
        # A non-empty configured secret must not hide a file that rstrips to empty.
        with pytest.raises(RuntimeError, match="ldap_secret"):
            self.configure({"auth": {"type": "ldap", "ldap_security": "none",
                                     "ldap_ssl_verify_mode": "REQUIRED",
                                     "ldap_reader_dn": "cn=reader",
                                     "ldap_secret": "not-from-file",
                                     "ldap_secret_file": secret}})

    def test_ldap_missing_module(self) -> None:
        removed = {}
        for name in ("ldap", "ldap.filter", "ldap.dn"):
            if name in sys.modules:
                removed[name] = sys.modules.pop(name)
        try:
            with patch.dict(sys.modules, {"ldap3": None}):
                with pytest.raises(ModuleNotFoundError, match="ldap3 or ldap"):
                    self.configure({"auth": {"type": "ldap"}})
        finally:
            sys.modules.update(removed)

    @pytest.mark.skipif(skip_ldap is True, reason="No LDAP module found")
    def test_ldap3_login_groups_user_attribute_and_escape(self) -> None:
        directory = _MockLdap()
        directory.add(OWNER_DN, uid="Owner", cn="owner", userPassword="secret", memberOf=[
            "cn=family,ou=groups,dc=example,dc=com",
            "cn=staff,ou=groups,dc=example,dc=com",
        ])
        directory.add("uid=ab,ou=people,dc=example,dc=com", uid="a(b)", cn="a(b)", userPassword="secret")
        self._configure_ldap3(ldap_user_attribute="cn", ldap_groups_attribute="memberOf")
        with directory.patch():
            assert _principal(self, "Owner:secret") == "/owner/"
            assert self.application._auth._groups == {"family", "staff"}
            assert self.application._rights._user_groups == {"family", "staff"}
            assert directory.servers[0] == {}
            assert _principal(self, "a(b):secret") == quote("/a(b)/")
            assert _principal(self, "a*:secret", check=401) == ""

    @pytest.mark.skipif(skip_ldap is True, reason="No LDAP module found")
    def test_ldap3_scalar_attributes_and_group_search(self) -> None:
        directory = _MockLdap(ldap3.OFFLINE_SLAPD_2_4)
        directory.add(OWNER_DN, objectClass="inetOrgPerson", uid="alias", cn="owner", sn="owner",
                      displayName="owner", employeeNumber="ignored", userPassword="secret")
        for name, member in (("family", OWNER_DN), ("other", "uid=other,ou=people,dc=example,dc=com")):
            directory.add("cn=%s,ou=groups,dc=example,dc=com" % name, objectClass="groupOfNames",
                          cn=name, member=member)
        self._configure_ldap3(
            ldap_user_attribute="displayName",
            ldap_groups_attribute="employeeNumber",
            ldap_group_members_attribute="member",
            ldap_group_filter="(objectClass=groupOfNames)",
            ldap_group_base="ou=groups,dc=example,dc=com")
        with directory.patch():
            assert _principal(self, "alias:secret") == "/owner/"
        # Member search replaces attribute groups.
        assert self.application._auth._groups == {"family"}

    @pytest.mark.skipif(skip_ldap is True, reason="No LDAP module found")
    def test_ldap3_group_search_failure_keeps_attribute_groups(self) -> None:
        directory = _MockLdap(ldap3.OFFLINE_SLAPD_2_4)
        directory.add(OWNER_DN, objectClass="inetOrgPerson", uid="owner", cn="owner", sn="owner",
                      employeeNumber="staff", userPassword="secret")
        search = directory.connection.search

        def failing_group_search(conn: Any, **kwargs: Any) -> Any:
            if "(member=" in kwargs["search_filter"]:
                raise RuntimeError("group lookup down")
            return search(conn, **kwargs)

        self._configure_ldap3(ldap_groups_attribute="employeeNumber",
                              ldap_group_members_attribute="member",
                              ldap_group_filter="(objectClass=groupOfNames)")
        with directory.patch(), directory.patch_method("search", failing_group_search):
            assert _principal(self, "owner:secret") == "/owner/"
        # A scalar value that is not a DN is kept whole.
        assert self.application._auth._groups == {"staff"}

    @pytest.mark.skipif(skip_ldap is True, reason="No LDAP module found")
    def test_ldap3_tls_modes_secret_file_and_quirks(self) -> None:
        secret = os.path.join(self.colpath, "ldap.secret")
        with open(secret, "w", encoding="utf-8") as handle:
            handle.write("reader-secret\n")
        ca_file = os.path.join(self.colpath, "ca.pem")
        with open(ca_file, "w", encoding="utf-8") as handle:
            handle.write("not a certificate\n")
        directory = _MockLdap()
        directory.add(OWNER_DN, uid="owner", userPassword="secret")

        self._configure_ldap3(ldap_secret="", ldap_secret_file=secret,
                              ldap_security="tls", ldap_ssl_ca_file=ca_file,
                              ldap_ignore_attribute_create_modify_timestamp="true")
        excluded = ldap3.utils.config._ATTRIBUTES_EXCLUDED_FROM_CHECK
        before = len(excluded)
        try:
            with directory.patch() as start_tls:
                assert _principal(self, "owner:secret") == "/owner/"
            assert directory.servers[-1]["use_ssl"] is True
            assert directory.servers[-1]["tls"].ca_certs_file == ca_file
            assert directory.servers[-1]["tls"].validate == ssl.CERT_REQUIRED
            assert not start_tls.called
            assert "createTimestamp" in excluded
            assert "modifyTimestamp" in excluded
        finally:
            del excluded[before:]

        self._configure_ldap3(ldap_security="starttls", ldap_ssl_verify_mode="OPTIONAL")
        with directory.patch() as start_tls:
            assert _principal(self, "owner:secret") == "/owner/"
        assert directory.servers[-1]["use_ssl"] is False
        assert directory.servers[-1]["tls"].validate == ssl.CERT_OPTIONAL
        assert [call.args[0].user for call in start_tls.call_args_list] == [_MockLdap.reader_dn, OWNER_DN]

        self._configure_ldap3(ldap_uri="ldaps://ldap.example", ldap_security="none",
                              ldap_ssl_verify_mode="NONE")
        with directory.patch():
            assert _principal(self, "owner:secret") == "/owner/"
        assert directory.servers[-1]["use_ssl"] is True

        self._configure_ldap3(ldap_uri="ldapi:///", ldap_ssl_verify_mode="REQUIRED")
        auth_any: Any = self.application._auth
        assert auth_any._ldap_ssl_verify_mode == "NONE"
        # No group base was configured, so the user base is used.
        assert auth_any._ldap_group_base == "ou=people,dc=example,dc=com"
        with directory.patch():
            assert _principal(self, "owner:secret") == "/owner/"

    @pytest.mark.skipif(skip_ldap is True, reason="No LDAP module found")
    def test_ldap3_login_failures(self, caplog) -> None:
        caplog.set_level(logging.ERROR)
        directory = _MockLdap()
        directory.add(OWNER_DN, uid="owner", userPassword="secret")
        directory.add("uid=twin,ou=people,dc=example,dc=com", uid="twin", userPassword="secret")
        directory.add("uid=twin,ou=staff,ou=people,dc=example,dc=com", uid="twin", userPassword="secret")
        self._configure_ldap3()
        with directory.patch() as start_tls:
            assert _principal(self, "twin:secret", check=401) == ""
            assert _principal(self, "missing:secret", check=401) == ""
            assert _principal(self, "owner:wrong", check=401) == ""

            with directory.patch_method("search", RuntimeError("search down")):
                assert _principal(self, "owner:secret", check=401) == ""

            with directory.patch_method("unbind", _raise_for_user(RuntimeError("unbind failed"))):
                assert _principal(self, "owner:secret", check=401) == ""

            with patch.object(ldap3, "Connection", side_effect=ldap3.core.exceptions.LDAPSocketOpenError("down")):
                _principal(self, "owner:secret", check=500)
            assert "Unable to reach LDAP server" in caplog.text

            self._configure_ldap3(ldap_security="starttls")
            start_tls.side_effect = _raise_for_user(ldap3.core.exceptions.LDAPStartTLSError("user tls"))
            assert _principal(self, "owner:secret", check=401) == ""

            # The reader connection raises on bind, so the "Unable to read" branch is unreachable.
            self._configure_ldap3(ldap_secret="wrong")
            _principal(self, "owner:secret", check=500)
            assert "invalidCredentials" in caplog.text

    def test_ldap2_login(self, caplog) -> None:
        caplog.set_level(logging.ERROR)
        state = _Ldap2State()
        user_dn = "uid=owner,ou=people,dc=example,dc=com"
        state.passwords[user_dn] = "secret"
        state.user_results = [("owner", (user_dn, {
            "cn": [b"owner"],
            "memberOf": [b"cn=family,ou=groups,dc=example,dc=com", "BAD"],
        }))]
        ldap_mod = _install_ldap2(state)
        ldap_auth.Auth._ldap_attributes = []
        modules = {"ldap3": None, "ldap": ldap_mod, "ldap.filter": ldap_mod.filter, "ldap.dn": ldap_mod.dn}
        with patch.dict(sys.modules, modules):
            self.configure({"auth": {
                "type": "ldap",
                "delay": "0.001",
                "ldap_uri": "ldap://ldap.example",
                "ldap_base": "ou=people,dc=example,dc=com",
                "ldap_reader_dn": state.reader_dn,
                "ldap_secret": state.reader_password,
                "ldap_security": "tls",
                "ldap_ssl_verify_mode": "OPTIONAL",
                "ldap_ssl_ca_file": os.path.join(self.colpath, "ca.pem"),
                "ldap_user_attribute": "cn",
                "ldap_groups_attribute": "memberOf",
            }})
        auth_any: Any = self.application._auth
        assert auth_any._ldap_module_version == 2
        assert _principal(self, "owner:secret") == "/owner/"
        # python-ldap stores groups on _ldap_groups. Bytes and unparseable DNs are kept as text.
        assert auth_any._ldap_groups == {"cn=family,ou=groups,dc=example,dc=com", "BAD"}
        conn = state.connections[-1]
        assert conn.started_tls is False
        assert conn.options[ldap_mod.OPT_X_TLS_REQUIRE_CERT] == ldap_mod.OPT_X_TLS_ALLOW
        assert conn.options[ldap_mod.OPT_X_TLS_CACERTFILE] == os.path.join(self.colpath, "ca.pem")
        assert conn.unbound is True

        state.connections.clear()
        with patch.dict(sys.modules, modules):
            self.configure({"auth": {
                "type": "ldap",
                "delay": "0.001",
                "ldap_reader_dn": state.reader_dn,
                "ldap_secret": state.reader_password,
                "ldap_security": "starttls",
                "ldap_group_members_attribute": "member",
                "ldap_group_filter": "(objectClass=groupOfNames)",
                "ldap_group_base": "ou=groups,dc=example,dc=com",
            }})
        state.group_members_attr = "member"
        state.group_results = [
            ("cn=family,ou=groups,dc=example,dc=com", {}),
            ("cn=staff,ou=groups,dc=example,dc=com", {}),
        ]
        assert _principal(self, "owner:secret") == "/owner/"
        assert state.connections[-1].started_tls is True
        assert getattr(self.application._auth, "_ldap_groups") == {"family", "staff"}

        assert _principal(self, "owner:wrong", check=401) == ""
        state.duplicate = True
        assert _principal(self, "owner:secret", check=401) == ""
        state.duplicate = False
        state.search_error = True
        _principal(self, "owner:secret", check=500)
        assert "Invalid LDAP configuration" in caplog.text
        state.search_error = False
        state.group_search_error = True
        _principal(self, "owner:secret", check=500)

    def _configure_imap(self, box: _ImapBox, **auth: str) -> None:
        _ImapBox.current = box
        config = {"type": "imap", "delay": "0.001", "imap_host": "imap.example"}
        config.update(auth)
        self.configure({"auth": config})

    def test_imap_plain_tls_and_login_mechanism(self) -> None:
        box = _ImapBox()
        self._configure_imap(box, imap_security="tls")
        with patch("radicale.auth.imap.imaplib.IMAP4_SSL", _FakeIMAP), \
                patch("radicale.auth.imap.imaplib.IMAP4", _FakeIMAP):
            assert _principal(self, "owner:secret") == "/owner/"
        conn = box.connections[-1]
        assert conn.secure is True
        assert conn.port == 993
        assert conn.auth_calls == [("PLAIN", b"owner\x00owner\x00secret")]
        assert conn.logout_called is True

        box = _ImapBox()
        box.capabilities = ("AUTH=LOGIN",)
        self._configure_imap(box, imap_security="starttls", imap_host="imap.example:1143",
                             imap_append_domain="example.com")
        with patch("radicale.auth.imap.imaplib.IMAP4_SSL", _FakeIMAP), \
                patch("radicale.auth.imap.imaplib.IMAP4", _FakeIMAP):
            assert _principal(self, "owner:secret") == "/owner/"
        conn = box.connections[-1]
        assert conn.secure is False
        assert conn.port == 1143
        assert conn.starttls_called is True
        assert conn.login_calls == [("owner@example.com", "secret")]
        assert conn.logout_called is True

        box = _ImapBox()
        box.capabilities = ("AUTH=PLAIN",)
        self._configure_imap(box, imap_security="none", imap_append_domain="")
        with patch("radicale.auth.imap.imaplib.IMAP4_SSL", _FakeIMAP), \
                patch("radicale.auth.imap.imaplib.IMAP4", _FakeIMAP):
            assert _principal(self, "owner:secret") == "/owner/"
        assert box.connections[-1].port == 143
        assert box.connections[-1].secure is False

    def test_imap_failures(self) -> None:
        box = _ImapBox()
        box.capabilities = ("IMAP4rev1",)
        self._configure_imap(box, imap_security="tls", imap_host="imap.example:1993")
        with patch("radicale.auth.imap.imaplib.IMAP4_SSL", _FakeIMAP), \
                patch("radicale.auth.imap.imaplib.IMAP4", _FakeIMAP):
            assert _principal(self, "owner:secret", check=401) == ""
        assert box.connections[-1].port == 1993
        assert box.connections[-1].auth_calls == []

        box = _ImapBox()
        box.auth_error = imaplib.IMAP4.error("no")
        self._configure_imap(box, imap_security="tls")
        with patch("radicale.auth.imap.imaplib.IMAP4_SSL", _FakeIMAP), \
                patch("radicale.auth.imap.imaplib.IMAP4", _FakeIMAP):
            assert _principal(self, "owner:secret", check=401) == ""

        box = _ImapBox()
        box.connect_error = OSError("down")
        self._configure_imap(box, imap_security="starttls")
        with patch("radicale.auth.imap.imaplib.IMAP4_SSL", _FakeIMAP), \
                patch("radicale.auth.imap.imaplib.IMAP4", _FakeIMAP):
            assert _principal(self, "owner:secret", check=401) == ""

        box = _ImapBox()
        box.connect_error = imaplib.IMAP4.error("banner")
        self._configure_imap(box, imap_security="none")
        with patch("radicale.auth.imap.imaplib.IMAP4_SSL", _FakeIMAP), \
                patch("radicale.auth.imap.imaplib.IMAP4", _FakeIMAP):
            assert _principal(self, "owner:secret", check=401) == ""

        box = _ImapBox()
        box.starttls_error = imaplib.IMAP4.error("tls")
        self._configure_imap(box, imap_security="starttls")
        with patch("radicale.auth.imap.imaplib.IMAP4_SSL", _FakeIMAP), \
                patch("radicale.auth.imap.imaplib.IMAP4", _FakeIMAP):
            assert _principal(self, "owner:secret", check=401) == ""

        box = _ImapBox()
        box.logout_error = imaplib.IMAP4.error("bye")
        self._configure_imap(box, imap_security="tls")
        with patch("radicale.auth.imap.imaplib.IMAP4_SSL", _FakeIMAP), \
                patch("radicale.auth.imap.imaplib.IMAP4", _FakeIMAP):
            assert _principal(self, "owner:secret", check=401) == ""
        assert box.connections[-1].auth_calls

    def test_oauth2(self) -> None:
        with pytest.raises(RuntimeError, match="OAuth2 token endpoint"):
            self.configure({"auth": {"type": "oauth2", "oauth2_token_endpoint": ""}})

        calls: list = []

        def fake_post(url, data=None, headers=None):
            calls.append((url, dict(data), dict(headers)))
            mode = calls[-1][1]["username"]
            if mode == "down":
                raise OSError("unreachable")
            if mode == "denied":
                return _OauthResponse(401, {})
            if mode == "empty":
                return _OauthResponse(200, {"token_type": "bearer"})
            return _OauthResponse(200, {"access_token": "tok"})

        endpoint = "https://auth.example/token"
        with patch("radicale.auth.oauth2.requests.post", fake_post):
            self.configure({"auth": {"type": "oauth2", "delay": "0.001",
                                     "oauth2_token_endpoint": endpoint,
                                     "oauth2_client_id": "radicale",
                                     "oauth2_client_secret": "secret"}})
            assert _principal(self, "owner:secret") == "/owner/"
            assert _principal(self, "empty:secret", check=401) == ""
            assert _principal(self, "denied:secret", check=401) == ""
            assert _principal(self, "down:secret", check=401) == ""
            self.configure({"auth": {"oauth2_client_secret": ""}})
            assert _principal(self, "owner:secret") == "/owner/"

        url, data, headers = calls[0]
        assert url == endpoint
        assert data["username"] == "owner"
        assert data["password"] == "secret"
        assert data["grant_type"] == "password"
        assert data["client_id"] == "radicale"
        assert data["client_secret"] == "secret"
        assert headers["Content-Type"] == "application/x-www-form-urlencoded"
        assert "client_secret" not in calls[-1][1]

    @pytest.mark.skipif(sys.platform == "win32", reason="Not supported on Windows")
    @pytest.mark.skipif(skip_pam is True, reason="No PAM module found")
    def test_pam(self) -> None:
        class Pw:
            def __init__(self, uid: int, gid: int) -> None:
                self.pw_uid = uid
                self.pw_gid = gid

        class Gr:
            def __init__(self, name: str, members: list) -> None:
                self.gr_name = name
                self.gr_mem = members

        users = {"owner": Pw(1, 10), "guest": Pw(2, 10)}
        groups = {10: Gr("users", []), "wheel": Gr("wheel", ["owner"])}
        calls: list = []

        def getpwnam(name: str) -> Pw:
            if name not in users:
                raise KeyError(name)
            return users[name]

        def getgrgid(gid: int) -> Gr:
            if gid not in groups:
                raise KeyError(gid)
            return groups[gid]

        def getgrnam(name: str) -> Gr:
            if name not in groups:
                raise KeyError(name)
            return groups[name]

        def authenticate(login: str, password: str, service: str = "") -> bool:
            calls.append((login, password, service))
            return password == "secret"

        with patch("radicale.auth.pam.pwd.getpwnam", getpwnam), \
                patch("radicale.auth.pam.grp.getgrgid", getgrgid), \
                patch("radicale.auth.pam.grp.getgrnam", getgrnam), \
                patch.object(pam, "authenticate", authenticate):
            self.configure({"auth": {"type": "pam", "delay": "0.001", "pam_service": "radicale"},
                            "group": {"type": "from_auth"}})
            auth_any: Any = self.application._auth
            assert auth_any._login(None, "secret") == ""
            assert auth_any._login("owner", None) == ""
            assert _principal(self, "missing:secret", check=401) == ""
            assert _principal(self, "owner:secret") == "/owner/"
            assert ("owner", "secret", "radicale") in calls
            assert "users" in self.application._rights._user_groups

            self.configure({"auth": {"pam_group_membership": "wheel"}})
            assert _principal(self, "owner:secret") == "/owner/"
            assert self.application._auth._groups == {"owner", "users"}
            assert _principal(self, "guest:secret", check=401) == ""
            assert _principal(self, "owner:wrong", check=401) == ""

            self.configure({"auth": {"pam_group_membership": "absent"}})
            assert _principal(self, "owner:secret", check=401) == ""

            groups.pop(10)
            self.configure({"auth": {"pam_group_membership": ""}})
            assert _principal(self, "owner:secret", check=401) == ""


class _OauthResponse:
    def __init__(self, status: int, body: dict) -> None:
        self.status_code = status
        self._body = body

    def json(self) -> dict:
        return self._body
