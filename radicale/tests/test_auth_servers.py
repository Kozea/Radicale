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

import imaplib
import logging
import os
import ssl
import sys
import types
from typing import Any, Optional, Union
from unittest.mock import patch
from urllib.parse import quote

import ldap3
import pytest

from radicale import xmlutils
from radicale.auth import ldap as ldap_auth
from radicale.tests import BaseTest


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


class _Ldap3State:
    def __init__(self) -> None:
        self.reader_dn = "cn=reader,dc=example,dc=com"
        self.reader_password = "reader-secret"
        self.users: dict = {}
        self.by_dn: dict = {}
        self.group_members_attr = ""
        self.group_response: list = []
        self.user_filter = "(cn={0})"
        self.duplicate = False
        self.search_error: Optional[BaseException] = None
        self.group_search_error: Optional[BaseException] = None
        self.reader_starttls_error: Optional[BaseException] = None
        self.user_starttls_error: Optional[BaseException] = None
        self.reader_bind_ok = True
        self.user_unbind_error = False
        self.socket_error = False
        self.servers: list = []
        self.connections: list = []
        self.tls: list = []
        self.filters: list = []

    def add_user(self, login: str, password: str, dn: str, attrs: dict) -> None:
        user = {"dn": dn, "password": password, "attrs": attrs}
        self.users[login] = user
        self.by_dn[dn] = user


class _Ldap3Holder:
    state: _Ldap3State


class _FakeTls:
    def __init__(self, validate: int = ssl.CERT_NONE, ca_certs_file: Optional[str] = None) -> None:
        self.validate = validate
        self.ca_certs_file = ca_certs_file
        _Ldap3Holder.state.tls.append(self)


class _FakeServer:
    def __init__(self, uri: str, use_ssl: bool = False, tls: Optional[_FakeTls] = None) -> None:
        self.uri = uri
        self.use_ssl = use_ssl
        self.tls = tls
        _Ldap3Holder.state.servers.append(self)


