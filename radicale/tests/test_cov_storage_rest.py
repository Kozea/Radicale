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

"""Outcome tests for storage lines the rest of the suite still misses."""

import json
import os
import typing
from typing import overload as real_overload

import pytest

from radicale import config, storage
from radicale.storage.multifilesystem import meta as storage_meta


def _configuration(folder):
    configuration = config.load()
    configuration.update({
        "storage": {"filesystem_folder": str(folder), "filesystem_fsync": False},
    }, "test", privileged=True)
    return configuration


def _capture_overloads(paths):
    """Execute ``paths`` where ``@overload`` keeps the original function.

    The files are compiled under their real names so coverage counts the
    stub lines, and they are not installed over the live modules. Reloading
    ``radicale.storage`` would replace ``BaseCollection`` and break every
    later ``isinstance`` check in the suite.
    """
    captured = []

    def capturing(func):
        filename = func.__code__.co_filename.replace("\\", "/")
        if filename.endswith("storage/__init__.py") or filename.endswith(
                "multifilesystem/meta.py"):
            captured.append(func)
        return real_overload(func)

    typing.overload = capturing
    try:
        for path in paths:
            with open(path, encoding="utf-8") as handle:
                source = handle.read()
            exec(compile(source, path, "exec"), {
                "__name__": "overload_probe",
                "__file__": path,
            })
    finally:
        typing.overload = real_overload
    return captured


def test_overload_stubs_return_none_and_leave_props_unchanged(tmp_path):
    """Both overload signatures return None and do not touch stored props.

    The no-key body accepts a missing key. The key-only body rejects that
    same call, which is the boundary of the two signatures.
    """
    storage_ = storage.load(_configuration(tmp_path))
    with storage_.acquire_lock("w"):
        collection = storage_.create_collection(
            "/user/cal/", props={"tag": "VCALENDAR", "D:displayname": "Team"})[0]
    props_path = collection._props_path
    with open(props_path, encoding="utf-8") as handle:
        before = json.load(handle)
    assert before["tag"] == "VCALENDAR"
    assert collection.get_meta("tag") == "VCALENDAR"
    assert collection.get_meta("D:displayname") == "Team"

    captured = _capture_overloads((storage.__file__, storage_meta.__file__))
    try:
        by_file = {}
        for func in captured:
            by_file.setdefault(
                os.path.basename(func.__code__.co_filename), []).append(func)

        def pair(filename):
            optional = [func for func in by_file[filename]
                        if func.__defaults__ == (None,)]
            required = [func for func in by_file[filename]
                        if func.__defaults__ is None]
            assert len(optional) == 1 and len(required) == 1
            return optional[0], required[0]

        base_optional, base_required = pair("__init__.py")
        meta_optional, meta_required = pair("meta.py")

        assert base_optional(collection) is None
        assert base_optional(collection, "tag") is None
        assert base_required(collection, "tag") is None
        with pytest.raises(TypeError, match="key"):
            base_required(collection)

        assert meta_optional(collection) is None
        assert meta_optional(collection, "D:displayname") is None
        assert meta_required(collection, "D:displayname") is None
        with pytest.raises(TypeError, match="key"):
            meta_required(collection)

        with open(props_path, encoding="utf-8") as handle:
            after = json.load(handle)
        assert after == before
        # The live method is the implementation, not the discarded stub.
        assert collection.get_meta("tag") == "VCALENDAR"
        assert collection.get_meta()["D:displayname"] == "Team"
    finally:
        typing.overload = real_overload

    restored = storage.load(_configuration(tmp_path / "restored"))
    with restored.acquire_lock("w"):
        again = restored.create_collection(
            "/user/cal/", props={"tag": "VCALENDAR"})[0]
    assert again.get_meta("tag") == "VCALENDAR"
    assert again.get_meta("missing") is None
