# This file is part of Radicale - CalDAV and CardDAV server
# Copyright © 2017-2019 Unrud <unrud@outlook.com>
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
Radicale tests with simple requests and rights.
"""

import logging
import os

from radicale import xmlutils
from radicale.tests import BaseTest
from radicale.tests.helpers import get_file_content


class TestBaseRightsRequests(BaseTest):
    """Tests basic requests with rights."""

    def _test_rights(self, rights_type: str, user: str, path: str, mode: str,
                     expected_status: int, with_auth: bool = True) -> None:
        assert mode in ("r", "w")
        assert user in ("", "tmp", "user@domain.test")
        htpasswd_file_path = os.path.join(self.colpath, ".htpasswd")
        with open(htpasswd_file_path, "w") as f:
            f.write("tmp:bepo\nother:bepo\nuser@domain.test:bepo")
        self.configure({
            "rights": {"type": rights_type},
            "auth": {"type": "htpasswd" if with_auth else "none",
                     "htpasswd_filename": htpasswd_file_path,
                     "htpasswd_encryption": "plain"}})
        for u in ("tmp", "other"):
            # Indirect creation of principal collection
            self.propfind("/%s/" % u, login="%s:bepo" % u)
        os.makedirs(os.path.join(self.colpath, "collection-root", "domain.test"), exist_ok=True)
        (self.propfind if mode == "r" else self.proppatch)(
            path, check=expected_status, login="%s:bepo" % user if user else None)

    def test_owner_only(self) -> None:
        self._test_rights("owner_only", "", "/", "r", 401)
        self._test_rights("owner_only", "", "/", "w", 401)
        self._test_rights("owner_only", "", "/tmp/", "r", 401)
        self._test_rights("owner_only", "", "/tmp/", "w", 401)
        self._test_rights("owner_only", "tmp", "/", "r", 207)
        self._test_rights("owner_only", "tmp", "/", "w", 403)
        self._test_rights("owner_only", "tmp", "/tmp/", "r", 207)
        self._test_rights("owner_only", "tmp", "/tmp/", "w", 207)
        self._test_rights("owner_only", "tmp", "/other/", "r", 403)
        self._test_rights("owner_only", "tmp", "/other/", "w", 403)

    def test_owner_only_without_auth(self) -> None:
        self._test_rights("owner_only", "", "/", "r", 207, False)
        self._test_rights("owner_only", "", "/", "w", 401, False)
        self._test_rights("owner_only", "", "/tmp/", "r", 207, False)
        self._test_rights("owner_only", "", "/tmp/", "w", 207, False)

    def test_owner_write(self) -> None:
        self._test_rights("owner_write", "", "/", "r", 401)
        self._test_rights("owner_write", "", "/", "w", 401)
        self._test_rights("owner_write", "", "/tmp/", "r", 401)
        self._test_rights("owner_write", "", "/tmp/", "w", 401)
        self._test_rights("owner_write", "tmp", "/", "r", 207)
        self._test_rights("owner_write", "tmp", "/", "w", 403)
        self._test_rights("owner_write", "tmp", "/tmp/", "r", 207)
        self._test_rights("owner_write", "tmp", "/tmp/", "w", 207)
        self._test_rights("owner_write", "tmp", "/other/", "r", 207)
        self._test_rights("owner_write", "tmp", "/other/", "w", 403)

    def test_owner_write_without_auth(self) -> None:
        self._test_rights("owner_write", "", "/", "r", 207, False)
        self._test_rights("owner_write", "", "/", "w", 401, False)
        self._test_rights("owner_write", "", "/tmp/", "r", 207, False)
        self._test_rights("owner_write", "", "/tmp/", "w", 207, False)

    def test_authenticated(self) -> None:
        self._test_rights("authenticated", "", "/", "r", 401)
        self._test_rights("authenticated", "", "/", "w", 401)
        self._test_rights("authenticated", "", "/tmp/", "r", 401)
        self._test_rights("authenticated", "", "/tmp/", "w", 401)
        self._test_rights("authenticated", "tmp", "/", "r", 207)
        self._test_rights("authenticated", "tmp", "/", "w", 207)
        self._test_rights("authenticated", "tmp", "/tmp/", "r", 207)
        self._test_rights("authenticated", "tmp", "/tmp/", "w", 207)
        self._test_rights("authenticated", "tmp", "/other/", "r", 207)
        self._test_rights("authenticated", "tmp", "/other/", "w", 207)

    def test_authenticated_without_auth(self) -> None:
        self._test_rights("authenticated", "", "/", "r", 207, False)
        self._test_rights("authenticated", "", "/", "w", 207, False)
        self._test_rights("authenticated", "", "/tmp/", "r", 207, False)
        self._test_rights("authenticated", "", "/tmp/", "w", 207, False)

    def test_from_file(self) -> None:
        rights_file_path = os.path.join(self.colpath, "rights")
        with open(rights_file_path, "w") as f:
            f.write("""\
