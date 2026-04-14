# This file is part of Radicale - CalDAV and CardDAV server
# Copyright © 2012-2017 Guillaume Ayoub
# Copyright © 2017-2022 Unrud <unrud@outlook.com>
# Copyright © 2024-2026 Peter Bieringer <pb@bieringer.de>
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
Tests for storage backends.

"""

import json
import logging
import os
import re
import shutil
import tempfile
from typing import ClassVar, cast

import pytest

import radicale.tests.custom.storage_simple_sync
from radicale import logger, pathutils
from radicale.tests import BaseTest
from radicale.tests.helpers import get_file_content
from radicale.tests.test_base import TestBaseRequests as _TestBaseRequests


class TestMultiFileSystem(BaseTest):
    """Tests for multifilesystem."""

    def setup_method(self) -> None:
        _TestBaseRequests.setup_method(cast(_TestBaseRequests, self))
        self.configure({"storage": {"type": "multifilesystem"}})

    def test_folder_creation(self) -> None:
        """Verify that the folder is created."""
        folder = os.path.join(self.colpath, "subfolder")
        self.configure({"storage": {"filesystem_folder": folder}})
        assert os.path.isdir(folder)

    def test_folder_creation_with_umask(self) -> None:
        """Verify that the folder is created with umask."""
        folder = os.path.join(self.colpath, "subfolder")
        self.configure({"storage": {"filesystem_folder": folder, "folder_umask": "0077"}})
        assert os.path.isdir(folder)

    def test_fsync(self) -> None:
        """Create a directory and file with syncing enabled."""
        self.configure({"storage": {"_filesystem_fsync": "True"}})
        self.mkcalendar("/calendar.ics/")

    def test_hook(self) -> None:
        """Run hook."""
        self.configure({"storage": {"hook": "mkdir %s" % os.path.join(
            "collection-root", "created_by_hook")}})
        self.mkcalendar("/calendar.ics/")
        self.propfind("/created_by_hook/")

    def test_hook_read_access(self) -> None:
        """Verify that hook is not run for read accesses."""
        self.configure({"storage": {"hook": "mkdir %s" % os.path.join(
            "collection-root", "created_by_hook")}})
        self.propfind("/")
        self.propfind("/created_by_hook/", check=404)

    @pytest.mark.skipif(not shutil.which("flock"), reason="flock command not found")
    def test_hook_storage_locked(self) -> None:
        """Verify that the storage is locked when the hook runs."""
        self.configure({"storage": {"hook": (
            "flock -n .Radicale.lock || exit 0; exit 1")}})
        self.mkcalendar("/calendar.ics/")

    def test_hook_principal_collection_creation(self) -> None:
        """Verify that the hooks runs when a new user is created."""
        self.configure({"storage": {"hook": "mkdir %s" % os.path.join(
            "collection-root", "created_by_hook")}})
        self.configure({"auth": {"type": "none"}})
        self.propfind("/", login="user:")
        self.propfind("/created_by_hook/")

    def test_hook_fail(self) -> None:
        """Verify that a request succeeded if the hook still fails (anyhow no rollback implemented)."""
        self.configure({"storage": {"hook": "exit 1"}})
        self.mkcalendar("/calendar.ics/", check=201)

    def test_item_cache_rebuild(self) -> None:
        """Delete the item cache and verify that it is rebuild."""
        self.mkcalendar("/calendar.ics/")
        event = get_file_content("event1.ics")
        path = "/calendar.ics/event1.ics"
        self.put(path, event)
        _, answer1 = self.get(path)
        cache_folder = os.path.join(self.colpath, "collection-root",
                                    "calendar.ics", ".Radicale.cache", "item")
        assert os.path.exists(os.path.join(cache_folder, "event1.ics"))
        shutil.rmtree(cache_folder)
        _, answer2 = self.get(path)
        assert answer1 == answer2
        assert os.path.exists(os.path.join(cache_folder, "event1.ics"))

    def test_item_cache_rebuild_subfolder(self) -> None:
        """Delete the item cache and verify that it is rebuild."""
        self.configure({"storage": {"use_cache_subfolder_for_item": "True"}})
        self.mkcalendar("/calendar.ics/")
        event = get_file_content("event1.ics")
        path = "/calendar.ics/event1.ics"
        self.put(path, event)
        _, answer1 = self.get(path)
        cache_folder = os.path.join(self.colpath, "collection-cache",
                                    "calendar.ics", ".Radicale.cache", "item")
        assert os.path.exists(os.path.join(cache_folder, "event1.ics"))
        shutil.rmtree(cache_folder)
        _, answer2 = self.get(path)
        assert answer1 == answer2
        assert os.path.exists(os.path.join(cache_folder, "event1.ics"))

    def test_item_cache_rebuild_mtime_and_size(self) -> None:
        """Delete the item cache and verify that it is rebuild."""
        self.configure({"storage": {"use_mtime_and_size_for_item_cache": "True"}})
        self.mkcalendar("/calendar.ics/")
        event = get_file_content("event1.ics")
        path = "/calendar.ics/event1.ics"
        self.put(path, event)
        _, answer1 = self.get(path)
        cache_folder = os.path.join(self.colpath, "collection-root",
                                    "calendar.ics", ".Radicale.cache", "item")
        assert os.path.exists(os.path.join(cache_folder, "event1.ics"))
        shutil.rmtree(cache_folder)
        _, answer2 = self.get(path)
        assert answer1 == answer2
        assert os.path.exists(os.path.join(cache_folder, "event1.ics"))

    def test_put_whole_calendar_uids_used_as_file_names(self) -> None:
        """Test if UIDs are used as file names."""
        _TestBaseRequests.test_put_whole_calendar(
            cast(_TestBaseRequests, self))
        for uid in ("todo", "event"):
            _, answer = self.get("/calendar.ics/%s.ics" % uid)
            assert "\r\nUID:%s\r\n" % uid in answer

    def test_put_whole_calendar_random_uids_used_as_file_names(self) -> None:
        """Test if UIDs are used as file names."""
        _TestBaseRequests.test_put_whole_calendar_without_uids(
            cast(_TestBaseRequests, self))
        _, answer = self.get("/calendar.ics")
        assert answer is not None
        uids = []
        for line in answer.split("\r\n"):
            if line.startswith("UID:"):
                uids.append(line[len("UID:"):])
        for uid in uids:
            _, answer = self.get("/calendar.ics/%s.ics" % uid)
            assert answer is not None
            assert "\r\nUID:%s\r\n" % uid in answer

    def test_put_whole_addressbook_uids_used_as_file_names(self) -> None:
        """Test if UIDs are used as file names."""
        _TestBaseRequests.test_put_whole_addressbook(
            cast(_TestBaseRequests, self))
        for uid in ("contact1", "contact2"):
            _, answer = self.get("/contacts.vcf/%s.vcf" % uid)
            assert "\r\nUID:%s\r\n" % uid in answer

    def test_put_whole_addressbook_random_uids_used_as_file_names(
            self) -> None:
        """Test if UIDs are used as file names."""
        _TestBaseRequests.test_put_whole_addressbook_without_uids(
            cast(_TestBaseRequests, self))
        _, answer = self.get("/contacts.vcf")
        assert answer is not None
        uids = []
        for line in answer.split("\r\n"):
            if line.startswith("UID:"):
                uids.append(line[len("UID:"):])
        for uid in uids:
            _, answer = self.get("/contacts.vcf/%s.vcf" % uid)
            assert answer is not None
            assert "\r\nUID:%s\r\n" % uid in answer

    @pytest.mark.skipif(not pathutils.path_supports_symlink(tempfile.mkdtemp()), reason="TEMP is not supporting symlink")
    def test_collection_sharing_by_softlink(self) -> None:
        """Test collection sharing by softlink."""
        self.configure({"auth": {"type": "none"}})
        path_group_col = "/group/calendar-shared.ics/"
        file_item = "event1.ics"
        self.mkcalendar(path_group_col, login="group:grouppw")
        event = get_file_content(file_item)
        self.put(path_group_col + file_item, event)
        fs_path_group_col = os.path.join(self.colpath, "collection-root", "group", "calendar-shared.ics")
        fs_path_group_col_rel = os.path.join("..", "group", "calendar-shared.ics")
        fs_path_user = os.path.join(self.colpath, "collection-root", "user")
        fs_path_user_col = os.path.join(self.colpath, "collection-root", "user", "calendar-group.ics")
        logger.debug("colpath=%r fs_path_group_col=%r", self.colpath, fs_path_group_col)
        assert os.path.isdir(fs_path_group_col)
        # create user directory and check
        logger.debug("create dir fs_path_user=%r", fs_path_user)
        os.mkdir(fs_path_user)
        assert os.path.isdir(fs_path_user)
        # create relative symlink and check
        logger.debug("create symlink src=%r dst=%r", fs_path_group_col_rel, fs_path_user_col)
        os.symlink(fs_path_group_col_rel, fs_path_user_col)
        logger.debug("test exists: fs_path_user_col=%r", fs_path_user_col)
        assert os.path.exists(fs_path_user_col)
        logger.debug("test is softlink: fs_path_user_col=%r", fs_path_user_col)
        assert os.path.islink(fs_path_user_col)
        self.propfind("/user/", login="user:userpw", HTTP_DEPTH="1")

    def test_colliding_items_by_file_case_insensitive(self, caplog) -> None:
        """Test for colliding files on file systems."""
        caplog.set_level(logging.WARNING)
        self.configure({"logging": {"request_content_on_debug": "False"}})
        fs_colliding_free = pathutils.path_is_collision_free(tempfile.mkdtemp())
        file_item = "EvEnT1.iCs"
        path_coll = "/calendar.ics/"
        self.mkcalendar(path_coll)
        event = get_file_content(file_item.lower())
        path_item = os.path.join(path_coll, file_item)
        path_uc = os.path.join(path_coll, file_item.upper())
        path_lc = os.path.join(path_coll, file_item.lower())
        self.put(path_item, event)
        self.put(path_uc, event, check=409)
        if not fs_colliding_free:
            logs = caplog.messages
            assert len([log for log in logs if "File name collision" in log]) == 1
        self.put(path_lc, event, check=409)
        if not fs_colliding_free:
            logs = caplog.messages
            assert len([log for log in logs if "File name collision" in log]) == 2

    def test_colliding_items_by_dir_case_insensitive(self, caplog) -> None:
        """Test for colliding dirs on file systems."""
        caplog.set_level(logging.WARNING)
        self.configure({"logging": {"request_content_on_debug": "False"}})
        fs_colliding_free = pathutils.path_is_collision_free(tempfile.mkdtemp())
        path_coll = "/CaLeNdAr.ics/"
        self.mkcalendar(path_coll)
        if fs_colliding_free:
            self.mkcalendar(path_coll.lower(), check=201)
        else:
            self.mkcalendar(path_coll.lower(), check=409)
            logs = caplog.messages
            assert len([log for log in logs if "File name collision" in log]) == 1
        if fs_colliding_free:
            self.mkcalendar(path_coll.upper(), check=201)
        else:
            self.mkcalendar(path_coll.upper(), check=409)
            logs = caplog.messages
            assert len([log for log in logs if "File name collision" in log]) == 2

    def test_colliding_items_by_dir_shortname(self, caplog) -> None:
        """Test for colliding dirs (shortname) on file systems."""
        caplog.set_level(logging.WARNING)
        self.configure({"logging": {"request_content_on_debug": "False"}})
        fs_colliding_free = pathutils.path_is_collision_free(tempfile.mkdtemp())
        path_coll = "/calendarlongname.ics/"
        path_coll_short = "/calend~1.ics/"
        self.mkcalendar(path_coll)
        if fs_colliding_free:
            self.mkcalendar(path_coll_short.lower(), check=201)
        else:
            self.mkcalendar(path_coll_short.lower(), check=409)
            logs = caplog.messages
            assert len([log for log in logs if "File name collision" in log]) == 1
        if fs_colliding_free:
            self.mkcalendar(path_coll_short.upper(), check=201)
        else:
            self.mkcalendar(path_coll_short.upper(), check=409)
            logs = caplog.messages
            assert len([log for log in logs if "File name collision" in log]) == 2

    @pytest.mark.skipif(not shutil.which("flock"), reason="flock command not found")
    @pytest.mark.skipif(radicale.log.logger.getEffectiveLevel() == logging.INFO, reason="requires loglevel DEBUG")
    def test_hook_placeholders_PUT(self, caplog) -> None:
        """Run hook and check placeholders via debug log: PUT"""
        caplog.set_level(logging.DEBUG)
        self.configure({"storage": {"hook": "echo \"hook-json {'user':'%(user)s', 'cwd':'%(cwd)s', 'path':'%(path)s', 'request':'%(request)s', 'to_path':'%(to_path)s'}\""}})
        found = 0
        self.mkcalendar("/calendar.ics/")
        event = get_file_content("event1.ics")
        path = "/calendar.ics/event1.ics"
        self.put(path, event)
        for line in caplog.messages:
            if line.find("\"hook-json ") != -1:
                found = 1
                r = re.search('.*\"hook-json ({.*})".*', line)
                if r:
                    s = r.group(1).replace("'", "\"")
                else:
                    break
                d = json.loads(s)
                if d["user"] == "Anonymous":
                    found = found | 2
                if d["cwd"]:
                    found = found | 4
                if d["path"]:
                    found = found | 8
                    if d["path"] == d["cwd"] + "/collection-root/calendar.ics/event1.ics":
                        found = found | 16
                if d["request"]:
                    found = found | 64
                    if d["request"] == "PUT":
                        found = found | 128
                if d["to_path"]:
                    found = found | 32
                    if d["to_path"] == "":
                        found = found | 256
                else:
                    found = found | 256 | 32
        if (found != 511):
            raise ValueError("Logging misses expected hook log line, found=%d data=%r", found, d)
        else:
            logging.info("Logging contains expected hook line, found=%d data=%r", found, d)

    @pytest.mark.skipif(not shutil.which("flock"), reason="flock command not found")
    @pytest.mark.skipif(radicale.log.logger.getEffectiveLevel() == logging.INFO, reason="requires loglevel DEBUG")
    def test_hook_placeholders_DELETE(self, caplog) -> None:
        """Run hook and check placeholders via debug log: DELETE"""
        caplog.set_level(logging.DEBUG)
        self.configure({"storage": {"hook": "echo \"hook-json {'user':'%(user)s', 'cwd':'%(cwd)s', 'path':'%(path)s', 'request':'%(request)s', 'to_path':'%(to_path)s'}\""}})
        found = 0
        self.mkcalendar("/calendar.ics/")
        event = get_file_content("event1.ics")
        path = "/calendar.ics/event1.ics"
        self.put(path, event)
        self.delete(path)
        for line in caplog.messages:
            if line.find("\"hook-json ") != -1:
                found = 1
                r = re.search('.*\"hook-json ({.*})".*', line)
                if r:
                    s = r.group(1).replace("'", "\"")
                else:
                    break
                d = json.loads(s)
                if d["user"] == "Anonymous":
                    found = found | 2
                if d["cwd"]:
                    found = found | 4
                if d["path"]:
                    found = found | 8
                    if d["path"] == d["cwd"] + "/collection-root/calendar.ics/event1.ics":
                        found = found | 16
                if d["request"]:
                    found = found | 64
                    if d["request"] == "DELETE":
                        found = found | 128
                if d["to_path"]:
                    found = found | 32
                    if d["to_path"] == "":
                        found = found | 256
                else:
                    found = found | 256 | 32
        if (found != 511):
            raise ValueError("Logging misses expected hook log line, found=%d data=%r", found, s)
        else:
            logging.info("Logging contains expected hook line, found=%d data=%r", found, d)

    @pytest.mark.skipif(not shutil.which("flock"), reason="flock command not found")
    @pytest.mark.skipif(radicale.log.logger.getEffectiveLevel() == logging.INFO, reason="requires loglevel DEBUG")
    def test_hook_placeholders_MKCALENDAR(self, caplog) -> None:
        """Run hook and check placeholders via debug log: MKCALENDAR"""
        caplog.set_level(logging.DEBUG)
        self.configure({"storage": {"hook": "echo \"hook-json {'user':'%(user)s', 'cwd':'%(cwd)s', 'path':'%(path)s', 'request':'%(request)s', 'to_path':'%(to_path)s'}\""}})
        found = 0
        self.mkcalendar("/calendar.ics/")
        for line in caplog.messages:
            if line.find("\"hook-json ") != -1:
                found = 1
                r = re.search('.*\"hook-json ({.*})".*', line)
                if r:
                    s = r.group(1).replace("'", "\"")
                else:
                    break
                d = json.loads(s)
                if d["user"] == "Anonymous":
                    found = found | 2
                if d["cwd"]:
                    found = found | 4
                if d["path"]:
                    found = found | 8
                    if d["path"] == d["cwd"] + "/collection-root/calendar.ics/":
                        found = found | 16
                if d["request"]:
                    found = found | 64
                    if d["request"] == "MKCALENDAR":
                        found = found | 128
                if d["to_path"]:
                    found = found | 32
                    if d["to_path"] == "":
                        found = found | 256
                else:
                    found = found | 256 | 32
        if (found != 511):
            raise ValueError("Logging misses expected hook log line, found=%d data=%r", found, d)
        else:
            logging.info("Logging contains expected hook line, found=%d data=%r", found, d)

    @pytest.mark.skipif(not shutil.which("flock"), reason="flock command not found")
    @pytest.mark.skipif(radicale.log.logger.getEffectiveLevel() == logging.INFO, reason="requires loglevel DEBUG")
    def test_hook_placeholders_MKCOL(self, caplog) -> None:
        """Run hook and check placeholders via debug log: MKCOL"""
        caplog.set_level(logging.DEBUG)
        self.configure({"storage": {"hook": "echo \"hook-json {'user':'%(user)s', 'cwd':'%(cwd)s', 'path':'%(path)s', 'request':'%(request)s', 'to_path':'%(to_path)s'}\""}})
        found = 0
        self.mkcol("/user1/")
        for line in caplog.messages:
            if line.find("\"hook-json ") != -1:
                found = 1
                r = re.search('.*\"hook-json ({.*})".*', line)
                if r:
                    s = r.group(1).replace("'", "\"")
                else:
                    break
                d = json.loads(s)
                if d["user"] == "Anonymous":
                    found = found | 2
                if d["cwd"]:
                    found = found | 4
                if d["path"]:
                    found = found | 8
                    if d["path"] == d["cwd"] + "/collection-root/user1/":
                        found = found | 16
                if d["request"]:
                    found = found | 64
                    if d["request"] == "MKCOL":
                        found = found | 128
                if d["to_path"]:
                    found = found | 32
                    if d["to_path"] == "":
                        found = found | 256
                else:
                    found = found | 256 | 32
        if (found != 511):
            raise ValueError("Logging misses expected hook log line, found=%d data=%r", found, d)
        else:
            logging.info("Logging contains expected hook line, found=%d data=%r", found, d)

    @pytest.mark.skipif(not shutil.which("flock"), reason="flock command not found")
    @pytest.mark.skipif(radicale.log.logger.getEffectiveLevel() == logging.INFO, reason="requires loglevel DEBUG")
    def test_hook_placeholders_PROPPATCH(self, caplog) -> None:
        """Run hook and check placeholders via debug log: PROPPATCH"""
        caplog.set_level(logging.DEBUG)
        self.configure({"storage": {"hook": "echo \"hook-json {'user':'%(user)s', 'cwd':'%(cwd)s', 'path':'%(path)s', 'request':'%(request)s', 'to_path':'%(to_path)s'}\""}})
        found = 0
        self.mkcalendar("/calendar.ics/")
        proppatch = get_file_content("proppatch_set_calendar_color.xml")
        _, responses = self.proppatch("/calendar.ics/", proppatch)
        for line in caplog.messages:
            if line.find("\"hook-json ") != -1:
                found = 1
                r = re.search('.*\"hook-json ({.*})".*', line)
                if r:
                    s = r.group(1).replace("'", "\"")
                else:
                    break
                d = json.loads(s)
                if d["user"] == "Anonymous":
                    found = found | 2
                if d["cwd"]:
                    found = found | 4
                if d["path"]:
                    found = found | 8
                    if d["path"] == d["cwd"] + "/collection-root/calendar.ics/":
                        found = found | 16
                if d["request"]:
                    found = found | 64
                    if d["request"] == "PROPPATCH":
                        found = found | 128
                if d["to_path"]:
                    found = found | 32
                    if d["to_path"] == "":
                        found = found | 256
                else:
                    found = found | 256 | 32
        if (found != 511):
            raise ValueError("Logging misses expected hook log line, found=%d data=%r", found, d)
        else:
            logging.info("Logging contains expected hook line, found=%d data=%r", found, d)

    @pytest.mark.skipif(not shutil.which("flock"), reason="flock command not found")
    @pytest.mark.skipif(radicale.log.logger.getEffectiveLevel() == logging.INFO, reason="requires loglevel DEBUG")
    def test_hook_placeholders_MOVE(self, caplog) -> None:
        """Run hook and check placeholders via debug log: MOVE"""
        caplog.set_level(logging.DEBUG)
        self.configure({"storage": {"hook": "echo \"hook-json {'user':'%(user)s', 'cwd':'%(cwd)s', 'path':'%(path)s', 'request':'%(request)s', 'to_path':'%(to_path)s'}\""}})
        found = 0
        self.mkcalendar("/calendar.ics/")
        event = get_file_content("event1.ics")
        path1 = "/calendar.ics/event1.ics"
        path2 = "/calendar.ics/event2.ics"
        self.put(path1, event)
        self.request("MOVE", path1, check=201,
                     HTTP_DESTINATION="http://127.0.0.1/"+path2)
        for line in caplog.messages:
            if line.find("\"hook-json ") != -1:
                found = 1
                r = re.search('.*\"hook-json ({.*})".*', line)
                if r:
                    s = r.group(1).replace("'", "\"")
                else:
                    break
                d = json.loads(s)
                if d["user"] == "Anonymous":
                    found = found | 2
                if d["cwd"]:
                    found = found | 4
                if d["path"]:
                    found = found | 8
                    if d["path"] == d["cwd"] + "/collection-root/calendar.ics/event1.ics":
                        found = found | 16
                if d["request"]:
                    found = found | 64
                    if d["request"] == "MOVE":
                        found = found | 128
                if d["to_path"]:
                    found = found | 32
                    if d["to_path"] == d["cwd"] + "/collection-root/calendar.ics/event2.ics":
                        found = found | 256
        if (found != 511):
            raise ValueError("Logging misses expected hook log line, found=%d data=%r", found, d)
        else:
            logging.info("Logging contains expected hook line, found=%d data=%r", found, d)


class TestMultiFileSystemNoLock(BaseTest):
    """Tests for multifilesystem_nolock."""

    def setup_method(self) -> None:
        _TestBaseRequests.setup_method(cast(_TestBaseRequests, self))
        self.configure({"storage": {"type": "multifilesystem_nolock"}})

    test_add_event = _TestBaseRequests.test_add_event
    test_item_cache_rebuild = TestMultiFileSystem.test_item_cache_rebuild


class TestCustomStorageSystem(BaseTest):
    """Test custom backend loading."""

    def setup_method(self) -> None:
        _TestBaseRequests.setup_method(cast(_TestBaseRequests, self))
        self.configure({"storage": {
            "type": "radicale.tests.custom.storage_simple_sync"}})

    full_sync_token_support: ClassVar[bool] = False

    test_add_event = _TestBaseRequests.test_add_event
    _report_sync_token = _TestBaseRequests._report_sync_token
    # include tests related to sync token
    s: str = ""
    for s in dir(_TestBaseRequests):
        if s.startswith("test_") and "sync" in s.split("_"):
            locals()[s] = getattr(_TestBaseRequests, s)
    del s


class TestCustomStorageSystemCallable(BaseTest):
    """Test custom backend loading with ``callable``."""

    def setup_method(self) -> None:
        _TestBaseRequests.setup_method(cast(_TestBaseRequests, self))
        self.configure({"storage": {
            "type": radicale.tests.custom.storage_simple_sync.Storage}})

    test_add_event = _TestBaseRequests.test_add_event
