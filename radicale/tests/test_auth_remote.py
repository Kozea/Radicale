# This file is part of Radicale - CalDAV and CardDAV server
# Copyright © 2026 Peter Bieringer <pb@bieringer.de>
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

"""Outcome tests for IMAP, OAuth2, LDAP, and PAM authentication.

Remote clients are faked at the library boundary. The Radicale auth classes
under test are the real ones.
"""

import logging
import ssl
import sys
import types
from types import SimpleNamespace

import ldap3
import pytest

from radicale import auth, config
from radicale.auth import imap as imap_auth
from radicale.auth import ldap as ldap_auth
from radicale.auth import oauth2 as oauth2_auth


def load_auth(updates):
    configuration = config.load()
    section = {"delay": "0", "cache_logins": "False"}
    section.update(updates)
    configuration.update({"auth": section}, "test")
    return auth.load(configuration)


def _login(plugin, user, password):
    user_name, _groups, auth_type = plugin.login(user, password, auth.AuthContext())
    return user_name, auth_type


class _Response:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class _ImapScript:
    def __init__(self, host, port, security, capabilities=("IMAP4REV1", "AUTH=PLAIN"), allow=True, connect_error=None):
        self.host = host
        self.port = port
        self.security = security
        self.capabilities = capabilities
        self.allow = allow
        self.connect_error = connect_error
        self.clients = []


def _install_imap(monkeypatch, script):
    # Capture the real exception class before IMAP4 is replaced. The auth
    # module catches imaplib.IMAP4.error, which then resolves to FakeIMAP.
    imap_error = imap_auth.imaplib.IMAP4.error

    def make(tls):
        class FakeIMAP:
            error = imap_error

            def __init__(self, host, port, ssl_context=None):
                self.host = host
                self.port = port
                self.ssl_context = ssl_context
                self.capabilities = script.capabilities
                self.logged_out = False
                self.mech = None
                self.payload = None
                self.login_user = None
                self.login_password = None
                script.clients.append(self)
                if script.connect_error is not None:
                    raise script.connect_error
                if tls and script.security != "tls":
                    raise OSError("unexpected implicit TLS")
                if not tls and script.security == "tls":
                    raise OSError("expected implicit TLS")
                if host != script.host or port != script.port:
                    raise OSError("connected to %s:%s" % (host, port))

            def starttls(self, context):
                if script.security != "starttls":
                    raise OSError("unexpected STARTTLS")
                self.started_tls = True
                self.ssl_context = context

            def authenticate(self, mech, callback):
                if script.security == "starttls" and not getattr(self, "started_tls", False):
                    raise OSError("STARTTLS was not negotiated")
                self.mech = mech
                self.payload = callback(None)
                if not script.allow:
                    raise imap_error("authentication failed")

            def login(self, user, password):
                if script.security == "starttls" and not getattr(self, "started_tls", False):
                    raise OSError("STARTTLS was not negotiated")
                self.mech = "LOGIN"
                self.login_user = user
                self.login_password = password
                if not script.allow:
                    raise imap_error("authentication failed")

            def logout(self):
                self.logged_out = True

        return FakeIMAP

    monkeypatch.setattr(imap_auth.imaplib, "IMAP4_SSL", make(True))
    monkeypatch.setattr(imap_auth.imaplib, "IMAP4", make(False))