[owner]
user: .+
collection: {user}(/.*)?
permissions: RrWw
[custom]
user: .*
collection: custom(/.*)?
permissions: Rr
[read-domain-principal]
user: .+@([^@]+)
collection: {0}
permissions: R""")
        self.configure({"rights": {"file": rights_file_path}})
        self._test_rights("from_file", "", "/other/", "r", 401)
        self._test_rights("from_file", "tmp", "/tmp/", "r", 207)
        self._test_rights("from_file", "tmp", "/other/", "r", 403)
        self._test_rights("from_file", "", "/custom/sub", "r", 404)
        self._test_rights("from_file", "tmp", "/custom/sub", "r", 404)
        self._test_rights("from_file", "", "/custom/sub", "w", 401)
        self._test_rights("from_file", "tmp", "/custom/sub", "w", 403)
        self._test_rights("from_file", "tmp", "/custom/sub", "w", 403)
        self._test_rights("from_file", "user@domain.test", "/domain.test/", "r", 207)
        self._test_rights("from_file", "user@domain.test", "/tmp/", "r", 403)
        self._test_rights("from_file", "user@domain.test", "/other/", "r", 403)

    def test_from_file_limited_get(self):
        rights_file_path = os.path.join(self.colpath, "rights")
        with open(rights_file_path, "w") as f:
            f.write("""\
[write-all]
user: tmp
collection: .*
permissions: RrWw
[limited-public]
user: .*
collection: public/[^/]*
permissions: i""")
        self.configure({"rights": {"type": "from_file",
                                   "file": rights_file_path}})
        self.configure({"auth": {"type": "none"}})
        self.mkcalendar("/tmp/calendar", login="tmp:bepo")
        self.mkcol("/public", login="tmp:bepo")
        self.mkcalendar("/public/calendar", login="tmp:bepo")
        self.get("/tmp/calendar", check=401)
        self.get("/public/", check=401)
        self.get("/public/calendar")
        self.get("/public/calendar/1.ics", check=401)

    def test_from_file_freebusy(self) -> None:
        """Permission f allows free-busy and not calendar data."""
        rights_file_path = os.path.join(self.colpath, "rights")
        htpasswd_file_path = os.path.join(self.colpath, ".htpasswd")
        with open(rights_file_path, "w") as f:
            f.write("""\
[write-all]
user: tmp
collection: .*
permissions: RrWw
[freebusy]
user: .*
collection: public/[^/]*
permissions: f""")
        with open(htpasswd_file_path, "w") as f:
            f.write("tmp:bepo\nother:bepo\n")
        self.configure({
            "rights": {"type": "from_file", "file": rights_file_path},
            "auth": {"type": "htpasswd",
                     "htpasswd_filename": htpasswd_file_path,
                     "htpasswd_encryption": "plain"}})
        self.mkcol("/public/", login="tmp:bepo")
        calendar_path = "/public/calendar/"
        self.mkcalendar(calendar_path, login="tmp:bepo")
        event_path = calendar_path + "event.ics"
        event = """\
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Radicale//EN
BEGIN:VEVENT
UID:hidden-secret
SUMMARY:Hidden title
DTSTART:20130901T160000Z
DTEND:20130901T170000Z
END:VEVENT
END:VCALENDAR
"""
        self.put(event_path, event, login="tmp:bepo")
        _status, answer = self.get(calendar_path, login="tmp:bepo")
        assert "Hidden title" in answer

        for path in (calendar_path, event_path):
            status, _headers, answer = self.request(
                "GET", path, check=403, login="other:bepo")
            assert "Hidden title" not in answer
            assert "hidden-secret" not in answer

        calendar_query = """\
