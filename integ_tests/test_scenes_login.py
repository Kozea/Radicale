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
Integration tests for scene navigation (login/logout specific)
"""

import pathlib
from typing import Any, Generator

import pytest
from playwright.sync_api import Page, expect

from integ_tests.common import (
    NOSHARE_HTPASSWD,
    SHARING_HTPASSWD,
    Config,
    login,
    start_radicale_server,
)


@pytest.fixture(params=[SHARING_HTPASSWD, NOSHARE_HTPASSWD], ids=lambda c: c.name)
def config(request: pytest.FixtureRequest) -> Config:
    return request.param


@pytest.fixture
def radicale_server(
    tmp_path: pathlib.Path, config: Config
) -> Generator[str, Any, None]:
    yield from start_radicale_server(tmp_path, config)


def test_login_logout_login(page: Page, radicale_server: str, config: Config) -> None:
    # 1. First login
    login(page, radicale_server, config)
    expect(page.locator("#collectionsscene")).to_be_visible()

    # 2. Logout
    page.click('#logoutview a[data-name="logout"]')
    expect(page.locator("#loginscene")).to_be_visible()
    expect(page.locator("#collectionsscene")).to_be_hidden()

    # 3. Second login
    login(page, radicale_server, config)
    expect(page.locator("#collectionsscene")).to_be_visible()