class TestImapAuth:
    @pytest.mark.parametrize(("security", "configured_host", "expect_host", "expect_port"), [
        ("tls", "imap.example", "imap.example", 993),
        ("tls", "imap.example:1993", "imap.example", 1993),
        ("starttls", "imap.example", "imap.example", 143),
        ("starttls", "imap.example:2143", "imap.example", 2143),
        ("none", "imap.example", "imap.example", 143),
        ("none", "[::1]:1143", "::1", 1143),
    ])
    def test_security_mode_selects_port_and_accepts_plain(self, monkeypatch, security, configured_host, expect_host, expect_port, caplog):
        caplog.set_level(logging.INFO)
        script = _ImapScript(expect_host, expect_port, security)
        _install_imap(monkeypatch, script)
        plugin = load_auth({
            "type": "imap",
            "imap_host": configured_host,
            "imap_security": security,
        })
        assert _login(plugin, "alice", "secret") == ("alice", "imap")
        client = script.clients[-1]
        assert client.mech == "PLAIN"
        assert client.payload == b"alice\x00alice\x00secret"
        assert client.logged_out is True
        if security == "tls":
            assert client.ssl_context is not None
        if security == "starttls":
            assert client.started_tls is True
        if security == "none":
            assert "INSECURE" in caplog.text

    def test_appends_domain_and_returns_the_original_login(self, monkeypatch):
        script = _ImapScript("imap.example", 993, "tls")
        _install_imap(monkeypatch, script)
        plugin = load_auth({
            "type": "imap",
            "imap_host": "imap.example",
            "imap_security": "tls",
            "imap_append_domain": "example.com",
        })
        assert _login(plugin, "alice", "secret") == ("alice", "imap")
        assert script.clients[-1].payload == b"alice@example.com\x00alice@example.com\x00secret"

    def test_login_mechanism_when_plain_is_absent(self, monkeypatch):
        script = _ImapScript("imap.example", 143, "starttls", capabilities=("IMAP4REV1", "AUTH=LOGIN"))
        _install_imap(monkeypatch, script)
        plugin = load_auth({
            "type": "imap",
            "imap_host": "imap.example",
            "imap_security": "starttls",
            "imap_append_domain": "example.com",
        })
        assert _login(plugin, "alice", "secret") == ("alice", "imap")
        client = script.clients[-1]
        assert client.mech == "LOGIN"
        assert client.login_user == "alice@example.com"
        assert client.login_password == "secret"

    def test_rejects_bad_password_missing_mechanism_and_connect_errors(self, monkeypatch, caplog):
        caplog.set_level(logging.INFO)
        script = _ImapScript("imap.example", 993, "tls", allow=False)
        _install_imap(monkeypatch, script)
        plugin = load_auth({"type": "imap", "imap_host": "imap.example", "imap_security": "tls"})
        assert _login(plugin, "alice", "wrong") == ("", "imap")

        script = _ImapScript("imap.example", 993, "tls", capabilities=("IMAP4REV1",))
        _install_imap(monkeypatch, script)
        plugin = load_auth({"type": "imap", "imap_host": "imap.example", "imap_security": "tls"})
        assert _login(plugin, "alice", "secret") == ("", "imap")
        assert "neither supporting AUTH=PLAIN or AUTH=LOGIN" in caplog.text

        script = _ImapScript("::1", 993, "tls", connect_error=OSError("network down"))
        _install_imap(monkeypatch, script)
        plugin = load_auth({"type": "imap", "imap_host": "[::1]", "imap_security": "tls"})
        assert _login(plugin, "alice", "secret") == ("", "imap")
        assert "[::1]:993" in caplog.text
        assert "network down" in caplog.text

        script = _ImapScript("imap.example", 993, "tls", connect_error=imap_auth.imaplib.IMAP4.error("bye"))
        _install_imap(monkeypatch, script)
        plugin = load_auth({"type": "imap", "imap_host": "imap.example", "imap_security": "tls"})
        assert _login(plugin, "alice", "secret") == ("", "imap")

    def test_security_value_is_rejected_by_configuration(self):
        with pytest.raises(RuntimeError, match="unsupported IMAP security"):
            load_auth({"type": "imap", "imap_host": "imap.example", "imap_security": "bogus"})


def _install_oauth(monkeypatch, endpoint, client_id, password, secret=None, status=200, body=None, error=None):
    def post(url, data=None, headers=None, **kwargs):
        if error is not None:
            raise error
        if url != endpoint:
            return _Response(404, {})
        headers = headers or {}
        data = data or {}
        if headers.get("Content-Type") != "application/x-www-form-urlencoded":
            return _Response(415, {})
        if data.get("grant_type") != "password" or data.get("client_id") != client_id:
            return _Response(400, {})
        if data.get("username") != "alice" or data.get("password") != password:
            return _Response(200, {"error": "invalid_grant"})
        if secret is None:
            if "client_secret" in data:
                return _Response(401, {})
        elif data.get("client_secret") != secret:
            return _Response(401, {})
        return _Response(status, {"access_token": "token-1"} if body is None else body)

    monkeypatch.setattr(oauth2_auth.requests, "post", post)


class TestOAuth2Auth:
    def test_missing_endpoint_raises(self):
        with pytest.raises(RuntimeError, match="OAuth2 token endpoint URL is required"):
            load_auth({"type": "oauth2", "oauth2_token_endpoint": ""})

    def test_accepts_token_and_rejects_bad_password(self, monkeypatch):
        endpoint = "https://idp.example/token"
        _install_oauth(monkeypatch, endpoint, "radicale-client", "secret")
        plugin = load_auth({
            "type": "oauth2",
            "oauth2_token_endpoint": endpoint,
            "oauth2_client_id": "radicale-client",
        })
        assert _login(plugin, "alice", "secret") == ("alice", "oauth2")
        assert _login(plugin, "alice", "wrong") == ("", "oauth2")

    def test_sends_client_secret_when_configured(self, monkeypatch):
        endpoint = "https://idp.example/token"
        _install_oauth(monkeypatch, endpoint, "radicale-client", "secret", secret="s3cret")
        plugin = load_auth({
            "type": "oauth2",
            "oauth2_token_endpoint": endpoint,
            "oauth2_client_id": "radicale-client",
            "oauth2_client_secret": "s3cret",
        })
        assert _login(plugin, "alice", "secret") == ("alice", "oauth2")

    def test_rejects_missing_token_http_error_and_network_failure(self, monkeypatch, caplog):
        caplog.set_level(logging.INFO)
        endpoint = "https://idp.example/token"
        updates = {
            "type": "oauth2",
            "oauth2_token_endpoint": endpoint,
            "oauth2_client_id": "radicale-client",
        }
        _install_oauth(monkeypatch, endpoint, "radicale-client", "secret", body={"error": "invalid_grant"})
        plugin = load_auth(updates)
        assert _login(plugin, "alice", "secret") == ("", "oauth2")

        _install_oauth(monkeypatch, endpoint, "radicale-client", "secret", status=401, body={"access_token": "ignored"})
        plugin = load_auth(updates)
        assert _login(plugin, "alice", "secret") == ("", "oauth2")

        _install_oauth(monkeypatch, endpoint, "radicale-client", "secret", error=OSError("idp down"))
        plugin = load_auth(updates)
        assert _login(plugin, "alice", "secret") == ("", "oauth2")
        assert "Failed to authenticate against OAuth2 server" in caplog.text
        assert endpoint in caplog.text
        assert "idp down" in caplog.text