<?xml version="1.0" encoding="utf-8" ?>
<C:calendar-query xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
    <D:prop>
        <D:getetag />
        <C:calendar-data />
    </D:prop>
    <C:filter>
        <C:comp-filter name="VCALENDAR">
            <C:comp-filter name="VEVENT" />
        </C:comp-filter>
    </C:filter>
</C:calendar-query>"""
        status, _headers, answer = self.request(
            "REPORT", calendar_path, calendar_query, check=403, login="other:bepo")
        assert "Hidden title" not in answer
        assert "hidden-secret" not in answer

        freebusy_query = """\
<?xml version="1.0" encoding="utf-8" ?>
<C:free-busy-query xmlns:C="urn:ietf:params:xml:ns:caldav">
    <C:time-range start="20130901T000000Z" end="20130902T000000Z"/>
</C:free-busy-query>"""
        status, headers, answer = self.request(
            "REPORT", calendar_path, freebusy_query, check=200, login="other:bepo")
        assert headers["Content-Type"].startswith("text/calendar")
        assert answer.count("BEGIN:VFREEBUSY") == 1
        assert "FREEBUSY" in answer
        assert "Hidden title" not in answer
        assert "hidden-secret" not in answer
        status, headers, answer = self.request(
            "REPORT", event_path, freebusy_query, check=403, login="other:bepo")
        assert "Hidden title" not in answer
        assert "BEGIN:VEVENT" not in answer

        propfind_body = """\
<?xml version="1.0" encoding="utf-8" ?>
<D:propfind xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
    <D:prop>
        <D:current-user-privilege-set />
        <D:supported-report-set />
    </D:prop>
</D:propfind>"""
        _status, responses = self.propfind(
            calendar_path, propfind_body, login="other:bepo")
        response = responses[calendar_path]
        assert not isinstance(response, int)
        status, privileges_prop = response["D:current-user-privilege-set"]
        assert status == 200
        privileges = [
            xmlutils.make_human_tag(node.findall("*")[0].tag)
            for node in privileges_prop.findall(xmlutils.make_clark("D:privilege"))]
        assert privileges == ["C:read-free-busy"]
        status, reports_prop = response["D:supported-report-set"]
        assert status == 200
        reports = []
        for supported in reports_prop.findall(xmlutils.make_clark("D:supported-report")):
            report = supported.find(xmlutils.make_clark("D:report"))
            reports.append(xmlutils.make_human_tag(list(report)[0].tag))
        assert reports == ["C:free-busy-query"]
        status, _headers, answer = self.request(
            "PROPFIND", calendar_path, propfind_body, check=403,
            login="other:bepo", HTTP_DEPTH="1")
        assert "Hidden title" not in answer
        assert event_path not in answer
        self.propfind(event_path, propfind_body, check=403, login="other:bepo")

        _status, responses = self.propfind(
            calendar_path, propfind_body, login="tmp:bepo")
        response = responses[calendar_path]
        assert not isinstance(response, int)
        _status, privileges_prop = response["D:current-user-privilege-set"]
        privileges = [
            xmlutils.make_human_tag(node.findall("*")[0].tag)
            for node in privileges_prop.findall(xmlutils.make_clark("D:privilege"))]
        assert "D:read" in privileges
        assert "C:read-free-busy" in privileges
        _status, reports_prop = response["D:supported-report-set"]
        reports = []
        for supported in reports_prop.findall(xmlutils.make_clark("D:supported-report")):
            report = supported.find(xmlutils.make_clark("D:report"))
            reports.append(xmlutils.make_human_tag(list(report)[0].tag))
        assert "C:free-busy-query" in reports
        assert "C:calendar-query" in reports

        status, _headers, answer = self.request(
            "PROPFIND", calendar_path, login="other:bepo", check=207)
        assert "Hidden title" not in answer
        assert "hidden-secret" not in answer
        responses = self.parse_responses(answer)
        response = responses[calendar_path]
        assert not isinstance(response, int)
        assert "D:getcontentlength" not in response

        length_body = """\
<?xml version="1.0" encoding="utf-8" ?>
<D:propfind xmlns:D="DAV:">
    <D:prop>
        <D:getcontentlength />
    </D:prop>
