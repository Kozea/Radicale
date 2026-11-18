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

"""Outcome tests for auth and hook branches the rest of the suite skips."""

import email
import logging
import os
import sys
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from radicale.auth import AuthContext
from radicale.hook import HookNotificationItem, HookNotificationItemTypes
from radicale.tests import BaseTest


def _freeze_auth_clock(monkeypatch, nanos):
    import radicale.auth as auth_module

    clock = {"ns": nanos}
    monkeypatch.setattr(auth_module.time, "time_ns", lambda: clock["ns"])
    return clock


def _event_ics(uid="evt-1", summary="Title", sequence=1,
               organizer="mailto:owner@example.com", attendees=None,
               dtend=True, recurrence=False, method=None, dtstamp=True):
    if attendees is None:
        attendees = [("alice@example.com", "Alice")]
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Radicale test//EN"]
    if method:
        lines.append("METHOD:%s" % method)
    lines.extend(["BEGIN:VEVENT", "UID:%s" % uid])
    if dtstamp:
        lines.append("DTSTAMP:20300101T000000Z")
    lines.append("DTSTART:20300101T110000Z")
    if dtend:
        lines.append("DTEND:20300101T120000Z")
    if recurrence:
        lines.append("RECURRENCE-ID:20300101T110000Z")
    lines.append("SUMMARY:%s" % summary)
    if sequence is not None:
        lines.append("SEQUENCE:%s" % sequence)
    if organizer is not None:
        lines.append("ORGANIZER:%s" % organizer)
    for address, name in attendees:
        if name:
            lines.append("ATTENDEE;CN=%s:mailto:%s" % (name, address))
        else:
            lines.append("ATTENDEE:%s" % address)
    lines.extend(["END:VEVENT", "END:VCALENDAR"])
    return "\n".join(lines) + "\n"


def _mail_text(raw):
    """Headers plus every decoded MIME part.

    iTIP calendar parts are base64, so METHOD and SEQUENCE are not
    visible in the raw SMTP payload.
    """
    parsed = email.message_from_string(raw)
    chunks = [raw]
    for part in parsed.walk():
        payload = part.get_payload(decode=True)
        if not payload:
            continue
        charset = part.get_content_charset() or "utf-8"
        chunks.append(payload.decode(charset, "replace"))
    return "\n".join(chunks)


def _todo_ics():
    return "\n".join([
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "BEGIN:VTODO",
        "UID:todo-1",
        "SUMMARY:Task",
        "END:VTODO",
        "END:VCALENDAR",
        "",
    ])


class TestAuthLoadAndCache(BaseTest):
    """Loopback warnings, username shaping, and the login caches."""

    def _login(self, user, password):
        return self.application._auth.login(user, password, AuthContext())

    def _plain(self, content, **extra):
        path = os.path.join(self.colpath, ".htpasswd")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)
        auth_config = {
            "type": "htpasswd",
            "htpasswd_filename": path,
            "htpasswd_encryption": "plain",
            "htpasswd_cache": "False",
            "delay": "0",
            "cache_logins": "False",
        }
        auth_config.update(extra)
        self.configure({"auth": auth_config, "server": {"delay_on_error": "0"}})
        return path

    def test_remote_user_warns_only_off_loopback_without_sgi(self, monkeypatch, caplog):
        caplog.set_level(logging.WARNING)
        monkeypatch.delenv("SERVER_GATEWAY_INTERFACE", raising=False)
        self.configure({
            "auth": {"type": "http_remote_user"},
            "server": {"hosts": "127.0.0.1:5232,[::1]:5232,localhost:5232,localhost6:5232"},
        })
        status, _responses = self.propfind("/", HTTP_REMOTE_USER="test")
        assert status == 207
        assert "potentially INSECURE" not in caplog.text

        caplog.clear()
        self.configure({
            "auth": {"type": "http_remote_user"},
            "server": {"hosts": "127.0.0.2:5232"},
        })
        status, _responses = self.propfind("/", HTTP_REMOTE_USER="test")
        assert status == 207
        assert "potentially INSECURE" in caplog.text
        assert "127.0.0.2" in caplog.text

        caplog.clear()
        monkeypatch.setenv("SERVER_GATEWAY_INTERFACE", "CGI")
        self.configure({
            "auth": {"type": "http_x_remote_user"},
            "server": {"hosts": "127.0.0.2:5232"},
        })
        status, _responses = self.propfind("/", HTTP_X_REMOTE_USER="test")
        assert status == 207
        assert "potentially INSECURE" not in caplog.text

    def test_lower_and_upper_username_cannot_both_be_enabled(self):
        with pytest.raises(RuntimeError, match="cannot be enabled together"):
            self.configure({"auth": {
                "type": "none",
                "lc_username": "True",
                "uc_username": "True",
            }})

    def test_negative_cache_expiry_is_rejected(self):
        with pytest.raises(RuntimeError, match="cache_successful_logins_expiry"):
            self.configure({"auth": {
                "type": "htpasswd",
                "cache_logins": "True",
                "cache_successful_logins_expiry": "-1",
                "cache_failed_logins_expiry": "0",
            }})
        with pytest.raises(RuntimeError, match="cache_failed_logins_expiry"):
            self.configure({"auth": {
                "type": "htpasswd",
                "cache_logins": "True",
                "cache_successful_logins_expiry": "0",
                "cache_failed_logins_expiry": "-1",
            }})

    def test_empty_login_versus_domain_stripped_to_one_character(self, caplog):
        caplog.set_level(logging.WARNING)
        self._plain("a:secret\n", strip_domain="True")
        assert self._login("", "secret")[0] == ""
        assert "is empty" in caplog.text
        caplog.clear()
        assert self._login("@host", "secret")[0] == ""
        assert "turned empty" in caplog.text
        assert self._login("a@", "secret")[0] == "a"
        assert self._login("a@example.com", "secret")[0] == "a"
        assert self._login("ab@example.com", "secret")[0] == ""

    def test_successful_cache_expires_on_the_far_side_of_the_window(self, monkeypatch, caplog):
        caplog.set_level(logging.DEBUG)
        clock = _freeze_auth_clock(monkeypatch, 1_000_000_000_000)
        self._plain("tmp:secret\n", cache_logins="True",
                    cache_successful_logins_expiry="10",
                    cache_failed_logins_expiry="5")
        assert self._login("tmp", "secret")[2] == "htpasswd"
        clock["ns"] += 10 * 10 ** 9
        assert self._login("tmp", "secret")[2] == "htpasswd/cached"
        clock["ns"] += 1 * 10 ** 9
        caplog.clear()
        assert self._login("tmp", "secret") == ("tmp", set(), "htpasswd")
        assert "expired" in caplog.text
        clock["ns"] += 1 * 10 ** 9
        assert self._login("tmp", "secret")[2] == "htpasswd/cached"

    def test_expired_success_cache_rejects_the_previous_password(self, monkeypatch):
        clock = _freeze_auth_clock(monkeypatch, 1_000_000_000_000)
        path = self._plain("tmp:one\n", cache_logins="True", htpasswd_cache="True",
                           cache_successful_logins_expiry="10",
                           cache_failed_logins_expiry="5")
        assert self._login("tmp", "one")[0] == "tmp"
        clock["ns"] += 1 * 10 ** 9
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("tmp:two\n")
        # Same length, so a coarse mtime (VFAT is about 2s) would keep the
        # cached hash. Move the stamp so every filesystem reports a change.
        # NTFS refuses an explicit stamp. A rewrite there already moves mtime;
        # if it did not, a second entry changes the size and the cache reloads.
        stamped = os.stat(path)
        previous_ns = stamped.st_mtime_ns
        try:
            os.utime(path, ns=(stamped.st_atime_ns, previous_ns + 2_000_000_000))
        except OSError:
            if os.stat(path).st_mtime_ns == previous_ns:
                with open(path, "a", encoding="utf-8") as handle:
                    handle.write("other:unused\n")
        assert self._login("tmp", "one")[2] == "htpasswd/cached"
        clock["ns"] += 10 * 10 ** 9
        assert self._login("tmp", "one")[0] == ""
        assert self._login("tmp", "two")[0] == "tmp"

    def test_wrong_password_does_not_reuse_the_successful_cache(self, monkeypatch, caplog):
        caplog.set_level(logging.DEBUG)
        _freeze_auth_clock(monkeypatch, 1_000_000_000_000)
        self._plain("tmp:secret\n", cache_logins="True",
                    cache_successful_logins_expiry="10",
                    cache_failed_logins_expiry="5")
        assert self._login("tmp", "secret")[0] == "tmp"
        caplog.clear()
        assert self._login("tmp", "secretX") == ("", set(), "htpasswd")
        assert "not matching" in caplog.text

    def test_failed_cache_survives_the_expiry_instant_and_drops_after(self, monkeypatch, caplog):
        caplog.set_level(logging.DEBUG)
        clock = _freeze_auth_clock(monkeypatch, 1_000_000_000_000)
        self._plain("tmp:secret\n", cache_logins="True",
                    cache_successful_logins_expiry="10",
                    cache_failed_logins_expiry="5")
        assert self._login("tmp", "nope")[2] == "htpasswd"
        clock["ns"] += 5 * 10 ** 9
        caplog.clear()
        assert self._login("tmp", "nope") == ("", set(), "htpasswd/cached")
        assert "expired" not in caplog.text
        clock["ns"] += 1 * 10 ** 9
        caplog.clear()
        assert self._login("tmp", "nope")[2] == "htpasswd"
        assert "expired" in caplog.text

    def test_successful_login_clears_a_failed_cache_entry(self, monkeypatch, caplog):
        caplog.set_level(logging.DEBUG)
        clock = _freeze_auth_clock(monkeypatch, 1_000_000_000_000)
        self._plain("tmp:secret\n", cache_logins="True",
                    cache_successful_logins_expiry="10",
                    cache_failed_logins_expiry="5")
        backend = self.application._auth
        real = backend._login_ext_with_groups

        def wrapped(login, password, context):
            digest_failed = login + ":" + backend._cache_digest(
                login, password, str(backend._cache_failed_logins_salt_ns))
            backend._cache_failed[digest_failed] = (clock["ns"], login)
            return real(login, password, context)

        backend._login_ext_with_groups = wrapped
        caplog.clear()
        assert self._login("tmp", "secret")[0] == "tmp"
        assert "Login failed cache for user cleared" in caplog.text


