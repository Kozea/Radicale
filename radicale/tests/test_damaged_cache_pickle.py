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

"""A damaged cache pickle that raises KeyError is ignored."""

import logging
import os

import pytest

from radicale import config
from radicale import item as radicale_item
from radicale import storage
from radicale.storage.multifilesystem import cache as cache_module
from radicale.storage.multifilesystem import history as history_module
from radicale.storage.multifilesystem import sync as sync_module


def _storage(folder):
    configuration = config.load()
    configuration.update({
        "storage": {
            "filesystem_folder": str(folder),
            "filesystem_fsync": False,
        },
    }, "test", privileged=True)
    return storage.load(configuration)


def _event():
    text = (
        "BEGIN:VCALENDAR\r\nVERSION:2.0\r\n"
        "BEGIN:VEVENT\r\nUID:event1\r\nSUMMARY:Event\r\n"
        "DTSTART:20130901T160000Z\r\nDTEND:20130901T170000Z\r\n"
        "END:VEVENT\r\nEND:VCALENDAR\r\n")
    return radicale_item.Item(collection_path="", text=text)


def _calendar(storage_):
    with storage_.acquire_lock("w"):
        return storage_.create_collection(
            "/user/cal/", items=[_event()], props={"tag": "VCALENDAR"})[0]


def _raise_keyerror(_file):
    raise KeyError(110)


def test_item_cache_keyerror_is_a_damaged_entry(tmp_path, monkeypatch, caplog):
    """KeyError while unpickling an item cache leaves that entry unloaded.

    CPython reports an unknown opcode as UnpicklingError. PyPy raises
    KeyError from the opcode table. The file written here is that opcode.
    """
    caplog.set_level(logging.WARNING)
    storage_ = _storage(tmp_path)
    collection = _calendar(storage_)
    item = _event()
    cache_hash = collection._item_cache_hash(item.serialize().encode())
    collection._store_item_cache("event1.ics", item, cache_hash)
    cache_folder = storage_._get_collection_cache_subfolder(
        collection._filesystem_path, ".Radicale.cache", "item")
    corrupt = os.path.join(cache_folder, "corrupt.ics")
    with open(corrupt, "wb") as handle:
        handle.write(b"not pickle")

    monkeypatch.setattr(cache_module.pickle, "load", _raise_keyerror)
    assert collection._load_item_cache("corrupt.ics", cache_hash) is None
    assert "Failed to load item cache entry" in caplog.text

    monkeypatch.undo()
    caplog.clear()
    assert collection._load_item_cache("corrupt.ics", cache_hash) is None
    assert "Failed to load item cache entry" in caplog.text


def test_history_cache_keyerror_still_builds_a_sync_token(tmp_path, monkeypatch, caplog):
    """KeyError in the history cache starts a new etag instead of failing sync."""
    caplog.set_level(logging.WARNING)
    storage_ = _storage(tmp_path)
    collection = _calendar(storage_)
    with storage_.acquire_lock("w"):
        collection.sync()
    history_folder = storage_._get_collection_cache_subfolder(
        collection._filesystem_path, ".Radicale.cache", "history")
    corrupt = os.path.join(history_folder, "event1.ics")
    with open(corrupt, "wb") as handle:
        handle.write(b"not pickle")

    monkeypatch.setattr(history_module.pickle, "load", _raise_keyerror)
    with storage_.acquire_lock("w"):
        token, changes = collection.sync()
    assert token.startswith("http://radicale.org/ns/sync/")
    assert "event1.ics" in changes
    assert "Failed to load history cache entry" in caplog.text

    monkeypatch.undo()
    caplog.clear()
    with open(corrupt, "wb") as handle:
        handle.write(b"not pickle")
    with storage_.acquire_lock("w"):
        token, changes = collection.sync()
    assert token.startswith("http://radicale.org/ns/sync/")
    assert "event1.ics" in changes
    assert "Failed to load history cache entry" in caplog.text


def test_sync_token_keyerror_is_a_missing_token(tmp_path, monkeypatch, caplog):
    """KeyError in a stored sync token is reported as a missing token.

    The damaged file is removed, and the warning names that token.
    """
    caplog.set_level(logging.WARNING)
    storage_ = _storage(tmp_path)
    collection = _calendar(storage_)
    with storage_.acquire_lock("w"):
        token, _changes = collection.sync()
    token_folder = storage_._get_collection_cache_subfolder(
        collection._filesystem_path, ".Radicale.cache", "sync-token")
    token_path = os.path.join(token_folder, token.rsplit("/", 1)[-1])
    with open(token_path, "wb") as handle:
        handle.write(b"not pickle")

    monkeypatch.setattr(sync_module.pickle, "load", _raise_keyerror)
    with storage_.acquire_lock("w"):
        with pytest.raises(ValueError, match="^Token not found:"):
            collection.sync(token)
    assert not os.path.exists(token_path)
    assert "Failed to load stored sync token" in caplog.text

    monkeypatch.undo()
    caplog.clear()
    with open(token_path, "wb") as handle:
        handle.write(b"not pickle")
    with storage_.acquire_lock("w"):
        with pytest.raises(ValueError, match="^Token not found:"):
            collection.sync(token)
    assert not os.path.exists(token_path)
    assert "Failed to load stored sync token" in caplog.text