</D:propfind>"""
        status, _headers, answer = self.request(
            "PROPFIND", calendar_path, length_body, login="other:bepo", check=207)
        assert "Hidden title" not in answer
        assert "hidden-secret" not in answer
        responses = self.parse_responses(answer)
        response = responses[calendar_path]
        assert not isinstance(response, int)
        status, _prop = response["D:getcontentlength"]
        assert status == 404

    def test_from_file_freebusy_parent_rights(self) -> None:
        """Parent r or f does not grant free-busy on a child calendar."""
        rights_file_path = os.path.join(self.colpath, "rights")
        htpasswd_file_path = os.path.join(self.colpath, ".htpasswd")
        with open(rights_file_path, "w") as f:
            f.write("""\
[alice]
user: alice
collection: alice(/.*)?
permissions: RrWw
[bob]
user: bob
collection: alice
permissions: r
[carol]
user: carol
collection: alice
permissions: f
[dave-calendar]
user: dave
collection: alice/cal
permissions: i
[dave]
user: dave
collection: alice
permissions: r""")
        with open(htpasswd_file_path, "w") as f:
            f.write("alice:bepo\nbob:bepo\ncarol:bepo\ndave:bepo\n")
        self.configure({
            "rights": {"type": "from_file", "file": rights_file_path},
            "auth": {"type": "htpasswd",
                     "htpasswd_filename": htpasswd_file_path,
                     "htpasswd_encryption": "plain"}})
        calendar_path = "/alice/cal/"
        self.mkcalendar(calendar_path, login="alice:bepo")
        event = """\
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Radicale//EN
BEGIN:VEVENT
UID:hidden-secret
SUMMARY:Hidden title
DTSTART:20130901T160000Z
DTEND:20130901T170000Z
END:VEVENT
END:VCALENDAR
"""
        self.put(calendar_path + "event.ics", event, login="alice:bepo")
        freebusy_query = """\
<?xml version="1.0" encoding="utf-8" ?>
<C:free-busy-query xmlns:C="urn:ietf:params:xml:ns:caldav">
    <C:time-range start="20130901T000000Z" end="20130902T000000Z"/>
</C:free-busy-query>"""
        busy = "FREEBUSY;FBTYPE=BUSY:20130901T160000Z/20130901T170000Z"
        status, headers, answer = self.request(
            "REPORT", calendar_path, freebusy_query, check=200, login="alice:bepo")
        assert headers["Content-Type"].startswith("text/calendar")
        assert busy in answer
        assert "Hidden title" not in answer
        assert "hidden-secret" not in answer

        for login in ("bob:bepo", "carol:bepo"):
            status, _headers, answer = self.request(
                "GET", calendar_path, check=403, login=login)
            assert "Hidden title" not in answer
            assert busy not in answer
        for login in ("bob:bepo", "carol:bepo", "dave:bepo"):
            status, _headers, answer = self.request(
                "REPORT", calendar_path, freebusy_query, check=403, login=login)
            assert "Hidden title" not in answer
            assert "hidden-secret" not in answer
            assert busy not in answer
            status, _headers, answer = self.request(
                "PROPFIND", calendar_path, check=403, login=login)
            assert "Hidden title" not in answer
            assert busy not in answer

        _status, answer = self.get(calendar_path, login="dave:bepo")
        assert "Hidden title" in answer

    def test_from_file_freebusy_write(self) -> None:
        """Permission wf writes events and advertises free-busy only."""
        rights_file_path = os.path.join(self.colpath, "rights")
        htpasswd_file_path = os.path.join(self.colpath, ".htpasswd")
        with open(rights_file_path, "w") as f:
            f.write("""\
