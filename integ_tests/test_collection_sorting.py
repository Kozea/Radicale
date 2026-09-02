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
Test for checking if the collections are sorted correctly.
"""

import pathlib
import re
from typing import Any, Generator

import pytest
from playwright.sync_api import Page, expect

from integ_tests.common import SHARING_HTPASSWD, login, start_radicale_server


@pytest.fixture
def radicale_server(tmp_path: pathlib.Path) -> Generator[str, Any, None]:
    yield from start_radicale_server(tmp_path, SHARING_HTPASSWD)


def create_named_collection(page: Page, name: str) -> None:
    page.click('.fabcontainer a[data-name="new"]')
    page.fill('#createcollectionscene input[data-name="displayname"]', name)
    page.click('#createcollectionscene button[data-name="submit"]')
    expect(page.locator("#createcollectionscene")).to_be_hidden()


def test_collection_sorting(page: Page, radicale_server: str) -> None:
    config = SHARING_HTPASSWD

    # 1. Admin logs in and creates "Z" and "A"
    login(page, radicale_server, config)
    create_named_collection(page, "Z")
    create_named_collection(page, "A")

    # 2. Admin shares "M" to "max"
    create_named_collection(page, "M")
    article_m = page.locator("article:not(.hidden)").filter(
        has=page.locator("[data-name='title']", has_text="M")
    )
    article_m.hover()
    article_m.locator("a[data-name='share']").click(force=True)

    page.click('button[data-name="sharebymap"]')
    page.locator('input[data-name="shareuser"]').fill(config.user_username)
    page.locator('input[data-name="sharehref"]').fill("m-shared")
    page.click('#createeditsharescene button[data-name="submit"]')
    expect(
        page.locator("tr[data-name='sharemaprowtemplate']:not(.hidden)")
    ).to_have_count(1)
    page.click('#sharecollectionscene button[data-name="cancel"]')
    expect(page.locator("#sharecollectionscene")).to_be_hidden()

    # 3. Admin logs out
    page.click('a[data-name="logout"]')
    expect(page.locator("#loginscene")).to_be_visible()

    # 4. Max logs in
    page.fill('#loginscene input[data-name="user"]', config.user_username)
    page.fill('#loginscene input[data-name="password"]', "userpassword")
    page.click('button:has-text("Next")')
    expect(page.locator("#collectionsscene")).to_be_visible()
    expect(page.locator("#loadingscene")).to_be_hidden()

    # 5. Max creates his own "B" and "Y"
    create_named_collection(page, "Y")
    create_named_collection(page, "B")

    # 6. Max enables the shared collection "M"
    page.click('a[data-name="incomingshares"]')
    expect(page.locator("#incomingsharingscene")).to_be_visible()
    row = page.locator("tr[data-name='incomingsharerowtemplate']:not(.hidden)")
    expect(row).to_have_count(1)
    expect(row.locator("input[data-name='pathortoken']")).to_have_value(
        re.compile("m-shared")
    )
    page.check(
        "tr[data-name='incomingsharerowtemplate']:not(.hidden) input[data-name='enabled']"
    )
    expect(
        page.locator(
            "tr[data-name='incomingsharerowtemplate']:not(.hidden) input[data-name='shown']"
        )
    ).not_to_be_disabled()
    page.check(
        "tr[data-name='incomingsharerowtemplate']:not(.hidden) input[data-name='shown']"
    )
    expect(
        page.locator(
            "tr[data-name='incomingsharerowtemplate']:not(.hidden) input[data-name='shown']"
        )
    ).to_be_checked()
    expect(
        page.locator(
            "tr[data-name='incomingsharerowtemplate']:not(.hidden) input[data-name='shown']"
        )
    ).not_to_be_disabled()
    page.click('#incomingsharingscene button[data-name="close"]')
    expect(page.locator("#incomingsharingscene")).to_be_hidden()

    # 7. Verify the order
    # Expected: "B", "Y" (Owned), then "M" (Shared)
    # Wait for articles to be rendered
    expect(page.locator("article:not(.hidden) [data-name='title']")).to_have_count(3)

    titles = page.locator(
        "article:not(.hidden) [data-name='title']"
    ).all_text_contents()
    titles = [t.strip() for t in titles if t.strip()]

    assert titles == ["B", "Y", "M"], f"Expected order ['B', 'Y', 'M'], got {titles}"

    # 8. Max creates "A"
    create_named_collection(page, "A")

    # Wait for articles to be rendered (now 4)
    expect(page.locator("article:not(.hidden) [data-name='title']")).to_have_count(4)

    titles = page.locator(
        "article:not(.hidden) [data-name='title']"
    ).all_text_contents()
    titles = [t.strip() for t in titles if t.strip()]

    # Expected: "A", "B", "Y", then "M"
    assert titles == [
        "A",
        "B",
        "Y",
        "M",
    ], f"Expected order ['A', 'B', 'Y', 'M'], got {titles}"
