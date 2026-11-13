# This file is part of Radicale - CalDAV and CardDAV server
# Copyright © 2017-2022 Unrud <unrud@outlook.com>
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

"""Outcome tests for paths the rest of the unit suite does not drive."""

import errno
import json
import logging
import os
import socket
import sys
import wsgiref.util
from io import BytesIO

import pytest

import radicale
import radicale.item as radicale_item
from radicale import httputils, pathutils, xmlutils
from radicale.storage.multifilesystem import Collection
from radicale.tests import BaseTest
from radicale.tests import broken_hook
from radicale.tests.helpers import get_file_content

CALENDAR_MKCOL = """<?xml version="1.0" encoding="utf-8" ?>
<mkcol xmlns="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
  <set>
    <prop>
      <resourcetype>
        <collection />
        <C:calendar />
      </resourcetype>
    </prop>
  </set>
</mkcol>"""

PROPFIND_NAMES = """<?xml version="1.0" encoding="utf-8"?>
<D:propfind xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
  <D:prop>
    <D:displayname />
    <C:calendar-description />
  </D:prop>
</D:propfind>"""

PROPPATCH_DISPLAYNAME = """<?xml version="1.0" encoding="utf-8"?>
<D:propertyupdate xmlns:D="DAV:">
  <D:set>
    <D:prop>
      <D:displayname>Name</D:displayname>
    </D:prop>
  </D:set>
</D:propertyupdate>"""


class TimeoutStream:
    def read(self, size=-1):
        raise socket.timeout("timed out")


def _errno_error(code):
    if code is None:
        return ValueError("properties are not acceptable")
    return ValueError("failed [Errno %d]" % code)


def _grant_write(test):
    """Owner-only rights omit lowercase w on a top-level collection."""
    rights = os.path.join(test.colpath, "rights")
    with open(rights, "w") as handle:
        handle.write("[all]\nuser: .*\ncollection: .*\npermissions: RrWw\n")
    test.configure({
        "auth": {"type": "none"},
        "rights": {"type": "from_file", "file": rights},
    })


class TestWsgiAndHooks(BaseTest):

    def setup_method(self) -> None:
        super().setup_method()
        self.configure({})

    def test_wsgi_config_path_is_locked(self) -> None:
        saved = os.environ.pop("RADICALE_CONFIG", None)
        radicale._application_instance = None
        radicale._application_config_path = None
        saved_level = radicale.log.logger.level
        saved_factory = logging.getLogRecordFactory()
        saved_register = radicale.log.register_stream
        saved_filters = list(radicale.log.logger.filters)
        path_a = os.path.join(self.colpath, "a.cfg")
        path_b = os.path.join(self.colpath, "b.cfg")
        config_text = "[storage]\nfilesystem_folder = %s\n" % self.colpath
        for path in (path_a, path_b):
            with open(path, "w") as handle:
                handle.write(config_text)

        def start_response(status, headers):
            start_response.status = int(status.split()[0])

        try:
            environ = {"RADICALE_CONFIG": path_a, "wsgi.errors": sys.stderr}
            wsgiref.util.setup_testing_defaults(environ)
            list(radicale.application(environ, start_response))
            assert start_response.status == 302
            environ = {"RADICALE_CONFIG": path_b, "wsgi.errors": sys.stderr}
            wsgiref.util.setup_testing_defaults(environ)
            with pytest.raises(ValueError, match="RADICALE_CONFIG must not change"):
                list(radicale.application(environ, start_response))
        finally:
            radicale._application_instance = None
            radicale._application_config_path = None
            radicale.log.logger.setLevel(saved_level)
            radicale.log.logger.filters[:] = saved_filters
            logging.setLogRecordFactory(saved_factory)
            radicale.log.register_stream = saved_register
            if saved is None:
                os.environ.pop("RADICALE_CONFIG", None)
            else:
                os.environ["RADICALE_CONFIG"] = saved

    def test_broken_hook_falls_back_to_none(self, caplog) -> None:
        caplog.set_level(logging.WARNING)
        broken_hook.Hook.constructed = 0
        broken_hook.Hook.notifications = []
        _grant_write(self)
        self.configure({"hook": {"type": "radicale.tests.broken_hook"}})
        assert broken_hook.Hook.constructed == 1
        assert self.application._hook.enabled is False
        self.mkcalendar("/calendar.ics/")
        self.put("/calendar.ics/event1.ics", get_file_content("event1.ics"))
        assert broken_hook.Hook.notifications == []
        assert any('falling back to "none"' in message for message in caplog.messages)