[write-all]
user: tmp
collection: .*
permissions: RrWw
[freebusy-write]
user: .*
collection: public/[^/]*
permissions: wf
[other-read]
user: other
collection: other(/.*)?
permissions: RrWw""")
        with open(htpasswd_file_path, "w") as f:
            f.write("tmp:bepo\nother:bepo\n")
        self.configure({
            "rights": {"type": "from_file", "file": rights_file_path},
            "auth": {"type": "htpasswd",
                     "htpasswd_filename": htpasswd_file_path,
                     "htpasswd_encryption": "plain"}})
        self.mkcol("/public/", login="tmp:bepo")
        calendar_path = "/public/calendar/"
        self.mkcalendar(calendar_path, login="tmp:bepo")
        self.mkcol("/other/", login="tmp:bepo")
        self.mkcalendar("/other/mine/", login="tmp:bepo")
        event = """\
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Radicale//EN
BEGIN:VEVENT
UID:hidden-secret
SUMMARY:Hidden title
DESCRIPTION:Hidden details
DTSTART:20130901T160000Z
DTEND:20130901T170000Z
END:VEVENT
END:VCALENDAR
"""
        self.put(calendar_path + "event.ics", event, login="other:bepo")
        status, _headers, answer = self.request(
            "GET", calendar_path, check=403, login="other:bepo")
        assert "Hidden title" not in answer
        calendar_query = """\
<?xml version="1.0" encoding="utf-8" ?>
<C:calendar-query xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
    <D:prop>
        <D:getetag />
        <C:calendar-data />
    </D:prop>
    <C:filter>
        <C:comp-filter name="VCALENDAR">
            <C:comp-filter name="VEVENT" />
        </C:comp-filter>
    </C:filter>
</C:calendar-query>"""
        status, _headers, answer = self.request(
            "REPORT", calendar_path, calendar_query, check=403, login="other:bepo")
        assert "Hidden title" not in answer
        freebusy_query = """\
<?xml version="1.0" encoding="utf-8" ?>
<C:free-busy-query xmlns:C="urn:ietf:params:xml:ns:caldav">
    <C:time-range start="20130901T000000Z" end="20130902T000000Z"/>
</C:free-busy-query>"""
        status, headers, answer = self.request(
            "REPORT", calendar_path, freebusy_query, check=200, login="other:bepo")
        assert headers["Content-Type"].startswith("text/calendar")
        assert "FREEBUSY;FBTYPE=BUSY:20130901T160000Z/20130901T170000Z" in answer
        assert "Hidden title" not in answer
        assert "hidden-secret" not in answer
        propfind_body = """\
<?xml version="1.0" encoding="utf-8" ?>
<D:propfind xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
    <D:prop>
        <D:current-user-privilege-set />
        <D:supported-report-set />
    </D:prop>
</D:propfind>"""
        _status, responses = self.propfind(
            calendar_path, propfind_body, login="other:bepo")
        response = responses[calendar_path]
        assert not isinstance(response, int)
        status, privileges_prop = response["D:current-user-privilege-set"]
        assert status == 200
        privileges = [
            xmlutils.make_human_tag(node.findall("*")[0].tag)
            for node in privileges_prop.findall(xmlutils.make_clark("D:privilege"))]
        assert privileges == ["C:read-free-busy", "D:write-content"]
        status, reports_prop = response["D:supported-report-set"]
        assert status == 200
        reports = []
        for supported in reports_prop.findall(xmlutils.make_clark("D:supported-report")):
            report = supported.find(xmlutils.make_clark("D:report"))
            reports.append(xmlutils.make_human_tag(list(report)[0].tag))
        assert reports == ["C:free-busy-query"]
        status, _headers, answer = self.request(
            "MOVE", calendar_path + "event.ics", check=403, login="other:bepo",
            HTTP_DESTINATION="http://127.0.0.1/other/mine/stolen.ics")
        assert "Hidden title" not in answer
        assert "Hidden details" not in answer
        self.get("/other/mine/stolen.ics", check=404, login="tmp:bepo")
        _status, answer = self.get(calendar_path + "event.ics", login="tmp:bepo")
        assert "Hidden title" in answer
        assert "Hidden details" in answer

    def test_from_file_freebusy_listing(self) -> None:
        """Free-busy calendars stay limited when a parent is readable."""
        rights_file_path = os.path.join(self.colpath, "rights")
        htpasswd_file_path = os.path.join(self.colpath, ".htpasswd")
        with open(rights_file_path, "w") as f:
            f.write("""\
