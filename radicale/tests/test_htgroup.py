# This file is part of Radicale - CalDAV and CardDAV server
# Copyright © 2026 Peter Bieringer <pb@bieringer.de>
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

"""Outcome tests for the htgroup membership file."""

import logging
import time

import pytest

from radicale import config, group


def _load(path, cache):
    configuration = config.load()
    configuration.update({
        "group": {
            "type": "htgroup",
            "htgroup_filename": str(path),
            "htgroup_cache": "True" if cache else "False",
        }
    }, "test")
    return group.load(configuration)


class TestHtgroup:
    def test_comments_blank_lines_and_membership(self, tmp_path):
        path = tmp_path / "htgroup"
        path.write_text(
            "# comment\n\nstaff:alice  bob\nops:alice\n",
            encoding="utf-8")
        plugin = _load(path, cache=False)
        assert plugin.groups("alice") == {"staff", "ops"}
        assert plugin.groups("bob") == {"staff"}
        # A doubled space is its own member token.
        assert plugin.groups("") == {"staff"}
        assert plugin.groups("nobody") == set()

    def test_missing_file_raises(self, tmp_path):
        missing = tmp_path / "absent"
        with pytest.raises(RuntimeError, match="Failed to load htgroup file"):
            _load(missing, cache=False)

    def test_empty_group_name_raises_on_init(self, tmp_path):
        path = tmp_path / "htgroup"
        path.write_text(": alice\n", encoding="utf-8")
        with pytest.raises(RuntimeError, match="problematic line"):
            _load(path, cache=False)

    def test_duplicate_group_raises_on_init(self, tmp_path):
        path = tmp_path / "htgroup"
        path.write_text("staff: alice\nstaff: bob\n", encoding="utf-8")
        with pytest.raises(RuntimeError, match="duplicate group"):
            _load(path, cache=False)

    def test_uncached_reread_ignores_new_errors_and_sees_edits(self, tmp_path, caplog):
        caplog.set_level(logging.WARNING)
        path = tmp_path / "htgroup"
        path.write_text("staff: alice\n", encoding="utf-8")
        plugin = _load(path, cache=False)
        assert plugin.groups("alice") == {"staff"}
        path.write_text("staff: alice\nstaff: bob\n: carol\nops: bob\n", encoding="utf-8")
        assert plugin.groups("alice") == {"staff"}
        assert plugin.groups("bob") == {"ops"}
        assert plugin.groups("carol") == set()
        assert "duplicate group" in caplog.text
        assert "problematic line" in caplog.text

    def test_cached_reread_sees_a_rewritten_file(self, tmp_path):
        path = tmp_path / "htgroup"
        path.write_text("staff: alice\n", encoding="utf-8")
        plugin = _load(path, cache=True)
        assert plugin.groups("alice") == {"staff"}
        assert plugin.groups("bob") == set()
        path.write_text("ops: bob\n", encoding="utf-8")
        assert plugin.groups("alice") == set()
        assert plugin.groups("bob") == {"ops"}

    def test_cached_bad_file_reminds_until_it_is_fixed(self, tmp_path, caplog):
        caplog.set_level(logging.WARNING)
        path = tmp_path / "htgroup"
        path.write_text("staff: alice\n", encoding="utf-8")
        plugin = _load(path, cache=True)
        path.write_text("staff: alice\n: bob\n", encoding="utf-8")
        assert plugin.groups("alice") == {"staff"}
        plugin._htgroup_not_ok_time = time.time() - plugin._htgroup_not_ok_reminder_seconds - 5
        assert plugin.groups("alice") == {"staff"}
        assert "REMINDER" in caplog.text

    def test_reread_of_unreadable_path_returns_no_groups(self, tmp_path, caplog):
        caplog.set_level(logging.WARNING)
        path = tmp_path / "htgroup"
        path.write_text("staff: alice\n", encoding="utf-8")
        plugin = _load(path, cache=False)
        path.unlink()
        path.mkdir()
        assert plugin.groups("alice") == set()
        assert "Failed to load htgroup file on re-read" in caplog.text
