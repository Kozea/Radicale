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

"""Outcome tests for item-cache debug lines and get/upload edges."""

import logging
import os
import socket
import sys
import tempfile
import xml.etree.ElementTree as ET

import pytest

from radicale import config
from radicale import item as radicale_item
from radicale import storage, xmlutils
from radicale.log import logger


def _event(uid, start="20130901T160000Z", end="20130901T170000Z"):
    text = (
        "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\n"
        "UID:%s\r\nSUMMARY:Cache\r\n"
        "DTSTART:%s\r\nDTEND:%s\r\n"
        "END:VEVENT\r\nEND:VCALENDAR\r\n" % (uid, start, end))
    return radicale_item.Item(collection_path="", text=text)


def _storage(folder):
    configuration = config.load()
    configuration.update({
        "storage": {
            "filesystem_folder": str(folder),
            "filesystem_fsync": False,
        },
    }, "test", privileged=True)
    return storage.load(configuration)


def _time_filters(start, end):
    filt = ET.Element(xmlutils.make_clark("C:filter"))
    comp = ET.SubElement(filt, xmlutils.make_clark("C:comp-filter"))
    comp.set("name", "VCALENDAR")
    rng = ET.SubElement(comp, xmlutils.make_clark("C:time-range"))
    rng.set("start", start)
    rng.set("end", end)
    return [filt]


def test_cache_debug_reports_mtime_or_hash_and_skips_missing_names(
        tmp_path, caplog):
    """A stored item reports which cache key was written.

    Mtime mode and hash mode are the two cache keys. With cache debug off,
    a second read still returns the item and does not claim a cache hit.
    A listed name that is not a file is omitted; the real item remains.
    With the logger below DEBUG, a multi-get still returns both items and
    does not trace each name.
    """
    storage_ = _storage(tmp_path)
    saved_level = logger.level
    try:
        with storage_.acquire_lock("w"):
            collection = storage_.create_collection(
                "/user/cal/", props={"tag": "VCALENDAR"})[0]
            storage_._use_mtime_and_size_for_item_cache = True
            storage_._debug_cache_actions = True
            caplog.set_level(logging.DEBUG, logger="radicale")
            caplog.clear()
            uploaded, previous = collection.upload("mtime.ics", _event("mtime"))
            assert previous is None
            assert uploaded.uid == "mtime"
            assert "with mtime and size" in caplog.text

            storage_._use_mtime_and_size_for_item_cache = False
            caplog.clear()
            uploaded, previous = collection.upload("hash.ics", _event("hash"))
            assert previous is None
            assert uploaded.uid == "hash"
            assert "with hash" in caplog.text

            storage_._use_mtime_and_size_for_item_cache = True
            storage_._debug_cache_actions = False
            caplog.clear()
            collection._upload_all_nonatomic([_event("bulk")])
            assert collection._get("bulk").uid == "bulk"
            assert "with mtime and size" not in caplog.text
            assert "Store item from list with uid: 'bulk'" in caplog.text

            caplog.clear()
            again = collection._get("bulk")
            assert again.uid == "bulk"
            assert "Item cache hit" not in caplog.text

            def listed_and_missing():
                yield "gone.ics"
                yield "bulk"

            collection._list = listed_and_missing
            assert [found.uid for found in collection.get_all()] == ["bulk"]

            logger.setLevel(logging.ERROR)
            caplog.clear()
            multi = dict(collection.get_multi(["bulk", "mtime.ics"]))
            assert multi["bulk"].uid == "bulk"
            assert multi["mtime.ics"].uid == "mtime"
            assert "storage/get_multi" not in caplog.text
    finally:
        logger.setLevel(saved_level)


@pytest.mark.skipif(
    not hasattr(socket, "AF_UNIX"),
    reason="This platform has no unix-socket inode")