class TestDovecotGaps(BaseTest):
    """Clear-text families, empty credentials, and version 1.3 handshake."""

    def test_ip_families_fail_closed_when_connect_fails(self, monkeypatch, caplog):
        import socket

        caplog.set_level(logging.WARNING)
        seen = {}

        class BoomSocket:
            def __init__(self, family, sock_type):
                seen["family"] = family
                seen["type"] = sock_type

            def settimeout(self, timeout):
                seen["timeout"] = timeout

            def connect(self, address):
                seen["address"] = address
                raise socket.error("no dovecot")

            def close(self):
                seen["closed"] = True

        monkeypatch.setattr("radicale.auth.dovecot.socket.socket", BoomSocket)
        self.configure({"auth": {
            "type": "dovecot",
            "dovecot_connection_type": "AF_INET",
            "dovecot_host": "127.0.0.1",
            "dovecot_port": "2525",
            "delay": "0",
        }})
        result = self.application._auth.login("user", "secret", AuthContext())
        assert result[0] == ""
        assert seen["family"] == socket.AF_INET
        assert seen["address"] == ("127.0.0.1", 2525)
        assert "clear text" in caplog.text
        assert "Failed to communicate" in caplog.text

        seen.clear()
        caplog.clear()
        self.configure({"auth": {
            "type": "dovecot",
            "dovecot_connection_type": "AF_INET6",
            "dovecot_host": "::1",
            "dovecot_port": "2525",
            "delay": "0",
        }})
        result = self.application._auth.login("user", "secret", AuthContext())
        assert result[0] == ""
        assert seen["family"] == socket.AF_INET6
        assert seen["address"] == ("::1", 2525)

    def test_empty_credentials_do_not_open_a_socket(self, monkeypatch, caplog):
        caplog.set_level(logging.WARNING)

        def boom(*args, **kwargs):
            raise AssertionError("socket opened")

        monkeypatch.setattr("radicale.auth.dovecot.socket.socket", boom)
        self.configure({"auth": {"type": "dovecot", "delay": "0"}})
        backend = self.application._auth
        assert backend._login_ext("", "secret", AuthContext()) == ""
        assert "requires non-empty user" in caplog.text
        caplog.clear()
        assert backend.login("user", "", AuthContext())[0] == ""
        assert "requires non-empty password" in caplog.text

    def test_version_1_3_sends_version_once_and_returns_the_user(self, monkeypatch):
        class ScriptedSocket:
            def __init__(self, family, sock_type):
                self.sent = []
                self._recv = 0

            def settimeout(self, timeout):
                pass

            def connect(self, address):
                pass

            def close(self):
                pass

            def send(self, data):
                self.sent.append(data)
                return len(data)

            def recv(self, size):
                self._recv += 1
                if self._recv == 1:
                    return b"VERSION\t1\t3\n"
                if self._recv == 2:
                    return b"MECH\tPLAIN\nDONE\n"
                versions = [item for item in self.sent if item.startswith(b"VERSION")]
                if len(versions) != 1:
                    return b"FAIL\t1\n"
                return b"OK\t1\n"

        monkeypatch.setattr("radicale.auth.dovecot.socket.socket", ScriptedSocket)
        self.configure({"auth": {"type": "dovecot", "delay": "0"}})
        user, _groups, kind = self.application._auth.login("a", "b", AuthContext())
        assert (user, kind) == ("a", "dovecot")


class TestHtpasswdGaps(BaseTest):
    """Import failures, odd hashes, and re-read error handling."""

    def _write(self, content):
        path = os.path.join(self.colpath, ".htpasswd")
        parent = os.path.dirname(path)
        if os.path.isdir(path):
            os.rmdir(path)
        os.makedirs(parent, exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)
        return path

    def _configure(self, content, encryption="plain", **extra):
        path = self._write(content)
        auth_config = {
            "type": "htpasswd",
            "htpasswd_filename": path,
            "htpasswd_encryption": encryption,
            "htpasswd_cache": "False",
            "cache_logins": "False",
            "delay": "0",
        }
        auth_config.update(extra)
        self.configure({"auth": auth_config, "server": {"delay_on_error": "0"}})
        return path

    def _login(self, user, password):
        return self.application._auth.login(user, password, AuthContext())

    def test_missing_bcrypt_warns_without_entries_and_rejects_with_them(self, caplog):
        caplog.set_level(logging.WARNING)
        with pytest.MonkeyPatch.context() as patch:
            patch.setitem(sys.modules, "bcrypt", None)
            self._configure("tmp:secret\n", encryption="autodetect")
            assert self._login("tmp", "secret")[0] == "tmp"
            assert "no entries found" in caplog.text
            wide = "$2b$12$" + ("A" * 53)
            with pytest.raises(RuntimeError, match="bcrypt"):
                self._configure("tmp:%s\n" % wide, encryption="autodetect")
            with pytest.raises(RuntimeError, match="bcrypt"):
                self._configure("tmp:secret\n", encryption="bcrypt")

    def test_missing_argon2_warns_without_entries_and_rejects_with_them(self, caplog):
        caplog.set_level(logging.WARNING)
        with pytest.MonkeyPatch.context() as patch:
            patch.setitem(sys.modules, "argon2", None)
            self._configure("tmp:secret\n", encryption="autodetect")
            assert self._login("tmp", "secret")[0] == "tmp"
            assert "no entries found" in caplog.text
            with pytest.raises(RuntimeError, match="argon2"):
                self._configure("tmp:$argon2id$not-a-real-hash\n", encryption="autodetect")
            with pytest.raises(RuntimeError, match="argon2"):
                self._configure("tmp:secret\n", encryption="argon2")

    def test_unknown_encryption_is_rejected(self):
        with pytest.raises(RuntimeError, match="not supported"):
            self._configure("tmp:secret\n", encryption="rot13")

    def test_short_bcrypt_looking_hash_falls_back_to_plain(self):
        pytest.importorskip("bcrypt")
        short = "$2$10$" + ("B" * 53)
        wide = "$2b$12$" + ("A" * 53)
        assert len(short) == 59
        assert len(wide) == 60
        self._configure("short:%s\nwide:%s\n" % (short, wide), encryption="autodetect")
        assert self._login("short", short)[0] == "short"
        assert self._login("short", short[:-1] + "C")[0] == ""

    def test_autodetect_argon2_entry_verifies(self):
        pytest.importorskip("argon2")
        from passlib.hash import argon2

        digest = argon2.using(type="ID").hash("bepo")
        self._configure("tmp:%s\n" % digest, encryption="autodetect")
        assert self._login("tmp", "bepo")[0] == "tmp"
        assert self._login("tmp", "nope")[0] == ""

    def test_malformed_md5_hash_fails_login(self, caplog):
        caplog.set_level(logging.ERROR)
        self._configure("tmp:x\n", encryption="md5")
        assert self._login("tmp", "bepo")[0] == ""
        assert "Login verification failed" in caplog.text

    def test_duplicate_and_colonless_lines_fail_startup_but_reread_keeps_going(self, caplog):
        caplog.set_level(logging.WARNING)
        with pytest.raises(RuntimeError, match="duplicate"):
            self._configure("tmp:one\ntmp:two\n")
        with pytest.raises(RuntimeError, match="Invalid htpasswd file"):
            self._configure("nocolon\n")
        path = self._configure("tmp:one\n", htpasswd_cache="True")
        assert self._login("tmp", "one")[0] == "tmp"
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("tmp:one\ntmp:two\n")
        caplog.clear()
        assert self._login("tmp", "one")[0] == "tmp"
        assert self._login("tmp", "two")[0] == ""
        assert "duplicate" in caplog.text
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("nocolon\ntmp:two\n# kept\n")
        assert self._login("tmp", "two")[0] == "tmp"
        assert self._login("tmp", "one")[0] == ""

    def test_reread_skips_bcrypt_and_argon2_when_the_module_was_not_loaded(self, caplog):
        caplog.set_level(logging.WARNING)
        path = self._configure("tmp:one\n", encryption="plain", htpasswd_cache="True")
        bcrypt_hash = "$2b$12$" + ("A" * 53)
        argon_hash = "$argon2id$v=19$not-really"
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("tmp:one\nbcrypt:%s\nargon:%s\n" % (bcrypt_hash, argon_hash))
        caplog.clear()
        assert self._login("tmp", "one")[0] == "tmp"
        assert self._login("bcrypt", bcrypt_hash)[0] == ""
        assert self._login("argon", argon_hash)[0] == ""
        assert "bcrypt" in caplog.text
        assert "argon2" in caplog.text
        assert "module is not loaded" in caplog.text

    def test_missing_file_fails_startup_and_directory_reread_fails_login(self, caplog):
        caplog.set_level(logging.WARNING)
        missing = os.path.join(self.colpath, "missing-htpasswd")
        with pytest.raises(RuntimeError, match="Failed to load htpasswd file"):
            self.configure({"auth": {
                "type": "htpasswd",
                "htpasswd_filename": missing,
                "htpasswd_encryption": "plain",
                "delay": "0",
            }})
        path = self._configure("tmp:one\n", htpasswd_cache="True")
        assert self._login("tmp", "one")[0] == "tmp"
        os.remove(path)
        os.mkdir(path)
        caplog.clear()
        assert self._login("tmp", "one")[0] == ""
        assert "Failed to load htpasswd file on re-read" in caplog.text

    def test_reread_problem_is_not_reminded_until_the_interval_elapses(self, monkeypatch, caplog):
        import radicale.auth.htpasswd as htpasswd_module

        caplog.set_level(logging.WARNING)
        clock = {"now": 1_000_000.0}
        monkeypatch.setattr(htpasswd_module.time, "time", lambda: clock["now"])
        path = self._configure("tmp:bepo\n", htpasswd_cache="True")
        assert self._login("tmp", "bepo")[0] == "tmp"
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("tmp:bepo\n:broken\n")
        assert self._login("tmp", "bepo")[0] == "tmp"
        clock["now"] += 59
        caplog.clear()
        assert self._login("tmp", "bepo")[0] == "tmp"
        assert "REMINDER" not in caplog.text


