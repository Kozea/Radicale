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
Integration tests for delete collection scene
"""

import pathlib
from typing import Any, Generator

import pytest
from playwright.sync_api import BrowserContext, Page, expect

from integ_tests.common import (
    NOSHARE_HTPASSWD,
    SHARING_HTPASSWD,
    SHARING_XREMOTE,
    Config,
    create_collection,
    login,
    start_radicale_server,
)


@pytest.fixture
def radicale_server(
    tmp_path: pathlib.Path, config: Config
) -> Generator[str, Any, None]:
    yield from start_radicale_server(tmp_path, config)


@pytest.mark.parametrize("config", [SHARING_HTPASSWD, SHARING_XREMOTE, NOSHARE_HTPASSWD])
def test_delete_wrong_confirmation(
    context: BrowserContext, page: Page, radicale_server: str, config: Config
) -> None:
    login(page, radicale_server, config, context=context)
    create_collection(page, radicale_server)

    # Open delete scene
    page.hover("article:not(.hidden)")
    page.click('article:not(.hidden) a[data-name="delete"]', force=True)

    # Input wrong confirmation
    page.fill('#deleteconfirmationscene input[data-name="confirmationtxt"]', "foo")
    page.click('#deleteconfirmationscene button[data-name="delete"]')

    # Check for error message
    error_locator = page.locator('#deleteconfirmationscene span[data-name="error"]')
    expect(error_locator).to_be_visible()
    expect(error_locator).to_contain_text(
        "Please type DELETE in the confirmation field"
    )

    # Scene should still be visible
    expect(page.locator("#deleteconfirmationscene")).to_be_visible()


@pytest.mark.parametrize("config", [SHARING_HTPASSWD, SHARING_XREMOTE, NOSHARE_HTPASSWD])
def test_delete_correct_confirmation(
    context: BrowserContext, page: Page, radicale_server: str, config: Config
) -> None:
    login(page, radicale_server, config, context=context)
    create_collection(page, radicale_server)

    # Verify collection exists
    expect(page.locator("article:not(.hidden)")).to_have_count(1)

    # Open delete scene
    page.hover("article:not(.hidden)")
    page.click('article:not(.hidden) a[data-name="delete"]', force=True)

    # Input correct confirmation
    page.fill('#deleteconfirmationscene input[data-name="confirmationtxt"]', "DELETE")
    page.click('#deleteconfirmationscene button[data-name="delete"]')

    # Verify collection is gone
    expect(page.locator("article:not(.hidden)")).to_have_count(0)

    # Scene should be hidden
    expect(page.locator("#deleteconfirmationscene")).to_be_hidden()
