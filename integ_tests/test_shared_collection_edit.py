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
Integration tests for editing properties of a shared collection.
"""

import pathlib
from typing import Any, Generator

import pytest
from playwright.sync_api import Page, expect

from integ_tests.common import (SHARING_HTPASSWD, create_named_collection,
                                login, share_collection_to_user,
                                start_radicale_server)


@pytest.fixture
def radicale_server(tmp_path: pathlib.Path) -> Generator[str, Any, None]:
    yield from start_radicale_server(tmp_path, SHARING_HTPASSWD)


def test_shared_collection_property_edit(page: Page, radicale_server: str) -> None:
    config = SHARING_HTPASSWD

    # 1. Admin logs in and creates "Shared"
    login(page, radicale_server, config)
    create_named_collection(page, "Shared")

    # 2. Admin shares it with "max" with "Allow Properties write" enabled
    share_collection_to_user(
        page, "Shared", config.user_username, "shared-mapped", allow_properties_write=True
    )

    # 3. Admin logs out
    page.click('a[data-name="logout"]')
    expect(page.locator("#loginscene")).to_be_visible()

    # 4. Max logs in
    page.fill('#loginscene input[data-name="user"]', config.user_username)
    page.fill('#loginscene input[data-name="password"]', "userpassword")
    page.click('button:has-text("Next")')
    expect(page.locator("#collectionsscene")).to_be_visible()
    expect(page.locator("#loadingscene")).to_be_hidden()

    # 5. Max enables and shows the shared collection via card toggles
    shared_article = page.locator("article:not(.hidden)").filter(
        has=page.locator("[data-name='title']", has_text="Shared")
    )
    expect(shared_article).to_be_visible()
    shared_article.hover()
    enabled_btn = shared_article.locator('button[data-name="enabled"]')
    shown_btn = shared_article.locator('button[data-name="shown"]')
    enabled_btn.click(force=True)
    expect(shown_btn).not_to_be_disabled()
    shown_btn.click(force=True)
    expect(shown_btn).not_to_be_disabled()

    # 6. Verify "Edit" button and permissions badge is visible
    expect(shared_article.locator('[data-name="shared-by"]')).to_be_visible()
    expect(shared_article.locator('[data-name="shared-by-owner"]')).to_have_text(
        config.admin_username
    )
    expect(
        shared_article.locator('[data-name="permissions"] [data-name="ro"]')
    ).to_be_visible()
    expect(
        shared_article.locator('[data-name="permissions"] [data-name="rw"]')
    ).to_be_hidden()
    shared_article.hover()
    expect(shared_article.locator("a[data-name='edit']")).to_be_visible()

    # 7. Max edits the collection
    shared_article.locator("a[data-name='edit']").click()
    expect(page.locator("#editcollectionscene")).to_be_visible()
    page.fill('#editcollectionscene input[data-name="displayname"]', "Renamed by Max")
    page.click('#editcollectionscene button[data-name="submit"]')
    expect(page.locator("#editcollectionscene")).to_be_hidden()

    # 8. Verify the change
    expect(
        page.locator(
            "article:not(.hidden) [data-name='title']", has_text="Renamed by Max"
        )
    ).to_be_visible()