class TestImapOauthPamGaps(BaseTest):
    """Empty credentials and the debug-disabled PAM group trace."""

    def test_imap_rejects_empty_credentials_and_accepts_one_character(self, monkeypatch, caplog):
        import imaplib

        caplog.set_level(logging.WARNING)
        self.configure({"auth": {"type": "imap", "imap_security": "none", "delay": "0"}})
        backend = self.application._auth
        imap_error = imaplib.IMAP4.error

        class BoomIMAP:
            error = imap_error

            def __init__(self, *args, **kwargs):
                raise AssertionError("imap opened")

        monkeypatch.setattr("radicale.auth.imap.imaplib.IMAP4", BoomIMAP)
        assert backend._login("", "b") == ""
        assert "requires non-empty user" in caplog.text
        caplog.clear()
        assert backend._login("a", "") == ""
        assert "requires non-empty password" in caplog.text

        class OkIMAP:
            error = imap_error

            def __init__(self, host, port, ssl_context=None):
                self.capabilities = ("AUTH=LOGIN",)

            def login(self, user, password):
                if not user or not password:
                    raise AssertionError("empty imap credentials")
                self.user = user
                self.password = password

            def logout(self):
                pass

        monkeypatch.setattr("radicale.auth.imap.imaplib.IMAP4", OkIMAP)
        assert backend._login("a", "b") == "a"

    def test_oauth2_rejects_empty_credentials_and_accepts_one_character(self, monkeypatch, caplog):
        caplog.set_level(logging.WARNING)
        self.configure({"auth": {
            "type": "oauth2",
            "oauth2_token_endpoint": "https://auth.example/token",
            "delay": "0",
        }})
        backend = self.application._auth

        class Response:
            status_code = 200

            def json(self):
                return {"access_token": "token"}

        def post(url, data=None, headers=None):
            if not data or not data.get("username") or not data.get("password"):
                raise AssertionError("empty oauth credentials")
            return Response()

        monkeypatch.setattr("radicale.auth.oauth2.requests.post", post)
        assert backend._login("", "b") == ""
        assert "requires non-empty user" in caplog.text
        caplog.clear()
        assert backend._login("a", "") == ""
        assert "requires non-empty password" in caplog.text
        assert backend._login("a", "b") == "a"

    def test_oauth2_import_error_names_requests(self):
        saved_oauth = sys.modules.pop("radicale.auth.oauth2", None)
        saved_requests = sys.modules.get("requests")
        sys.modules["requests"] = None
        try:
            with pytest.raises(ImportError, match="requests"):
                import radicale.auth.oauth2  # noqa: F401
        finally:
            sys.modules.pop("radicale.auth.oauth2", None)
            if saved_oauth is not None:
                sys.modules["radicale.auth.oauth2"] = saved_oauth
            if saved_requests is not None:
                sys.modules["requests"] = saved_requests
            else:
                sys.modules.pop("requests", None)

    def test_pam_skips_group_trace_when_debug_is_disabled(self, monkeypatch):
        if sys.platform == "win32":
            pytest.skip("Not supported on Windows")
        pytest.importorskip("pam")
        import radicale.auth.pam as pam_auth
        from radicale.log import logger

        class Pw:
            def __init__(self, uid, gid):
                self.pw_uid = uid
                self.pw_gid = gid

        class Gr:
            def __init__(self, name, members):
                self.gr_name = name
                self.gr_mem = members

        users = {"owner": Pw(1, 10)}
        groups = {10: Gr("users", []), 20: Gr("wheel", ["owner"])}

        def getpwnam(name):
            if name not in users:
                raise KeyError(name)
            return users[name]

        def getgrgid(gid):
            if gid not in groups:
                raise KeyError(gid)
            return groups[gid]

        def getgrnam(name):
            for group in groups.values():
                if group.gr_name == name:
                    return group
            raise KeyError(name)

        def getgrouplist(name, gid):
            found = [gid]
            for group_id, group in groups.items():
                if name in group.gr_mem and group_id not in found:
                    found.append(group_id)
            return found

        def authenticate(login, password, service=""):
            return password == "secret"

        def trace(*args, **kwargs):
            raise AssertionError("trace called")

        import pam

        monkeypatch.setattr(pam_auth.pwd, "getpwnam", getpwnam)
        monkeypatch.setattr(pam_auth.grp, "getgrgid", getgrgid)
        monkeypatch.setattr(pam_auth.grp, "getgrnam", getgrnam)
        monkeypatch.setattr(pam_auth.os, "getgrouplist", getgrouplist)
        monkeypatch.setattr(pam, "authenticate", authenticate)
        self.configure({"auth": {
            "type": "pam",
            "delay": "0",
            "pam_group_membership": "wheel",
        }})
        logger.setLevel(logging.INFO)
        monkeypatch.setattr(logger, "trace", trace)
        user, groups_out = self.application._auth._login_ext_with_groups(
            "owner", "secret", AuthContext())
        assert user == "owner"
        assert "wheel" in groups_out
        assert "users" in groups_out


