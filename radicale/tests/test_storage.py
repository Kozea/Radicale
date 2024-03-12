# This file is part of Radicale - CalDAV and CardDAV server
# Copyright © 2012-2017 Guillaume Ayoub
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
Tests for storage backends.

"""

import os
import shutil
from typing import ClassVar, cast

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
        self.propfind("/", login="user:")
        self.propfind("/created_by_hook/")

    def test_hook_fail(self) -> None:
        """Verify that a request fails if the hook fails."""
        self.configure({"storage": {"hook": "exit 1"}})
        self.mkcalendar("/calendar.ics/", check=500)

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
