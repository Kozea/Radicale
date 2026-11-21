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

"""A mtime probe that observes no change is not reported as 1 ns."""

import logging
from types import SimpleNamespace

import pytest

from radicale import config, log, storage
from radicale.storage import multifilesystem


def _patch_mtime_delta(monkeypatch, delta):
    real_stat = multifilesystem.os.stat
    state = {"n": 0, "base": 0}

    def fake_stat(path, *args, **kwargs):
        result = real_stat(path, *args, **kwargs)
        if not str(path).endswith(".Radicale.mtime_test"):
            return result
        state["n"] += 1
        if state["n"] == 1:
            state["base"] = result.st_mtime_ns
            return result
        return SimpleNamespace(st_mtime_ns=state["base"] + delta)

    monkeypatch.setattr(multifilesystem.os, "stat", fake_stat)


@pytest.mark.skipif(log.logger.getEffectiveLevel() == logging.INFO, reason="requires loglevel DEBUG")
def test_unchanged_mtime_probe_is_not_one_nanosecond(tmp_path, monkeypatch, caplog):
    caplog.set_level(logging.DEBUG)
    _patch_mtime_delta(monkeypatch, 0)
    configuration = config.load()
    configuration.update({
        "storage": {"filesystem_folder": str(tmp_path),
                    "filesystem_fsync": False,
                    "use_mtime_and_size_for_item_cache": "False"},
    }, "test", privileged=True)
    storage.load(configuration)
    assert "test get: 0 ns" in caplog.text
    assert "result: 1 ns" not in caplog.text
    assert "may be an option" not in caplog.text
    assert "not successful" in caplog.text