[alice-wf]
user: alice
collection: alice/wf(/.*)?
permissions: wf
[alice-f]
user: alice
collection: alice/f(/.*)?
permissions: f
[alice]
user: alice
collection: alice
permissions: R
[bob-cal]
user: bob
collection: bob/cal(/.*)?
permissions: f
[bob]
user: bob
collection: bob
permissions: r
[carol-cal]
user: carol
collection: carol/cal(/.*)?
permissions: Rf
[owner]
user: tmp
collection: .*
permissions: RrWw""")
        with open(htpasswd_file_path, "w") as f:
            f.write("alice:bepo\nbob:bepo\ncarol:bepo\ntmp:bepo\n")
        self.configure({
            "rights": {"type": "from_file", "file": rights_file_path},
            "auth": {"type": "htpasswd",
                     "htpasswd_filename": htpasswd_file_path,
                     "htpasswd_encryption": "plain"}})
        for principal, calendars in (
                ("/alice/", ("/alice/wf/", "/alice/f/")),
                ("/bob/", ("/bob/cal/",)),
                ("/carol/", ("/carol/cal/",))):
            self.mkcol(principal, login="tmp:bepo")
            for calendar in calendars:
                self.mkcalendar(calendar, login="tmp:bepo")
        event = """\
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Radicale//EN
BEGIN:VEVENT
UID:hidden-secret
SUMMARY:Hidden title
DTSTART:20130901T160000Z
DTEND:20130901T170000Z
END:VEVENT
END:VCALENDAR
"""
        for calendar in ("/alice/wf/", "/alice/f/", "/bob/cal/", "/carol/cal/"):
            self.put(calendar + "event.ics", event, login="tmp:bepo")
        propfind_body = """\
<?xml version="1.0" encoding="utf-8" ?>
<D:propfind xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
    <D:prop>
        <D:current-user-privilege-set />
        <D:supported-report-set />
        <D:getcontentlength />
    </D:prop>
</D:propfind>"""
        freebusy_query = """\
<?xml version="1.0" encoding="utf-8" ?>
<C:free-busy-query xmlns:C="urn:ietf:params:xml:ns:caldav">
    <C:time-range start="20130901T000000Z" end="20130902T000000Z"/>
</C:free-busy-query>"""

        def listed(responses: dict, path: str) -> tuple:
            response = responses[path]
            assert not isinstance(response, int)
            status, privileges_prop = response["D:current-user-privilege-set"]
            assert status == 200
            privileges = [
                xmlutils.make_human_tag(node.findall("*")[0].tag)
                for node in privileges_prop.findall(xmlutils.make_clark("D:privilege"))]
            status, reports_prop = response["D:supported-report-set"]
            assert status == 200
            reports = []
            for supported in reports_prop.findall(xmlutils.make_clark("D:supported-report")):
                report = supported.find(xmlutils.make_clark("D:report"))
                reports.append(xmlutils.make_human_tag(list(report)[0].tag))
            status, _prop = response["D:getcontentlength"]
            return privileges, reports, status

        status, _headers, answer = self.request(
            "PROPFIND", "/alice/", propfind_body, login="alice:bepo",
            HTTP_DEPTH="1", check=207)
        assert "Hidden title" not in answer
        assert "hidden-secret" not in answer
        assert "/alice/wf/event.ics" not in answer
        responses = self.parse_responses(answer)
        assert listed(responses, "/alice/wf/") == (
            ["C:read-free-busy", "D:write-content"], ["C:free-busy-query"], 404)
        assert listed(responses, "/alice/f/") == (
            ["C:read-free-busy"], ["C:free-busy-query"], 404)

        for path, login in (("/alice/wf/", "alice:bepo"),
                            ("/alice/f/", "alice:bepo"),
                            ("/bob/cal/", "bob:bepo"),
                            ("/carol/cal/", "carol:bepo")):
            status, _headers, answer = self.request(
                "PROPFIND", path, propfind_body, login=login, check=207)
            assert "Hidden title" not in answer
            assert "hidden-secret" not in answer
            responses = self.parse_responses(answer)
            if path == "/alice/wf/":
                assert listed(responses, path) == (
                    ["C:read-free-busy", "D:write-content"],
                    ["C:free-busy-query"], 404)
            else:
                assert listed(responses, path) == (
                    ["C:read-free-busy"], ["C:free-busy-query"], 404)
            status, _headers, answer = self.request(
                "PROPFIND", path, propfind_body, login=login,
                HTTP_DEPTH="1", check=403)
            assert "Hidden title" not in answer
            status, headers, answer = self.request(
                "REPORT", path, freebusy_query, login=login, check=200)
            assert headers["Content-Type"].startswith("text/calendar")
            assert "FREEBUSY;FBTYPE=BUSY:20130901T160000Z/20130901T170000Z" in answer
            assert "Hidden title" not in answer
            assert "hidden-secret" not in answer

    def test_from_file_freebusy_view(self) -> None:
        """Permission f or i can read the free-busy view and not event details."""
        rights_file_path = os.path.join(self.colpath, "rights")
        htpasswd_file_path = os.path.join(self.colpath, ".htpasswd")
        with open(rights_file_path, "w") as f:
            f.write("""\
