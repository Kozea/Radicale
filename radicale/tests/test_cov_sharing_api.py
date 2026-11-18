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

"""Outcome tests for the sharing HTTP API."""

import base64
import contextlib
import json
import logging
import os
import pickle
import shutil
import socket
import wsgiref.util
from io import BytesIO

import radicale.sharing as sharing_pkg
from radicale import sharing
from radicale.log import logger
from radicale.sharing import files as files_sharing
from radicale.tests import BaseTest
from radicale.tests.helpers import get_file_content

TRACE = 5
_OMIT = object()


def _restore_mode(path, mode):
    try:
        os.chmod(path, mode)
    except OSError:
        return False
    return True


def _writes_blocked(path):
    """True when this user cannot create or append on path."""
    if os.path.isdir(path):
        probe = os.path.join(path, ".cov-write-probe")
        try:
            fd = os.open(probe, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except OSError:
            return True
        os.close(fd)
        os.remove(probe)
        return False
    try:
        fd = os.open(path, os.O_WRONLY | os.O_APPEND)
    except OSError:
        return True
    os.close(fd)
    return False


def _restrict_writes(path, mode):
    """Apply mode. True only when a later write by this user fails."""
    try:
        os.chmod(path, mode)
    except OSError:
        return False
    return _writes_blocked(path)


class _TimeoutStream:
    def read(self, size=-1):
        raise socket.timeout("timed out")


class _FixedUUID:
    def __init__(self, payload):
        self.bytes = payload


class _InitOnly(sharing.BaseSharing):
    """Base hooks stay in place; only initialization succeeds."""

    def database_init(self):
        return True


class _MemorySharing(sharing.BaseSharing):
    """In-memory database hooks so verify() can see crafted rows."""

    script_init = True
    script_init_error = None
    script_info = {"type": "memory"}
    script_verify = True
    script_rows: list[dict] = []

    def database_init(self):
        if self.script_init_error is not None:
            raise self.script_init_error
        return self.script_init

    def database_get_info(self):
        return self.script_info

    def database_verify(self):
        return self.script_verify

    def database_list_sharing(self, *args, **kwargs):
        return list(self.script_rows)


def _memory_sharing(configuration, rows=None, verify_db=True, info=_OMIT,
                    init=True, init_error=None):
    if info is _OMIT:
        info = {"type": "memory"}
    _MemorySharing.script_rows = [] if rows is None else rows
    _MemorySharing.script_verify = verify_db
    _MemorySharing.script_info = info
    _MemorySharing.script_init = init
    _MemorySharing.script_init_error = init_error
    return _MemorySharing(configuration)


def _entry(**overrides):
    row = {
        "ShareType": "map",
        "PathOrToken": "/owner/alias.ics/",
        "PathMapped": "/owner/covcal.ics/",
        "Conversion": "none",
        "Owner": "owner",
        "User": "owner",
        "Permissions": "r",
        "EnabledByOwner": True,
        "EnabledByUser": True,
        "HiddenByOwner": False,
        "HiddenByUser": False,
        "TimestampCreated": 1,
        "TimestampUpdated": 1,
        "Properties": {},
        "Actions": {},
    }
    row.update(overrides)
    return row


class TestSharingCoverage(BaseTest):

    def setup_method(self):
        super().setup_method()
        self.htpasswd_file_path = os.path.join(self.colpath, ".htpasswd")
        self.htgroup_file_path = os.path.join(self.colpath, ".htgroup")
        # Not named htpasswd: CodeQL treats that assignment as a password
        # and reports the test fixture write as clear-text storage.
        accounts = "\n".join([
            "owner:ownerpw",
            "user:userpw",
            "user1:user1pw",
            "user2:user2pw",
            "outsider:outsiderpw",
            "user1@domain.example:user1@pw",
        ])
        htgroup = "\n".join(["group1:user1"])
        encoding = self.configuration.get("encoding", "stock")
        with open(self.htpasswd_file_path, "w", encoding=encoding) as handle:
            handle.write(accounts)
        with open(self.htgroup_file_path, "w", encoding=encoding) as handle:
            handle.write(htgroup)

    def _enable(self, backend="csv", group=False, **sharing_options):
        options = {
            "type": backend,
            "collection_by_map": "true",
            "collection_by_token": "true",
            "permit_create_map": "true",
            "permit_create_token": "true",
            "permit_properties_overlay": "false",
        }
        options.update(sharing_options)
        cfg = {
            "auth": {"type": "htpasswd",
                     "htpasswd_filename": self.htpasswd_file_path,
                     "htpasswd_encryption": "plain"},
            "rights": {"type": "owner_only"},
            "sharing": options,
        }
        if group:
            cfg["group"] = {"type": "htgroup",
                            "htgroup_filename": self.htgroup_file_path}
        self.configure(cfg)

    def _api(self, kind, action, payload, login="owner:ownerpw", check=200,
             accept="application/json", content_type="application/json"):
        if isinstance(payload, dict):
            data = json.dumps(payload)
        else:
            data = payload
        kwargs = {"login": login, "content_type": content_type}
        if accept is not None:
            kwargs["accept"] = accept
        status, headers, answer = self.request(
            "POST", "/.sharing/v1/%s/%s" % (kind, action),
            data, check=check, **kwargs)
        return status, headers, answer

    def _wsgi(self, path, body, login="owner:ownerpw", content_type=None,
              accept=None, content_length=None, stream=None):
        environ = {}
        wsgiref.util.setup_testing_defaults(environ)
        environ["REQUEST_METHOD"] = "POST"
        environ["PATH_INFO"] = path
        raw = body if isinstance(body, bytes) else body.encode("utf-8")
        environ["wsgi.input"] = stream if stream is not None else BytesIO(raw)
        length = len(raw) if content_length is None else content_length
        environ["CONTENT_LENGTH"] = str(length)
        if content_type:
            environ["CONTENT_TYPE"] = content_type
        if accept:
            environ["HTTP_ACCEPT"] = accept
        if login:
            token = base64.b64encode(login.encode("utf-8")).decode("ascii")
            environ["HTTP_AUTHORIZATION"] = "Basic " + token
        holder = {}

        def start_response(status, headers, exc_info=None):
            holder["status"] = int(status.split()[0])
            holder["headers"] = dict(headers)

        chunks = list(self.application(environ, start_response))
        answer = b"".join(chunks).decode()
        return holder["status"], holder["headers"], answer

    @contextlib.contextmanager
    def _patched(self, name, fn):
        target = self.application._sharing
        old = getattr(target, name)
        setattr(target, name, fn)
        try:
            yield
        finally:
            setattr(target, name, old)

    def _listed(self, kind="map", login="owner:ownerpw", payload=None):
        _, _, answer = self._api(kind, "list", payload or {}, login=login)
        return json.loads(answer)

    def _store_files_row(self, row, version=None):
        backend = self.application._sharing
        if version is None:
            version = files_sharing.DB_VERSION
        directory = backend._sharing_database_path_ShareType[row["ShareType"]]
        path = os.path.join(directory, backend._encode_path(row["PathOrToken"]))
        with open(path, "wb") as handle:
            pickle.dump((version, row), handle)
        return path

    def test_api_rejects_malformed_requests(self, caplog):
        self._enable("csv")
        collection = "/owner/covcal.ics/"
        self.mkcalendar(collection, login="owner:ownerpw")
        for level in (logging.DEBUG, logging.INFO):
            with caplog.at_level(level, logger="radicale"):
                self._api("bogus", "list", {}, check=404)
                self._api("map", "frobnicate", {}, check=404)
                status, _, answer = self._wsgi(
                    "/.sharing/v1/token", b"{}", content_type="application/json",
                    accept="application/json")
                assert status == 404
                assert answer
        self._api("map", "list", "{", check=400)
        _, _, answer = self._api(
            "map", "list", "", content_type="text/plain", check=400)
        assert "Content-type not supported" in answer
        _, _, answer = self._api(
            "map", "create",
            "Properties=nocolon&PathMapped=%s" % collection,
            content_type="application/x-www-form-urlencoded",
            accept="text/plain", check=400)
        assert "Invalid properties format" in answer
        _, _, answer = self._api(
            "map", "create", "Enabled=maybe",
            content_type="application/x-www-form-urlencoded",
            accept="text/plain", check=400)
        assert "Invalid non-boolean" in answer
        _, _, answer = self._api(
            "map", "create", "Enabled=yes",
            content_type="application/x-www-form-urlencoded",
            accept="text/plain", check=400)
        assert "Missing PathMapped" in answer

        status, _, answer = self._wsgi(
            "/.sharing/v1/map/list", b"{}", content_type="application/json",
            content_length=20)
        assert status == 400
        assert "Failed read POST request body" in answer
        status, _, answer = self._wsgi(
            "/.sharing/v1/map/list", b"", content_type="application/json",
            content_length=4, stream=_TimeoutStream())
        assert status == 408
        assert "timed out" in answer

        short = "/.token/v1/" + ("a" * 43) + "/"
        exact = "/.token/v1/" + ("a" * 44) + "/"
        long = "/.token/v1/" + ("a" * 45) + "/"
        _, _, answer = self._api(
            "token", "update", {"PathOrToken": short}, check=400)
        assert "Invalid value for PathOrToken" in answer
        _, _, answer = self._api(
            "token", "update", {"PathOrToken": long}, check=400)
        assert "Invalid value for PathOrToken" in answer
        self._api("token", "update", {"PathOrToken": exact}, check=404)
        _, _, answer = self._api(
            "map", "create",
            {"PathMapped": "/owner/bad*.ics/", "User": "user",
             "PathOrToken": "/user/x.ics/"}, check=400)
        assert "Invalid value for PathMapped" in answer
        _, _, answer = self._api(
            "token", "create",
            {"PathMapped": collection, "PathOrToken": exact}, check=400)
        assert "PathOrToken not supported" in answer
        _, _, answer = self._api(
            "all", "info", {}, accept="text/csv", check=400)
        assert "CSV output format is only allowed for list" in answer

        status, headers, answer = self._api(
            "all", "info", {}, accept=None)
        assert status == 200
        assert headers["Content-Type"].startswith("text/json")
        assert json.loads(answer)["Status"] == "success"
        _, _, answer = self._api("all", "info", {}, accept="text/plain")
        assert "Status='success'" in answer
        assert "FeatureEnabledCollectionByMap=True" in answer
        assert "SupportedConversions=(bday none)" in answer

    def test_api_create_boundaries(self, caplog):
        self._enable("csv")
        collection = "/owner/covcal.ics/"
        plain = "/owner/plain.ics/"
        self.mkcalendar(collection, login="owner:ownerpw")
        # owner_only grants "W" only on the home collection, so a tag-less
        # collection cannot be created through MKCOL.
        self.application._storage.create_collection(plain)
        event = get_file_content("event1.ics")
        self.put(collection + "event1.ics", event, login="owner:ownerpw")

        self._api("map", "create", {
            "User": "user", "PathMapped": collection, "Enabled": True,
        }, check=400)
        _, _, answer = self._api("map", "create", {
            "PathMapped": collection, "PathOrToken": "/user/need-user.ics/",
        }, check=400)
        assert "Missing User" in answer
        self._api("map", "create", {
            "User": "user", "PathMapped": collection,
            "PathOrToken": "/owner/foreign.ics/", "Permissions": "r",
        }, check=403)
        _, _, answer = self._api("map", "create", {
            "User": "user", "PathMapped": collection + "event1.ics/",
            "PathOrToken": "/user/item.ics/", "Permissions": "r",
        }, check=400)
        assert "not a collection" in answer
        _, _, answer = self._api("map", "create", {
            "User": "user", "PathMapped": collection,
            "PathOrToken": "/user/badprop.ics/", "Permissions": "r",
            "Properties": {"CR:addressbook-description": "nope"},
        }, check=400)
        assert "not supported to overlay" in answer
        created = self._api("map", "create", {
            "User": "user", "PathMapped": plain,
            "PathOrToken": "/user/plain.ics/", "Permissions": "r",
            "Enabled": True, "Hidden": False,
            "Properties": {"CR:addressbook-description": "kept"},
        })
        assert json.loads(created[2])["Status"] == "success"
        plain_rows = [row for row in self._listed()["Content"]
                      if row["PathOrToken"] == "/user/plain.ics/"]
        assert plain_rows[0]["Properties"]["CR:addressbook-description"] == "kept"
        _, _, answer = self._api("all", "create", {
            "PathMapped": collection, "User": "user",
            "PathOrToken": "/user/all.ics/",
        }, check=400)
        assert "Invalid share type" in answer
        self._api("all", "update", {"PathOrToken": "/user/plain.ics/"}, check=400)
        self._api("all", "delete", {"PathOrToken": "/user/plain.ics/"}, check=400)
        self._api("all", "hide", {"PathOrToken": "/user/plain.ics/"}, check=400)

        payload = "PathMapped=%s&PathOrToken=/user/form.ics/&User=user&Permissions=r&Enabled=true&Hidden=false&Properties=&Properties=D:displayname=FormName" % collection
        _, _, answer = self._api(
            "map", "create", payload,
            content_type="application/x-www-form-urlencoded",
            accept="text/plain")
        assert "Status='success'" in answer
        listed = self._listed()
        form_rows = [row for row in listed["Content"]
                     if row["PathOrToken"] == "/user/form.ics/"]
        assert form_rows[0]["Properties"]["D:displayname"] == "FormName"

        fixed = _FixedUUID(b"\x22" * 16)
        original = sharing_pkg.uuid.uuid4
        sharing_pkg.uuid.uuid4 = lambda: fixed
        try:
            for backend in ("csv", "files"):
                self._enable(backend)
                if not os.path.isdir(os.path.join(
                        self.colpath, "collection-root", "owner", "covcal.ics")):
                    self.mkcalendar(collection, login="owner:ownerpw")
                first = json.loads(self._api("token", "create", {
                    "PathMapped": collection, "Enabled": True, "Hidden": False,
                })[2])
                assert first["Status"] == "success"
                token = first["PathOrToken"]
                self._api("token", "create", {
                    "PathMapped": collection, "Enabled": True, "Hidden": False,
                }, check=409)
                if backend == "csv":
                    rows = [row for row in self.application._sharing._sharing_cache
                            if row.get("ShareType") == "token"
                            and row.get("PathOrToken") == token]
                    assert len(rows) == 1
                    assert rows[0]["Owner"] == "owner"
                else:
                    token_dir = self.application._sharing._sharing_database_path_ShareType["token"]
                    assert len(os.listdir(token_dir)) == 1
        finally:
            sharing_pkg.uuid.uuid4 = original

        self._enable("files")
        if not os.path.isdir(os.path.join(
                self.colpath, "collection-root", "owner", "covcal.ics")):
            self.mkcalendar(collection, login="owner:ownerpw")
        token_dir = self.application._sharing._sharing_database_path_ShareType["token"]
        token_blocked = _restrict_writes(token_dir, 0o555)
        try:
            caplog.clear()
            payload = {
                "PathMapped": collection, "User": "owner",
                "Enabled": True, "Hidden": False,
            }
            if token_blocked:
                self._api("token", "create", payload, check=500)
                assert "cannot store share-config" in caplog.text
            else:
                created = json.loads(self._api("token", "create", payload)[2])
                assert created["Status"] == "success"
                assert created["PathOrToken"]
        finally:
            _restore_mode(token_dir, 0o755)

        def weird(**kwargs):
            return {"status": "weird"}

        with self._patched("database_create_sharing", weird):
            _, _, answer = self._api("token", "create", {
                "PathMapped": collection, "User": "owner",
            }, check=400)
        assert "Internal Error" in answer

    def test_api_update_delete_toggle_results(self, caplog):
        self._enable("csv")
        collection = "/owner/covcal.ics/"
        shared = "/user/live.ics/"
        self.mkcalendar(collection, login="owner:ownerpw")
        event = get_file_content("event1.ics")
        self.put(collection + "event1.ics", event, login="owner:ownerpw")
        self._api("map", "create", {
            "User": "user", "PathMapped": collection, "PathOrToken": shared,
            "Permissions": "r", "Enabled": True, "Hidden": False,
            "Actions": {"config": {"view": "freebusy",
                                   "conversion_bday_categories": "Old"}},
        })
        self._api("map", "update", {
            "PathOrToken": shared,
            "Actions": {"config": {"view": "freebusy", "format": "vevent"}},
        })
        row = [item for item in self._listed()["Content"]
               if item["PathOrToken"] == shared][0]
        assert row["Actions"]["config"]["conversion_bday_categories"] == "Old"
        assert row["Actions"]["config"]["format"] == "vevent"
        self._api("map", "update", {
            "PathOrToken": shared,
            "Actions": {"config": {
                "view": sharing.SHARING_ACTIONS_DELETE_VALUE,
                "format": sharing.SHARING_ACTIONS_DELETE_VALUE,
                "conversion_bday_categories": sharing.SHARING_ACTIONS_DELETE_VALUE,
            }},
        })
        row = [item for item in self._listed()["Content"]
               if item["PathOrToken"] == shared][0]
        assert row["Actions"] == {}
        self._api("map", "update", {
            "PathOrToken": shared,
            "Actions": {"config": {"view": "freebusy"}},
        })
        self._api("map", "update", {"PathOrToken": shared, "Actions": {}})
        row = [item for item in self._listed()["Content"]
               if item["PathOrToken"] == shared][0]
        assert row["Actions"] == {}

        self.application._sharing.database_update_sharing(
            ShareType="map", PathOrToken=shared,
            PathMapped=collection + "event1.ics", OwnerOrUser="owner")
        _, _, answer = self._api(
            "map", "update", {"PathOrToken": shared, "Hidden": True}, check=400)
        assert "not a collection" in answer
        self.application._sharing.database_update_sharing(
            ShareType="map", PathOrToken=shared, PathMapped=collection,
            OwnerOrUser="owner")
        shutil.rmtree(os.path.join(
            self.colpath, "collection-root", "owner", "covcal.ics"))
        self._api("map", "update", {"PathOrToken": shared, "Hidden": False},
                  check=404)
        self.mkcalendar(collection, login="owner:ownerpw")

        self._enable("files")
        self._api("map", "create", {
            "User": "user", "PathMapped": collection,
            "PathOrToken": "/user/fileshare.ics/",
            "Permissions": "r", "Enabled": True, "Hidden": False,
        })
        target = os.path.join(
            self.application._sharing._sharing_database_path_ShareType["map"],
            self.application._sharing._encode_path("/user/fileshare.ics/"))
        file_blocked = _restrict_writes(target, 0o444)
        try:
            caplog.clear()
            payload = {
                "PathOrToken": "/user/fileshare.ics/", "Hidden": True,
                "User": "owner",
            }
            if file_blocked:
                _, _, answer = self._api("map", "update", payload, check=400)
                assert "Internal Error" in answer
                assert "cannot store share-config" in caplog.text
            else:
                updated = json.loads(self._api("map", "update", payload)[2])
                assert updated["Status"] == "success"
        finally:
            _restore_mode(target, 0o644)
        dir_blocked = _restrict_writes(os.path.dirname(target), 0o555)
        try:
            caplog.clear()
            payload = {"PathOrToken": "/user/fileshare.ics/", "User": "owner"}
            if dir_blocked:
                _, _, answer = self._api("map", "delete", payload, check=400)
                assert "Internal Error" in answer
                assert "cannot remove share-config" in caplog.text
            else:
                deleted = json.loads(self._api("map", "delete", payload)[2])
                assert deleted["Status"] == "success"
        finally:
            _restore_mode(os.path.dirname(target), 0o755)
        assert os.path.isfile(target) is dir_blocked

        def status_of(status):
            def inner(*args, **kwargs):
                return {"status": status}
            return inner

        self._enable("csv")
        with self._patched("database_update_sharing", status_of("not-found")):
            self._api("map", "update", {"PathOrToken": shared, "Hidden": True},
                      check=404)
        with self._patched("database_update_sharing",
                           status_of("permission-denied")):
            self._api("map", "hide", {"PathOrToken": shared}, check=403)
        with self._patched("database_update_sharing", status_of("error")):
            _, _, answer = self._api(
                "map", "update", {"PathOrToken": shared, "Hidden": True},
                check=400)
            assert "Internal Error" in answer
        with self._patched("database_update_sharing", lambda *args, **kwargs: None):
            _, _, answer = self._api(
                "map", "hide", {"PathOrToken": shared}, check=400)
            assert "Internal Error" in answer
        with self._patched("database_delete_sharing", status_of("not-found")):
            self._api("map", "delete", {
                "PathOrToken": shared, "User": "owner"}, check=404)
        with self._patched("database_delete_sharing",
                           status_of("permission-denied")):
            self._api("map", "delete", {
                "PathOrToken": shared, "User": "owner"}, check=403)
        with self._patched("database_delete_sharing", status_of("weird")):
            _, _, answer = self._api("map", "delete", {
                "PathOrToken": shared, "User": "owner"}, check=400)
            assert "Internal Error" in answer

        cache = self.application._sharing._sharing_cache
        for row in cache:
            if row.get("PathOrToken") == shared:
                row["PathMapped"] = None
        self._api("map", "update", {"PathOrToken": shared, "Hidden": False},
                  check=404)

    def test_api_group_overlay_and_disabled_features(self, caplog):
        self._enable("csv", group=True)
        collection = "/owner/covcal.ics/"
        shared = "/{user}/realm.ics/"
        self.mkcalendar(collection, login="owner:ownerpw")
        self._api("map", "create", {
            "User": "@domain.example", "PathMapped": collection,
            "PathOrToken": shared, "Permissions": "r",
            "Enabled": True, "Hidden": False,
        })
        self._api("map", "update", {
            "PathOrToken": shared, "Hidden": False,
        })
        _, _, answer = self._api("map", "update", {
            "PathOrToken": shared, "Permissions": "rE",
        }, check=400)
        assert "share-by-group" in answer
        listed = self._listed()
        row = [item for item in listed["Content"]
               if item["PathOrToken"] == shared][0]
        assert "E" not in row["Permissions"]
        self._api("map", "update", {
            "PathOrToken": "/user1/does-not-exist.ics/", "Hidden": True,
        }, login="user1:user1pw", check=404)
        self._api("map", "hide", {
            "PathOrToken": "/user1/does-not-exist.ics/",
        }, login="user1:user1pw", check=404)

        self._enable("csv")
        personal = "/user/personal.ics/"
        self._api("map", "create", {
            "User": "user", "PathMapped": collection, "PathOrToken": personal,
            "Permissions": "rP", "Enabled": True, "Hidden": False,
        })
        with caplog.at_level(logging.INFO, logger="radicale"):
            self._api("map", "update", {
                "PathOrToken": personal,
                "Properties": {"D:displayname": "Nope"},
            }, login="user:userpw", check=403)
            assert "granted by permission 'P'" in caplog.text
        rows = [item for item in self._listed()["Content"]
                if item["PathOrToken"] == personal]
        stored = rows[0]["Properties"] or {}
        assert stored.get("D:displayname") != "Nope"
        self._api("map", "hide", {"PathOrToken": personal},
                  login="user2:user2pw", check=403)
        self._api("map", "hide", {"PathOrToken": "/user/missing.ics/"},
                  check=404)

        backend = self.application._sharing
        backend.sharing_collection_by_map = False
        backend.sharing_collection_by_token = False
        self._api("all", "list", {}, check=404)
        info = json.loads(self._api("all", "info", {})[2])
        assert info["Status"] == "success"
        assert info["FeatureEnabledCollectionByMap"] is False
        assert info["FeatureEnabledCollectionByToken"] is False

    def test_bday_defaults_resolvers_and_property_filter(self, caplog):
        self._enable("csv")
        backend = self.application._sharing
        collection = "/owner/covcal.ics/"
        self.mkcalendar(collection, login="owner:ownerpw")

        def plant(path, actions):
            result = backend.database_create_sharing(
                ShareType="map", PathOrToken=path, PathMapped=collection,
                Conversion="bday", Owner="owner", User="owner",
                Permissions="r", EnabledByOwner=True, EnabledByUser=True,
                HiddenByOwner=False, HiddenByUser=False, Timestamp=1,
                Properties={}, Actions=actions,
            )
            assert result["status"] == "success"
            return backend.sharing_collection_resolver(path, "owner", set())

        complete = {
            "config": {
                "conversion_bday_summary_template": "S",
                "conversion_bday_description_template": "D",
                "conversion_bday_alarm_trigger_template": "-P1D;Hi",
                "conversion_bday_categories": "C",
                "conversion_bday_age_max": 12,
            },
        }
        resolved = plant("/owner/bday-all.ics/", complete)
        assert "config_default" not in resolved["Actions"]
        assert resolved["Actions"]["config"]["conversion_bday_categories"] == "C"
        assert resolved["Actions"]["config"]["conversion_bday_alarm_trigger_template"] == "-P1D;Hi"

        missing_categories = {
            "config": {
                "conversion_bday_summary_template": "S",
                "conversion_bday_description_template": "D",
                "conversion_bday_alarm_trigger_template": "-P1D;Hi",
                "conversion_bday_age_max": 12,
            },
        }
        resolved = plant("/owner/bday-nocat.ics/", missing_categories)
        assert resolved["Actions"]["config_default"]["conversion_bday_categories"] == backend.conversion_bday_categories
        assert "conversion_bday_age_max" not in resolved["Actions"]["config_default"]

        missing_age = {
            "config": {
                "conversion_bday_summary_template": "S",
                "conversion_bday_description_template": "D",
                "conversion_bday_alarm_trigger_template": "-P1D;Hi",
                "conversion_bday_categories": "C",
            },
        }
        resolved = plant("/owner/bday-noage.ics/", missing_age)
        assert resolved["Actions"]["config_default"]["conversion_bday_age_max"] == backend.conversion_bday_age_max

        direct = "/owner/direct.ics/"
        assert backend.database_create_sharing(
            ShareType="map", PathOrToken=direct, PathMapped=collection,
            Conversion="none", Owner="owner", User="owner", Permissions="r",
            EnabledByOwner=True, EnabledByUser=True,
            HiddenByOwner=False, HiddenByUser=False, Timestamp=1,
            Properties={"D:displayname": "Keep"}, Actions={},
        )["status"] == "success"
        assert backend.database_create_sharing(
            ShareType="map", PathOrToken="/", PathMapped=collection,
            Conversion="none", Owner="owner", User="owner", Permissions="r",
            EnabledByOwner=True, EnabledByUser=True,
            HiddenByOwner=False, HiddenByUser=False, Timestamp=1,
            Properties={}, Actions={},
        )["status"] == "success"
        assert backend.database_get_sharing(
            "map", "/", OnlyEnabled=False, User="owner")["mapped"] is True
        assert backend.sharing_collection_resolver("/", "owner", set()) is None

        with caplog.at_level(logging.INFO, logger="radicale"):
            hit = backend.sharing_collection_resolver(direct, "owner", set())
            parent = backend.sharing_collection_resolver(
                direct + "event1.ics", "owner", set())
            slashed = backend.sharing_collection_resolver(
                direct.rstrip("/"), "owner", set())
            assert backend.sharing_collection_resolver(
                "/owner/missing.ics/", "owner", set()) is None
            exact = "/.token/v1/" + ("d" * 44) + "/"
            assert backend.sharing_collection_by_token_resolver(
                "/owner/direct.ics/") is None
            assert backend.sharing_collection_by_token_resolver(
                "/.token/v1/short/")["error"] == "token-not-supported"
            missing = backend.sharing_collection_by_token_resolver(exact)
            assert missing["error"] == "token-not-found"
        assert hit["PathMapped"] == collection
        assert parent["PathMapped"] == collection + "event1.ics"
        assert slashed["PathOrToken"] == direct
        assert slashed["PathMapped"] == collection

        with caplog.at_level(TRACE, logger="radicale"):
            backend.sharing_collection_update("map", direct, "owner", {
                "D:displayname": "Shown",
                "NOPE:nope": "hidden",
            })
            assert "silent discard" in caplog.text
            assert "NOPE:nope" in caplog.text
        stored = backend.database_get_sharing(
            "map", direct, OnlyEnabled=False, User="owner")
        assert stored["Properties"] == {"D:displayname": "Shown"}
        with caplog.at_level(logging.INFO, logger="radicale"):
            caplog.clear()
            backend.sharing_collection_update("map", direct, "owner", {
                "D:displayname": "Shown2",
                "NOPE:nope": "hidden",
            })
            assert "silent discard" not in caplog.text
        stored = backend.database_get_sharing(
            "map", direct, OnlyEnabled=False, User="owner")
        assert stored["Properties"] == {"D:displayname": "Shown2"}

        saved_token = backend.sharing_collection_by_token
        saved_map = backend.sharing_collection_by_map
        try:
            backend.sharing_collection_by_token = False
            backend.sharing_collection_by_map = False
            with caplog.at_level(TRACE, logger="radicale"):
                assert backend.sharing_collection_resolver(
                    direct, "owner", set()) is None
                assert backend.sharing_collection_by_token_resolver(direct) is None
                assert backend.sharing_collection_by_map_resolver(
                    direct, "owner", set()) is None
                assert backend.sharing_collection_list(User="owner") == []
                assert "sharing/token: not active" in caplog.text
                assert "sharing/map: not active" in caplog.text
            caplog.clear()
            with caplog.at_level(logging.INFO, logger="radicale"):
                assert backend.sharing_collection_by_token_resolver(direct) is None
                assert backend.sharing_collection_by_map_resolver(
                    direct, "owner", set()) is None
                assert backend.sharing_collection_list(User="owner") == []
                assert "not active" not in caplog.text
        finally:
            backend.sharing_collection_by_token = saved_token
            backend.sharing_collection_by_map = saved_map

    def test_info_level_still_creates_and_lists(self):
        self._enable("csv")
        collection = "/owner/covcal.ics/"
        shared = "/user/quiet.ics/"
        self.mkcalendar(collection, login="owner:ownerpw")
        with caplog_level(logging.INFO):
            created = json.loads(self._api("map", "create", {
                "User": "user", "PathMapped": collection,
                "PathOrToken": shared, "Permissions": "r",
                "Enabled": True, "Hidden": False,
                "Properties": {"D:displayname": "Quiet"},
            })[2])
            assert created["Status"] == "success"
            token = json.loads(self._api("token", "create", {
                "PathMapped": collection, "Enabled": True, "Hidden": False,
            })[2])
            assert token["Status"] == "success"
            assert token["PathOrToken"].startswith("/.token/v1/")
            listed = self._listed(payload={"PathOrToken": shared})
            assert listed["Lines"] == 1
            assert listed["Content"][0]["Properties"]["D:displayname"] == "Quiet"
            self._api("map", "update", {
                "PathOrToken": shared, "Hidden": True,
                "Actions": {"config": {"view": "freebusy",
                                       "conversion_bday_categories": "Q"}},
            })
            self._api("map", "update", {
                "PathOrToken": shared,
                "Actions": {"config": {"conversion_bday_categories": "#DEL#"}},
                "Properties": {"D:displayname": ""},
            })
            _, headers, answer = self._api(
                "map", "list", {"PathOrToken": shared}, accept="text/csv")
            assert headers["Content-Type"].startswith("text/csv")
            assert answer.splitlines()[0].startswith("ShareType;")
            assert shared in answer
            self._api("map", "delete", {"PathOrToken": shared, "User": "owner"})
            self._api("token", "delete", {
                "PathOrToken": token["PathOrToken"], "User": "owner"})
        remaining = self._listed()
        assert remaining["Lines"] == 0 or remaining["Status"] == "not-found"

    def test_quiet_arcs_null_user_and_files_fallback(self, caplog):
        self._enable("csv", group=True)
        collection = "/owner/covcal.ics/"
        plain = "/owner/plain.ics/"
        self.mkcalendar(collection, login="owner:ownerpw")
        self.application._storage.create_collection(plain)
        backend = self.application._sharing

        environ = {}
        wsgiref.util.setup_testing_defaults(environ)
        environ["REQUEST_METHOD"] = "POST"
        environ["PATH_INFO"] = "/.sharing/v1/all/info"
        environ["wsgi.input"] = BytesIO(b"{}")
        environ["CONTENT_LENGTH"] = "2"
        environ["CONTENT_TYPE"] = "application/json"
        environ["HTTP_ACCEPT"] = "application/json"
        status, _headers, answer, _xml = backend.post(
            environ, "", "/.sharing/v1/all/info", None, set(), {})
        assert status == 200
        assert json.loads(answer)["Status"] == "success"
        assert json.loads(answer)["FeatureEnabledCollectionByMap"] is True

        with caplog.at_level(logging.INFO, logger="radicale"):
            payload = (
                "PathMapped=%s&PathOrToken=/user/forminfo.ics/&User=user"
                "&Permissions=r&Enabled=true&Hidden=false"
                "&Properties=&Properties=D:displayname=QuietForm" % collection)
            _, _, answer = self._api(
                "map", "create", payload,
                content_type="application/x-www-form-urlencoded",
                accept="text/plain")
            assert "Status='success'" in answer
            assert "parse property" not in caplog.text
            _, _, answer = self._api(
                "map", "list", "", content_type="text/plain", check=400)
            assert "Content-type not supported" in answer
            assert "no supported content data" not in caplog.text
            self._api("map", "update", {
                "PathOrToken": "/user1/does-not-exist.ics/", "Hidden": True,
            }, login="user1:user1pw", check=404)
            self._api("map", "hide", {
                "PathOrToken": "/user1/does-not-exist.ics/",
            }, login="user1:user1pw", check=404)
            assert "retry with user" not in caplog.text
        form_rows = [row for row in self._listed()["Content"]
                     if row["PathOrToken"] == "/user/forminfo.ics/"]
        assert form_rows[0]["Properties"]["D:displayname"] == "QuietForm"

        plain_path = "/user/plaininfo.ics/"
        self._api("map", "create", {
            "User": "user", "PathMapped": plain, "PathOrToken": plain_path,
            "Permissions": "r", "Enabled": True, "Hidden": False,
            "Properties": {
                "D:displayname": "Keep",
                "CR:addressbook-description": "A",
            },
            "Actions": {"config": {"view": "freebusy",
                                   "conversion_bday_categories": "Q"}},
        })
        with caplog.at_level(logging.INFO, logger="radicale"):
            self._api("map", "update", {
                "PathOrToken": plain_path,
                "Properties": {"D:displayname": "New"},
                "Actions": {"config": {
                    "view": sharing.SHARING_ACTIONS_DELETE_VALUE,
                    "conversion_bday_categories": sharing.SHARING_ACTIONS_DELETE_VALUE,
                }},
            })
            assert "overtake property" not in caplog.text
            assert "delete Actions entry" not in caplog.text
        stored = [row for row in self._listed()["Content"]
                  if row["PathOrToken"] == plain_path][0]
        assert stored["Properties"]["D:displayname"] == "New"
        assert stored["Properties"]["CR:addressbook-description"] == "A"
        assert stored["Actions"] == {}

        def status_of(name):
            def inner(*args, **kwargs):
                return {"status": name}
            return inner

        with self._patched("database_update_sharing",
                           status_of("permission-denied")):
            self._api("map", "update", {
                "PathOrToken": plain_path, "Hidden": True}, check=403)
        with self._patched("database_update_sharing", status_of("not-found")):
            self._api("map", "hide", {"PathOrToken": plain_path}, check=404)
        hidden = [row for row in self._listed()["Content"]
                  if row["PathOrToken"] == plain_path][0]
        assert hidden["HiddenByOwner"] is False

        saved_token = backend.sharing_collection_by_token
        saved_map = backend.sharing_collection_by_map
        try:
            backend.sharing_collection_by_token = False
            backend.sharing_collection_by_map = False
            with caplog.at_level(logging.INFO, logger="radicale"):
                assert backend.sharing_collection_resolver(
                    collection, "owner", set()) is None
                assert "not active" not in caplog.text
        finally:
            backend.sharing_collection_by_token = saved_token
            backend.sharing_collection_by_map = saved_map

        self._enable("files")
        files_backend = self.application._sharing
        with caplog.at_level(logging.INFO, logger="radicale"):
            created = files_backend.database_create_sharing(
                ShareType="map", PathOrToken="/user/quiet-file.ics/",
                PathMapped=collection, Conversion="none",
                Owner="owner", User="user", Permissions="r",
                EnabledByOwner=True, EnabledByUser=True,
                HiddenByOwner=False, HiddenByUser=False, Timestamp=1,
                Properties={}, Actions={},
            )
            assert created["status"] == "success"
            assert "sharing_config_file" not in caplog.text
        stored_file = os.path.join(
            files_backend._sharing_database_path_ShareType["map"],
            files_backend._encode_path("/user/quiet-file.ics/"))
        with open(stored_file, "rb") as handle:
            _version, row = pickle.load(handle)
        assert row["Owner"] == "owner"
        self._store_files_row(_entry(
            ShareType="map", User=":group1",
            PathOrToken="/{user}/quiet-group.ics/",
            EnabledByOwner=True, EnabledByUser=True, Permissions="rw"))
        with caplog.at_level(logging.INFO, logger="radicale"):
            grouped = files_backend.database_get_sharing(
                "map", "/user1/quiet-group.ics/", OnlyEnabled=True,
                User="user1:group1")
            assert "no direct share found" not in caplog.text
            removed = files_backend.database_delete_sharing(
                "map", "/user/quiet-file.ics/", "owner")
            assert removed["status"] == "success"
            assert "sharing/map/delete" not in caplog.text
        assert grouped["mapped"] is True
        assert grouped["User"] == "user1"
        assert grouped["PathMapped"] == collection
        assert os.path.isfile(stored_file) is False


@contextlib.contextmanager
def caplog_level(level):
    old = logger.level
    logger.setLevel(level)
    try:
        yield
    finally:
        logger.setLevel(old)
