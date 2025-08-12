# This file is part of Radicale - CalDAV and CardDAV server
# Copyright © 2012-2017 Guillaume Ayoub
# Copyright © 2017-2022 Unrud <unrud@outlook.com>
# Copyright © 2024-2024 Peter Bieringer <pb@bieringer.de>
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
import os
import shutil
from typing import ClassVar, cast
import logging

import pytest

import radicale.tests.custom.storage_simple_sync
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

    @pytest.mark.skipif(not shutil.which("flock"),
                        reason="flock command not found")
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


class TestStorageHook(BaseTest):
    """Test the storage hook"""

    HOOK_STRING = "Captured stdout from storage hook:"
    SANATISED_STRING = "Sanitized path:"

    # TODO: How to give the result of the cmd to the test
    def setup_method(self) -> None:
        _TestBaseRequests.setup_method(cast(_TestBaseRequests, self))
        cmd = "echo \'{\"user\":\"%(user)s\", \"path\":\"%(path)s\", \"cwd\":\"%(cwd)s\"}\'"
        self.configure({"storage": {"hook": cmd}})

    def get_output(self, records: list[logging.LogRecord]) -> dict[str, str]:
        """
        Get the result of the storage hook execution

        Args:
            records (list[logging.LogRecord]): The records to look through
        """
        for record in records:
            if record.levelname != "DEBUG":
                # This should be a debug level message
                continue
            message = record.getMessage()
            # We assume a message looks like such: [date] [thread] [DEBUG] Captured stdout from storage hook: "{user:"", "path":"", "cwd":""}"
            if self.HOOK_STRING not in message:
                continue
            print("Message:", message)
            _, raw_info = message.split(self.HOOK_STRING)
            raw_info = raw_info.strip("\"")
            try:
                return json.loads(raw_info)
            except json.JSONDecodeError:
                # Try and find the next one
                pass
        assert False, "Unable to find storage hook"

    def check_path(self, records: list[logging.LogRecord], path: str):
        result = self.get_output(records)
        assert result["path"].endswith(path), f"{result["path"]} does not end in {path}"

    def test_put(self, caplog: pytest.LogCaptureFixture) -> None:
        """Create an event"""
        caplog.set_level(logging.INFO)
        self.mkcalendar("/calendar.ics/")
        event = get_file_content("event1.ics")
        path = "/calendar.ics/event1.ics"
        caplog.set_level(logging.DEBUG)
        self.put(path, event)
        self.check_path(caplog.records, path)

        caplog.set_level(logging.INFO)

    def test_update_event(self, caplog: pytest.LogCaptureFixture) -> None:
        """Update an event."""
        caplog.set_level(logging.INFO)
        self.mkcalendar("/calendar.ics/")
        event = get_file_content("event1.ics")
        event_modified = get_file_content("event1_modified.ics")
        path = "/calendar.ics/event1.ics"
        self.put(path, event)
        caplog.set_level(logging.DEBUG)
        self.put(path, event_modified, check=204)
        caplog.set_level(logging.INFO)
        self.check_path(caplog.records, path)

    def test_delete(self, caplog: pytest.LogCaptureFixture) -> None:
        """Delete an event"""
        caplog.set_level(logging.INFO)
        self.mkcalendar("/calendar.ics/")
        event = get_file_content("event1.ics")
        path = "/calendar.ics/event1.ics"
        self.put(path, event)
        caplog.set_level(logging.DEBUG)
        self.delete(path)
        caplog.set_level(logging.INFO)
        self.check_path(caplog.records, path)

    def test_mkcalendar(self, caplog: pytest.LogCaptureFixture) -> None:
        """Make a calendar"""
        path = "/calendar.ics/"
        caplog.set_level(logging.DEBUG)
        self.mkcalendar(path)
        caplog.set_level(logging.INFO)
        self.check_path(caplog.records, path)

    def test_mkcol(self, caplog: pytest.LogCaptureFixture) -> None:
        """Make a collection."""
        path = "/user/"
        caplog.set_level(logging.DEBUG)
        self.mkcol(path)
        caplog.set_level(logging.INFO)
        self.check_path(caplog.records, path)