def test_mtime_cache_refuses_a_socket_masquerading_as_an_item():
    """A path that exists and is neither a file nor a directory is not an item.

    Mode 000 fails the read check, so the socket is not opened.

    The socket is created under ``/tmp``. Darwin's ``sun_path`` holds 104
    bytes, and the pytest temporary directory on macOS is longer than that.
    """
    # ``dir="/tmp"`` stays short. The default temp directory on macOS does not.
    with tempfile.TemporaryDirectory(prefix="rc", dir="/tmp") as folder:
        storage_ = _storage(folder)
        with storage_.acquire_lock("w"):
            collection = storage_.create_collection(
                "/user/cal/", props={"tag": "VCALENDAR"})[0]
            storage_._use_mtime_and_size_for_item_cache = True
            sock_path = os.path.join(collection._filesystem_path, "sock.ics")
            # ``sun_path`` includes the terminating NUL.
            sun_path_max = 104 if sys.platform == "darwin" else 108
            assert len(os.fsencode(sock_path)) < sun_path_max
            sock = socket.socket(socket.AF_UNIX)
            try:
                sock.bind(sock_path)
                os.chmod(sock_path, 0)
                if not os.access(sock_path, os.R_OK):
                    with pytest.raises(PermissionError):
                        collection._get("sock.ics")
                assert os.path.exists(sock_path)
                assert not os.path.isfile(sock_path)
                assert not os.path.isdir(sock_path)
            finally:
                sock.close()
                # A failed bind leaves no inode. Restoring the mode then
                # would hide the bind error.
                if os.path.exists(sock_path):
                    os.chmod(sock_path, 0o600)


def test_read_lock_recheck_uses_a_cache_entry_that_appears(
        tmp_path, caplog):
    """A read lock looks up the item cache a second time before parsing.

    The first lookup misses and the second, performed only under a read
    lock, finds the entry. The event is returned and is not stored again.
    Under a write lock that second lookup does not run, so the same first
    miss parses the file and stores a cache entry.
    """
    storage_ = _storage(tmp_path)
    caplog.set_level(logging.DEBUG, logger="radicale")
    with storage_.acquire_lock("w"):
        collection = storage_.create_collection(
            "/user/cal/", props={"tag": "VCALENDAR"})[0]
        storage_._use_mtime_and_size_for_item_cache = False
        storage_._debug_cache_actions = True
        uploaded, previous = collection.upload("race.ics", _event("race"))
    assert previous is None
    assert uploaded.uid == "race"
    stored = uploaded.serialize()
    assert stored == _event("race").serialize()

    real_load = collection._load_item_cache

    def miss_once(counter):
        def load(href, cache_hash):
            counter["calls"] += 1
            if counter["calls"] == 1:
                return None
            return real_load(href, cache_hash)
        return load

    read_counter = {"calls": 0}
    collection._load_item_cache = miss_once(read_counter)
    caplog.clear()
    with storage_.acquire_lock("r"):
        found = collection._get("race.ics")
    assert found is not None
    assert found.uid == "race"
    assert found.serialize() == stored
    assert read_counter["calls"] == 2
    assert "Item cache miss" in caplog.text
    assert "Item cache store" not in caplog.text
    assert "Item cache late read" not in caplog.text

    write_counter = {"calls": 0}
    collection._load_item_cache = miss_once(write_counter)
    caplog.clear()
    with storage_.acquire_lock("w"):
        rewritten = collection._get("race.ics")
    assert rewritten is not None
    assert rewritten.uid == "race"
    assert write_counter["calls"] == 1
    assert "Item cache store" in caplog.text


def test_quiet_prefilter_omits_events_outside_the_window(tmp_path, caplog):
    """An event outside the requested window is omitted while logging is quiet.

    The window that contains the event returns it as fully matched. The
    same event is omitted when the window ends at its start, ends strictly
    before its start, or starts at its end. None of those omissions is traced.
    """
    storage_ = _storage(tmp_path)
    saved_level = logger.level
    try:
        with storage_.acquire_lock("w"):
            collection = storage_.create_collection(
                "/user/cal/",
                items=[_event("edge")],
                props={"tag": "VCALENDAR"})[0]
        logger.setLevel(logging.ERROR)
        caplog.set_level(logging.DEBUG, logger="radicale")
        caplog.clear()
        logger.setLevel(logging.ERROR)
        inside = list(collection.get_filtered(
            _time_filters("20130901T000000Z", "20130902T000000Z")))
        assert [(item.uid, matched) for item, matched in inside] == [
            ("edge", True)]
        assert list(collection.get_filtered(
            _time_filters("20130801T000000Z", "20130901T160000Z"))) == []
        assert list(collection.get_filtered(
            _time_filters("20130801T000000Z", "20130901T150000Z"))) == []
        assert list(collection.get_filtered(
            _time_filters("20130901T170000Z", "20130902T000000Z"))) == []
        assert "storage/get_filtered" not in caplog.text
        assert "skip iuid" not in caplog.text
    finally:
        logger.setLevel(saved_level)