[write-all]
user: tmp
collection: .*
permissions: RrWw
[freebusy]
user: other
collection: public/[^/]*
permissions: f
[limited]
user: limited
collection: public/[^/]*
permissions: i""")
        with open(htpasswd_file_path, "w") as f:
            f.write("tmp:bepo\nother:bepo\nlimited:bepo\n")
        self.configure({
            "rights": {"type": "from_file", "file": rights_file_path},
            "auth": {"type": "htpasswd",
                     "htpasswd_filename": htpasswd_file_path,
                     "htpasswd_encryption": "plain"}})
        self.mkcol("/public/", login="tmp:bepo")
        calendar_path = "/public/calendar/"
        self.mkcalendar(calendar_path, login="tmp:bepo")
        event = """\
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Radicale//EN
BEGIN:VEVENT
UID:hidden-secret
SUMMARY:Hidden title
DESCRIPTION:Hidden details
DTSTART:20130901T160000Z
DTEND:20130901T170000Z
END:VEVENT
END:VCALENDAR
"""
        self.put(calendar_path + "event.ics", event, login="tmp:bepo")
        query = "view=freebusy&start=20130901T000000Z&end=20130902T000000Z"
        _, _, answer = self.request(
            "GET", calendar_path, check=403, login="other:bepo")
        assert "Hidden title" not in answer
        assert "Hidden details" not in answer
        _, headers, answer = self.request(
            "GET", calendar_path, check=200, login="other:bepo",
            QUERY_STRING=query)
        assert headers["Content-Type"].startswith("text/calendar")
        assert answer.count("BEGIN:VFREEBUSY") == 1
        assert "FREEBUSY;FBTYPE=BUSY:20130901T160000Z/20130901T170000Z" in answer
        for secret in ("SUMMARY", "DESCRIPTION", "UID", "Hidden title",
                       "Hidden details", "hidden-secret", "BEGIN:VEVENT"):
            assert secret not in answer
        _, _, answer = self.request(
            "GET", calendar_path, check=200, login="limited:bepo")
        assert "Hidden title" in answer
        assert "Hidden details" in answer
        _, _, answer = self.request(
            "GET", calendar_path, check=200, login="limited:bepo",
            QUERY_STRING=query)
        assert answer.count("BEGIN:VFREEBUSY") == 1
        assert "FREEBUSY;FBTYPE=BUSY:20130901T160000Z/20130901T170000Z" in answer
        for secret in ("SUMMARY", "DESCRIPTION", "UID", "Hidden title",
                       "Hidden details", "hidden-secret", "BEGIN:VEVENT"):
            assert secret not in answer

    def test_custom(self) -> None:
        """Custom rights management."""
        self._test_rights("radicale.tests.custom.rights", "", "/", "r", 401)
        self._test_rights(
            "radicale.tests.custom.rights", "", "/tmp/", "r", 207)

    def test_collections_and_items(self) -> None:
        """Test rights for creation of collections, calendars and items.

        Collections are allowed at "/" and "/.../".
        Calendars/Address books are allowed at "/.../.../".
        Items are allowed at "/.../.../...".

        """
        self.configure({"auth": {"type": "none"}})
        self.mkcalendar("/", check=401)
        self.mkcalendar("/user/", check=401)
        self.mkcol("/user/")
        self.mkcol("/user/calendar/", check=401)
        self.mkcalendar("/user/calendar/")
        self.mkcol("/user/calendar/item", check=401)
        self.mkcalendar("/user/calendar/item", check=401)

    def test_put_collections_and_items(self) -> None:
        """Test rights for creation of calendars and items with PUT."""
        self.configure({"auth": {"type": "none"}})
        self.put("/user/", "BEGIN:VCALENDAR\r\nEND:VCALENDAR", check=401)
        self.mkcol("/user/")
        self.put("/user/calendar/", "BEGIN:VCALENDAR\r\nEND:VCALENDAR")
        event1 = get_file_content("event1.ics")
        self.put("/user/calendar/event1.ics", event1)

    def test_conflicting_rights(self) -> None:
        """tests conflicting rights permissions."""
        rights_file_path = os.path.join(self.colpath, "rights")

        logging.info("\n*** check conflicting rights: Dd")
        with open(rights_file_path, "w") as f:
            f.write("""\