class TestApplicationLimits(BaseTest):

    def test_temp_missing_or_not_writable(self) -> None:
        saved = os.environ.get("TEMP")
        readonly = os.path.join(self.colpath, "readonly-temp")
        os.mkdir(readonly)
        try:
            os.environ["TEMP"] = os.path.join(self.colpath, "missing-temp")
            with pytest.raises(RuntimeError, match="directory is not existing"):
                self.configure({})
            os.chmod(readonly, 0o500)
            os.environ["TEMP"] = readonly
            with pytest.raises(RuntimeError, match="not writable"):
                self.configure({})
        finally:
            os.chmod(readonly, 0o700)
            if saved is None:
                os.environ.pop("TEMP", None)
            else:
                os.environ["TEMP"] = saved

    def test_script_name_must_be_a_prefix(self) -> None:
        with pytest.raises(RuntimeError, match="has to start with '/'"):
            self.configure({"server": {"script_name": "radicale"}})
        with pytest.raises(RuntimeError, match="must not end with '/'"):
            self.configure({"server": {"script_name": "/radicale/"}})

    def test_unsafe_username_is_cleared(self, caplog) -> None:
        caplog.set_level(logging.INFO)
        self.configure({
            "auth": {"type": "none"},
            "server": {"validate_user_value": "none"},
            "rights": {"type": "owner_only"}})
        status, _headers, _body = self.request(
            "PROPFIND", "/", login="..:secret", check=401)
        assert status == 401
        assert any("Refused unsafe username" in message for message in caplog.messages)

    def test_predefined_collection_is_created_for_a_new_principal(self) -> None:
        htpasswd = os.path.join(self.colpath, ".htpasswd")
        with open(htpasswd, "w") as handle:
            handle.write("tmp:bepo\n")
        self.configure({
            "auth": {"type": "htpasswd",
                     "htpasswd_filename": htpasswd,
                     "htpasswd_encryption": "plain"},
            "rights": {"type": "owner_write"},
            "storage": {"predefined_collections": json.dumps({
                "calendar.ics/": {"tag": "VCALENDAR", "D:displayname": "Predefined"}})}})
        self.propfind("/tmp/", login="tmp:bepo", check=207)
        _status, responses = self.propfind("/tmp/calendar.ics/", login="tmp:bepo")
        response = responses["/tmp/calendar.ics/"]
        assert response["D:displayname"][1].text == "Predefined"

    def test_principal_create_failure_returns_500(self) -> None:
        htpasswd = os.path.join(self.colpath, ".htpasswd")
        with open(htpasswd, "w") as handle:
            handle.write("tmp:bepo\n")
        self.configure({
            "auth": {"type": "htpasswd",
                     "htpasswd_filename": htpasswd,
                     "htpasswd_encryption": "plain"},
            "rights": {"type": "owner_write"},
            "storage": {"predefined_collections": json.dumps({
                "calendar.ics/": {"tag": "VCALENDAR"}})}})
        real = self.application._storage.create_collection

        def fail_principal(href, items=None, props=None):
            if href.strip("/") == "tmp":
                raise ValueError("cannot create principal")
            return real(href, items=items, props=props)

        self.application._storage.create_collection = fail_principal
        self.propfind("/tmp/", login="tmp:bepo", check=500)

        def fail_principal_os(href, items=None, props=None):
            if href.strip("/") == "tmp":
                raise OSError(errno.EIO, "principal create failed")
            return real(href, items=items, props=props)

        self.application._storage.create_collection = fail_principal_os
        self.propfind("/tmp/", login="tmp:bepo", check=500)

    def test_predefined_collection_valueerror_is_logged(self, caplog) -> None:
        caplog.set_level(logging.WARNING)
        htpasswd = os.path.join(self.colpath, ".htpasswd")
        with open(htpasswd, "w") as handle:
            handle.write("tmp:bepo\n")
        self.configure({
            "auth": {"type": "htpasswd",
                     "htpasswd_filename": htpasswd,
                     "htpasswd_encryption": "plain"},
            "rights": {"type": "owner_write"},
            "storage": {"predefined_collections": json.dumps({
                "calendar.ics/": {"tag": "VCALENDAR", "D:displayname": "Predefined"}})}})
        real = self.application._storage.create_collection

        def fail_predefined(href, items=None, props=None):
            if href.strip("/") != "tmp":
                raise ValueError("predefined collection rejected")
            return real(href, items=items, props=props)

        self.application._storage.create_collection = fail_predefined
        self.propfind("/tmp/", login="tmp:bepo", check=207)
        assert any(
            "Failed to create predefined collection" in message
            and "calendar.ics/" in message
            and "predefined collection rejected" in message
            for message in caplog.messages)

    def test_request_body_over_max_length_returns_413(self) -> None:
        self.configure({
            "server": {"_internal_server": "True", "max_content_length": "8"}})
        _status, _headers, body = self.request(
            "PUT", "/calendar.ics/event.ics", data="0123456789", check=413)
        assert body == "Request body too large."