class _Ldap3Script:
    def __init__(self, **kwargs):
        self.reader_dn = kwargs.get("reader_dn", "cn=reader,dc=example,dc=com")
        self.reader_secret = kwargs.get("reader_secret", "reader-secret")
        self.user_password = kwargs.get("user_password", "secret")
        self.login = kwargs.get("login", "alice")
        self.user_dn = kwargs.get("user_dn", "uid=alice,ou=people,dc=example,dc=com")
        self.user_base = kwargs.get("user_base", "ou=people,dc=example,dc=com")
        self.attributes = kwargs.get("attributes", {})
        self.group_dns = kwargs.get("group_dns", [])
        self.duplicate_users = kwargs.get("duplicate_users", False)
        self.user_search_error = kwargs.get("user_search_error", False)
        self.group_search_error = kwargs.get("group_search_error", False)
        self.socket_error = kwargs.get("socket_error", False)
        self.reader_starttls_error = kwargs.get("reader_starttls_error", False)
        self.user_starttls_error = kwargs.get("user_starttls_error", False)
        self.reader_generic_tls_error = kwargs.get("reader_generic_tls_error", False)
        self.user_boom = kwargs.get("user_boom", False)
        self.require_ssl = kwargs.get("require_ssl", False)
        self.require_verify = kwargs.get("require_verify", None)
        self.no_user = kwargs.get("no_user", False)


def _install_ldap3(monkeypatch, script):
    class Tls:
        def __init__(self, validate=None, ca_certs_file=None, sni=None, **kwargs):
            self.validate = validate
            self.ca_certs_file = ca_certs_file
            self.sni = sni

    class Server:
        def __init__(self, uri, use_ssl=False, tls=None):
            self.uri = uri
            self.use_ssl = use_ssl
            self.tls = tls

    class Connection:
        def __init__(self, server, user, password=None, auto_bind=False, raise_exceptions=False):
            self.server = server
            self.user = user
            self.password = password
            self.entries = []
            self.response = []
            if script.socket_error and user == script.reader_dn:
                raise ldap3.core.exceptions.LDAPSocketOpenError("socket down")
            if script.user_boom and user != script.reader_dn:
                raise ValueError("user connection failed")

        def start_tls(self):
            if self.user == script.reader_dn and script.reader_starttls_error:
                raise ldap3.core.exceptions.LDAPStartTLSError("reader starttls failed")
            if self.user == script.reader_dn and script.reader_generic_tls_error:
                raise ValueError("generic starttls failure")
            if self.user != script.reader_dn and script.user_starttls_error:
                raise ldap3.core.exceptions.LDAPStartTLSError("user starttls failed")
            self.started_tls = True

        def bind(self, read_server_info=False):
            if self.user == script.reader_dn:
                if script.reader_generic_tls_error:
                    return False
                if script.require_ssl and not self.server.use_ssl:
                    return False
                if script.require_verify is not None:
                    tls = self.server.tls
                    if tls is None or tls.validate != script.require_verify:
                        return False
                return self.password == script.reader_secret
            return self.password == script.user_password

        def search(self, search_base, search_filter, search_scope, attributes):
            if search_filter.startswith("(&"):
                if script.group_search_error:
                    raise RuntimeError("group search failed")
                self.response = [{"dn": dn} for dn in script.group_dns]
                self.entries = list(self.response)
                return
            if script.user_search_error:
                raise RuntimeError("user search failed")
            escaped = ldap3.utils.conv.escape_filter_chars(script.login)
            if script.no_user or escaped not in search_filter or search_base != script.user_base:
                self.entries = []
                self.response = []
                return
            if script.duplicate_users:
                self.entries = [1, 2]
                self.response = [{}, {}]
                return
            entry = {"dn": script.user_dn, "attributes": script.attributes}
            self.response = [entry]
            self.entries = [entry]

        def unbind(self):
            self.unbound = True

    monkeypatch.setattr(ldap3, "Tls", Tls)
    monkeypatch.setattr(ldap3, "Server", Server)
    monkeypatch.setattr(ldap3, "Connection", Connection)