[owner1-Dd]
user: owner1
collection: {user}/cal-Dd(/.*)?
permissions: RrWwDd""")

        try:
            self.configure({"rights": {"file": rights_file_path, "type": "from_file"}})
        except RuntimeError as e:
            logging.debug("Exception: %s", str(e))
            assert "Dd" in str(e)
        except Exception:
            raise

        logging.info("\n*** check conflicting rights: Oo")
        with open(rights_file_path, "w") as f:
            f.write("""\
[owner1-Oo]
user: owner1
collection: {user}/cal-Oo(/.*)?
permissions: RrWwOo""")

        try:
            self.configure({"rights": {"file": rights_file_path, "type": "from_file"}})
        except RuntimeError as e:
            logging.debug("Exception: %s", str(e))
            assert "Oo" in str(e)
        except Exception:
            raise

        logging.info("\n*** check conflicting rights: Tt")
        with open(rights_file_path, "w") as f:
            f.write("""\
[owner1-Tt]
user: owner1
collection: {user}/cal-Tt(/.*)?
permissions: RrWwTt""")

        try:
            self.configure({"rights": {"file": rights_file_path, "type": "from_file"}})
        except RuntimeError as e:
            logging.debug("Exception: %s", str(e))
            assert "Tt" in str(e)
        except Exception:
            raise

        logging.info("\n*** check conflicting rights: Mm")
        with open(rights_file_path, "w") as f:
            f.write("""\
[owner1-Mm]
user: owner1
collection: {user}/cal-Mm(/.*)?
permissions: RrWwMm""")

        try:
            self.configure({"rights": {"file": rights_file_path, "type": "from_file"}})
        except RuntimeError as e:
            logging.debug("Exception: %s", str(e))
            assert "Mm" in str(e)
        except Exception:
            raise

        logging.info("\n*** check conflicting rights: pP")
        with open(rights_file_path, "w") as f:
            f.write("""\
[owner1-Pp]
user: owner1
collection: {user}/cal-Pp(/.*)?
permissions: RrWwPp""")

        try:
            self.configure({"rights": {"file": rights_file_path, "type": "from_file"}})
        except RuntimeError as e:
            logging.debug("Exception: %s", str(e))
            assert "Pp" in str(e)
        except Exception:
            raise

        logging.info("\n*** check conflicting rights: Ee")
        with open(rights_file_path, "w") as f:
            f.write("""\
[owner1-Ee]
user: owner1
collection: {user}/cal-Ee(/.*)?
permissions: RrWwEe""")

        try:
            self.configure({"rights": {"file": rights_file_path, "type": "from_file"}})
        except RuntimeError as e:
            logging.debug("Exception: %s", str(e))
            assert "Ee" in str(e)
        except Exception:
            raise

        logging.info("\n*** check server-side-only rights flag: U")
        with open(rights_file_path, "w") as f:
            f.write("""\
[owner1-U]
user: owner1
collection: {user}/cal-U(/.*)?
permissions: RrWwU""")

        try:
            self.configure({"rights": {"file": rights_file_path, "type": "from_file"}})
        except RuntimeError as e:
            logging.debug("Exception: %s", str(e))
            assert "U" in str(e)
        except Exception:
            raise

        logging.info("\n*** check server-side-only rights flag: u")
        with open(rights_file_path, "w") as f:
            f.write("""\
[owner1-u]
user: owner1
collection: {user}/cal-u(/.*)?
permissions: RrWwu""")

        try:
            self.configure({"rights": {"file": rights_file_path, "type": "from_file"}})
        except RuntimeError as e:
            logging.debug("Exception: %s", str(e))
            assert "u" in str(e)
        except Exception:
            raise
