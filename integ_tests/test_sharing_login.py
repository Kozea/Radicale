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
from typing import Any, Generator

import pytest
from playwright.sync_api import Page, expect

from integ_tests.common import (SHARING_HTPASSWD, create_collection, login,
                                start_radicale_server)


@pytest.fixture
def radicale_server(tmp_path: pathlib.Path) -> Generator[str, Any, None]:
    yield from start_radicale_server(tmp_path, SHARING_HTPASSWD)


@pytest.mark.parametrize("permissions", ["ro", "rw"])
def test_incoming_shares(page: Page, radicale_server: str, permissions: str) -> None:
    # 1. Admin logs in and creates a map share for 'max'
    login(page, radicale_server, SHARING_HTPASSWD)
    create_collection(page, radicale_server)

    page.hover("article:not(.hidden)")
    page.click('article:not(.hidden) a[data-name="share"]', force=True, strict=True)
    page.click('button[data-name="sharebymap"]')
    page.locator('input[data-name="shareuser"]').fill("max")
    page.locator('input[data-name="sharehref"]').fill("mapped")
    if permissions == "rw":
        page.check("#newshare_attr_permissions_rw")
    page.click('#newshare button[data-name="submit"]')
    expect(
        page.locator("tr[data-name='sharemaprowtemplate']:not(.hidden)")
    ).to_have_count(1)
    page.click('#sharecollectionscene button[data-name="cancel"]')

    # 2. Admin logs out
    page.click('a[data-name="logout"]')

    # 3. Max logs in
    page.fill('#loginscene input[data-name="user"]', "max")
    page.fill('#loginscene input[data-name="password"]', "maxpassword")
    page.click('button:has-text("Next")')

    # 4. Max sees the incoming share
    page.click('a[data-name="incomingshares"]')
    expect(page.locator("#incomingsharingscene")).to_be_visible()
    expect(
        page.locator("tr[data-name='incomingsharerowtemplate']:not(.hidden)")
    ).to_have_count(1)

    expect(
        page.locator(
            "tr[data-name='incomingsharerowtemplate']:not(.hidden) input[data-name='pathortoken']"
        )
    ).to_have_value("mapped")

    # 5. Max enables and shows the share
    # Initially, it's disabled and not shown (security by default)
    expect(
        page.locator(
            "tr[data-name='incomingsharerowtemplate']:not(.hidden) input[data-name='enabled']"
        )
    ).not_to_be_checked()
    expect(
        page.locator(
            "tr[data-name='incomingsharerowtemplate']:not(.hidden) input[data-name='shown']"
        )
    ).not_to_be_checked()
    expect(
        page.locator(
            "tr[data-name='incomingsharerowtemplate']:not(.hidden) input[data-name='shown']"
        )
    ).to_be_disabled()

    # Enable it
    page.check(
        "tr[data-name='incomingsharerowtemplate']:not(.hidden) input[data-name='enabled']"
    )
    expect(
        page.locator(
            "tr[data-name='incomingsharerowtemplate']:not(.hidden) input[data-name='shown']"
        )
    ).not_to_be_disabled()

    # Show it
    page.check(
        "tr[data-name='incomingsharerowtemplate']:not(.hidden) input[data-name='shown']"
    )
    expect(
        page.locator(
            "tr[data-name='incomingsharerowtemplate']:not(.hidden) input[data-name='shown']"
        )
    ).to_be_checked()

    # 6. Verify "shared by admin" and button visibility in the collection article
    page.click('#incomingsharingscene button[data-name="cancel"]')
    expect(page.locator("#incomingsharingscene")).to_be_hidden()

    article = page.locator("article:not(.hidden)").first
    expect(article.locator('[data-name="shared-by"]')).to_be_visible()
    expect(article.locator('[data-name="shared-by-owner"]')).to_have_text("admin")

    # Action buttons are only visible on mouseover
    article.hover()

    # Share and delete buttons should be hidden for all incoming shares
    expect(article.locator('a[data-name="share"]')).to_be_hidden()
    expect(article.locator('[data-name="shareoption"]')).to_be_hidden()
    expect(article.locator('a[data-name="delete"]')).to_be_hidden()

    # Edit button depends on permissions
    if permissions == "rw":
        expect(article.locator('a[data-name="edit"]')).to_be_visible()
    else:
        expect(article.locator('a[data-name="edit"]')).to_be_hidden()

    # 7. Assert no error was shown
    expect(page.locator('#incomingsharingscene span[data-name="error"]')).to_be_hidden()


def test_no_incoming_shares_message(page: Page, radicale_server: str) -> None:
    # 1. Max logs in
    page.goto(radicale_server)
    page.fill('#loginscene input[data-name="user"]', "max")
    page.fill('#loginscene input[data-name="password"]', "maxpassword")
    page.click('button:has-text("Next")')

    # 2. Max goes to incoming shares scene
    page.click('a[data-name="incomingshares"]')
    expect(page.locator("#incomingsharingscene")).to_be_visible()

    # 3. Verify that the table is hidden and the message is visible
    expect(page.locator("#incomingsharingscene table")).to_be_hidden()
    expect(
        page.locator('#incomingsharingscene [data-name="nosharesmessage"]')
    ).to_be_visible()
    expect(
        page.locator('#incomingsharingscene [data-name="nosharesmessage"]')
    ).to_have_text("No incoming shares")

    page.click('#incomingsharingscene button[data-name="cancel"]')
    expect(page.locator("#incomingsharingscene")).to_be_hidden()