def _assert_groups(caplog, expected):
    messages = [message for message in caplog.messages if "LDAP groups of user:" in message]
    assert messages, caplog.text
    listed = messages[-1].split("LDAP groups of user:", 1)[1].strip()
    got = set(filter(None, listed.split(",")))
    assert got == expected


class TestLdap3Auth:
    def _base(self, **extra):
        updates = {
            "type": "ldap",
            "ldap_uri": "ldap://ldap.example",
            "ldap_base": "ou=people,dc=example,dc=com",
            "ldap_reader_dn": "cn=reader,dc=example,dc=com",
            "ldap_secret": "reader-secret",
            "ldap_filter": "(uid={0})",
            "ldap_security": "none",
        }
        updates.update(extra)
        return updates

    def test_accepts_password_and_rewrites_user_from_attribute(self, monkeypatch, caplog):
        caplog.set_level(logging.DEBUG)
        script = _Ldap3Script(attributes={"uid": ["carol"]})
        _install_ldap3(monkeypatch, script)
        plugin = load_auth(self._base(ldap_user_attribute="uid"))
        assert _login(plugin, "alice", "secret") == ("carol", "ldap")
        assert _login(plugin, "alice", "wrong") == ("", "ldap")

    def test_scalar_user_attribute_and_group_rdns(self, monkeypatch, caplog):
        caplog.set_level(logging.DEBUG)
        script = _Ldap3Script(attributes={
            "uid": "carol",
            "memberOf": [
                "cn=staff,dc=example,dc=com",
                "cn=ops,dc=example,dc=com",
                "not-a-dn",
            ],
        })
        _install_ldap3(monkeypatch, script)
        plugin = load_auth(self._base(ldap_user_attribute="uid", ldap_groups_attribute="memberOf"))
        assert _login(plugin, "alice", "secret") == ("carol", "ldap")
        _assert_groups(caplog, {"staff", "ops", "not-a-dn"})

    def test_group_member_search_replaces_user_attribute_groups(self, monkeypatch, caplog):
        caplog.set_level(logging.DEBUG)
        script = _Ldap3Script(
            attributes={"memberOf": ["cn=fromuser,dc=example,dc=com"]},
            group_dns=["cn=fromsearch,ou=groups,dc=example,dc=com"],
        )
        _install_ldap3(monkeypatch, script)
        plugin = load_auth(self._base(
            ldap_groups_attribute="memberOf",
            ldap_group_members_attribute="member",
            ldap_group_filter="(objectClass=groupOfNames)",
            ldap_group_base="ou=groups,dc=example,dc=com",
        ))
        assert _login(plugin, "alice", "secret") == ("alice", "ldap")
        _assert_groups(caplog, {"fromsearch"})

    def test_group_search_failure_keeps_attribute_groups(self, monkeypatch, caplog):
        caplog.set_level(logging.DEBUG)
        script = _Ldap3Script(
            attributes={"memberOf": "cn=staff,dc=example,dc=com"},
            group_search_error=True,
        )
        _install_ldap3(monkeypatch, script)
        plugin = load_auth(self._base(
            ldap_groups_attribute="memberOf",
            ldap_group_members_attribute="member",
            ldap_group_filter="(objectClass=groupOfNames)",
        ))
        assert _login(plugin, "alice", "secret") == ("alice", "ldap")
        _assert_groups(caplog, {"staff"})

    def test_unknown_duplicate_and_search_errors_reject(self, monkeypatch):
        updates = self._base()
        _install_ldap3(monkeypatch, _Ldap3Script(no_user=True))
        plugin = load_auth(updates)
        assert _login(plugin, "alice", "secret") == ("", "ldap")

        _install_ldap3(monkeypatch, _Ldap3Script(duplicate_users=True))
        plugin = load_auth(updates)
        assert _login(plugin, "alice", "secret") == ("", "ldap")

        _install_ldap3(monkeypatch, _Ldap3Script(user_search_error=True))
        plugin = load_auth(updates)
        assert _login(plugin, "alice", "secret") == ("", "ldap")

    def test_special_characters_are_escaped_in_the_filter(self, monkeypatch):
        script = _Ldap3Script(login="a*b", user_dn="uid=a*b,ou=people,dc=example,dc=com")
        _install_ldap3(monkeypatch, script)
        plugin = load_auth(self._base())
        assert _login(plugin, "a*b", "secret") == ("a*b", "ldap")

    def test_reader_failures_raise(self, monkeypatch):
        _install_ldap3(monkeypatch, _Ldap3Script(reader_secret="other"))
        plugin = load_auth(self._base())
        with pytest.raises(RuntimeError, match="Unable to read from LDAP server"):
            _login(plugin, "alice", "secret")

        _install_ldap3(monkeypatch, _Ldap3Script(socket_error=True))
        plugin = load_auth(self._base())
        with pytest.raises(RuntimeError, match="Unable to reach LDAP server"):
            _login(plugin, "alice", "secret")

    def test_starttls_and_user_connection_errors(self, monkeypatch):
        updates = self._base(ldap_security="starttls")
        _install_ldap3(monkeypatch, _Ldap3Script(reader_starttls_error=True))
        plugin = load_auth(updates)
        with pytest.raises(RuntimeError, match="StartTLS"):
            _login(plugin, "alice", "secret")

        _install_ldap3(monkeypatch, _Ldap3Script(user_starttls_error=True))
        plugin = load_auth(updates)
        assert _login(plugin, "alice", "secret") == ("", "ldap")

        _install_ldap3(monkeypatch, _Ldap3Script(reader_generic_tls_error=True))
        plugin = load_auth(updates)
        with pytest.raises(RuntimeError, match="Unable to read from LDAP server"):
            _login(plugin, "alice", "secret")

        _install_ldap3(monkeypatch, _Ldap3Script(user_boom=True))
        plugin = load_auth(self._base())
        assert _login(plugin, "alice", "secret") == ("", "ldap")

    def test_ldaps_infers_tls_and_ldapi_lowers_verification(self, monkeypatch):
        _install_ldap3(monkeypatch, _Ldap3Script(require_ssl=True))
        plugin = load_auth(self._base(ldap_uri="ldaps://ldap.example", ldap_security="none"))
        assert _login(plugin, "alice", "secret") == ("alice", "ldap")

        _install_ldap3(monkeypatch, _Ldap3Script(require_verify=ssl.CERT_NONE))
        plugin = load_auth(self._base(
            ldap_uri="ldapi:///",
            ldap_security="tls",
            ldap_ssl_verify_mode="REQUIRED",
        ))
        assert _login(plugin, "alice", "secret") == ("alice", "ldap")

    def test_certificate_warnings_still_authenticate(self, monkeypatch, caplog, tmp_path):
        caplog.set_level(logging.WARNING)
        ca_file = tmp_path / "ca.pem"
        ca_file.write_text("not a certificate\n", encoding="utf-8")
        _install_ldap3(monkeypatch, _Ldap3Script())
        plugin = load_auth(self._base(ldap_security="tls", ldap_ssl_ca_file=""))
        assert _login(plugin, "alice", "secret") == ("alice", "ldap")
        assert "Certificate verification not possible" in caplog.text

        caplog.clear()
        _install_ldap3(monkeypatch, _Ldap3Script())
        plugin = load_auth(self._base(ldap_security="none", ldap_ssl_ca_file=str(ca_file)))
        assert _login(plugin, "alice", "secret") == ("alice", "ldap")
        assert "useless without encrypted" in caplog.text

    def test_secret_file_overrides_config_and_empty_file_is_rejected(self, monkeypatch, tmp_path):
        secret = tmp_path / "secret"
        secret.write_text("from-file\n", encoding="utf-8")
        _install_ldap3(monkeypatch, _Ldap3Script(reader_secret="from-file"))
        plugin = load_auth(self._base(ldap_secret="from-config", ldap_secret_file=str(secret)))
        assert _login(plugin, "alice", "secret") == ("alice", "ldap")

        empty = tmp_path / "empty-secret"
        empty.write_text("\n", encoding="utf-8")
        with pytest.raises(RuntimeError, match="requires ldap_secret"):
            load_auth(self._base(ldap_secret="from-config", ldap_secret_file=str(empty)))

        with pytest.raises(OSError):
            load_auth(self._base(ldap_secret_file=str(tmp_path)))

    def test_illegal_security_and_verify_mode(self):
        with pytest.raises(RuntimeError, match="ldap_security"):
            load_auth(self._base(ldap_security="bogus"))
        with pytest.raises(RuntimeError, match="ldap_ssl_verify_mode"):
            load_auth(self._base(ldap_ssl_verify_mode="SOMETIMES"))

    def test_ignore_timestamp_quirk_records_the_attributes(self, monkeypatch):
        saved = list(ldap3.utils.config._ATTRIBUTES_EXCLUDED_FROM_CHECK)
        try:
            _install_ldap3(monkeypatch, _Ldap3Script())
            plugin = load_auth(self._base(ldap_ignore_attribute_create_modify_timestamp="True"))
            assert _login(plugin, "alice", "secret") == ("alice", "ldap")
            excluded = ldap3.utils.config._ATTRIBUTES_EXCLUDED_FROM_CHECK
            assert "createTimestamp" in excluded
            assert "modifyTimestamp" in excluded
        finally:
            ldap3.utils.config._ATTRIBUTES_EXCLUDED_FROM_CHECK[:] = saved

    def test_missing_reader_secret_raises(self):
        with pytest.raises(RuntimeError, match="requires ldap_secret"):
            load_auth(self._base(ldap_secret=""))


