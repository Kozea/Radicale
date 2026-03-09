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
Integration tests for sharing pages
"""

import pathlib
from typing import Any, Generator

import pytest
from playwright.sync_api import Page, expect

from integ_tests.common import create_collection, login, start_radicale_server


@pytest.fixture
def radicale_server(tmp_path: pathlib.Path) -> Generator[str, Any, None]:
    yield from start_radicale_server(tmp_path)


def test_create_and_delete_share_by_key(page: Page, radicale_server: str) -> None:
    login(page, radicale_server)
    create_collection(page, radicale_server)
    page.hover("article:not(.hidden)")
    page.click('article:not(.hidden) a[data-name="share"]', force=True, strict=True)

    expect(
        page.locator("tr[data-name='sharetokenrowtemplate']:not(.hidden)")
    ).to_have_count(0)

    page.click('button[data-name="sharebytoken"]')
    page.click('#newshare button[data-name="submit"]')
    expect(
        page.locator("tr[data-name='sharetokenrowtemplate']:not(.hidden)")
    ).to_have_count(1)
    expect(
        page.locator("tr[data-name='sharetokenrowtemplate']:not(.hidden) img[alt='RO']")
    ).to_be_visible()
    page.once("dialog", lambda dialog: dialog.accept())
    page.click('tr:not(.hidden) button[data-name="delete"]', strict=True)
    expect(
        page.locator("tr[data-name='sharetokenrowtemplate']:not(.hidden)")
    ).to_have_count(0)
    page.click('button[data-name="sharebytoken"]')
    page.click('label[for="newshare_attr_permissions_rw"]')
    page.click('#newshare button[data-name="submit"]')
    expect(
        page.locator("tr[data-name='sharetokenrowtemplate']:not(.hidden)")
    ).to_have_count(1)
    expect(
        page.locator("tr[data-name='sharetokenrowtemplate']:not(.hidden) img[alt='RW']")
    ).to_be_visible()
    page.once("dialog", lambda dialog: dialog.accept())
    page.click('tr:not(.hidden) button[data-name="delete"]', strict=True)
    expect(
        page.locator("tr[data-name='sharetokenrowtemplate']:not(.hidden)")
    ).to_have_count(0)


def test_create_and_delete_share_by_map(page: Page, radicale_server: str) -> None:
    login(page, radicale_server)
    create_collection(page, radicale_server)
    page.hover("article:not(.hidden)")
    page.click('article:not(.hidden) a[data-name="share"]', force=True, strict=True)

    expect(
        page.locator("tr[data-name='sharemaprowtemplate']:not(.hidden)")
    ).to_have_count(0)

    page.click('button[data-name="sharebymap"]')
    page.locator('input[data-name="shareuser"]').fill("max")
    page.locator('input[data-name="sharehref"]').fill("1234")
    page.click('#newshare button[data-name="submit"]')
    expect(
        page.locator("tr[data-name='sharemaprowtemplate']:not(.hidden)")
    ).to_have_count(1)
    expect(
        page.locator("tr[data-name='sharemaprowtemplate']:not(.hidden) img[alt='RO']")
    ).to_be_visible()
    page.once("dialog", lambda dialog: dialog.accept())
    page.click('tr:not(.hidden) button[data-name="delete"]', strict=True)
    expect(
        page.locator("tr[data-name='sharemaprowtemplate']:not(.hidden)")
    ).to_have_count(0)
    page.click('button[data-name="sharebymap"]')
    page.click('label[for="newshare_attr_permissions_rw"]')
    page.locator('input[data-name="shareuser"]').fill("max")
    page.locator('input[data-name="sharehref"]').fill("1234")
    page.click('#newshare button[data-name="submit"]')
    expect(
        page.locator("tr[data-name='sharemaprowtemplate']:not(.hidden)")
    ).to_have_count(1)
    expect(
        page.locator("tr[data-name='sharemaprowtemplate']:not(.hidden) img[alt='RW']")
    ).to_be_visible()
    page.once("dialog", lambda dialog: dialog.accept())
    page.click('tr:not(.hidden) button[data-name="delete"]', strict=True)
    expect(
        page.locator("tr[data-name='sharemaprowtemplate']:not(.hidden)")
    ).to_have_count(0)