class TestLdapGaps(BaseTest):
    """python-ldap stand-in plus the ldap3 bind fall-through."""

    def _ldap2(self, state, **extra):
        from radicale.auth import ldap as ldap_auth
        from radicale.tests.test_auth_servers import _install_ldap2

        ldap_mod = _install_ldap2(state)
        modules = {
            "ldap3": None,
            "ldap": ldap_mod,
            "ldap.filter": ldap_mod.filter,
            "ldap.dn": ldap_mod.dn,
        }
        config = {
            "type": "ldap",
            "delay": "0",
            "ldap_uri": "ldap://ldap.example",
            "ldap_base": "ou=people,dc=example,dc=com",
            "ldap_reader_dn": state.reader_dn,
            "ldap_secret": state.reader_password,
            "ldap_filter": state.user_filter,
        }
        config.update(extra)
        return ldap_auth, ldap_mod, modules, config

    def test_ldap2_security_modes_user_attribute_and_groups(self, caplog):
        from radicale.tests.test_auth_servers import _Ldap2State

        caplog.set_level(logging.DEBUG)
        state = _Ldap2State()
        state.user_filter = "(uid={0})"
        user_dn = "uid=owner,ou=people,dc=example,dc=com"
        state.passwords[user_dn] = "secret"
        state.user_results = [("owner", (user_dn, {
            "cn": [b"carol"],
            "memberOf": [
                "cn=staff,ou=groups,dc=example,dc=com",
                b"cn=bytes,ou=groups,dc=example,dc=com",
                "BAD",
            ],
        }))]
        ldap_auth, ldap_mod, modules, config = self._ldap2(
            state, ldap_user_attribute="cn", ldap_groups_attribute="memberOf")
        ldap_auth.Auth._ldap_attributes = []
        try:
            with patch.dict(sys.modules, modules):
                self.configure({"auth": config})
                backend = self.application._auth
                assert backend._ldap_module_version == 2
                user, groups = backend._login_ext_with_groups("owner", "secret", None)
                assert user == "carol"
                assert groups == {
                    "staff",
                    "BAD",
                    "cn=bytes,ou=groups,dc=example,dc=com",
                }
                conn = state.connections[-1]
                assert conn.started_tls is False
                assert ldap_mod.OPT_X_TLS_REQUIRE_CERT not in conn.options

                state.user_results[0][1][1]["cn"] = ["carol"]
                ldap_auth.Auth._ldap_attributes = []
                self.configure({"auth": dict(config, ldap_security="tls",
                                             ldap_ssl_verify_mode="REQUIRED")})
                state.connections.clear()
                user, _groups = self.application._auth._login_ext_with_groups(
                    "owner", "secret", None)
                assert user == "carol"
                conn = state.connections[-1]
                assert conn.options[ldap_mod.OPT_X_TLS_REQUIRE_CERT] == ldap_mod.OPT_X_TLS_DEMAND
                assert ldap_mod.OPT_X_TLS_CACERTFILE not in conn.options
                assert ldap_mod.OPT_X_TLS_NEWCTX in conn.options

                ca_file = os.path.join(self.colpath, "ca.pem")
                with open(ca_file, "w", encoding="utf-8") as handle:
                    handle.write("not-a-cert\n")
                ldap_auth.Auth._ldap_attributes = []
                self.configure({"auth": dict(
                    config, ldap_security="tls", ldap_ssl_ca_file=ca_file)})
                state.connections.clear()
                assert self.application._auth._login_ext_with_groups(
                    "owner", "secret", None)[0] == "carol"
                assert state.connections[-1].options[ldap_mod.OPT_X_TLS_CACERTFILE] == ca_file

                ldap_auth.Auth._ldap_attributes = []
                self.configure({"auth": dict(config, ldap_security="starttls")})
                state.connections.clear()
                assert self.application._auth._login_ext_with_groups(
                    "owner", "secret", None)[0] == "carol"
                assert state.connections[-1].started_tls is True
        finally:
            ldap_auth.Auth._ldap_attributes = []

    def test_ldap2_miss_duplicate_search_password_and_empty(self, caplog):
        from radicale.tests.test_auth_servers import _Ldap2State

        caplog.set_level(logging.WARNING)
        state = _Ldap2State()
        state.user_filter = "(uid={0})"
        user_dn = "uid=owner,ou=people,dc=example,dc=com"
        state.passwords[user_dn] = "secret"
        state.user_results = [("owner", (user_dn, {"cn": []}))]
        ldap_auth, _ldap_mod, modules, config = self._ldap2(
            state, ldap_user_attribute="cn")
        ldap_auth.Auth._ldap_attributes = []
        try:
            with patch.dict(sys.modules, modules):
                self.configure({"auth": config})
                backend = self.application._auth
                assert backend._login_ext_with_groups("owner", "secret", None)[0] == "owner"
                state.user_results = []
                assert backend._login_ext_with_groups("missing", "secret", None) == ("", set())
                state.user_results = [("owner", (user_dn, {"cn": ["carol"]}))]
                state.duplicate = True
                assert backend._login_ext_with_groups("owner", "secret", None) == ("", set())
                state.duplicate = False
                state.search_error = True
                with pytest.raises(RuntimeError, match="Invalid LDAP configuration"):
                    backend._login_ext_with_groups("owner", "secret", None)
                state.search_error = False
                assert backend._login_ext_with_groups("owner", "wrong", None) == ("", set())
                caplog.clear()
                state.connections.clear()
                saved = backend.ldap.initialize
                backend.ldap.initialize = lambda uri: (_ for _ in ()).throw(
                    AssertionError("ldap opened"))
                try:
                    assert backend._login_ext_with_groups("", "secret", None) == ("", set())
                    assert "requires non-empty user" in caplog.text
                    caplog.clear()
                    assert backend._login_ext_with_groups("owner", "", None) == ("", set())
                    assert "requires non-empty password" in caplog.text
                    assert state.connections == []
                finally:
                    backend.ldap.initialize = saved
        finally:
            ldap_auth.Auth._ldap_attributes = []

    def test_ldap2_member_search_replaces_attribute_groups(self):
        from radicale.tests.test_auth_servers import _Ldap2State

        state = _Ldap2State()
        state.user_filter = "(uid={0})"
        state.group_members_attr = "member"
        user_dn = "uid=owner,ou=people,dc=example,dc=com"
        state.passwords[user_dn] = "secret"
        state.user_results = [("owner", (user_dn, {
            "memberOf": ["cn=staff,ou=groups,dc=example,dc=com"],
        }))]
        state.group_results = [("cn=family,ou=groups,dc=example,dc=com", {})]
        ldap_auth, _ldap_mod, modules, config = self._ldap2(
            state,
            ldap_groups_attribute="memberOf",
            ldap_group_members_attribute="member",
            ldap_group_filter="(objectClass=groupOfNames)",
            ldap_group_base="ou=groups,dc=example,dc=com",
        )
        ldap_auth.Auth._ldap_attributes = []
        try:
            with patch.dict(sys.modules, modules):
                self.configure({"auth": config})
                user, groups = self.application._auth._login_ext_with_groups(
                    "owner", "secret", None)
                assert user == "owner"
                assert groups == {"family"}
                state.group_results = []
                user, groups = self.application._auth._login_ext_with_groups(
                    "owner", "secret", None)
                assert groups == set()
                state.group_search_error = True
                with pytest.raises(RuntimeError, match="Invalid LDAP configuration"):
                    self.application._auth._login_ext_with_groups("owner", "secret", None)
        finally:
            ldap_auth.Auth._ldap_attributes = []

    def test_ldap3_falsy_user_attribute_keeps_the_login(self):
        ldap3 = pytest.importorskip("ldap3")
        from radicale.auth import ldap as ldap_auth
        from radicale.tests.test_auth_servers import OWNER_DN, _MockLdap

        directory = _MockLdap()
        directory.add(OWNER_DN, uid="owner", userPassword="secret", displayName=[])
        ldap_auth.Auth._ldap_attributes = []
        try:
            with directory.patch():
                self.configure({"auth": {
                    "type": "ldap",
                    "delay": "0",
                    "ldap_uri": "ldap://ldap.example",
                    "ldap_base": "ou=people,dc=example,dc=com",
                    "ldap_reader_dn": _MockLdap.reader_dn,
                    "ldap_secret": _MockLdap.reader_password,
                    "ldap_filter": "(uid={0})",
                    "ldap_user_attribute": "displayName",
                }})
                user, _groups = self.application._auth._login_ext_with_groups(
                    "owner", "secret", None)
                assert user == "owner"
                ldap_auth.Auth._ldap_attributes = []
                directory.add("uid=blank,ou=people,dc=example,dc=com",
                              uid="blank", userPassword="secret", cn="")
                self.configure({"auth": {
                    "type": "ldap",
                    "delay": "0",
                    "ldap_uri": "ldap://ldap.example",
                    "ldap_base": "ou=people,dc=example,dc=com",
                    "ldap_reader_dn": _MockLdap.reader_dn,
                    "ldap_secret": _MockLdap.reader_password,
                    "ldap_filter": "(uid={0})",
                    "ldap_user_attribute": "cn",
                }})
                # The mock directory is shared; blank is found by uid.
                user, _groups = self.application._auth._login_ext_with_groups(
                    "blank", "secret", None)
                assert user == ""
        finally:
            ldap_auth.Auth._ldap_attributes = []
        assert ldap3 is not None

    def _configure_ldap3_reader(self):
        from radicale.tests.test_auth_servers import _MockLdap

        self.configure({"auth": {
            "type": "ldap",
            "delay": "0",
            "ldap_uri": "ldap://ldap.example",
            "ldap_base": "ou=people,dc=example,dc=com",
            "ldap_reader_dn": _MockLdap.reader_dn,
            "ldap_secret": _MockLdap.reader_password,
            "ldap_filter": "(uid={0})",
            "ldap_security": "starttls",
        }})

    def test_ldap3_starttls_socket_error_does_not_bind_the_reader(self):
        """A socket error during reader StartTLS is an unreachable server.

        A generic StartTLS failure is already "StartTLS Error" and does not
        bind. LDAPSocketOpenError is re-raised and reported as unreachable.
        """
        ldap3 = pytest.importorskip("ldap3")
        from radicale.auth import ldap as ldap_auth
        from radicale.tests.test_auth_servers import OWNER_DN, _MockLdap

        directory = _MockLdap()
        directory.add(OWNER_DN, uid="owner", userPassword="secret")
        binds = []
        ldap_auth.Auth._ldap_attributes = []
        try:
            with directory.patch():
                inner = ldap3.Connection

                def factory(*args, **kwargs):
                    conn = inner(*args, **kwargs)

                    def start_tls(*_args, **_kwargs):
                        raise ldap3.core.exceptions.LDAPSocketOpenError("socket down")

                    def bind(*_args, **_kwargs):
                        binds.append(args[1] if len(args) > 1 else None)
                        return True

                    conn.start_tls = start_tls
                    conn.bind = bind
                    return conn

                ldap3.Connection = factory
                self._configure_ldap3_reader()
                with pytest.raises(RuntimeError, match="Unable to reach LDAP server") as caught:
                    self.application._auth._login_ext_with_groups("owner", "secret", None)
                assert str(caught.value) == "Unable to reach LDAP server"
                assert isinstance(caught.value.__context__, ldap3.core.exceptions.LDAPSocketOpenError)
                assert str(caught.value.__context__) == "socket down"
                assert binds == []
        finally:
            ldap_auth.Auth._ldap_attributes = []

    def test_ldap3_reader_bind_false_is_unable_to_read(self, caplog):
        """StartTLS succeeded and the reader bind returned False.

        The mock raises on a bad reader password, so this is the only way to
        reach the False return. The reader password was already sent: the
        outcome is that the directory cannot be read.
        """
        ldap3 = pytest.importorskip("ldap3")
        from radicale.auth import ldap as ldap_auth
        from radicale.tests.test_auth_servers import OWNER_DN, _MockLdap

        caplog.set_level(logging.DEBUG)
        directory = _MockLdap()
        directory.add(OWNER_DN, uid="owner", userPassword="secret")
        ldap_auth.Auth._ldap_attributes = []
        try:
            with directory.patch():
                inner = ldap3.Connection

                def factory(*args, **kwargs):
                    conn = inner(*args, **kwargs)

                    def start_tls(*_args, **_kwargs):
                        return True

                    conn.start_tls = start_tls
                    if len(args) > 1 and args[1] == _MockLdap.reader_dn:
                        conn.bind = lambda *_a, **_k: False
                    return conn

                ldap3.Connection = factory
                self._configure_ldap3_reader()
                caplog.clear()
                with pytest.raises(RuntimeError, match="Unable to read from LDAP server") as caught:
                    self.application._auth._login_ext_with_groups("owner", "secret", None)
                assert str(caught.value) == "Unable to read from LDAP server"
                assert "cannot bind (reader)" in caplog.text
        finally:
            ldap_auth.Auth._ldap_attributes = []

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