class _Ldap2Script:
    def __init__(self, **kwargs):
        self.reader_dn = kwargs.get("reader_dn", "cn=reader,dc=example,dc=com")
        self.reader_secret = kwargs.get("reader_secret", "reader-secret")
        self.user_password = kwargs.get("user_password", "secret")
        self.login = kwargs.get("login", "alice")
        self.user_dn = kwargs.get("user_dn", "uid=alice,ou=people,dc=example,dc=com")
        self.user_base = kwargs.get("user_base", "ou=people,dc=example,dc=com")
        self.attrs = kwargs.get("attrs", {"uid": [b"carol"], "memberOf": [b"plain-bytes"]})
        self.group_dns = kwargs.get("group_dns", [])
        self.use_group_search = kwargs.get("use_group_search", False)
        self.duplicate = kwargs.get("duplicate", False)
        self.search_error = kwargs.get("search_error", False)
        self.group_search_error = kwargs.get("group_search_error", False)
        self.down = kwargs.get("down", False)
        self.security = kwargs.get("security", "none")
        self.expect_verify = kwargs.get("expect_verify", None)
        self.bad_password = kwargs.get("bad_password", False)
        self.constants = {}


def _escape_filter_chars(value):
    return (value.replace("\\", r"\5c").replace("*", r"\2a")
            .replace("(", r"\28").replace(")", r"\29"))


