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
Integration tests for edit collection scene
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


@pytest.fixture(
    params=[SHARING_HTPASSWD, SHARING_XREMOTE, NOSHARE_HTPASSWD], ids=lambda c: c.name
)
def config(request: pytest.FixtureRequest) -> Config:
    return request.param


@pytest.fixture
def radicale_server(
    tmp_path: pathlib.Path, config: Config
) -> Generator[str, Any, None]:
    yield from start_radicale_server(tmp_path, config)


def test_edit_save(
    context: BrowserContext, page: Page, radicale_server: str, config: Config
) -> None:
    login(page, radicale_server, config, context=context)
    create_collection(page, radicale_server)

    # Get original values
    article = page.locator("article:not(.hidden)")

    # Open edit scene
    page.hover("article:not(.hidden)")
    page.click('article:not(.hidden) a[data-name="edit"]', force=True)

    # Update title and description
    new_title = "Updated Title"
    new_description = "Updated Description"
    page.fill('#editcollectionscene input[data-name="displayname"]', new_title)
    page.fill('#editcollectionscene input[data-name="description"]', new_description)
    page.click('#editcollectionscene button[data-name="submit"]')

    # Verify updates in the list
    expect(article.locator('[data-name="title"]')).to_have_text(new_title)
    expect(article.locator('[data-name="description"]')).to_have_text(new_description)


def test_edit_cancel(
    context: BrowserContext, page: Page, radicale_server: str, config: Config
) -> None:
    login(page, radicale_server, config, context=context)
    create_collection(page, radicale_server)

    # Get original values
    article = page.locator("article:not(.hidden)")
    original_title = article.locator('[data-name="title"]').text_content()
    original_description = article.locator('[data-name="description"]').text_content()

    # Open edit scene
    page.hover("article:not(.hidden)")
    page.click('article:not(.hidden) a[data-name="edit"]', force=True)

    # Update title and description but cancel
    page.fill('#editcollectionscene input[data-name="displayname"]', "Changed Title")
    page.fill(
        '#editcollectionscene input[data-name="description"]', "Changed Description"
    )
    page.click('#editcollectionscene button[data-name="cancel"]')

    # Verify values remain unchanged
    expect(article.locator('[data-name="title"]')).to_have_text(original_title)
    expect(article.locator('[data-name="description"]')).to_have_text(
        original_description
    )
