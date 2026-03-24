# This file is part of Radicale - CalDAV and CardDAV server
# Copyright © 2026-2026 Max Berger <max@berger.name>
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
Integration test for basic operations
"""

import pathlib
from typing import Any, Generator

import pytest
from playwright.sync_api import Page, expect

from integ_tests.common import login, start_radicale_server


@pytest.fixture
def radicale_server(tmp_path: pathlib.Path) -> Generator[str, Any, None]:
    yield from start_radicale_server(tmp_path)


def test_index_html_loads(page: Page, radicale_server: str) -> None:
    """Test that the index.html loads from the server."""
    console_msgs: list[str] = []
    page.on("console", lambda msg: console_msgs.append(msg.text))
    page.goto(radicale_server)
    expect(page).to_have_title("Radicale Web Interface")
    # There should be no errors on the console, except for the expected 401 from auto-login check
    errors = [msg for msg in console_msgs if "401 (Unauthorized)" not in msg]
    assert len(errors) == 0


def test_user_login_works(page: Page, radicale_server: str) -> None:
    """Test that the login form works."""
    login(page, radicale_server)

    # After login, we should see the collections list (which is empty)
    expect(
        page.locator('span[data-name="user"]', has_text="admin's Collections")
    ).to_be_visible()