def _install_ldap2(monkeypatch, script):
    invalid_credentials = type("INVALID_CREDENTIALS", (Exception,), {})
    ldap_mod = types.ModuleType("ldap")
    ldap_mod.__path__ = []
    ldap_filter = types.ModuleType("ldap.filter")
    ldap_dn = types.ModuleType("ldap.dn")
    ldap_mod.filter = ldap_filter
    ldap_mod.dn = ldap_dn
    ldap_filter.escape_filter_chars = _escape_filter_chars

    def explode_dn(dn, notypes=True):
        if not isinstance(dn, str) or "=" not in dn:
            raise ValueError("bad dn")
        return [dn.split(",")[0].split("=", 1)[1]]

    ldap_dn.explode_dn = explode_dn
    constants = {
        "VERSION3": 3,
        "OPT_REFERRALS": 1,
        "OPT_X_TLS_NEVER": 10,
        "OPT_X_TLS_ALLOW": 11,
        "OPT_X_TLS_DEMAND": 12,
        "OPT_X_TLS_REQUIRE_CERT": 13,
        "OPT_X_TLS_CACERTFILE": 14,
        "OPT_X_TLS_NEWCTX": 15,
        "OPT_ON": 16,
        "SCOPE_SUBTREE": 2,
    }
    for name, value in constants.items():
        setattr(ldap_mod, name, value)
    script.constants = constants
    ldap_mod.INVALID_CREDENTIALS = invalid_credentials

    class Conn:
        def __init__(self, uri):
            self.uri = uri
            self.options = {}
            self.protocol_version = None

        def set_option(self, option, value):
            self.options[option] = value

        def start_tls_s(self):
            self.started_tls = True

        def simple_bind_s(self, dn, password):
            if script.security in ("tls", "starttls"):
                if constants["OPT_X_TLS_NEWCTX"] not in self.options:
                    raise RuntimeError("TLS context was not created")
                if script.expect_verify is not None and self.options.get(constants["OPT_X_TLS_REQUIRE_CERT"]) != script.expect_verify:
                    raise RuntimeError("unexpected verify mode")
            if script.security == "starttls" and not getattr(self, "started_tls", False):
                raise RuntimeError("STARTTLS was not started")
            if dn == script.reader_dn and password != script.reader_secret:
                raise RuntimeError("reader bind failed")
            if dn != script.reader_dn and (script.bad_password or password != script.user_password):
                raise invalid_credentials("bad password")

        def search_s(self, base, scope, filterstr="", attrlist=None):
            if filterstr.startswith("(&"):
                if script.group_search_error:
                    raise RuntimeError("group search failed")
                return [(dn, {}) for dn in script.group_dns]
            if script.search_error:
                raise RuntimeError("search failed")
            if _escape_filter_chars(script.login) not in filterstr or base != script.user_base:
                return []
            if script.duplicate:
                return [("dn-1", {}), ("dn-2", {})]
            return [(script.user_dn, script.attrs)]

        def unbind(self):
            self.unbound = True

    def initialize(uri):
        if script.down:
            raise OSError("ldap down")
        return Conn(uri)

    ldap_mod.initialize = initialize
    monkeypatch.setitem(sys.modules, "ldap3", None)
    monkeypatch.setitem(sys.modules, "ldap", ldap_mod)
    monkeypatch.setitem(sys.modules, "ldap.filter", ldap_filter)
    monkeypatch.setitem(sys.modules, "ldap.dn", ldap_dn)