class TestWebdavErrors(BaseTest):

    def setup_method(self) -> None:
        super().setup_method()
        _grant_write(self)

    def _call(self, method, path, data=b"", content_length=None, content_type=None):
        environ = {}
        wsgiref.util.setup_testing_defaults(environ)
        environ["REQUEST_METHOD"] = method
        environ["PATH_INFO"] = path
        if hasattr(data, "read"):
            environ["wsgi.input"] = data
        else:
            if isinstance(data, str):
                data = data.encode()
            environ["wsgi.input"] = BytesIO(data)
            if content_length is None:
                content_length = len(data)
        if content_length is not None:
            environ["CONTENT_LENGTH"] = str(content_length)
        if content_type:
            environ["CONTENT_TYPE"] = content_type
        status = {}

        def start_response(status_line, headers):
            status["code"] = int(status_line.split()[0])

        answers = list(self.application(environ, start_response))
        body = answers[0].decode() if answers else ""
        return status["code"], body

    @pytest.mark.parametrize("method", ["MKCALENDAR", "MKCOL", "PROPPATCH"])
    def test_bad_xml_returns_400(self, method) -> None:
        status, _body = self._call(method, "/calendar.ics/", data=b"<not xml")
        assert status == 400

    @pytest.mark.parametrize("method", ["MKCALENDAR", "MKCOL", "PROPPATCH"])
    def test_read_timeout_returns_408(self, method) -> None:
        status, body = self._call(
            method, "/calendar.ics/", data=TimeoutStream(), content_length=8)
        assert status == 408
        assert body == "Connection timed out."

    def test_bad_properties_return_400(self, monkeypatch) -> None:
        def bad_props(_xml):
            return {"D:displayname": 5}

        monkeypatch.setattr(
            "radicale.app.mkcalendar.xmlutils.props_from_request", bad_props)
        for method in ("MKCALENDAR", "MKCOL"):
            status, _body = self._call(method, "/bad-props.ics/", data=b"<mkcol/>")
            assert status == 400

    def test_tagged_parent_returns_403(self) -> None:
        self.mkcalendar("/calendar.ics/")
        self.mkcalendar("/calendar.ics/nested.ics/", check=403)
        self.mkcol("/calendar.ics/nested/", CALENDAR_MKCOL, check=403)

    def test_mkcol_tagged_without_write_returns_405(self) -> None:
        rights = os.path.join(self.colpath, "rights")
        with open(rights, "w") as handle:
            handle.write("[all]\nuser: .*\ncollection: .*\npermissions: RW\n")
        self.configure({"rights": {"type": "from_file", "file": rights}})
        status, _headers, body = self.request(
            "MKCOL", "/calendar.ics/", CALENDAR_MKCOL, login="tmp:secret", check=None)
        assert status == 403
        assert body == "Access to the requested resource forbidden."

    @pytest.mark.parametrize(("code", "status"), [
        (errno.ENOSPC, 507),
        (errno.EPERM, 403),
        (errno.EACCES, 403),
        (errno.EIO, 500),
        (None, 400),
    ])
    def test_mkcalendar_create_errno(self, monkeypatch, code, status) -> None:
        self.mkcalendar("/parent.ics/")
        # Parent of /errno.ics/ is /, which exists. Create is what fails.
        monkeypatch.setattr(
            self.application._storage, "create_collection",
            lambda *args, **kwargs: (_ for _ in ()).throw(_errno_error(code)))
        self.mkcalendar("/errno.ics/", check=status)

    def test_mkcalendar_colliding_path_returns_409(self, monkeypatch) -> None:
        def boom(*args, **kwargs):
            raise pathutils.CollidingPathError("errno.ics")

        monkeypatch.setattr(self.application._storage, "create_collection", boom)
        self.mkcalendar("/errno.ics/", check=409)

    @pytest.mark.parametrize(("code", "status"), [
        (errno.ENOSPC, 507),
        (errno.EPERM, 403),
        (errno.EACCES, 403),
        (errno.EIO, 500),
        (None, 400),
    ])
    def test_mkcol_create_errno(self, monkeypatch, code, status) -> None:
        monkeypatch.setattr(
            self.application._storage, "create_collection",
            lambda *args, **kwargs: (_ for _ in ()).throw(_errno_error(code)))
        self.mkcol("/errno/", check=status)

    def test_mkcol_colliding_path_returns_409(self, monkeypatch) -> None:
        def boom(*args, **kwargs):
            raise pathutils.CollidingPathError("errno")

        monkeypatch.setattr(self.application._storage, "create_collection", boom)
        self.mkcol("/errno/", check=409)

    def test_move_to_another_host_returns_502(self) -> None:
        self.mkcalendar("/calendar.ics/")
        self.put("/calendar.ics/event1.ics", get_file_content("event1.ics"))
        status, _headers, body = self.request(
            "MOVE", "/calendar.ics/event1.ics",
            HTTP_DESTINATION="http://example.com/calendar.ics/event1.ics",
            check=502)
        assert status == 502
        assert body == "Remote destination not supported."

    def test_move_collection_returns_405(self) -> None:
        self.mkcalendar("/calendar.ics/")
        self.request(
            "MOVE", "/calendar.ics/",
            HTTP_DESTINATION="/elsewhere/calendar.ics/",
            check=405)

    @pytest.mark.parametrize(("code", "status"), [
        (errno.ENOSPC, 507),
        (errno.EPERM, 403),
        (errno.EACCES, 403),
        (errno.EIO, 500),
        (None, 400),
    ])
    def test_move_errno(self, monkeypatch, code, status) -> None:
        self.mkcalendar("/calendar.ics/")
        self.put("/calendar.ics/event1.ics", get_file_content("event1.ics"))
        monkeypatch.setattr(
            self.application._storage, "move",
            lambda *args, **kwargs: (_ for _ in ()).throw(_errno_error(code)))
        self.request(
            "MOVE", "/calendar.ics/event1.ics",
            HTTP_DESTINATION="/calendar.ics/moved.ics",
            check=status)

    def test_whole_calendar_put_stores_calname_and_description(self) -> None:
        body = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Radicale//EN
