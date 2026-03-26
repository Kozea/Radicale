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
Integration tests for scene navigation
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


def test_navigation_create_collection_cancel(
    context: BrowserContext, page: Page, radicale_server: str, config: Config
) -> None:
    login(page, radicale_server, config, context=context)
    expect(page.locator("#collectionsscene")).to_be_visible()

    page.click('a[data-name="new"]')
    expect(page.locator("#createcollectionscene")).to_be_visible()

    page.click('#createcollectionscene button[data-name="cancel"]')
    expect(page.locator("#createcollectionscene")).to_be_hidden()
    expect(page.locator("#collectionsscene")).to_be_visible()


def test_navigation_create_collection_submit(
    context: BrowserContext, page: Page, radicale_server: str, config: Config
) -> None:
    login(page, radicale_server, config, context=context)
    expect(page.locator("#collectionsscene")).to_be_visible()

    page.click('a[data-name="new"]')
    expect(page.locator("#createcollectionscene")).to_be_visible()

    page.locator('#createcollectionscene input[data-name="displayname"]').fill(
        "Nav Test Col"
    )
    page.click('#createcollectionscene button[data-name="submit"]')

    expect(page.locator("#createcollectionscene")).to_be_hidden()
    expect(page.locator("#collectionsscene")).to_be_visible()
    expect(page.locator("article:has-text('Nav Test Col')")).to_be_visible()


def test_navigation_delete_collection_cancel(
    context: BrowserContext, page: Page, radicale_server: str, config: Config
) -> None:
    login(page, radicale_server, config, context=context)
    create_collection(page, radicale_server)
    expect(page.locator("#collectionsscene")).to_be_visible()

    page.hover("article:not(.hidden)")
    page.click('article:not(.hidden) a[data-name="delete"]', force=True)
    expect(page.locator("#deleteconfirmationscene")).to_be_visible()

    page.click('#deleteconfirmationscene button[data-name="cancel"]')
    expect(page.locator("#deleteconfirmationscene")).to_be_hidden()
    expect(page.locator("#collectionsscene")).to_be_visible()


def test_navigation_delete_collection_confirm(
    context: BrowserContext, page: Page, radicale_server: str, config: Config
) -> None:
    login(page, radicale_server, config, context=context)
    create_collection(page, radicale_server)
    expect(page.locator("#collectionsscene")).to_be_visible()

    page.hover("article:not(.hidden)")
    page.click('article:not(.hidden) a[data-name="delete"]', force=True)
    expect(page.locator("#deleteconfirmationscene")).to_be_visible()

    # We need to fill the confirmation text
    confirmation_text = page.locator(
        "#deleteconfirmationscene [data-name='deleteconfirmationtext']"
    ).inner_text()
    page.locator("#deleteconfirmationscene input[data-name='confirmationtxt']").fill(
        confirmation_text
    )
    page.click('#deleteconfirmationscene button[data-name="delete"]')

    expect(page.locator("#deleteconfirmationscene")).to_be_hidden()
    expect(page.locator("#collectionsscene")).to_be_visible()
    expect(page.locator("article:not(.hidden)")).to_have_count(0)


def test_navigation_refresh_button(
    context: BrowserContext, page: Page, radicale_server: str, config: Config
) -> None:
    login(page, radicale_server, config, context=context)
    expect(page.locator("#collectionsscene")).to_be_visible()

    page.click('#logoutview a[data-name="refresh"]')
    # It shows LoadingScene briefly then back to CollectionsScene
    expect(page.locator("#collectionsscene")).to_be_visible()