class TestLdap2Auth:
    def _base(self, **extra):
        updates = {
            "type": "ldap",
            "ldap_uri": "ldap://ldap.example",
            "ldap_base": "ou=people,dc=example,dc=com",
            "ldap_reader_dn": "cn=reader,dc=example,dc=com",
            "ldap_secret": "reader-secret",
            "ldap_filter": "(uid={0})",
            "ldap_security": "none",
            "ldap_user_attribute": "uid",
            "ldap_groups_attribute": "memberOf",
        }
        updates.update(extra)
        return updates

    def test_decodes_bytes_and_uses_rdn_or_raw_group_names(self, monkeypatch, caplog):
        caplog.set_level(logging.DEBUG)
        _install_ldap2(monkeypatch, _Ldap2Script())
        plugin = load_auth(self._base())
        assert _login(plugin, "alice", "secret") == ("carol", "ldap")
        _assert_groups(caplog, {"plain-bytes"})

        caplog.clear()
        _install_ldap2(monkeypatch, _Ldap2Script(attrs={
            "uid": ["carol"],
            "memberOf": ["cn=staff,dc=example,dc=com", "plain-group"],
        }))
        plugin = load_auth(self._base())
        assert _login(plugin, "alice", "secret") == ("carol", "ldap")
        _assert_groups(caplog, {"staff", "plain-group"})

    def test_bad_password_and_ambiguous_search_reject(self, monkeypatch):
        _install_ldap2(monkeypatch, _Ldap2Script(bad_password=True))
        plugin = load_auth(self._base())
        assert _login(plugin, "alice", "secret") == ("", "ldap")

        _install_ldap2(monkeypatch, _Ldap2Script(duplicate=True))
        plugin = load_auth(self._base())
        assert _login(plugin, "alice", "secret") == ("", "ldap")

    def test_starttls_and_tls_options_are_required(self, monkeypatch):
        _install_ldap2(monkeypatch, _Ldap2Script(security="starttls"))
        plugin = load_auth(self._base(ldap_security="starttls"))
        assert _login(plugin, "alice", "secret") == ("carol", "ldap")

        _install_ldap2(monkeypatch, _Ldap2Script(security="tls", expect_verify=12))
        plugin = load_auth(self._base(
            ldap_security="tls",
            ldap_ssl_verify_mode="REQUIRED",
            ldap_ssl_ca_file="/tmp/ca.pem",
        ))
        assert _login(plugin, "alice", "secret") == ("carol", "ldap")

    def test_search_and_connect_failures_raise(self, monkeypatch):
        _install_ldap2(monkeypatch, _Ldap2Script(search_error=True))
        plugin = load_auth(self._base())
        with pytest.raises(RuntimeError, match="Invalid LDAP configuration"):
            _login(plugin, "alice", "secret")

        _install_ldap2(monkeypatch, _Ldap2Script(down=True))
        plugin = load_auth(self._base())
        with pytest.raises(RuntimeError, match="Invalid LDAP configuration"):
            _login(plugin, "alice", "secret")

        _install_ldap2(monkeypatch, _Ldap2Script(
            use_group_search=True,
            group_search_error=True,
            group_dns=["cn=ops,dc=example,dc=com"],
        ))
        plugin = load_auth(self._base(
            ldap_group_members_attribute="member",
            ldap_group_filter="(objectClass=groupOfNames)",
        ))
        with pytest.raises(RuntimeError, match="Invalid LDAP configuration"):
            _login(plugin, "alice", "secret")

    def test_group_search_result_replaces_attribute_groups(self, monkeypatch, caplog):
        caplog.set_level(logging.DEBUG)
        _install_ldap2(monkeypatch, _Ldap2Script(
            use_group_search=True,
            group_dns=["cn=fromsearch,dc=example,dc=com"],
        ))
        plugin = load_auth(self._base(
            ldap_group_members_attribute="member",
            ldap_group_filter="(objectClass=groupOfNames)",
        ))
        assert _login(plugin, "alice", "secret") == ("carol", "ldap")
        _assert_groups(caplog, {"fromsearch"})

    def test_neither_ldap_library_imports(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "ldap3", None)
        monkeypatch.setitem(sys.modules, "ldap", None)
        configuration = config.load()
        configuration.update({"auth": {"type": "ldap", "delay": "0"}}, "test")
        with pytest.raises(ModuleNotFoundError, match="ldap3 or ldap"):
            ldap_auth.Auth(configuration)