X-WR-CALNAME:My Calendar
X-WR-CALDESC:A description
BEGIN:VEVENT
UID:event-calname
DTSTART:20300101T120000Z
DTEND:20300101T130000Z
SUMMARY:Named
END:VEVENT
END:VCALENDAR
"""
        self.put("/named.ics/", body)
        _status, responses = self.propfind("/named.ics/", PROPFIND_NAMES)
        response = responses["/named.ics/"]
        assert response["D:displayname"][1].text == "My Calendar"
        assert response["C:calendar-description"][1].text == "A description"

    @pytest.mark.parametrize(("code", "status"), [
        (errno.ENOSPC, 507),
        (errno.EPERM, 403),
        (errno.EACCES, 403),
        (errno.EIO, 500),
        (None, 400),
    ])
    def test_put_upload_errno(self, monkeypatch, code, status) -> None:
        self.mkcalendar("/calendar.ics/")
        monkeypatch.setattr(
            Collection, "upload",
            lambda *args, **kwargs: (_ for _ in ()).throw(_errno_error(code)))
        self.put("/calendar.ics/event1.ics", get_file_content("event1.ics"), check=status)

    @pytest.mark.parametrize(("code", "status"), [
        (errno.ENOSPC, 507),
        (errno.EPERM, 403),
        (errno.EACCES, 403),
        (errno.EIO, 500),
        (None, 400),
    ])
    def test_proppatch_errno(self, monkeypatch, code, status) -> None:
        self.mkcalendar("/calendar.ics/")
        monkeypatch.setattr(
            Collection, "set_meta",
            lambda *args, **kwargs: (_ for _ in ()).throw(_errno_error(code)))
        self.proppatch("/calendar.ics/", PROPPATCH_DISPLAYNAME, check=status)

    def test_proppatch_subscribed_and_component_set(self) -> None:
        self.mkcalendar("/calendar.ics/")
        self.mkcalendar("/subscribed.ics/")
        subscribed = """<?xml version="1.0" encoding="utf-8"?>
