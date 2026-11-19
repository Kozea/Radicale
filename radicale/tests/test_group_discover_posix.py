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

"""Group collections are discovered through a posix path on every platform."""

import base64
import logging
import os

from radicale import config, storage
from radicale.log import logger


def _storage(folder):
    configuration = config.load()
    configuration.update({
        "storage": {
            "filesystem_folder": str(folder),
            "filesystem_fsync": False,
        },
    }, "test", privileged=True)
    return storage.load(configuration)


def _encoded(name):
    return base64.b64encode(name.encode("ascii")).decode("ascii")


def _trace_calls(monkeypatch, level):
    calls = []
    logger.setLevel(level)

    def trace(msg, *args, **kwargs):
        try:
            calls.append(msg % args if args else msg)
        except Exception:
            calls.append(str(msg))

    monkeypatch.setattr(logger, "trace", trace)
    return calls


def _group_paths(storage_, groups):
    return [
        item.path for item in storage_.discover("/", "1", user_groups=groups)
        if isinstance(item, storage.BaseCollection)]


def test_missing_group_is_skipped_and_present_group_is_listed(tmp_path, monkeypatch):
    """An encoded group directory is listed. A group with no directory is not.

    The logical path is ``GROUPS/<base64>``. A backslash in that path is an
    unsafe component, so the join has to stay posix on Windows too.
    """
    saved = logger.level
    try:
        storage_ = _storage(tmp_path)
        storage_._group_collections_folder = "GROUPS"
        root = storage_._get_collection_root_folder()
        encoded = _encoded("staff")
        missing = _encoded("other")
        os.makedirs(os.path.join(root, "GROUPS"))
        calls = _trace_calls(monkeypatch, logging.DEBUG)
        assert "GROUPS/%s" % encoded not in _group_paths(storage_, {"staff"})
        assert any("is not existing (skip)" in msg for msg in calls)

        os.makedirs(os.path.join(root, "GROUPS", encoded))
        calls = _trace_calls(monkeypatch, logging.DEBUG)
        grouped = _group_paths(storage_, {"staff", "other"})
        assert "GROUPS/%s" % encoded in grouped
        assert "GROUPS/%s" % missing not in grouped
        assert any("child_path" in msg for msg in calls)

        calls = _trace_calls(monkeypatch, logging.ERROR)
        quiet = _group_paths(storage_, {"staff", "other"})
        assert "GROUPS/%s" % encoded in quiet
        assert "GROUPS/%s" % missing not in quiet
        assert calls == []

        calls = _trace_calls(monkeypatch, logging.ERROR)
        assert "GROUPS/%s" % encoded not in _group_paths(storage_, set())
        assert calls == []
    finally:
        logger.setLevel(saved)


def test_windows_join_cannot_hide_an_encoded_group(tmp_path, monkeypatch):
    """Discover still lists the group when ``os.path.join`` inserts a backslash.

    ``path_to_filesystem`` splits on ``/`` and rejects a backslash on Windows.
    The group folder is joined with ``posixpath``, so this replacement of
    ``os.path.join`` does not change the listed path.
    """
    import ntpath

    from radicale.storage.multifilesystem import discover as discover_module

    class _Path:
        def __init__(self, real):
            self._real = real

        def __getattr__(self, name):
            return getattr(self._real, name)

        @staticmethod
        def join(*parts):
            return ntpath.join(*parts)

    class _Os:
        def __init__(self, real):
            self._real = real
            self.path = _Path(real.path)

        def __getattr__(self, name):
            return getattr(self._real, name)

    storage_ = _storage(tmp_path)
    storage_._group_collections_folder = "GROUPS"
    encoded = _encoded("staff")
    os.makedirs(os.path.join(
        storage_._get_collection_root_folder(), "GROUPS", encoded))
    monkeypatch.setattr(discover_module, "os", _Os(discover_module.os))
    assert "GROUPS/%s" % encoded in _group_paths(storage_, {"staff"})
