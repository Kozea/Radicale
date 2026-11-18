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

"""Outcome tests for shared-collection WebDAV responses."""

import csv
import json
import logging
import os

from radicale.item import Item
from radicale.log import logger
from radicale.tests import BaseTest
from radicale.tests.helpers import get_file_content

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


EXPAND = (
    "<?xml version='1.0' encoding='utf-8'?>"
    "<C:calendar-query xmlns:D='DAV:' xmlns:C='urn:ietf:params:xml:ns:caldav'>"
    "<D:prop><C:calendar-data><C:expand start='{start}' end='{end}'/>"
    "</C:calendar-data></D:prop>"
    "<C:filter><C:comp-filter name='VCALENDAR'>"
    "<C:comp-filter name='VEVENT'>"
    "<C:time-range start='{start}' end='{end}'/>"
    "</C:comp-filter></C:comp-filter></C:filter>"
    "</C:calendar-query>")


class _TextStatus:
    """STATUS value that is not a string until it is rendered."""

    def __str__(self):
        return " tentative "


class TestCovAppRestSharing(BaseTest):

    def setup_method(self):
        super().setup_method()
        self.htpasswd = os.path.join(self.colpath, ".htpasswd")
        with open(self.htpasswd, "w", encoding="utf-8") as handle:
            handle.write("owner:ownerpw\nuser:userpw\n")
        _grant(self)
        self._enable_sharing()

    def _enable_sharing(self, rights_text=None):
        if rights_text:
            path = os.path.join(self.colpath, "rights")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(rights_text)
            rights = {"type": "from_file", "file": path}
        else:
            rights = {"type": "owner_only"}
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
             properties=None, conversion=None, owner_login="owner:ownerpw",
             user_login="user:userpw"):
        payload = {
            "User": user,
            "PathMapped": mapped,
            "PathOrToken": token,
            "Permissions": permissions,
            "Enabled": True,
            "Hidden": False,
        }
        if properties is not None:
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

    def _rewrite(self, token, **fields):
        path = os.path.join(self.colpath, "collection-db", "sharing.csv")
        with open(path, encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle, delimiter=";")
            rows = list(reader)
            fieldnames = reader.fieldnames
        found = False
        for row in rows:
            if row["PathOrToken"] != token:
                continue
            found = True
            for key, value in fields.items():
                row[key] = value
        assert found, token
        with open(path, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle, fieldnames=fieldnames, delimiter=";")
            writer.writeheader()
            writer.writerows(rows)
        self.configure({})

    def test_freebusy_filename_without_an_ics_suffix(self):
        self.mkcalendar("/owner/cal.ics/", login="owner:ownerpw")
        self.mkcalendar("/owner/other.ics/", login="owner:ownerpw")
        self.put("/owner/cal.ics/event.ics", _event(summary="Busy"),
                 login="owner:ownerpw")
        self.put("/owner/other.ics/event.ics", _event(summary="Busy"),
                 login="owner:ownerpw")
        self._map("/owner/cal.ics/", "/user/blank/", permissions="r",
                  properties={"D:displayname": ""})
        self._map("/owner/other.ics/", "/user/cased/", permissions="r",
                  properties={"D:displayname": "FILE.ICS"})
        status, headers, body = self.request(
            "GET", "/user/blank/",
            QUERY_STRING="view=freebusy&format=vfreebusy"
            "&start=20130601T000000Z&end=20130602T000000Z",
            login="user:userpw", check=None)
        assert status == 200 and "BEGIN:VFREEBUSY" in body
        assert "SUMMARY:Busy" not in body
        assert "-freebusy.ics" in headers.get("Content-Disposition", "")
        assert "FILE" not in headers.get("Content-Disposition", "")
        status, headers, body = self.request(
            "GET", "/user/cased/",
            QUERY_STRING="view=freebusy&format=vfreebusy"
            "&start=20130601T000000Z&end=20130602T000000Z",
            login="user:userpw", check=None)
        assert status == 200 and "BEGIN:VFREEBUSY" in body
        disposition = headers.get("Content-Disposition", "")
        assert "FILE-freebusy.ics" in disposition
        assert "FILE.ICS" not in disposition

    def test_share_propfind_when_debug_logging_is_off(self, caplog):
        self.mkcalendar("/owner/cal.ics/", login="owner:ownerpw")
        self.put("/owner/cal.ics/event.ics", _event(summary="Shared"),
                 login="owner:ownerpw")
        self._map("/owner/cal.ics/", "/user/shared/", permissions="r",
                  properties={"D:displayname": "Overlay",
                              "ICAL:calendar-color": "#112233"})
        caplog.set_level(logging.DEBUG)
        previous = logger.level
        logger.setLevel(logging.WARNING)
        try:
            status, _, body = self.request(
                "PROPFIND", "/user/shared/",
                PROPFIND_ONE.format(
                    "<RADICALE:displayname/><D:displayname/>"
                    "<ICAL:calendar-color "
                    "xmlns:ICAL='http://apple.com/ns/ical/'/>"),
                HTTP_DEPTH="0", login="user:userpw", check=None)
            assert status == 207
            assert "Overlay" in body and "#112233" in body
            assert "replace from share properties" not in "\n".join(caplog.messages)
            status, _, body = self.request(
                "PROPFIND", "/user/",
                PROPFIND_ONE.format("<D:resourcetype/>"),
                HTTP_DEPTH="1", login="user:userpw", check=None)
        finally:
            logger.setLevel(previous)
        assert status == 207 and "/user/shared/" in body
        assert "add mapping" not in "\n".join(caplog.messages)

    def test_bday_counts_principal_suffix_and_failed_conversion(self, caplog):
        self.create_addressbook("/owner/book/", login="owner:ownerpw")
        self.create_addressbook("/owner/empty/", login="owner:ownerpw")
        self.put("/owner/book/plain.vcf", get_file_content("contact1.vcf"),
                 login="owner:ownerpw")
        self.put("/owner/book/bday.vcf",
                 get_file_content("contact2-with-bday.vcf"),
                 login="owner:ownerpw")
        self._map("/owner/book/", "/user/birthdays/", permissions="r",
                  conversion="bday")
        self._map("/owner/empty/", "/user/empty-bday/", permissions="r",
                  conversion="bday")
        self._map("/owner/", "/user/home/", permissions="Rr")
        caplog.set_level(logging.DEBUG)
        previous = logger.level
        logger.setLevel(logging.WARNING)
        try:
            status, _, body = self.request(
                "PROPFIND", "/user/birthdays/",
                PROPFIND_ONE.format("<RADICALE:getcontentcount/>"),
                HTTP_DEPTH="0", login="user:userpw", check=None)
            empty = self.request(
                "PROPFIND", "/user/empty-bday/",
                PROPFIND_ONE.format("<RADICALE:getcontentcount/>"),
                HTTP_DEPTH="0", login="user:userpw", check=None)
            native = self.request(
                "PROPFIND", "/owner/book/",
                PROPFIND_ONE.format("<RADICALE:getcontentcount/>"),
                HTTP_DEPTH="0", login="owner:ownerpw", check=None)
        finally:
            logger.setLevel(previous)
        assert status == 207
        counted = self.parse_responses(body)["/user/birthdays/"]
        assert counted["RADICALE:getcontentcount"] == (
            200, counted["RADICALE:getcontentcount"][1])
        assert counted["RADICALE:getcontentcount"][1].text == "1"
        assert self.parse_responses(empty[2])["/user/empty-bday/"][
            "RADICALE:getcontentcount"][1].text == "0"
        assert self.parse_responses(native[2])["/owner/book/"][
            "RADICALE:getcontentcount"][1].text == "2"
        assert "getcontentcount: start bday" not in "\n".join(caplog.messages)

        real = Item.convert_vcf_to_ics

        def fail_after_admit(item, ShareActions=None):
            converted = real(item, ShareActions=ShareActions)
            if getattr(item, "uid", None) != "contact2-with-bday":
                return converted
            if fail_after_admit.admitted:
                return None
            fail_after_admit.admitted = True
            return converted

        fail_after_admit.admitted = False
        Item.convert_vcf_to_ics = fail_after_admit
        try:
            status, _, body = self.request(
                "PROPFIND", "/user/birthdays/",
                PROPFIND_ONE.format("<D:getetag/><D:getcontentlength/>"),
                HTTP_DEPTH="1", login="user:userpw", check=None)
        finally:
            Item.convert_vcf_to_ics = real
        assert status == 207
        responses = self.parse_responses(body)
        matched = [value for key, value in responses.items()
                   if key.endswith("/bday.ics")]
        assert matched
        props = matched[0]
        assert not isinstance(props, int)
        assert props["D:getetag"][0] == 404
        assert props["D:getcontentlength"][0] == 404

        self._retarget("/user/birthdays/", "/user/birthdays.vcf")
        self._rewrite(
            "/user/home/", PathOrToken="/user/home.vcf", Conversion="bday")
        status, _, body = self.request(
            "PROPFIND", "/user/",
            PROPFIND_ONE.format("<D:resourcetype/>"),
            HTTP_DEPTH="1", login="user:userpw", check=None)
        assert status == 207
        assert "/user/birthdays.ics" in body
        assert "birthdays.vcf" not in body
        status, _, body = self.request(
            "PROPFIND", "/user/home.vcf",
            PROPFIND_ONE.format("<D:principal-URL/>"),
            HTTP_DEPTH="0", login="user:userpw", check=None)
        assert status == 207
        assert "/user/home.ics" in body
        assert "home.vcf" not in body

    def test_subscribed_report_set_omits_calendar_reports(self):
        self.mkcol("/owner/sub.ics/", SUBSCRIBED_MKCOL, login="owner:ownerpw")
        self.mkcalendar("/owner/cal.ics/", login="owner:ownerpw")
        status, _, body = self.request(
            "PROPFIND", "/owner/sub.ics/",
            PROPFIND_ONE.format("<D:supported-report-set/>"),
            HTTP_DEPTH="0", login="owner:ownerpw", check=None)
        assert status == 207
        assert "sync-collection" in body
        assert "calendar-query" not in body
        assert "addressbook-query" not in body
        status, _, body = self.request(
            "PROPFIND", "/owner/cal.ics/",
            PROPFIND_ONE.format("<D:supported-report-set/>"),
            HTTP_DEPTH="0", login="owner:ownerpw", check=None)
        assert status == 207 and "calendar-query" in body
        assert "free-busy-query" in body

    def test_bday_report_keeps_foreign_hrefs_and_converts_contacts(self):
        self.create_addressbook("/owner/book/", login="owner:ownerpw")
        self.put("/owner/book/plain.vcf", get_file_content("contact1.vcf"),
                 login="owner:ownerpw")
        self.put("/owner/book/bday.vcf",
                 get_file_content("contact2-with-bday.vcf"),
                 login="owner:ownerpw")
        self._map("/owner/book/", "/user/birthdays/", permissions="r",
                  conversion="bday")
        query = (
            "<?xml version='1.0' encoding='utf-8'?>"
            "<C:calendar-query xmlns:D='DAV:' "
            "xmlns:C='urn:ietf:params:xml:ns:caldav'>"
            "<D:prop><C:calendar-data/></D:prop>"
            "<C:filter><C:comp-filter name='VCALENDAR'>"
            "<C:comp-filter name='VEVENT'/></C:comp-filter></C:filter>"
            "</C:calendar-query>")
        status, _, body = self.request(
            "REPORT", "/user/birthdays/", query, login="user:userpw",
            check=None)
        assert status == 207
        assert "bday.ics" in body and "VEVENT" in body
        assert "plain" not in body
        assert ".vcf" not in body
        multiget = (
            "<?xml version='1.0' encoding='utf-8'?>"
            "<C:calendar-multiget xmlns:D='DAV:' "
            "xmlns:C='urn:ietf:params:xml:ns:caldav'>"
            "<D:prop><D:getetag/></D:prop>"
            "<D:href>/elsewhere/person.vcf</D:href>"
            "</C:calendar-multiget>")
        status, _, body = self.request(
            "REPORT", "/user/birthdays/", multiget, login="user:userpw",
            check=None)
        assert status == 207
        assert "elsewhere/person.ics" in body
        assert "elsewhere/person.vcf" not in body
        assert "owner/book" not in body
        assert ">404<" in body or "404" in body

    def test_duplicate_share_targets_are_listed_once_without_debug(self, caplog):
        self.mkcalendar("/owner/cal.ics/", login="owner:ownerpw")
        self.put("/owner/cal.ics/event.ics", _event(summary="Once"),
                 login="owner:ownerpw")
        self.mkcalendar("/user/solo.ics/", login="user:userpw")
        self._map("/owner/cal.ics/", "/user/fresh/", permissions="r")
        self._retarget("/user/fresh/", "/user/solo.ics/")
        self._map("/owner/cal.ics/", "/owner/twin/", user="owner",
                  permissions="r", user_login="owner:ownerpw")
        caplog.set_level(logging.DEBUG)
        previous = logger.level
        logger.setLevel(logging.WARNING)
        try:
            status, _, body = self.request(
                "PROPFIND", "/user/",
                PROPFIND_ONE.format("<D:resourcetype/>"),
                HTTP_DEPTH="1", login="user:userpw", check=None)
            assert status == 207
            assert body.count("/user/solo.ics/") == 1
            owner = self.request(
                "PROPFIND", "/owner/",
                PROPFIND_ONE.format("<D:resourcetype/>"),
                HTTP_DEPTH="1", login="owner:ownerpw", check=None)
        finally:
            logger.setLevel(previous)
        assert owner[0] == 207
        assert "/owner/cal.ics/" in owner[2]
        assert "/owner/twin/" not in owner[2]
        logged = "\n".join(caplog.messages)
        assert "skipped (source existing)" not in logged
        assert "backmapped already existing" not in logged

    def test_share_color_absent_from_overlay_stays_on_the_collection(self):
        color = """<?xml version="1.0" encoding="utf-8"?>
            <D:propertyupdate xmlns:D="DAV:">
              <D:set><D:prop>
                <I:calendar-color xmlns:I="http://apple.com/ns/ical/">#abcdef</I:calendar-color>
              </D:prop></D:set>
            </D:propertyupdate>"""
        self.mkcalendar("/owner/cal.ics/", login="owner:ownerpw")
        self.mkcalendar("/owner/other.ics/", login="owner:ownerpw")
        self.request("PROPPATCH", "/owner/cal.ics/", color,
                     login="owner:ownerpw", check=None)
        self.request("PROPPATCH", "/owner/other.ics/", color,
                     login="owner:ownerpw", check=None)
        self._map("/owner/cal.ics/", "/user/colored/", permissions="r",
                  properties={"ICAL:calendar-color": "#111111"})
        self._map("/owner/other.ics/", "/user/blank-color/", permissions="r",
                  properties={"ICAL:calendar-color": None})
        prop = (
            "<ICAL:calendar-color xmlns:ICAL='http://apple.com/ns/ical/'/>")
        colored = self.request(
            "PROPFIND", "/user/colored/", PROPFIND_ONE.format(prop),
            HTTP_DEPTH="0", login="user:userpw", check=None)[2]
        assert "#111111" in colored and "#abcdef" not in colored
        blank = self.request(
            "PROPFIND", "/user/blank-color/", PROPFIND_ONE.format(prop),
            HTTP_DEPTH="0", login="user:userpw", check=None)[2]
        assert "#111111" not in blank
        assert "#abcdef" in blank or ">404<" in blank or "404" in blank