<D:propertyupdate xmlns:D="DAV:" xmlns:CS="http://calendarserver.org/ns/">
  <D:set>
    <D:prop>
      <D:resourcetype>
        <D:collection />
        <CS:subscribed />
      </D:resourcetype>
    </D:prop>
  </D:set>
</D:propertyupdate>"""
        status, _headers, _answer = self.request(
            "PROPPATCH", "/subscribed.ics/", subscribed, check=None)
        assert status in (207, 400)
        propfind = """<?xml version="1.0" encoding="utf-8"?>
<D:propfind xmlns:D="DAV:" xmlns:CS="http://calendarserver.org/ns/">
  <D:prop>
    <D:resourcetype />
  </D:prop>
</D:propfind>"""
        _status, responses = self.propfind("/subscribed.ics/", propfind)
        resourcetype = responses["/subscribed.ics/"]["D:resourcetype"][1]
        assert resourcetype.find(xmlutils.make_clark("CS:subscribed")) is not None
        components = """<?xml version="1.0" encoding="utf-8"?>
<D:propertyupdate xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
  <D:set>
    <D:prop>
      <C:supported-calendar-component-set>
        <C:comp name="VEVENT" />
        <C:comp name="VTODO" />
      </C:supported-calendar-component-set>
    </D:prop>
  </D:set>
</D:propertyupdate>"""
        self.proppatch("/calendar.ics/", components)
        propfind = """<?xml version="1.0" encoding="utf-8"?>
<D:propfind xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
  <D:prop>
    <C:supported-calendar-component-set />
  </D:prop>