class _FakeConnection:
    def __init__(self, server: _FakeServer, user: str, password: Optional[str] = None,
                 auto_bind: bool = False, raise_exceptions: bool = False) -> None:
        state = _Ldap3Holder.state
        if state.socket_error:
            raise ldap3.core.exceptions.LDAPSocketOpenError("unreachable")
        self.server = server
        self.user = user
        self.password = password
        self.raise_exceptions = raise_exceptions
        self.auto_bind = auto_bind
        self.response: list = []
        self.entries: list = []
        self.unbound = False
        self.starttls = False
        state.connections.append(self)

    def start_tls(self) -> None:
        state = _Ldap3Holder.state
        self.starttls = True
        error = state.reader_starttls_error if self.user == state.reader_dn else state.user_starttls_error
        if error is not None:
            raise error

    def bind(self, read_server_info: bool = False) -> bool:
        state = _Ldap3Holder.state
        if self.user == state.reader_dn:
            return state.reader_bind_ok and self.password == state.reader_password
        user = state.by_dn.get(self.user)
        return user is not None and self.password == user["password"]

    def search(self, search_base: str, search_filter: str, search_scope: str, attributes: list) -> None:
        state = _Ldap3Holder.state
        state.filters.append(search_filter)
        if state.group_members_attr and ("(%s=" % state.group_members_attr) in search_filter:
            if state.group_search_error is not None:
                raise state.group_search_error
            self.response = list(state.group_response)
            self.entries = list(state.group_response)
            return
        if state.search_error is not None:
            raise state.search_error
        matches = []
        for login, user in state.users.items():
            escaped = ldap3.utils.conv.escape_filter_chars(login)
            if search_filter == state.user_filter.format(escaped):
                matches.append({"dn": user["dn"], "attributes": user["attrs"]})
        if state.duplicate and matches:
            matches.append(dict(matches[0]))
        self.response = matches
        self.entries = matches

    def unbind(self) -> None:
        self.unbound = True
        state = _Ldap3Holder.state
        if self.user != state.reader_dn and state.user_unbind_error:
            raise RuntimeError("unbind failed")


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

    def _configure_ldap3(self, state: _Ldap3State, **auth: str) -> None:
        _Ldap3Holder.state = state
        # The backend appends to a class-level list. Give each server a fresh one.
        ldap_auth.Auth._ldap_attributes = []
        config = {
            "type": "ldap",
            "delay": "0.001",
            "ldap_uri": "ldap://ldap.example",
            "ldap_base": "ou=people,dc=example,dc=com",
            "ldap_reader_dn": state.reader_dn,
            "ldap_secret": state.reader_password,
            "ldap_filter": state.user_filter,
        }
        config.update(auth)
        self.configure({"auth": config, "group": {"type": "from_auth"}})

    def _patch_ldap3(self):
        return patch.multiple(ldap3, Server=_FakeServer, Connection=_FakeConnection, Tls=_FakeTls)

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

    def test_ldap3_login_groups_user_attribute_and_escape(self) -> None:
        state = _Ldap3State()
        state.add_user("Owner", "secret", "uid=owner,ou=people,dc=example,dc=com", {
            "cn": ["owner"],
            "memberOf": [
                "cn=family,ou=groups,dc=example,dc=com",
                "cn=staff,ou=groups,dc=example,dc=com",
            ],
        })
        state.add_user("a(b)", "secret", "uid=ab,ou=people,dc=example,dc=com", {
            "cn": ["a(b)"],
            "memberOf": [],
        })
        self._configure_ldap3(state, ldap_user_attribute="cn", ldap_groups_attribute="memberOf",
                              ldap_ssl_ca_file="/tmp/unused-ca.pem")
        with self._patch_ldap3():
            assert _principal(self, "Owner:secret") == "/owner/"
            assert self.application._auth._groups == {"family", "staff"}
            assert self.application._rights._user_groups == {"family", "staff"}
            assert state.servers[0].use_ssl is False
            assert _principal(self, "a(b):secret") == quote("/a(b)/")
        assert "(cn=a\\28b\\29)" in state.filters

    def test_ldap3_scalar_attributes_and_group_search(self) -> None:
        state = _Ldap3State()
        user_dn = "uid=owner,ou=people,dc=example,dc=com"
        state.group_members_attr = "member"
        state.add_user("Alias", "secret", user_dn, {
            "cn": "owner",
            "memberOf": "cn=ignored,ou=groups,dc=example,dc=com",
        })
        state.group_response = [
            {"dn": "cn=family,ou=groups,dc=example,dc=com"},
            {"dn": "not-a-dn"},
        ]
        self._configure_ldap3(
            state,
            ldap_user_attribute="cn",
            ldap_groups_attribute="memberOf",
            ldap_group_members_attribute="member",
            ldap_group_filter="(objectClass=groupOfNames)",
            ldap_group_base="ou=groups,dc=example,dc=com")
        with self._patch_ldap3():
            assert _principal(self, "Alias:secret") == "/owner/"
        # Member search replaces attribute groups. An unparseable DN is kept whole.
        assert self.application._auth._groups == {"family", "not-a-dn"}
        assert any("(member=" in item for item in state.filters)
        assert getattr(self.application._auth, "_ldap_group_base") == "ou=groups,dc=example,dc=com"

    def test_ldap3_group_search_failure_keeps_attribute_groups(self) -> None:
        state = _Ldap3State()
        state.group_members_attr = "member"
        state.group_search_error = RuntimeError("group lookup down")
        state.add_user("owner", "secret", "uid=owner,ou=people,dc=example,dc=com", {
            "memberOf": ["cn=family,ou=groups,dc=example,dc=com"],
        })
        self._configure_ldap3(state, ldap_groups_attribute="memberOf",
                              ldap_group_members_attribute="member",
                              ldap_group_filter="(objectClass=groupOfNames)")
        with self._patch_ldap3():
            assert _principal(self, "owner:secret") == "/owner/"
        assert self.application._auth._groups == {"family"}

    def test_ldap3_tls_modes_secret_file_and_quirks(self) -> None:
        secret = os.path.join(self.colpath, "ldap.secret")
        with open(secret, "w", encoding="utf-8") as handle:
            handle.write("reader-secret\n")
        ca_file = os.path.join(self.colpath, "ca.pem")
        with open(ca_file, "w", encoding="utf-8") as handle:
            handle.write("not a certificate\n")

        state = _Ldap3State()
        state.add_user("owner", "secret", "uid=owner,ou=people,dc=example,dc=com", {})
        self._configure_ldap3(state, ldap_secret="", ldap_secret_file=secret,
                              ldap_security="tls", ldap_ssl_ca_file=ca_file,
                              ldap_ignore_attribute_create_modify_timestamp="true")
        excluded = ldap3.utils.config._ATTRIBUTES_EXCLUDED_FROM_CHECK
        before = len(excluded)
        try:
            with self._patch_ldap3():
                assert _principal(self, "owner:secret") == "/owner/"
            assert state.servers[-1].use_ssl is True
            assert state.tls[-1].ca_certs_file == ca_file
            assert state.tls[-1].validate == ssl.CERT_REQUIRED
            assert "createTimestamp" in excluded
            assert "modifyTimestamp" in excluded
            assert state.connections[-1].unbound is True
        finally:
            del excluded[before:]

        state = _Ldap3State()
        state.add_user("owner", "secret", "uid=owner,ou=people,dc=example,dc=com", {})
        # A StartTLS error that is not LDAPStartTLSError is ignored and bind continues.
        state.reader_starttls_error = OSError("handshake reset")
        self._configure_ldap3(state, ldap_security="starttls", ldap_ssl_verify_mode="OPTIONAL")
        with self._patch_ldap3():
            assert _principal(self, "owner:secret") == "/owner/"
        assert state.servers[-1].use_ssl is False
        assert state.tls[-1].validate == ssl.CERT_OPTIONAL
        assert all(item.starttls for item in state.connections)

        state = _Ldap3State()
        state.add_user("owner", "secret", "uid=owner,ou=people,dc=example,dc=com", {})
        self._configure_ldap3(state, ldap_uri="ldaps://ldap.example", ldap_security="none",
                              ldap_ssl_verify_mode="NONE")
        with self._patch_ldap3():
            assert _principal(self, "owner:secret") == "/owner/"
        assert state.servers[-1].use_ssl is True

        state = _Ldap3State()
        state.add_user("owner", "secret", "uid=owner,ou=people,dc=example,dc=com", {})
        self._configure_ldap3(state, ldap_uri="ldapi:///", ldap_ssl_verify_mode="REQUIRED")
        auth_any: Any = self.application._auth
        assert auth_any._ldap_ssl_verify_mode == "NONE"
        # No group base was configured, so the user base is used.
        assert auth_any._ldap_group_base == "ou=people,dc=example,dc=com"
        with self._patch_ldap3():
            assert _principal(self, "owner:secret") == "/owner/"

    def test_ldap3_login_failures(self, caplog) -> None:
        caplog.set_level(logging.ERROR)
        state = _Ldap3State()
        state.add_user("owner", "secret", "uid=owner,ou=people,dc=example,dc=com", {})
        state.duplicate = True
        self._configure_ldap3(state)
        with self._patch_ldap3():
            assert _principal(self, "owner:secret", check=401) == ""
            state.duplicate = False
            assert _principal(self, "missing:secret", check=401) == ""
            assert _principal(self, "owner:wrong", check=401) == ""

        state = _Ldap3State()
        state.add_user("owner", "secret", "uid=owner,ou=people,dc=example,dc=com", {})
        state.search_error = RuntimeError("search down")
        self._configure_ldap3(state)
        with self._patch_ldap3():
            assert _principal(self, "owner:secret", check=401) == ""

        state = _Ldap3State()
        state.add_user("owner", "secret", "uid=owner,ou=people,dc=example,dc=com", {})
        state.reader_bind_ok = False
        self._configure_ldap3(state)
        with self._patch_ldap3():
            _principal(self, "owner:secret", check=500)
        assert "Unable to read from LDAP server" in caplog.text

        state = _Ldap3State()
        state.socket_error = True
        self._configure_ldap3(state)
        with self._patch_ldap3():
            _principal(self, "owner:secret", check=500)
        assert "Unable to reach LDAP server" in caplog.text

        state = _Ldap3State()
        state.add_user("owner", "secret", "uid=owner,ou=people,dc=example,dc=com", {})
        state.user_starttls_error = ldap3.core.exceptions.LDAPStartTLSError("user tls")
        self._configure_ldap3(state, ldap_security="starttls")
        with self._patch_ldap3():
            assert _principal(self, "owner:secret", check=401) == ""

        state = _Ldap3State()
        state.add_user("owner", "secret", "uid=owner,ou=people,dc=example,dc=com", {})
        state.user_unbind_error = True
        self._configure_ldap3(state)
        with self._patch_ldap3():
            assert _principal(self, "owner:secret", check=401) == ""

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
    def test_pam(self) -> None:
        import pam

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