def _patch_posix(monkeypatch, users, groups):
    from radicale.auth import pam as pam_auth

    def getpwnam(name):
        if name not in users:
            raise KeyError(name)
        uid, gid = users[name]
        return SimpleNamespace(pw_uid=uid, pw_gid=gid)

    def getgrgid(gid):
        for name, (group_gid, members) in groups.items():
            if group_gid == gid:
                return SimpleNamespace(gr_name=name, gr_mem=list(members))
        raise KeyError(gid)

    def getgrnam(name):
        if name not in groups:
            raise KeyError(name)
        group_gid, members = groups[name]
        return SimpleNamespace(gr_name=name, gr_gid=group_gid, gr_mem=list(members))

    def getgrouplist(name, gid):
        extra = [group_gid for _group_name, (group_gid, members) in groups.items()
                 if name in members and group_gid != gid]
        return [gid, *extra]

    monkeypatch.setattr(pam_auth.pwd, "getpwnam", getpwnam)
    monkeypatch.setattr(pam_auth.grp, "getgrgid", getgrgid)
    monkeypatch.setattr(pam_auth.grp, "getgrnam", getgrnam)
    monkeypatch.setattr(pam_auth.os, "getgrouplist", getgrouplist)


@pytest.mark.skipif(sys.platform == "win32", reason="Not supported on Windows")
class TestPamAuth:
    def test_accepts_primary_and_supplementary_members(self, monkeypatch):
        users = {"alice": (10, 20), "bob": (11, 21)}
        groups = {
            "calendars": (20, ["bob"]),
            "users": (21, []),
        }
        _patch_posix(monkeypatch, users, groups)

        def authenticate(username, password, service="login", **kwargs):
            return username in users and password == "secret" and service == "calendar"

        monkeypatch.setattr("pam.authenticate", authenticate)
        plugin = load_auth({
            "type": "pam",
            "pam_service": "calendar",
            "pam_group_membership": "calendars",
        })
        user, groups_found, auth_type = plugin.login("alice", "secret", auth.AuthContext())
        assert (user, auth_type) == ("alice", "pam")
        assert groups_found == {"calendars"}
        user, groups_found, auth_type = plugin.login("bob", "secret", auth.AuthContext())
        assert (user, auth_type) == ("bob", "pam")
        assert groups_found == {"users", "calendars"}

    def test_rejects_unknown_user_missing_group_and_bad_password(self, monkeypatch, caplog):
        caplog.set_level(logging.DEBUG)
        users = {"alice": (10, 20)}
        groups = {"users": (20, []), "calendars": (30, ["carol"])}
        _patch_posix(monkeypatch, users, groups)
        monkeypatch.setattr("pam.authenticate", lambda *args, **kwargs: False)
        plugin = load_auth({
            "type": "pam",
            "pam_service": "radicale",
            "pam_group_membership": "calendars",
        })
        assert _login(plugin, "missing", "secret") == ("", "pam")
        assert "PAM user not found" in caplog.text
        assert plugin._login_ext_with_groups("alice", None, auth.AuthContext()) == ("", set())
        assert plugin._login_ext_with_groups(None, "secret", auth.AuthContext()) == ("", set())

        caplog.clear()
        assert _login(plugin, "alice", "secret") == ("", "pam")
        assert "belongs not to the required group" in caplog.text

        groups["calendars"] = (30, ["alice"])
        _patch_posix(monkeypatch, users, groups)
        plugin = load_auth({
            "type": "pam",
            "pam_service": "radicale",
            "pam_group_membership": "calendars",
        })
        assert _login(plugin, "alice", "secret") == ("", "pam")
        assert "not successful" in caplog.text

    def test_missing_primary_group_and_missing_required_group(self, monkeypatch, caplog):
        caplog.set_level(logging.DEBUG)
        _patch_posix(monkeypatch, {"alice": (10, 99)}, {"calendars": (30, [])})
        monkeypatch.setattr("pam.authenticate", lambda *args, **kwargs: True)
        plugin = load_auth({"type": "pam", "pam_group_membership": ""})
        assert _login(plugin, "alice", "secret") == ("", "pam")
        assert "no primary group" in caplog.text

        _patch_posix(monkeypatch, {"alice": (10, 20)}, {"users": (20, [])})
        plugin = load_auth({"type": "pam", "pam_group_membership": "calendars"})
        assert _login(plugin, "alice", "secret") == ("", "pam")
        assert "doesn't exist" in caplog.text

    def test_empty_group_membership_still_checks_the_password(self, monkeypatch, caplog):
        caplog.set_level(logging.INFO)
        _patch_posix(monkeypatch, {"alice": (10, 20)}, {"users": (20, [])})

        def authenticate(username, password, service="login", **kwargs):
            return password == "secret" and service == "radicale"

        monkeypatch.setattr("pam.authenticate", authenticate)
        plugin = load_auth({"type": "pam", "pam_group_membership": "", "pam_service": "radicale"})
        user, groups_found, auth_type = plugin.login("alice", "secret", auth.AuthContext())
        assert (user, auth_type) == ("alice", "pam")
        assert groups_found == {"users"}
        assert "INSECURE" in caplog.text
        assert _login(plugin, "alice", "wrong") == ("", "pam")

    def test_missing_pam_module_raises(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "pam", None)
        with pytest.raises(ModuleNotFoundError, match="PAM authentication requires the Python pam module"):
            load_auth({"type": "pam"})