class TestHookItems:
    """Path cleanup and content-type predicates."""

    def _item(self, path, content_type=None, content=None, uid=None,
              new_content=None, old_content=None):
        return HookNotificationItem(
            HookNotificationItemTypes.UPSERT, path, content=content,
            content_type=content_type, uid=uid, new_content=new_content,
            old_content=old_content)

    def test_point_is_empty_until_the_second_component(self):
        assert self._item("/").point == ""
        assert self._item("/user").point == ""
        assert self._item("/user/cal").point == "user/cal"
        assert self._item("/user/cal/").point == "user/cal"
        assert self._item("/user/cal/event.ics").point == "user/cal"

    def test_content_type_and_replacement_boundaries(self):
        assert self._item("/user/cal", content_type=None).is_calendar_item is False
        assert self._item("/user/cal", content_type="").is_calendar_item is False
        assert self._item("/user/cal", content_type=" vcalendar ").is_calendar_item is True
        assert self._item("/user/cal", content_type="vcalendarx").is_calendar_item is False
        assert self._item("/user/cal", content_type="").is_card_item is False
        assert self._item("/user/cal", content_type=" vcard ").is_card_item is True
        assert self._item("/user/cal", content_type="vcardx").is_card_item is False
        assert self._item("/user/cal", content_type="").is_addressbook_item is False
        assert self._item("/user/cal", content_type=" vaddressbook ").is_addressbook_item is True
        assert self._item("/user/cal", content_type="vaddressbookx").is_addressbook_item is False
        assert self._item("/user/cal", old_content=None).replaces_existing_item is False
        assert self._item("/user/cal", old_content="").replaces_existing_item is True

    def test_content_falls_back_and_json_includes_it(self):
        import json

        legacy = self._item("/user/cal", content="legacy", uid="uid",
                            new_content="new", old_content="old")
        assert legacy.content == "legacy"
        payload = json.loads(legacy.to_json())
        assert payload["content"] == "legacy"
        assert payload["point"] == "user/cal"
        assert self._item("/user/cal", uid="uid", new_content="new").content == "uid"
        assert self._item("/user/cal", new_content="new", old_content="old").content == "new"
        assert self._item("/user/cal", old_content="old").content == "old"


class TestRabbitmqGaps(BaseTest):
    def test_import_error_names_pika(self):
        saved = {}
        for name in list(sys.modules):
            if name == "radicale.hook.rabbitmq" or name == "pika" or name.startswith("pika."):
                saved[name] = sys.modules.pop(name)
        sys.modules["pika"] = None
        try:
            with pytest.raises(ImportError, match="pika"):
                import radicale.hook.rabbitmq  # noqa: F401
        finally:
            sys.modules.pop("pika", None)
            sys.modules.pop("radicale.hook.rabbitmq", None)
            sys.modules.update(saved)

    def test_notify_ignores_objects_that_are_not_notification_items(self, caplog):
        caplog.set_level(logging.WARNING)
        self.configure({"hook": {
            "type": "rabbitmq",
            "dryrun": "True",
            "rabbitmq_endpoint": "amqp://127.0.0.1/",
            "rabbitmq_topic": "radicale",
            "rabbitmq_queue_type": "classic",
        }})
        self.application._hook.notify(object())
        assert "DRY-RUN _notify" not in caplog.text


class TestEmailParser:
    """Enum parsing and vobject property edges."""

    def test_security_and_verify_enums_reject_near_misses(self):
        from radicale.hook.email import (SMTP_SECURITY_TYPE_ENUM,
                                         SMTP_SSL_VERIFY_MODE_ENUM,
                                         extract_email)

        assert SMTP_SECURITY_TYPE_ENUM.from_string("starttls") is SMTP_SECURITY_TYPE_ENUM.STARTTLS
        assert SMTP_SECURITY_TYPE_ENUM.from_string("") is SMTP_SECURITY_TYPE_ENUM.EMPTY
        assert SMTP_SECURITY_TYPE_ENUM.from_string("tls") is SMTP_SECURITY_TYPE_ENUM.TLS
        with pytest.raises(ValueError, match="Invalid security type"):
            SMTP_SECURITY_TYPE_ENUM.from_string("start-tls")
        assert SMTP_SSL_VERIFY_MODE_ENUM.from_string("REQUIRED") is SMTP_SSL_VERIFY_MODE_ENUM.REQUIRED
        assert SMTP_SSL_VERIFY_MODE_ENUM.from_string("") is SMTP_SSL_VERIFY_MODE_ENUM.EMPTY
        assert SMTP_SSL_VERIFY_MODE_ENUM.from_string("NONE") is SMTP_SSL_VERIFY_MODE_ENUM.NONE
        with pytest.raises(ValueError, match="Invalid SSL verify mode"):
            SMTP_SSL_VERIFY_MODE_ENUM.from_string("required")
        assert extract_email(None) is None
        assert extract_email("") is None
        assert extract_email("A@B.com") == "a@b.com"
        assert extract_email("not-an-email") is None

    def test_component_properties_templates_and_config_repr(self):
        import vobject

        from radicale.hook.email import (Alarm, Attendee, Calendar,
                                         ContentLine, DaylightTimezone,
                                         EmailConfig, Event, MessageTemplate,
                                         StandardTimezone, TimeWithTimezone,
                                         Timezone)

        with pytest.raises(ValueError, match="must be a vobject"):
            Event(object())
        with pytest.raises(ValueError, match="Invalid component type"):
            Event(vobject.base.Component("VTODO"))

        def line(name, value, params=None):
            return vobject.base.ContentLine(name, params or {}, value)

        alarm = vobject.base.Component("VALARM")
        alarm.contents["action"] = line("action", "DISPLAY")
        alarm.contents["description"] = [line("description", "Wake")]
        alarm.contents["trigger"] = [line("trigger", timedelta(minutes=-5))]
        alarm.contents["repeat"] = [line("repeat", "2")]
        alarm.contents["duration"] = [line("duration", "PT5M")]
        parsed = Alarm(alarm)
        assert parsed.action == "DISPLAY"
        assert parsed.description == "Wake"
        assert parsed.trigger == timedelta(minutes=-5)
        assert parsed.repeat == 2
        assert parsed.duration == "PT5M"
        assert Alarm(vobject.base.Component("VALARM")).repeat is None

        start = datetime(2030, 1, 1, 11, 0, 0)
        stamped = TimeWithTimezone(ContentLine("dtstart", start, {"TZID": ["UTC"]}))
        assert stamped.timezone_id == "UTC"
        assert stamped.time_string() == "2030-01-01 11:00:00"
        assert TimeWithTimezone(ContentLine("dtstart", None, {})).time_string() is None

        std = vobject.base.Component("STANDARD")
        std.contents["dtstart"] = [line("dtstart", start)]
        std.contents["tzname"] = [line("tzname", "EST")]
        std.contents["tzoffsetfrom"] = [line("tzoffsetfrom", "-0500")]
        std.contents["tzoffsetto"] = [line("tzoffsetto", "-0400")]
        zone = vobject.base.Component("VTIMEZONE")
        zone.contents["tzid"] = [line("tzid", "America/New_York")]
        object.__setattr__(zone, "standard", [std, "nope"])
        parsed_zone = Timezone(zone)
        assert parsed_zone.timezone_id == "America/New_York"
        assert parsed_zone.standard.timezone_name == "EST"
        assert parsed_zone.standard.timezone_offset_from == "-0500"
        assert parsed_zone.standard.timezone_offset_to == "-0400"
        assert parsed_zone.standard.datetime_start == start
        assert parsed_zone.daylight is None
        day = vobject.base.Component("DAYLIGHT")
        day.contents["tzname"] = [line("tzname", "EDT")]
        assert DaylightTimezone(day).timezone_name == "EDT"
        assert StandardTimezone(std).timezone_name == "EST"

        event = vobject.base.Component("VEVENT")
        event.contents["dtstamp"] = [line("dtstamp", "20300101T000000Z")]
        event.contents["dtstart"] = [line("dtstart", start, {"TZID": ["UTC"]})]
        event.contents["summary"] = [line("summary", "Title")]
        event.contents["uid"] = [line("uid", "u1")]
        object.__setattr__(event, "valarm", [alarm, "nope"])
        parsed_event = Event(event)
        assert parsed_event.datetime_stamp == "20300101T000000Z"
        assert parsed_event.summary == "Title"
        assert len(parsed_event.alarms) == 1
        assert parsed_event.alarms[0].action == "DISPLAY"

        alice = Attendee(ContentLine(
            "attendee", "mailto:alice@example.com",
            {"ROLE": ["REQ-PARTICIPANT"], "PARTSTAT": ["ACCEPTED"],
             "CN": ["Alice"], "DELEGATED-FROM": ["mailto:boss@example.com"]}))
        bob = Attendee(ContentLine("attendee", "mailto:bob@example.com", {}))
        assert alice.role == "REQ-PARTICIPANT"
        assert alice.participation_status == "ACCEPTED"
        assert alice.name == "Alice"
        assert alice.delegated_from == "boss@example.com"
        assert bob.role is None
        assert bob.delegated_from is None

        calendar = vobject.base.Component("VCALENDAR")
        calendar.contents["version"] = [line("version", "2.0")]
        calendar.contents["prodid"] = [line("prodid", "-//Test//EN")]
        object.__setattr__(calendar, "vevent", [event])
        object.__setattr__(calendar, "vtimezone", [zone, "nope"])
        parsed_calendar = Calendar(calendar)
        assert parsed_calendar.version == "2.0"
        assert parsed_calendar.product_id == "-//Test//EN"
        assert parsed_calendar.event.uid == "u1"
        assert parsed_calendar.timezone.timezone_id == "America/New_York"

        with pytest.raises(ValueError, match="Invalid subject template"):
            MessageTemplate("Hello $nope", "Body")
        with pytest.raises(ValueError, match="Invalid body template"):
            MessageTemplate("Hello", "Body $nope")
        template = MessageTemplate("Hello $attendee_name", "Body $attendee_name")
        assert "Hello $attendee_name" in repr(template)
        assert str(template) == "Hello $attendee_name: Body $attendee_name"
        config = EmailConfig(
            "smtp.example", 25, "none", "NONE", "", "", "calendar@example.com",
            False, True, template, template, template)
        assert "smtp.example" in repr(config)


