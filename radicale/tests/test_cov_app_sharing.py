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

"""Outcome tests for sharing responses over WebDAV."""

import ast
import cProfile
import csv
import errno
import json
import logging
import os
import socket

from radicale import xmlutils
from radicale.log import logger
from radicale.tests import BaseTest
from radicale.tests.helpers import get_file_content

CALENDAR_MKCOL = """<?xml version="1.0" encoding="utf-8" ?>
<mkcol xmlns="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
  <set><prop><resourcetype><collection/><C:calendar/></resourcetype></prop></set>
</mkcol>"""

SUBSCRIBED_MKCOL = """<?xml version="1.0" encoding="utf-8" ?>
<mkcol xmlns="DAV:" xmlns:CS="http://calendarserver.org/ns/">
  <set><prop><resourcetype><collection/><CS:subscribed/></resourcetype></prop></set>
</mkcol>"""

PROPPATCH_NAME = """<?xml version="1.0" encoding="utf-8"?>
<D:propertyupdate xmlns:D="DAV:">
  <D:set><D:prop><D:displayname>%s</D:displayname></D:prop></D:set>
</D:propertyupdate>"""

PROPFIND_ONE = """<?xml version="1.0" encoding="utf-8"?>
<D:propfind xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav"
            xmlns:CS="http://calendarserver.org/ns/"
            xmlns:RADICALE="http://radicale.org/ns/">
  <D:prop>{0}</D:prop>
</D:propfind>"""

ACCESS_FORBIDDEN = "Access to the requested resource forbidden."
ACTION_REFUSED = "Action on the requested resource refused."
BAD_REQUEST = "Bad Request"
PRECONDITION = "Precondition failed."
NOT_FOUND = "The requested resource could not be found."
CONFLICT = "Conflict in the request."
METHOD_NOT_ALLOWED = "The method is not allowed on the requested resource."
TIMEOUT = "Connection timed out."
TOO_LARGE = "Request body too large."
REMOTE_DESTINATION = "Remote destination not supported."
INSUFFICIENT = "Insufficient Storage."
SERVER_ERROR = "A server error occurred.  Please contact the administrator."
LOGIN = "alice:secret"


def _event(uid="evt", summary="Event", start="20130901T160000Z",
           end="20130901T170000Z", extra=""):
    return (
        "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Test//EN\r\n"
        "BEGIN:VEVENT\r\nUID:%s\r\nDTSTAMP:20130101T000000Z\r\n"
        "DTSTART:%s\r\nDTEND:%s\r\nSUMMARY:%s\r\n%s"
        "END:VEVENT\r\nEND:VCALENDAR\r\n" % (uid, start, end, summary, extra))


def _vcard(uid="card", fn="Ada"):
    return (
        "BEGIN:VCARD\r\nVERSION:3.0\r\nUID:%s\r\nFN:%s\r\nEND:VCARD\r\n"
        % (uid, fn))


def _todo():
    return (
        "BEGIN:VTODO\r\nUID:todo-1\r\nDTSTAMP:20130101T000000Z\r\n"
        "SUMMARY:Task\r\nEND:VTODO\r\n")


def _set_rights(test, text, **extra):
    path = os.path.join(test.colpath, "rights")
    with open(path, "w") as handle:
        handle.write(text)
    config = {
        "auth": {"type": "none", "delay": "0"},
        "rights": {"type": "from_file", "file": path},
        "server": {"delay_on_error": "0"},
    }
    config.update(extra)
    test.configure(config)


def _grant(test):
    _set_rights(test, "[all]\nuser: .*\ncollection: .*\npermissions: RrWw\n")


class _Level:
    def __init__(self, level):
        self.level = level
        self.previous = None

    def __enter__(self):
        self.previous = logger.level
        logger.setLevel(self.level)
        return self

    def __exit__(self, *_args):
        logger.setLevel(self.previous)


class TimeoutStream:
    def read(self, size=-1):
        raise socket.timeout("timed out")


def _second_profiler_is_blocked():
    """True when a second ``cProfile`` cannot start while one is active."""
    holder = cProfile.Profile()
    holder.enable()
    try:
        nested = cProfile.Profile()
        try:
            nested.enable()
        except ValueError:
            return True
        nested.disable()
        return False
    finally:
        holder.disable()


class Hook:
    """Recording hook used by these tests."""

    events: list = []
    fail = False

    def __init__(self, configuration):
        self.configuration = configuration

    @property
    def enabled(self):
        return True

    def notify(self, notification_item):
        Hook.events.append(notification_item)
        if Hook.fail:
            raise RuntimeError("hook failed")


