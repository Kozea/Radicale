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
Integration tests for sharing (login/logout specific)
"""

import pathlib
import re
from typing import Any, Generator

import pytest
from playwright.sync_api import Page, expect

from integ_tests.common import (SHARING_HTPASSWD,
                                SHARING_HTPASSWD_USERSWITHDOMAIN, Config,
                                create_collection, login,
                                share_collection_to_user,
                                start_radicale_server)


@pytest.fixture(params=[SHARING_HTPASSWD, SHARING_HTPASSWD_USERSWITHDOMAIN])
def radicale_server_config(request: pytest.FixtureRequest) -> Config:
    return request.param


@pytest.fixture
def radicale_server(
    tmp_path: pathlib.Path, radicale_server_config: Config
) -> Generator[str, Any, None]:
    yield from start_radicale_server(tmp_path, radicale_server_config)


@pytest.mark.parametrize("permissions", ["ro", "rw"])
def test_incoming_shares(
    page: Page, radicale_server: str, radicale_server_config: Config, permissions: str
) -> None:
    # 1. Admin logs in and creates a map share for 'max'
    login(page, radicale_server, radicale_server_config)
    create_collection(page, radicale_server)

    share_collection_to_user(
        page,
        recipient=radicale_server_config.user_username,
        share_href="mapped",
        permissions=permissions,
    )

    # 2. Admin logs out
    page.click('a[data-name="logout"]')

    # 3. Max logs in
    page.fill(
        '#loginscene input[data-name="user"]', radicale_server_config.user_username
    )
    page.fill('#loginscene input[data-name="password"]', "userpassword")
    page.click('button:has-text("Next")')
    expect(page.locator("#collectionsscene")).to_be_visible()
    expect(page.locator("#loadingscene")).to_be_hidden()

    # 4. Max sees the incoming share card (initially disabled, not shown)
    article = page.locator("article:not(.hidden)").first
    expect(article).to_be_visible()
    expect(article).to_have_class(re.compile(r"\bshare-disabled\b"))
    expect(article).not_to_have_class(re.compile(r"\bshare-hidden\b"))

    article.hover()
    enabled_btn = article.locator('button[data-name="enabled"]')
    shown_btn = article.locator('button[data-name="shown"]')
    expect(enabled_btn).to_have_attribute("title", "Disabled")
    expect(enabled_btn).to_have_class(re.compile(r"\binactive\b"))
    expect(shown_btn).to_be_disabled()
    expect(shown_btn).to_have_attribute("title", "Hidden")
    expect(shown_btn).to_have_class(re.compile(r"\binactive\b"))

    # 5. Max enables the share -> becomes share-hidden
    enabled_btn.click(force=True)
    expect(enabled_btn).not_to_be_disabled()
    expect(article).not_to_have_class(re.compile(r"\bshare-disabled\b"))
    expect(article).to_have_class(re.compile(r"\bshare-hidden\b"))
    expect(enabled_btn).to_have_attribute("title", "Enabled")
    expect(shown_btn).not_to_be_disabled()

    # Max shows the share -> active card
    shown_btn.click(force=True)
    expect(shown_btn).not_to_be_disabled()
    expect(article).not_to_have_class(re.compile(r"\bshare-disabled\b"))
    expect(article).not_to_have_class(re.compile(r"\bshare-hidden\b"))
    expect(shown_btn).to_have_attribute("title", "Shown")

    # 6. Verify "shared by admin" and button visibility in the collection article
    expect(article.locator('[data-name="shared-by"]')).to_be_visible()
    expect(article.locator('[data-name="shared-by-owner"]')).to_have_text(
        radicale_server_config.admin_username
    )

    # Action buttons are only visible on mouseover
    article.hover()

    # Share and delete buttons should be hidden for all incoming shares
    expect(article.locator('a[data-name="share"]')).to_be_hidden()
    expect(article.locator('[data-name="shareoption"]')).to_be_hidden()
    expect(article.locator('a[data-name="delete"]')).to_be_hidden()

    # Edit button is visible if either data write or property write is allowed.
    expect(article.locator('a[data-name="edit"]')).to_be_visible()