class TestEmailHookGaps(BaseTest):
    """SMTP outcomes and the iTIP / legacy notification edges."""

    def _install_smtp(self, monkeypatch):
        import radicale.hook.email as email_hook

        class FakeSMTP:
            messages = []
            fail_after = None
            errors = None
            require_login = False
            logged_in = None

            def __init__(self, host=None, port=None, context=None, **kwargs):
                self.host = host
                self.port = port

            def ehlo(self):
                return (250, b"ok")

            def starttls(self, context=None, **kwargs):
                return (220, b"ready")

            def login(self, user=None, password=None, **kwargs):
                FakeSMTP.logged_in = (user, password)
                return (235, b"ok")

            def sendmail(self, from_addr, to_addrs, msg):
                if FakeSMTP.require_login and FakeSMTP.logged_in is None:
                    raise email_hook.smtplib.SMTPException("not logged in")
                if (FakeSMTP.fail_after is not None and
                        len(FakeSMTP.messages) >= FakeSMTP.fail_after):
                    raise email_hook.smtplib.SMTPException("send failed")
                FakeSMTP.messages.append((from_addr, list(to_addrs), msg))
                return dict(FakeSMTP.errors or {})

            def quit(self):
                return (221, b"bye")

        FakeSMTP.messages = []
        FakeSMTP.fail_after = None
        FakeSMTP.errors = None
        FakeSMTP.require_login = False
        FakeSMTP.logged_in = None
        monkeypatch.setattr(email_hook.smtplib, "SMTP", FakeSMTP)
        monkeypatch.setattr(email_hook.smtplib, "SMTP_SSL", FakeSMTP)
        return FakeSMTP

    def _hook(self, monkeypatch, **hook):
        smtp = self._install_smtp(monkeypatch)
        config = {
            "type": "email",
            "dryrun": "False",
            "smtp_server": "127.0.0.1",
            "smtp_port": "2525",
            "smtp_security": "none",
            "from_email": "calendar@example.com",
        }
        config.update(hook)
        self.configure({"hook": config})
        return self.application._hook, smtp

    def _notify(self, hook, kind, new=None, old=None, actor="owner",
                content_type="VCALENDAR"):
        item = HookNotificationItem(
            kind, "/owner/cal/event.ics", content_type=content_type,
            new_content=new, old_content=old, actor=actor)
        hook.notify(item)
        return item

    def test_smtp_login_partial_failure_and_undeliverable_addresses(self, monkeypatch, caplog):
        from radicale.hook.email import Attendee, ContentLine

        caplog.set_level(logging.WARNING)
        hook, smtp = self._hook(
            monkeypatch, smtp_username="mailer", smtp_password="secret")
        smtp.require_login = True
        event = _event_ics(attendees=[("a@b.com", "Ann"), ("c@d.com", "Cy")])
        import radicale.hook.email as email_hook
        email_event = email_hook._read_event(event)
        assert hook.email_config.send_added_email(
            email_event.event.attendees, email_event) is True
        assert smtp.logged_in == ("mailer", "secret")
        assert len(smtp.messages) == 2

        smtp.messages.clear()
        smtp.logged_in = ("mailer", "secret")
        smtp.fail_after = 1
        assert hook.email_config.send_added_email(
            email_event.event.attendees, email_event) is False
        assert len(smtp.messages) == 1

        smtp.fail_after = None
        smtp.messages.clear()
        smtp.errors = {"a@b.com": (550, b"no such user")}
        caplog.clear()
        assert hook.email_config.send_added_email(
            [email_event.event.attendees[0]], email_event) is False
        assert "a@b.com" in caplog.text
        assert len(smtp.messages) == 1

        smtp.errors = None
        smtp.messages.clear()
        bad = Attendee(ContentLine("attendee", "not-an-email", {"CN": ["X"]}))
        caplog.clear()
        assert hook.email_config.send_added_email([bad], email_event) is False
        assert "No valid email" in caplog.text
        assert smtp.messages == []

    def test_scheduling_kinds_choose_templates_and_send(self, monkeypatch):
        from radicale.hook.email.scheduling import PlannedMessage

        hook, smtp = self._hook(monkeypatch)
        import radicale.hook.email as email_hook
        ics = _event_ics(attendees=[("carol@example.com", "Carol")], summary="Standup")
        email_event = email_hook._read_event(ics)
        subjects = {
            "created": "You have been added to an event",
            "added": "You have been added to an event",
            "removed": "An event you were invited to has been deleted",
            "deleted": "An event you were invited to has been deleted",
            "updated": "An event you are invited to has been updated",
        }
        for kind, subject in subjects.items():
            smtp.messages.clear()
            method = "CANCEL" if kind in ("removed", "deleted") else "REQUEST"
            planned = PlannedMessage(method, "carol@example.com", "Carol", kind)
            assert hook.email_config.send_scheduling_email(
                planned, email_event, ics) is True
            _addr, recipients, message = smtp.messages[0]
            decoded = _mail_text(message)
            assert recipients == ["carol@example.com"]
            assert subject in message
            assert "Hello Carol" in message
            assert "text/calendar" in message
            assert "METHOD:%s" % method in decoded

        smtp.messages.clear()
        missing = PlannedMessage("REQUEST", "nobody@example.com", "Nobody", "created")
        assert hook.email_config.send_scheduling_email(missing, email_event, ics) is False
        assert smtp.messages == []

    def test_itip_cancel_uses_the_higher_sequence_plus_one(self, monkeypatch):
        hook, smtp = self._hook(
            monkeypatch, itip_enabled="True",
            itip_owner_map='{"owner": "owner@example.com"}')
        old = _event_ics(summary="OldTitle", sequence=2, attendees=[
            ("alice@example.com", "Alice"), ("bob@example.com", "Bob")])
        new = _event_ics(summary="NewTitle", sequence=9, attendees=[
            ("alice@example.com", "Alice"), ("carol@example.com", "Carol")])
        self._notify(hook, HookNotificationItemTypes.UPSERT, new=new, old=old)
        by_to = {message.split("To: ", 1)[1].splitlines()[0]: _mail_text(message)
                 for _addr, _rcpt, message in smtp.messages}
        assert "OldTitle" in by_to["bob@example.com"]
        assert "SEQUENCE:10" in by_to["bob@example.com"]
        assert "NewTitle" in by_to["carol@example.com"]
        assert "SEQUENCE:9" in by_to["carol@example.com"]

    def test_cancel_sequence_uses_zero_when_one_side_does_not_parse(self, monkeypatch):
        from radicale.hook.email.scheduling import PlannedMessage

        hook, smtp = self._hook(monkeypatch, itip_enabled="True",
                                itip_owner_map='{"owner": "owner@example.com"}')
        import radicale.hook.email as email_hook
        previous = _event_ics(summary="OldTitle", sequence=4,
                              attendees=[("bob@example.com", "Bob")])
        email_event = email_hook._read_event(previous)
        hook._send_planned(
            [PlannedMessage("CANCEL", "bob@example.com", "Bob", "removed")],
            email_event, previous, "not a calendar")
        assert "SEQUENCE:5" in _mail_text(smtp.messages[0][2])
        assert "OldTitle" in smtp.messages[0][2]

        smtp.messages.clear()
        recurrence = _event_ics(summary="Override", sequence=4, recurrence=True,
                                attendees=[("bob@example.com", "Bob")])
        new = _event_ics(summary="NewTitle", sequence=6,
                         attendees=[("bob@example.com", "Bob")])
        hook._send_planned(
            [PlannedMessage("CANCEL", "bob@example.com", "Bob", "removed")],
            email_hook._read_event(recurrence), recurrence, new)
        assert "SEQUENCE:7" in _mail_text(smtp.messages[0][2])

    def test_mass_email_guard_sends_nothing_for_itip(self, monkeypatch, caplog):
        caplog.set_level(logging.ERROR)
        hook, smtp = self._hook(
            monkeypatch, itip_enabled="True",
            itip_owner_map='{"owner": "owner@example.com"}')
        hook.email_config.send_mass_emails = True
        self._notify(hook, HookNotificationItemTypes.UPSERT, new=_event_ics())
        assert smtp.messages == []
        assert "mass_email is incompatible" in caplog.text

    def test_unknown_cpatch_and_foreign_items_send_nothing(self, monkeypatch, caplog):
        caplog.set_level(logging.WARNING)
        hook, smtp = self._hook(monkeypatch)
        item = self._notify(hook, HookNotificationItemTypes.UPSERT, new=_event_ics())
        smtp.messages.clear()
        caplog.clear()
        item.type = "explode"
        hook.notify(item)
        assert smtp.messages == []
        assert "Unknown notification item type" in caplog.text

        caplog.clear()
        self._notify(hook, HookNotificationItemTypes.CPATCH, new=_event_ics())
        assert smtp.messages == []
        assert "New event detected" not in caplog.text

        class Calendarish:
            is_calendar_item = True

        hook.notify(Calendarish())
        assert smtp.messages == []

    def test_todo_upsert_and_delete_send_nothing(self, monkeypatch, caplog):
        caplog.set_level(logging.DEBUG)
        hook, smtp = self._hook(monkeypatch)
        self._notify(hook, HookNotificationItemTypes.UPSERT, new=_todo_ics())
        assert smtp.messages == []
        assert "No event found" in caplog.text
        assert "Failed to read" not in caplog.text
        caplog.clear()
        self._notify(hook, HookNotificationItemTypes.DELETE, old=_todo_ics())
        assert smtp.messages == []
        assert "No event found" in caplog.text

    def test_event_without_end_is_still_mailed(self, monkeypatch):
        hook, smtp = self._hook(monkeypatch)
        self._notify(hook, HookNotificationItemTypes.UPSERT,
                     new=_event_ics(dtend=False, attendees=[("bob@example.com", "Bob")]))
        assert len(smtp.messages) == 1
        assert "Hello Bob" in smtp.messages[0][2]

    def test_unreadable_event_and_null_event_are_skipped(self, monkeypatch, caplog):
        import radicale.hook.email as email_hook

        caplog.set_level(logging.ERROR)
        hook, smtp = self._hook(monkeypatch)

        class Holder:
            event = None

        assert hook._is_past_event(Holder()) is False
        monkeypatch.setattr(email_hook, "_read_event", lambda vobject_data: None)
        self._notify(hook, HookNotificationItemTypes.UPSERT, new=_event_ics())
        assert smtp.messages == []
        assert "Failed to read event" in caplog.text

    def test_legacy_unparseable_previous_is_sent_as_new(self, monkeypatch, caplog):
        caplog.set_level(logging.WARNING)
        hook, smtp = self._hook(monkeypatch)
        new = _event_ics(attendees=[("bob@example.com", "Bob")])
        self._notify(hook, HookNotificationItemTypes.UPSERT, new=new, old=_todo_ics())
        assert len(smtp.messages) == 1
        assert "treating as a new event" in caplog.text

        smtp.messages.clear()
        smtp.fail_after = 0
        caplog.clear()
        self._notify(hook, HookNotificationItemTypes.UPSERT, new=new, old=_todo_ics())
        assert smtp.messages == []
        assert "treating as a new event" in caplog.text
        assert "Failed to send some or all added" in caplog.text

    def test_legacy_read_of_new_event_none_sends_nothing(self, monkeypatch, caplog):
        import radicale.hook.email as email_hook

        caplog.set_level(logging.WARNING)
        hook, smtp = self._hook(monkeypatch)
        ics = _event_ics()
        email_event = email_hook._read_event(ics)
        monkeypatch.setattr(email_hook, "read_ics_event", lambda contents: None)
        hook._process_legacy_upsert(ics, ics, email_event)
        assert smtp.messages == []
        assert "treating as a new event" not in caplog.text

    def test_legacy_unchanged_details_send_nothing(self, monkeypatch):
        hook, smtp = self._hook(monkeypatch)
        ics = _event_ics(attendees=[("bob@example.com", "Bob")])
        self._notify(hook, HookNotificationItemTypes.UPSERT, new=ics, old=ics)
        assert smtp.messages == []

    def test_legacy_send_failures_are_logged(self, monkeypatch, caplog):
        caplog.set_level(logging.ERROR)
        hook, smtp = self._hook(monkeypatch)
        smtp.fail_after = 0
        self._notify(hook, HookNotificationItemTypes.UPSERT, new=_event_ics())
        assert "Failed to send some or all added" in caplog.text

        caplog.clear()
        old = _event_ics(attendees=[("bob@example.com", "Bob")])
        new = _event_ics(attendees=[("carol@example.com", "Carol")])
        self._notify(hook, HookNotificationItemTypes.UPSERT, new=new, old=old)
        assert "Failed to send some or all added" in caplog.text
        assert "Failed to send some or all deleted" in caplog.text

        caplog.clear()
        updated = _event_ics(summary="Changed", attendees=[("bob@example.com", "Bob")])
        self._notify(hook, HookNotificationItemTypes.UPSERT, new=updated, old=old)
        assert "Failed to send some or all updated" in caplog.text

        caplog.clear()
        self._notify(hook, HookNotificationItemTypes.DELETE, old=old)
        assert "Failed to send some or all deleted" in caplog.text

    def test_legacy_attendee_changes_are_mailed_when_send_succeeds(self, monkeypatch, caplog):
        caplog.set_level(logging.ERROR)
        hook, smtp = self._hook(monkeypatch)
        old = _event_ics(summary="Standup", attendees=[
            ("alice@example.com", "Alice"), ("bob@example.com", "Bob")])
        new = _event_ics(summary="Moved", attendees=[
            ("bob@example.com", "Bob"), ("carol@example.com", "Carol")])
        self._notify(hook, HookNotificationItemTypes.UPSERT, new=new, old=old)
        by_to = {addrs[0]: message for _addr, addrs, message in smtp.messages}
        assert set(by_to) == {"alice@example.com", "bob@example.com", "carol@example.com"}
        assert "has been deleted" in by_to["alice@example.com"]
        assert "has been updated" in by_to["bob@example.com"]
        assert "have been added" in by_to["carol@example.com"]
        assert "Failed to send" not in caplog.text

    def test_itip_unparseable_previous_sends_nothing(self, monkeypatch, caplog):
        caplog.set_level(logging.ERROR)
        hook, smtp = self._hook(
            monkeypatch, itip_enabled="True",
            itip_owner_map='{"owner": "owner@example.com"}')
        self._notify(hook, HookNotificationItemTypes.UPSERT,
                     new=_event_ics(), old=_todo_ics())
        assert smtp.messages == []
        assert "could not be parsed" in caplog.text

    def test_itip_delete_sends_cancel(self, monkeypatch, caplog):
        caplog.set_level(logging.ERROR)
        hook, smtp = self._hook(
            monkeypatch, itip_enabled="True",
            itip_owner_map='{"owner": "owner@example.com"}')
        old = _event_ics(sequence=2, attendees=[("bob@example.com", "Bob")])
        self._notify(hook, HookNotificationItemTypes.DELETE, old=old)
        assert "SEQUENCE:3" in _mail_text(smtp.messages[0][2])
        assert "Reply-To:" not in smtp.messages[0][2]
        smtp.messages.clear()
        smtp.fail_after = 0
        self._notify(hook, HookNotificationItemTypes.DELETE, old=old)
        assert smtp.messages == []
        assert "Failed to send scheduling notification" in caplog.text

    def test_itip_reply_to_is_the_mapped_owner_or_absent(self, monkeypatch):
        hook, smtp = self._hook(
            monkeypatch, itip_enabled="True", itip_owner_reply_to="True",
            itip_owner_map='{"owner": "owner@example.com"}')
        ics = _event_ics(attendees=[("bob@example.com", "Bob")])
        self._notify(hook, HookNotificationItemTypes.UPSERT, new=ics,
                     actor=" owner ")
        assert len(smtp.messages) == 1
        assert "Reply-To: owner@example.com" in smtp.messages[0][2]
        assert "Reply-To: calendar@example.com" not in smtp.messages[0][2]

        # A blank actor is not an owner, so the delete sends nothing.
        smtp.messages.clear()
        self._notify(hook, HookNotificationItemTypes.DELETE, old=ics, actor="")
        assert smtp.messages == []
        blank = HookNotificationItem(
            HookNotificationItemTypes.DELETE, "/owner/cal/event.ics",
            content_type="VCALENDAR", old_content=ics, actor="")
        assert hook._owner_reply_to(blank) is None
        blank.actor = None
        assert hook._owner_reply_to(blank) is None
        missing = HookNotificationItem(
            HookNotificationItemTypes.DELETE, "/owner/cal/event.ics",
            content_type="VCALENDAR", old_content=ics)
        assert hook._owner_reply_to(missing) is None

    def test_one_attendee_mass_email_skips_trace_when_debug_is_off(self, monkeypatch):
        from radicale.log import logger

        hook, smtp = self._hook(monkeypatch, mass_email="True")
        logger.setLevel(logging.INFO)

        def trace(*args, **kwargs):
            raise AssertionError("trace called")

        monkeypatch.setattr(logger, "trace", trace)
        self._notify(hook, HookNotificationItemTypes.UPSERT,
                     new=_event_ics(attendees=[("bob@example.com", "Bob")]))
        assert len(smtp.messages) == 1
        assert "Hello Bob" in smtp.messages[0][2]
        assert "everyone" not in smtp.messages[0][2]

    def test_security_outside_the_enum_does_not_open_a_tls_socket(self, monkeypatch):
        hook, _smtp = self._hook(monkeypatch)
        hook.email_config.security = "bogus"
        with pytest.raises(UnboundLocalError):
            hook.email_config._smtp_send("text", ["a@b.com"])

    def test_delete_branch_is_not_taken_for_a_foreign_type(self, monkeypatch):
        hook, smtp = self._hook(monkeypatch)
        monkeypatch.setattr(hook, "_notification_type", lambda item: "other")
        self._notify(hook, HookNotificationItemTypes.UPSERT, new=_event_ics())
        assert smtp.messages == []