class TestCovAppSharing(BaseTest):
    """Sharing paths exercised through the real handlers."""

    def setup_method(self):
        super().setup_method()
        self.htpasswd = os.path.join(self.colpath, ".htpasswd")
        with open(self.htpasswd, "w") as handle:
            handle.write("owner:ownerpw\nuser:userpw\n")
        _grant(self)
        self._enable_sharing()

    def _enable_sharing(self, rights_type="owner_only", rights_text=None):
        if rights_text:
            path = os.path.join(self.colpath, "rights")
            with open(path, "w") as handle:
                handle.write(rights_text)
            rights = {"type": "from_file", "file": path}
        else:
            rights = {"type": rights_type}
        self.configure({
            "auth": {"type": "htpasswd", "htpasswd_filename": self.htpasswd,
                     "htpasswd_encryption": "plain", "delay": "0"},
            "rights": rights,
            "sharing": {
                "type": "csv",
                "collection_by_map": "True",
                "collection_by_token": "True",
                "permit_create_map": "True",
                "permit_create_token": "True",
                "permit_properties_overlay": "False",
                "enforce_properties_overlay": "True",
            },
            "server": {"delay_on_error": "0"},
        })

    def _api(self, kind, action, payload, login, check=200):
        status, _, body = self.request(
            "POST", "/.sharing/v1/%s/%s" % (kind, action),
            json.dumps(payload), login=login,
            content_type="application/json", HTTP_ACCEPT="application/json",
            check=None)
        assert status == check, body
        return body

    def _map(self, mapped, token, user="user", permissions="r",
             owner_login="owner:ownerpw", user_login="user:userpw",
             properties=None, conversion=None):
        payload = {
            "User": user,
            "PathMapped": mapped,
            "PathOrToken": token,
            "Permissions": permissions,
            "Enabled": True,
            "Hidden": False,
        }
        if properties:
            payload["Properties"] = properties
        if conversion:
            payload["Conversion"] = conversion
        body = self._api("map", "create", payload, owner_login)
        assert "success" in body
        self._api("map", "enable", {"PathOrToken": token}, owner_login)
        self._api("map", "enable", {"PathOrToken": token}, user_login)
        self._api("map", "unhide", {"PathOrToken": token}, user_login)
        return token

    def _retarget(self, old_token, new_token):
        path = os.path.join(self.colpath, "collection-db", "sharing.csv")
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        assert old_token in text
        text = text.replace(old_token, new_token)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        self.configure({})

    def _rewrite_row(self, token, permissions=None, properties=None,
                     path_mapped=None):
        path = os.path.join(self.colpath, "collection-db", "sharing.csv")
        with open(path, encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle, delimiter=";")
            fieldnames = reader.fieldnames
            rows = list(reader)
        found = False
        for row in rows:
            if row["PathOrToken"] != token:
                continue
            found = True
            if permissions is not None:
                row["Permissions"] = permissions
            if path_mapped is not None:
                row["PathMapped"] = path_mapped
            if properties is not None:
                current = ast.literal_eval(row["Properties"]) if row["Properties"] else {}
                current.update(properties)
                row["Properties"] = repr(current)
        assert found, token
        with open(path, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle, fieldnames=fieldnames, delimiter=";")
            writer.writeheader()
            writer.writerows(rows)
        self.configure({})

    def test_user_format_group_boundaries(self):
        self.mkcalendar("/owner/cal.ics/", login="owner:ownerpw")
        base = {
            "PathMapped": "/owner/cal.ics/",
            "PathOrToken": "/user/shared/",
            "Permissions": "r",
        }
        self.configure({"server": {"validate_user_value": "strict",
                                   "delay_on_error": "0"}})
        body = self._api("map", "create", dict(base, User=":bad name"),
                         "owner:ownerpw", check=400)
        assert "Invalid value for User" in body
        body = self._api(
            "map", "create",
            dict(base, User=":g1", PathOrToken="/{user}/g1/"),
            "owner:ownerpw")
        assert "success" in body
        assert "Invalid value for User" not in body
        body = self._api("map", "create", dict(base, User="alice:"),
                         "owner:ownerpw", check=400)
        assert "Invalid value for User" in body

        self.configure({"server": {"validate_user_value": "minimal",
                                   "delay_on_error": "0"}})
        with _Level(logging.INFO):
            body = self._api("map", "create", dict(base, User=":bad*"),
                             "owner:ownerpw", check=400)
            assert "Invalid value for User" in body
            self.mkcalendar("/owner/cal2.ics/", login="owner:ownerpw")
            body = self._api(
                "map", "create",
                dict(base, User=":g1,g2", PathMapped="/owner/cal2.ics/",
                     PathOrToken="/{user}/g1g2/"),
                "owner:ownerpw")
            assert "success" in body
            assert "Invalid value for User" not in body

    def test_overlap_skip_preserves_owner_rights(self, caplog):
        self.mkcalendar("/owner/cal.ics/", login="owner:ownerpw")
        self.put("/owner/cal.ics/event.ics", _event(summary="Owned"),
                 login="owner:ownerpw")
        self._map("/owner/cal.ics/", "/owner/alias/", user="owner",
                  permissions="w", user_login="owner:ownerpw")
        self._retarget("/owner/alias/", "/owner/cal.ics/")
        caplog.set_level(logging.TRACE)
        with _Level(logging.TRACE):
            status, body = self.get("/owner/cal.ics/", login="owner:ownerpw")
        assert status == 200 and "Owned" in body
        assert "skip overlap mapping" in "\n".join(caplog.messages)
        caplog.clear()
        with _Level(logging.INFO):
            status, body = self.get("/owner/cal.ics/", login="owner:ownerpw")
        assert status == 200 and "Owned" in body
        assert "skip overlap mapping" not in "\n".join(caplog.messages)
        caplog.clear()
        with _Level(logging.INFO):
            status, _, answer = self.request(
                "PROPFIND", "/owner/cal.ics/",
                PROPFIND_ONE.format("<D:displayname/>"),
                HTTP_DEPTH="0", login="owner:ownerpw", check=None)
        assert status == 207 and "cal.ics" in answer
        assert "skip overlap mapping" not in "\n".join(caplog.messages)
        caplog.clear()
        with _Level(logging.TRACE):
            status, _, body = self.request(
                "PUT", "/owner/cal.ics/event.ics", _event(summary="Traced"),
                login="owner:ownerpw", check=None)
        assert status in (201, 204), body
        assert "Traced" in self.get("/owner/cal.ics/event.ics",
                                    login="owner:ownerpw")[1]
        assert "skip overlap mapping" in "\n".join(caplog.messages)
        caplog.clear()
        with _Level(logging.INFO):
            status, _, body = self.request(
                "PUT", "/owner/cal.ics/event.ics", _event(summary="Updated"),
                login="owner:ownerpw", check=None)
        assert status in (201, 204), body
        assert "skip overlap mapping" not in "\n".join(caplog.messages)
        assert "Updated" in self.get("/owner/cal.ics/event.ics",
                                     login="owner:ownerpw")[1]
        caplog.clear()
        with _Level(logging.TRACE):
            status, _, body = self.request(
                "PROPPATCH", "/owner/cal.ics/", PROPPATCH_NAME % "TracedName",
                login="owner:ownerpw", check=None)
        assert status == 207 and "displayname" in body
        assert "skip overlap mapping" in "\n".join(caplog.messages)
        caplog.clear()
        with _Level(logging.INFO):
            status, _, body = self.request(
                "PROPPATCH", "/owner/cal.ics/", PROPPATCH_NAME % "OwnerName",
                login="owner:ownerpw", check=None)
        assert status == 207 and "displayname" in body
        assert "skip overlap mapping" not in "\n".join(caplog.messages)
        assert "Updated" in self.get("/owner/cal.ics/event.ics",
                                     login="owner:ownerpw")[1]
        report = (
            "<?xml version='1.0' encoding='utf-8'?>"
            "<C:calendar-query xmlns:D='DAV:' "
            "xmlns:C='urn:ietf:params:xml:ns:caldav'>"
            "<D:prop><D:getetag/></D:prop></C:calendar-query>")
        caplog.clear()
        with _Level(logging.TRACE):
            status, _, body = self.request(
                "REPORT", "/owner/cal.ics/", report,
                login="owner:ownerpw", check=None)
        assert status == 207 and "event.ics" in body
        assert "skip overlap mapping" in "\n".join(caplog.messages)
        caplog.clear()
        with _Level(logging.INFO):
            status, _, body = self.request(
                "REPORT", "/owner/cal.ics/", report,
                login="owner:ownerpw", check=None)
        assert status == 207 and "event.ics" in body
        assert "skip overlap mapping" not in "\n".join(caplog.messages)
        self.mkcalendar("/owner/other.ics/", login="owner:ownerpw")
        self.put("/owner/cal.ics/stay.ics", _event(uid="stay", summary="Stay"),
                 login="owner:ownerpw")
        caplog.clear()
        with _Level(logging.TRACE):
            status, _, body = self.request(
                "MOVE", "/owner/cal.ics/stay.ics",
                HTTP_DESTINATION="http://127.0.0.1/owner/other.ics/stay.ics",
                login="owner:ownerpw", check=None)
        assert status in (201, 204), body
        assert "Stay" in self.get("/owner/other.ics/stay.ics",
                                  login="owner:ownerpw")[1]
        assert "skip overlap mapping" in "\n".join(caplog.messages)
        caplog.clear()
        with _Level(logging.INFO):
            status, _, body = self.request(
                "MOVE", "/owner/cal.ics/event.ics",
                HTTP_DESTINATION="http://127.0.0.1/owner/other.ics/event.ics",
                login="owner:ownerpw", check=None)
        assert status in (201, 204), body
        assert "skip overlap mapping" not in "\n".join(caplog.messages)
        assert "Updated" in self.get(
            "/owner/other.ics/event.ics", login="owner:ownerpw")[1]

    def test_share_propfind_principal_overlay_and_depth(self):
        self.mkcalendar("/owner/cal.ics/", login="owner:ownerpw")
        self.put("/owner/cal.ics/event.ics", _event(summary="Shared"),
                 login="owner:ownerpw")
        self._map("/owner/cal.ics/", "/user/shared/", permissions="r",
                  properties={"D:displayname": "Overlay"})
        status, _, body = self.request(
            "PROPFIND", "/user/shared/",
            PROPFIND_ONE.format(
                "<D:displayname/><RADICALE:displayname/>"
                "<D:current-user-principal/>"),
            HTTP_DEPTH="0", login="user:userpw", check=None)
        assert status == 207
        assert "Overlay" in body
        assert "/user/" in body
        status, _, body = self.request(
            "PROPFIND", "/user/",
            PROPFIND_ONE.format("<D:resourcetype/>"),
            HTTP_DEPTH="1", login="user:userpw", check=None)
        assert status == 207 and "/user/shared/" in body

        self._map("/owner/", "/user/owner-home/", permissions="Rr")
        status, _, body = self.request(
            "PROPFIND", "/user/owner-home/",
            PROPFIND_ONE.format("<D:principal-URL/>"),
            HTTP_DEPTH="0", login="user:userpw", check=None)
        assert status == 207
        assert "/user/owner-home/" in body

    def test_proppatch_share_overlay_matrix(self, monkeypatch):
        self.mkcalendar("/owner/cal.ics/", login="owner:ownerpw")
        token = self._map("/owner/cal.ics/", "/user/shared/", permissions="rP")
        with _Level(logging.INFO):
            status, _, body = self.request(
                "PROPPATCH", token, PROPPATCH_NAME % "FromShare",
                login="user:userpw", check=None)
        assert status == 207 and "displayname" in body
        owner = self.request(
            "PROPFIND", "/owner/cal.ics/",
            PROPFIND_ONE.format("<D:displayname/>"),
            HTTP_DEPTH="0", login="owner:ownerpw", check=None)[2]
        assert "FromShare" not in owner
        shared = self.request(
            "PROPFIND", token, PROPFIND_ONE.format("<D:displayname/>"),
            HTTP_DEPTH="0", login="user:userpw", check=None)[2]
        assert "FromShare" in shared

        self.mkcalendar("/owner/blocked.ics/", login="owner:ownerpw")
        self._map("/owner/blocked.ics/", "/user/blocked-e/", permissions="rPe")
        status, _, body = self.request(
            "PROPPATCH", "/user/blocked-e/", PROPPATCH_NAME % "NoE",
            login="user:userpw", check=None)
        assert status == 403 and body == ACCESS_FORBIDDEN
        assert "NoE" not in self.request(
            "PROPFIND", "/user/blocked-e/",
            PROPFIND_ONE.format("<D:displayname/>"),
            HTTP_DEPTH="0", login="user:userpw", check=None)[2]

        self.mkcalendar("/owner/cal2.ics/", login="owner:ownerpw")
        self._enable_sharing(rights_text=(
            "[cal]\nuser: owner\ncollection: owner/cal2\\.ics\npermissions: re\n"
            "[all]\nuser: .*\ncollection: .*\npermissions: RrWw\n"))
        self._map("/owner/cal2.ics/", "/user/rights-e/", permissions="rP")
        status, _, body = self.request(
            "PROPPATCH", "/user/rights-e/", PROPPATCH_NAME % "RightsE",
            login="user:userpw", check=None)
        assert status == 403 and body == ACCESS_FORBIDDEN

        self._enable_sharing(rights_text=(
            "[cal]\nuser: owner\ncollection: owner/cal3\\.ics\npermissions: rwp\n"
            "[all]\nuser: .*\ncollection: .*\npermissions: RrWw\n"))
        self.mkcalendar("/owner/cal3.ics/", login="owner:ownerpw")
        self._map("/owner/cal3.ics/", "/user/rights-p/", permissions="rw")
        status, _, body = self.request(
            "PROPPATCH", "/user/rights-p/", PROPPATCH_NAME % "RightsP",
            login="user:userpw", check=None)
        assert status == 403 and ACCESS_FORBIDDEN in body
        assert "RightsP" not in self.get("/owner/cal3.ics/", login="owner:ownerpw")[1]

        def fail_update(**_kwargs):
            raise ValueError("failed [Errno %d]" % errno.EIO)

        self._enable_sharing()
        self.mkcalendar("/owner/cal4.ics/", login="owner:ownerpw")
        self._map("/owner/cal4.ics/", "/user/errno/", permissions="rP")
        monkeypatch.setattr(
            self.application._sharing, "sharing_collection_update", fail_update)
        status, _, body = self.request(
            "PROPPATCH", "/user/errno/", PROPPATCH_NAME % "Disk",
            login="user:userpw", check=None)
        assert status == 500 and body == SERVER_ERROR

    def test_bday_share_skips_contacts_without_birthday(self):
        self.create_addressbook("/owner/book/", login="owner:ownerpw")
        self.put("/owner/book/plain.vcf", get_file_content("contact1.vcf"),
                 login="owner:ownerpw")
        self.put("/owner/book/bday.vcf",
                 get_file_content("contact2-with-bday.vcf"),
                 login="owner:ownerpw")
        self._map("/owner/book/", "/user/birthdays/", permissions="r",
                  conversion="bday")
        status, _, body = self.request(
            "PROPFIND", "/user/birthdays/",
            PROPFIND_ONE.format("<D:getetag/><D:displayname/>"),
            HTTP_DEPTH="1", login="user:userpw", check=None)
        assert status == 207
        assert "bday.ics" in body
        assert "plain" not in body
        status, _, body = self.request(
            "GET", "/user/birthdays/plain.ics", login="user:userpw", check=None)
        assert status == 404 and body == NOT_FOUND
        status, body = self.get(
            "/user/birthdays/bday.ics", login="user:userpw")
        assert status == 200 and "VEVENT" in body

    def test_delete_through_share_with_encoded_prefix(self):
        self.mkcalendar("/owner/cal.ics/", login="owner:ownerpw")
        self.put("/owner/cal.ics/event.ics", _event(summary="Gone"),
                 login="owner:ownerpw")
        self._map("/owner/cal.ics/", "/user/shared/", permissions="rw")
        with _Level(logging.INFO):
            status, _, body = self.request(
                "DELETE", "/user/shared/event.ics",
                SCRIPT_NAME="/a:b", login="user:userpw", check=None)
        assert status == 200 and "multistatus" in body
        assert self.get("/owner/cal.ics/event.ics",
                        login="owner:ownerpw", check=404)[0] == 404

    def test_read_only_share_cannot_write_owner_still_can(self):
        self.mkcalendar("/owner/cal.ics/", login="owner:ownerpw")
        self.put("/owner/cal.ics/event.ics", _event(summary="Stay"),
                 login="owner:ownerpw")
        self._map("/owner/cal.ics/", "/user/shared/", permissions="r")
        status, _, body = self.request(
            "PUT", "/user/shared/event.ics", _event(summary="Hijack"),
            login="user:userpw", check=None)
        assert status == 403 and body == ACCESS_FORBIDDEN
        assert "Stay" in self.get("/owner/cal.ics/event.ics",
                                  login="owner:ownerpw")[1]
        status, _, body = self.request(
            "DELETE", "/user/shared/", login="user:userpw", check=None)
        assert status == 403 and body == ACCESS_FORBIDDEN
        assert "BEGIN:VCALENDAR" in self.get(
            "/owner/cal.ics/", login="owner:ownerpw")[1]

    def test_depth_filters_and_overlay_write_edges(self, monkeypatch, caplog):
        self.mkcalendar("/owner/cal.ics/", login="owner:ownerpw")
        self.put("/owner/cal.ics/event.ics", _event(summary="Listed"),
                 login="owner:ownerpw")
        self._map("/owner/cal.ics/", "/user/shared/", permissions="r")
        self.mkcalendar("/owner/hidden.ics/", login="owner:ownerpw")
        self._map("/owner/hidden.ics/", "/user/hidden/", permissions="w")
        self.mkcalendar("/owner/same.ics/", login="owner:ownerpw")
        self._map("/owner/same.ics/", "/owner/alias/", user="owner",
                  permissions="r", user_login="owner:ownerpw")

        status, _, body = self.request(
            "PROPFIND", "/owner/",
            PROPFIND_ONE.format("<D:resourcetype/>"),
            HTTP_DEPTH="1", login="owner:ownerpw", check=None)
        assert status == 207 and "/owner/cal.ics/" in body
        assert "/user/shared/" not in body
        assert "/owner/alias/" not in body

        with _Level(logging.INFO):
            status, _, body = self.request(
                "PROPFIND", "/user/",
                PROPFIND_ONE.format("<D:resourcetype/>"),
                HTTP_DEPTH="1", login="user:userpw", check=None)
        assert status == 207 and "/user/shared/" in body
        assert "/user/hidden/" not in body

        self._enable_sharing(rights_text=(
            "[cal]\nuser: owner\ncollection: owner/locked\\.ics\npermissions: rwl\n"
            "[all]\nuser: .*\ncollection: .*\npermissions: RrWw\n"))
        self.mkcalendar("/owner/locked.ics/", login="owner:ownerpw")
        self._map("/owner/locked.ics/", "/user/locked/", permissions="rP")
        status, _, body = self.request(
            "PROPPATCH", "/user/locked/", PROPPATCH_NAME % "LockedName",
            login="user:userpw", check=None)
        assert status == 403 and body == ACCESS_FORBIDDEN
        owner = self.request(
            "PROPFIND", "/owner/locked.ics/",
            PROPFIND_ONE.format("<D:displayname/>"),
            HTTP_DEPTH="0", login="owner:ownerpw", check=None)[2]
        assert "LockedName" not in owner

        self._enable_sharing(rights_text=(
            "[cal]\nuser: owner\ncollection: owner/native\\.ics\npermissions: rwe\n"
            "[all]\nuser: .*\ncollection: .*\npermissions: RrWw\n"))
        self.mkcalendar("/owner/native.ics/", login="owner:ownerpw")
        self._map("/owner/native.ics/", "/user/native/", permissions="rw")
        caplog.set_level(logging.INFO)
        status, _, body = self.request(
            "PROPPATCH", "/user/native/", PROPPATCH_NAME % "NativeName",
            login="user:userpw", check=None)
        assert status == 207 and "displayname" in body
        assert "disabled by rights permission 'e'" in "\n".join(caplog.messages)
        owner = self.request(
            "PROPFIND", "/owner/native.ics/",
            PROPFIND_ONE.format("<D:displayname/>"),
            HTTP_DEPTH="0", login="owner:ownerpw", check=None)[2]
        assert "NativeName" in owner

        def fail_update(**_kwargs):
            raise ValueError("failed [Errno %d]" % errno.EACCES)

        self._enable_sharing()
        self.mkcalendar("/owner/errno.ics/", login="owner:ownerpw")
        self._map("/owner/errno.ics/", "/user/errno/", permissions="rP")
        monkeypatch.setattr(
            self.application._sharing, "sharing_collection_update", fail_update)
        status, _, body = self.request(
            "PROPPATCH", "/user/errno/", PROPPATCH_NAME % "Denied",
            login="user:userpw", check=None)
        assert status == 403 and body == ACTION_REFUSED
        shared = self.request(
            "PROPFIND", "/user/errno/",
            PROPFIND_ONE.format("<D:displayname/>"),
            HTTP_DEPTH="0", login="user:userpw", check=None)[2]
        assert "Denied" not in shared

        monkeypatch.undo()
        self._enable_sharing()
        self.mkcalendar("/owner/empty.ics/", login="owner:ownerpw")
        self._map("/owner/empty.ics/", "/user/empty/", permissions="rP")
        status, _, body = self.request(
            "PROPPATCH", "/user/empty/", "", login="user:userpw", check=None)
        assert status == 207 and "multistatus" in body
        assert "Denied" not in self.request(
            "PROPFIND", "/user/empty/",
            PROPFIND_ONE.format("<D:displayname/>"),
            HTTP_DEPTH="0", login="user:userpw", check=None)[2]

    def test_depth_prefix_item_share_and_privilege_edges(self):
        self._enable_sharing(rights_text=(
            "[all]\nuser: .*\ncollection: .*\npermissions: RrWw\n"))
        self.mkcalendar("/owner/cal.ics/", login="owner:ownerpw")
        self.put("/owner/cal.ics/event.ics", _event(summary="SharedItem"),
                 login="owner:ownerpw")
        self.mkcalendar("/owner/same.ics/", login="owner:ownerpw")
        self._map("/owner/same.ics/", "/owner/alias/", user="owner",
                  permissions="r", user_login="owner:ownerpw")
        self.mkcalendar("/user/mine.ics/", login="user:userpw")
        self.put("/user/mine.ics/local.ics", _event(summary="Local"),
                 login="user:userpw")
        self._map("/owner/cal.ics/", "/user/item/", permissions="r")
        path = os.path.join(self.colpath, "collection-db", "sharing.csv")
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        assert "/owner/cal.ics/" in text
        text = text.replace("/owner/cal.ics/", "/owner/cal.ics/event.ics", 1)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        self.configure({})

        with _Level(logging.INFO):
            status, _, body = self.request(
                "PROPFIND", "/owner/",
                PROPFIND_ONE.format("<D:resourcetype/>"),
                HTTP_DEPTH="1", login="owner:ownerpw", check=None)
        assert status == 207 and "/owner/same.ics/" in body
        assert "/owner/alias/" not in body
        with _Level(logging.INFO):
            status, _, body = self.request(
                "PROPFIND", "/user/",
                PROPFIND_ONE.format("<D:resourcetype/>"),
                HTTP_DEPTH="1", login="user:userpw", check=None)
        assert status == 207 and "/user/item/" in body
        assert "/user/mine.ics/" in body
        with _Level(logging.INFO):
            status, _, body = self.request(
                "PROPFIND", "/user/mine.ics/",
                PROPFIND_ONE.format("<D:resourcetype/>"),
                HTTP_DEPTH="1", login="user:userpw", check=None)
        assert status == 207 and "local.ics" in body
        assert "/user/item/" not in body

        self._enable_sharing()
        self.mkcalendar("/owner/listed.ics/", login="owner:ownerpw")
        self.put("/owner/listed.ics/event.ics", _event(summary="Listed"),
                 login="owner:ownerpw")
        self._map("/owner/listed.ics/", "/user/fresh/", permissions="r")
        path = os.path.join(self.colpath, "collection-db", "sharing.csv")
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        assert "/user/fresh/" in text
        text = text.replace("/user/fresh/", "/user/mine.ics/")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        self.configure({})
        with _Level(logging.INFO):
            status, _, body = self.request(
                "PROPFIND", "/user/",
                PROPFIND_ONE.format("<D:resourcetype/>"),
                HTTP_DEPTH="1", login="user:userpw", check=None)
        assert status == 207 and body.count("/user/mine.ics/") == 1
        assert "Listed" not in body

        self.mkcalendar("/owner/multi.ics/", login="owner:ownerpw")
        self.put("/owner/multi.ics/event.ics", _event(summary="Multi"),
                 login="owner:ownerpw")
        self._map("/owner/multi.ics/", "/user/shared/", permissions="r")
        multiget = (
            "<?xml version='1.0' encoding='utf-8'?>"
            "<C:calendar-multiget xmlns:D='DAV:' "
            "xmlns:C='urn:ietf:params:xml:ns:caldav'>"
            "<D:prop><D:getetag/></D:prop>"
            "<D:href>/user/shared/event.ics</D:href>"
            "<D:href>/user/shared/a/b.ics</D:href>"
            "<D:href>/user/other.ics</D:href>"
            "</C:calendar-multiget>")
        with _Level(logging.INFO):
            status, _, body = self.request(
                "REPORT", "/user/shared/", multiget,
                login="user:userpw", check=None)
        assert status == 207 and "event.ics" in body
        assert body.count("404") >= 1
        empty = multiget.replace(
            "<D:href>/user/shared/event.ics</D:href>"
            "<D:href>/user/shared/a/b.ics</D:href>"
            "<D:href>/user/other.ics</D:href>", "")
        status, _, body = self.request(
            "REPORT", "/user/shared/", empty,
            login="user:userpw", check=None)
        assert status == 207 and "event.ics" not in body

    def test_privilege_set_and_bday_reports(self):
        self.mkcalendar("/owner/cal.ics/", login="owner:ownerpw")
        self.mkcalendar("/owner/locked.ics/", login="owner:ownerpw")
        self._map("/owner/cal.ics/", "/user/props/", permissions="rP")
        self._map("/owner/locked.ics/", "/user/locked/", permissions="rPl")
        props = (
            "<D:current-user-privilege-set/>"
            "<D:supported-report-set/>")
        with _Level(logging.INFO):
            status, _, body = self.request(
                "PROPFIND", "/user/props/",
                PROPFIND_ONE.format(props),
                HTTP_DEPTH="0", login="user:userpw", check=None)
        assert status == 207 and "write-properties" in body
        assert "free-busy-query" in body
        with _Level(logging.INFO):
            status, _, body = self.request(
                "PROPFIND", "/user/locked/",
                PROPFIND_ONE.format(props),
                HTTP_DEPTH="0", login="user:userpw", check=None)
        assert status == 207 and "write-properties" not in body
        assert "read" in body

        self.create_addressbook("/owner/book/", login="owner:ownerpw")
        self.put("/owner/book/bday.vcf",
                 get_file_content("contact2-with-bday.vcf"),
                 login="owner:ownerpw")
        self._map("/owner/book/", "/user/birthdays/", permissions="r",
                  conversion="bday")
        with _Level(logging.INFO):
            status, _, body = self.request(
                "PROPFIND", "/user/birthdays/",
                PROPFIND_ONE.format(
                    "<D:supported-report-set/><D:getcontentlength/>"),
                HTTP_DEPTH="0", login="user:userpw", check=None)
        assert status == 207
        assert "calendar-query" in body
        assert "free-busy-query" not in body
        assert "addressbook-query" not in body
        assert "getcontentlength" in body
        with _Level(logging.INFO):
            status, _, body = self.request(
                "PROPFIND", "/user/birthdays/",
                PROPFIND_ONE.format(
                    "<D:getcontentlength/><RADICALE:getcontentcount/>"),
                HTTP_DEPTH="1", login="user:userpw", check=None)
        assert status == 207 and "getcontentlength" in body
        assert "getcontentcount" in body and ">0<" not in body
        query = (
            "<?xml version='1.0' encoding='utf-8'?>"
            "<C:calendar-query xmlns:D='DAV:' "
            "xmlns:C='urn:ietf:params:xml:ns:caldav'>"
            "<D:prop><C:calendar-data/></D:prop>"
            "<C:filter><C:comp-filter name='VCALENDAR'>"
            "<C:comp-filter name='VEVENT'/></C:comp-filter></C:filter>"
            "</C:calendar-query>")
        with _Level(logging.INFO):
            status, _, body = self.request(
                "REPORT", "/user/birthdays/", query,
                login="user:userpw", check=None)
        assert status == 207 and "BEGIN:VEVENT" in body.upper()

        self.mkcalendar("/owner/ro.ics/", login="owner:ownerpw")
        self.mkcalendar("/owner/rw.ics/", login="owner:ownerpw")
        self._enable_sharing(rights_text=(
            "[ro]\nuser: owner\ncollection: owner/ro\\.ics\npermissions: r\n"
            "[all]\nuser: .*\ncollection: .*\npermissions: RrWw\n"))
        self._map("/owner/ro.ics/", "/user/ro/", permissions="rw")
        self._map("/owner/rw.ics/", "/user/rw/", permissions="rw",
                  properties={"C:calendar-description": "SharedDesc",
                              "D:displayname": "SharedName"})
        priv = PROPFIND_ONE.format("<D:current-user-privilege-set/>")
        status, _, body = self.request(
            "PROPFIND", "/user/ro/", priv,
            HTTP_DEPTH="0", login="user:userpw", check=None)
        assert status == 207 and "read" in body and "write-content" not in body
        status, _, body = self.request(
            "PROPFIND", "/user/rw/", priv,
            HTTP_DEPTH="0", login="user:userpw", check=None)
        assert status == 207 and "write-content" in body
        with _Level(logging.INFO):
            status, _, body = self.request(
                "PROPFIND", "/user/rw/",
                PROPFIND_ONE.format(
                    "<D:displayname/><C:calendar-description/>"),
                HTTP_DEPTH="0", login="user:userpw", check=None)
        assert status == 207 and "SharedName" in body and "SharedDesc" in body

    def test_null_overlay_bday_write_and_unconverted_item(self):
        self.mkcalendar("/owner/shown.ics/", login="owner:ownerpw")
        description = (
            "<?xml version='1.0' encoding='utf-8'?>"
            "<D:propertyupdate xmlns:D='DAV:' "
            "xmlns:C='urn:ietf:params:xml:ns:caldav'>"
            "<D:set><D:prop><C:calendar-description>NativeDesc"
            "</C:calendar-description></D:prop></D:set>"
            "</D:propertyupdate>")
        self.request(
            "PROPPATCH", "/owner/shown.ics/", description,
            login="owner:ownerpw")
        self._map(
            "/owner/shown.ics/", "/user/shown/", permissions="r",
            properties={"D:displayname": "OverlayName",
                        "C:calendar-description": "Sentinel"})
        self._rewrite_row(
            "/user/shown/",
            properties={"C:calendar-description": None})
        with _Level(logging.INFO):
            status, _, body = self.request(
                "PROPFIND", "/user/shown/",
                PROPFIND_ONE.format(
                    "<RADICALE:displayname/><C:calendar-description/>"),
                HTTP_DEPTH="0", login="user:userpw", check=None)
        assert status == 207 and "OverlayName" in body and "NativeDesc" in body
        assert "Sentinel" not in body

        self.create_addressbook("/owner/people/", login="owner:ownerpw")
        self.put("/owner/people/nobday.vcf", _vcard(uid="nobday", fn="NoDay"),
                 login="owner:ownerpw")
        self.put("/owner/people/bday.vcf",
                 get_file_content("contact2-with-bday.vcf"),
                 login="owner:ownerpw")
        self._map("/owner/people/", "/user/birthdays/", permissions="r",
                  conversion="bday")
        self._rewrite_row("/user/birthdays/", permissions="rw")
        status, _, body = self.request(
            "PROPFIND", "/user/birthdays/",
            PROPFIND_ONE.format("<D:current-user-privilege-set/>"),
            HTTP_DEPTH="0", login="user:userpw", check=None)
        assert status == 207 and "read" in body
        assert "write-content" not in body

        self._map("/owner/", "/user/principal/", permissions="Rr")
        status, responses = self.propfind(
            "/user/",
            PROPFIND_ONE.format("<D:principal-URL/>"),
            HTTP_DEPTH="1", login="user:userpw")
        principal = responses["/user/principal/"]["D:principal-URL"]
        assert principal[0] == 200
        href = principal[1].find(xmlutils.make_clark("D:href"))
        assert href is not None
        assert "/user/principal//user/" not in "".join(
            principal[1].itertext())

        self.create_addressbook("/owner/nonebook/", login="owner:ownerpw")
        self.create_addressbook("/owner/somebook/", login="owner:ownerpw")
        self.put("/owner/nonebook/nobday.vcf",
                 _vcard(uid="nobday-item", fn="NoDayItem"),
                 login="owner:ownerpw")
        self.put("/owner/somebook/bday.vcf",
                 get_file_content("contact2-with-bday.vcf"),
                 login="owner:ownerpw")
        self._map("/owner/nonebook/", "/user/nobday/", permissions="r",
                  conversion="bday")
        self._map("/owner/somebook/", "/user/yesbday/", permissions="r",
                  conversion="bday")
        self._rewrite_row(
            "/user/nobday/", path_mapped="/owner/nonebook/nobday.vcf")
        self._rewrite_row(
            "/user/yesbday/", path_mapped="/owner/somebook/bday.vcf")
        self._enable_sharing(rights_text=(
            "[all]\nuser: .*\ncollection: .*\npermissions: RrWw\n"))
        status, responses = self.propfind(
            "/user/",
            PROPFIND_ONE.format("<D:getetag/><D:getcontentlength/>"),
            HTTP_DEPTH="1", login="user:userpw")
        missing = responses["/user/nobday/"]
        assert missing["D:getetag"][0] == 404
        assert missing["D:getcontentlength"][0] == 404
        present = responses["/user/yesbday/"]
        assert present["D:getetag"][0] == 200
        assert present["D:getcontentlength"][0] == 200
        assert present["D:getcontentlength"][1].text not in (None, "", "0")