</D:propfind>"""
        _status, responses = self.propfind("/calendar.ics/", propfind)
        element = responses["/calendar.ics/"]["C:supported-calendar-component-set"][1]
        names = [child.attrib["name"] for child in element.findall(xmlutils.make_clark("C:comp"))]
        assert names == ["VEVENT", "VTODO"]

    def test_shared_proppatch_overlay_maps_valueerror(self) -> None:
        htpasswd = os.path.join(self.colpath, ".htpasswd")
        with open(htpasswd, "w") as handle:
            handle.write("owner:ownerpw\nuser:userpw\n")
        self.configure({
            "auth": {"type": "htpasswd",
                     "htpasswd_filename": htpasswd,
                     "htpasswd_encryption": "plain"},
            "rights": {"type": "owner_only"},
            "sharing": {
                "type": "csv",
                "collection_by_map": "True",
                "permit_create_map": "True",
            }})
        mapped = "/owner/calendar.ics/"
        shared = "/user/shared.ics/"
        self.mkcalendar(mapped, login="owner:ownerpw")
        created = json.dumps({
            "User": "user",
            "PathMapped": mapped,
            "PathOrToken": shared,
            "Permissions": "rP",
            "Enabled": True,
            "Hidden": False,
        })
        _status, _headers, answer = self.request(
            "POST", "/.sharing/v1/map/create", created,
            login="owner:ownerpw", content_type="application/json",
            accept="application/json", check=200)
        assert json.loads(answer)["Status"] == "success"
        enabled = json.dumps({
            "User": "user",
            "PathMapped": mapped,
            "PathOrToken": shared,
        })
        _status, _headers, answer = self.request(
            "POST", "/.sharing/v1/map/enable", enabled,
            login="user:userpw", content_type="application/json",
            accept="application/json", check=200)
        assert json.loads(answer)["Status"] == "success"
        proppatch = """<?xml version="1.0" encoding="utf-8"?>
<D:propertyupdate xmlns:D="DAV:">
<D:set>
<D:prop>
  <I:calendar-color xmlns:I="http://apple.com/ns/ical/">#112233</I:calendar-color>