class TestSchedulingGaps:
    """Planner and iTIP builder edges."""

    def test_extract_email_and_parse_edges(self):
        from radicale.hook.email import scheduling

        assert scheduling.extract_email(None) is None
        assert scheduling.extract_email("") is None
        assert scheduling.extract_email("  ") is None
        assert scheduling.extract_email("A@B.c") == "a@b.c"
        assert scheduling.extract_email("nope") is None
        assert scheduling.extract_email("MAILTO:A@B.c;x") == "a@b.c"
        assert scheduling.parse_event(None) is None
        assert scheduling.parse_event("") is None
        empty = "BEGIN:VCALENDAR\nVERSION:2.0\nEND:VCALENDAR\n"
        assert scheduling.parse_event(empty) is None
        no_organizer = _event_ics(organizer=None, attendees=[])
        parsed = scheduling.parse_event(no_organizer)
        assert parsed.organizer_email is None
        assert parsed.organizer_schedule_agent is None
        assert scheduling.plan_messages(
            None, no_organizer, owner_identities=["a@b.com"]) == []
        messy = "\n".join([
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "BEGIN:VEVENT",
            "UID:u",
            "DTSTART:20300101T110000Z",
            "SUMMARY:S",
            "SEQUENCE:nope",
            "ORGANIZER:mailto:a@b.com",
            "ATTENDEE:mailto:A@B.com",
            "ATTENDEE:mailto:a@b.com",
            "ATTENDEE:not-an-email",
            "END:VEVENT",
            "END:VCALENDAR",
            "",
        ])
        parsed = scheduling.parse_event(messy)
        assert parsed.sequence == 0
        assert list(parsed.attendees) == ["a@b.com"]

    def test_owner_map_and_ownership_skip_blanks(self):
        from radicale.hook.email import scheduling

        rules = scheduling.parse_owner_map('{"owner": "owner@example.com"}')
        # No actor, and an actor that is only whitespace, produce no address.
        # An actor with surrounding space still maps: that is just outside empty.
        assert scheduling.mapped_owner_email(None, rules) is None
        assert scheduling.mapped_owner_email("", rules) is None
        assert scheduling.mapped_owner_email("   ", rules) is None
        assert scheduling.mapped_owner_email(" owner ", rules) == "owner@example.com"
        assert scheduling.mapped_owner_email("other", rules) is None

        # Blank identities are skipped. A later real address still matches,
        # and a whitespace-only identity does not.
        assert scheduling.check_ownership(
            "A@B.com", ["", None, "a@b.com"]) is True
        assert scheduling.check_ownership("a@b.com", ["", None, "   "]) is False
        assert scheduling.check_ownership("", ["a@b.com"]) is False
        assert scheduling.check_ownership(None, ["a@b.com"]) is False
        assert scheduling.check_ownership("  A@B.com ", ["a@b.com"]) is True

    def test_plan_rejects_unparseable_multivevent_and_organizer_change(self):
        from radicale.hook.email import scheduling

        assert scheduling._vevent_count("") == 0
        assert scheduling._vevent_count(None) == 0
        assert scheduling._vevent_count("@@@") == 0
        assert scheduling._vevent_count(
            "BEGIN:VCALENDAR\nVERSION:2.0\nEND:VCALENDAR\n") == 0
        assert scheduling._vevent_count(_event_ics()) == 1
        assert scheduling.plan_messages("@@@", None, deleted=True,
                                        owner_identities=["owner@example.com"]) == []
        multi = "\n".join([
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "BEGIN:VEVENT",
            "UID:u",
            "DTSTART:20300101T110000Z",
            "DTEND:20300101T120000Z",
            "SUMMARY:Master",
            "ORGANIZER:mailto:owner@example.com",
            "ATTENDEE;CN=Bob:mailto:bob@example.com",
            "END:VEVENT",
            "BEGIN:VEVENT",
            "UID:u",
            "RECURRENCE-ID:20300102T110000Z",
            "DTSTART:20300102T110000Z",
            "DTEND:20300102T120000Z",
            "SUMMARY:Override",
            "ORGANIZER:mailto:owner@example.com",
            "ATTENDEE;CN=Bob:mailto:bob@example.com",
            "END:VEVENT",
            "END:VCALENDAR",
            "",
        ])
        assert scheduling.plan_messages(
            multi, None, deleted=True,
            owner_identities=["owner@example.com"]) == []
        old = _event_ics(summary="Same")
        assert scheduling.plan_messages(
            old, "garbage", owner_identities=["owner@example.com"]) == []
        changed = _event_ics(
            summary="Same", organizer="mailto:new@example.com",
            attendees=[("alice@example.com", "Alice"), ("c@d.com", "Cy")])
        assert scheduling.plan_messages(
            old, changed,
            owner_identities=["owner@example.com", "new@example.com"]) == []

    def test_vevent_count_without_a_list_attribute(self, monkeypatch):
        from radicale.hook.email import scheduling

        class FakeCalendar:
            vevent = object()

        monkeypatch.setattr(scheduling.vobject, "readOne", lambda text: FakeCalendar())
        assert scheduling._vevent_count("BEGIN:VCALENDAR") == 1

    def test_build_itip_rewrites_method_and_cancel_sequence(self):
        from radicale.hook.email import scheduling

        base = _event_ics(method="PUBLISH", attendees=[("bob@example.com", "Bob")])
        rewritten = scheduling.build_itip_ics(base, "REQUEST", "bob@example.com")
        assert "METHOD:REQUEST" in rewritten
        assert "PUBLISH" not in rewritten
        nope = _event_ics(sequence="nope", attendees=[("bob@example.com", "Bob")])
        cancelled = scheduling.build_itip_ics(nope, "CANCEL", "bob@example.com")
        assert "SEQUENCE:1" in cancelled
        plain = _event_ics(sequence=2, attendees=[("bob@example.com", "Bob")],
                           dtstamp=False)
        requested = scheduling.build_itip_ics(plain, "REQUEST", "bob@example.com")
        assert "METHOD:REQUEST" in requested
        missing_sequence = _event_ics(sequence=None, attendees=[("bob@example.com", "Bob")])
        added = scheduling.build_itip_ics(missing_sequence, "CANCEL", "bob@example.com")
        assert "METHOD:CANCEL" in added
        assert "SEQUENCE:1" in added
        assert "mailto:bob@example.com" in added.lower()

    def test_cancel_without_sequence_is_still_built_when_add_fails(self, monkeypatch):
        import vobject

        from radicale.hook.email import scheduling

        original = vobject.base.Component.add

        def add(self, name, group=None):
            if isinstance(name, str) and name.lower() == "sequence":
                raise RuntimeError("sequence store failed")
            return original(self, name, group)

        monkeypatch.setattr(vobject.base.Component, "add", add)
        source = _event_ics(sequence=None, attendees=[("bob@example.com", "Bob")])
        cancelled = scheduling.build_itip_ics(source, "CANCEL", "bob@example.com")
        assert "METHOD:CANCEL" in cancelled
        assert "SEQUENCE" not in cancelled
        assert "mailto:bob@example.com" in cancelled.lower()
        no_attendees = _event_ics(attendees=[])
        with pytest.raises(ValueError, match="not an attendee"):
            scheduling.build_itip_ics(no_attendees, "REQUEST", "bob@example.com")
        with pytest.raises(ValueError, match="not an attendee"):
            scheduling.build_itip_ics(
                _event_ics(attendees=[("alice@example.com", "Alice")]),
                "REQUEST", "bob@example.com")