</D:prop>
</D:set>
</D:propertyupdate>"""

        def raise_enospc(*_args, **_kwargs):
            raise ValueError("failed [Errno %d]" % errno.ENOSPC)

        self.application._sharing.sharing_collection_update = raise_enospc
        status, _headers, body = self.request(
            "PROPPATCH", shared, proppatch, login="user:userpw", check=None)
        assert status == 507
        assert body == "Insufficient Storage.  Please contact the administrator."

        def raise_plain(*_args, **_kwargs):
            raise ValueError("properties are not acceptable")

        self.application._sharing.sharing_collection_update = raise_plain
        status, _headers, body = self.request(
            "PROPPATCH", shared, proppatch, login="user:userpw", check=None)
        assert status == 400
        assert body == "Bad Request"


class TestStorageAndDecoding(BaseTest):

    def setup_method(self) -> None:
        super().setup_method()
        _grant_write(self)

    def _collection(self, path="/calendar.ics/"):
        self.mkcalendar(path)
        return next(self.application._storage.discover(path))

    def _item(self, collection):
        path = collection.path if collection.path.endswith("/") else collection.path + "/"
        self.put(path + "event1.ics", get_file_content("event1.ics"))
        item = collection._get("event1.ics")
        assert item is not None
        return item

    def test_upload_unsafe_href_raises(self) -> None:
        collection = self._collection()
        item = self._item(collection)
        with pytest.raises(pathutils.UnsafePathError):
            collection.upload("../event1.ics", item)

    def test_upload_write_failure_raises(self, monkeypatch) -> None:
        collection = self._collection()
        item = self._item(collection)

        def boom(*args, **kwargs):
            raise OSError(errno.EIO, "disk")

        monkeypatch.setattr(collection, "_atomic_write", boom)
        with pytest.raises(ValueError, match="Failed to store item"):
            collection.upload("event1.ics", item)

    def test_upload_cache_failure_raises(self, monkeypatch) -> None:
        collection = self._collection()
        item = self._item(collection)

        def boom(*args, **kwargs):
            raise OSError(errno.EIO, "cache")

        monkeypatch.setattr(collection, "_store_item_cache", boom)
        with pytest.raises(ValueError, match="Failed to store item cache"):
            collection.upload("event2.ics", item)

    def test_upload_missing_on_reread_raises(self, monkeypatch) -> None:
        collection = self._collection()
        item = self._item(collection)
        monkeypatch.setattr(collection, "_get", lambda *args, **kwargs: None)
        with pytest.raises(RuntimeError, match="Storage modified externally"):
            collection.upload("event2.ics", item)

    def test_temporary_collection_write_failure_raises(self, monkeypatch) -> None:
        collection = self._collection()
        item = self._item(collection)
        real_open = open

        class BadFile:
            def write(self, _data):
                raise OSError(errno.EIO, "temp write")

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

        def fake_open(file, mode="r", *args, **kwargs):
            name = os.fspath(file)
            if ".Radicale.tmp-" in name and "w" in mode and not name.endswith(".Radicale.props"):
                return BadFile()
            return real_open(file, mode, *args, **kwargs)

        monkeypatch.setattr("builtins.open", fake_open)
        with pytest.raises(ValueError, match="Failed to store item") as exc_info:
            self.application._storage.create_collection(
                "/other.ics/", items=[item], props={"tag": "VCALENDAR"})
        assert "temporary collection" in str(exc_info.value)

    def test_broken_item_is_skipped(self, caplog) -> None:
        caplog.set_level(logging.WARNING)
        collection = self._collection()
        with open(os.path.join(collection._filesystem_path, "broken.ics"), "w") as handle:
            handle.write("this is not a calendar component")
        self.propfind("/calendar.ics/", check=207)
        assert collection._get("broken.ics") is None
        assert any("Skip broken item" in message for message in caplog.messages)

    def test_unsafe_href_load_returns_none(self) -> None:
        collection = self._collection()
        assert collection._get("a/b.ics") is None

    def test_invalid_folder_umask_is_logged_and_raised(self, caplog) -> None:
        caplog.set_level(logging.CRITICAL)
        with pytest.raises(ValueError):
            self.configure({"storage": {"folder_umask": "zz"}})
        assert any("storage folder umask defined but invalid" in message
                   for message in caplog.messages)

    def test_decode_request_fails_when_every_charset_fails(self) -> None:
        class Undecodable(bytes):
            def decode(self, encoding="utf-8", errors="strict"):
                raise UnicodeDecodeError(
                    encoding or "undecodable", bytes(self), 0, max(len(self), 1), "forced")

        with pytest.raises(UnicodeDecodeError, match="all codecs failed"):
            httputils.decode_request(
                self.configuration,
                {"CONTENT_TYPE": "text/plain; charset=utf-8"},
                Undecodable(b"\xff"))

    def test_short_request_body_is_400_on_put(self) -> None:
        self.mkcalendar("/calendar.ics/")
        environ = {}
        wsgiref.util.setup_testing_defaults(environ)
        environ["REQUEST_METHOD"] = "PUT"
        environ["PATH_INFO"] = "/calendar.ics/event1.ics"
        environ["CONTENT_TYPE"] = "text/calendar"
        environ["CONTENT_LENGTH"] = "100"
        environ["wsgi.input"] = BytesIO(b"short")
        with pytest.raises(RuntimeError, match="Request body too short"):
            httputils.read_raw_request_body(self.configuration, dict(environ))
        status = {}

        def start_response(status_line, headers):
            status["code"] = int(status_line.split()[0])

        list(self.application(environ, start_response))
        assert status["code"] == 400

    def test_orphan_item_cache_file_is_removed(self) -> None:
        collection = self._collection()
        self.put("/calendar.ics/event1.ics", get_file_content("event1.ics"))
        cache_folder = collection._storage._get_collection_cache_subfolder(
            collection._filesystem_path, ".Radicale.cache", "item")
        orphan = os.path.join(cache_folder, "orphan.ics")
        with open(orphan, "wb") as handle:
            handle.write(b"orphan")
        for name in os.listdir(cache_folder):
            if name != "orphan.ics":
                os.remove(os.path.join(cache_folder, name))
        assert os.path.exists(orphan)
        self.get("/calendar.ics/event1.ics", check=200)
        assert not os.path.exists(orphan)

    def test_item_round_trip_still_uses_real_storage(self) -> None:
        # Keep a concrete read of the item created above the failure cases.
        collection = self._collection()
        item = self._item(collection)
        assert isinstance(item, radicale_item.Item)
        assert item.uid == "event1"
