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


def test_share_with_property_overrides(page: Page, radicale_server: str) -> None:
    login(page, radicale_server)
    # Create a collection with specific details
    page.click('a[data-name="new"]')
    page.locator('#createcollectionscene input[data-name="displayname"]').fill(
        "Test Collection"
    )
    page.locator('#createcollectionscene input[data-name="description"]').fill(
        "Original Description"
    )
    page.locator('#createcollectionscene input[data-name="color"]').fill("#ff0000")
    page.click('#createcollectionscene button[data-name="submit"]')

    page.hover("article:not(.hidden)")
    page.click('article:not(.hidden) a[data-name="share"]', force=True, strict=True)
    page.click('button[data-name="sharebytoken"]')

    # Verify defaults
    expect(page.locator('input[data-name="description_override"]')).to_have_value(
        "Original Description"
    )
    expect(page.locator('input[data-name="color_override"]')).to_have_value("#ff0000")
    expect(page.locator('input[data-name="description_override"]')).to_be_disabled()
    expect(page.locator('input[data-name="color_override"]')).to_be_disabled()

    # Set overrides
    page.click('label[for="newshare_attr_description_enabled"]')
    page.locator('input[data-name="description_override"]').fill(
        "Overridden Description"
    )
    page.click('label[for="newshare_attr_color_enabled"]')
    page.locator('input[data-name="color_override"]').fill("#00ff00")

    page.click('#newshare button[data-name="submit"]')

    # Verify the share was created
    expect(
        page.locator("tr[data-name='sharetokenrowtemplate']:not(.hidden)")
    ).to_have_count(1)


def test_share_journal_no_overrides(page: Page, radicale_server: str) -> None:
    login(page, radicale_server)
    # Create a collection of type JOURNAL
    page.click('a[data-name="new"]')
    page.locator('#createcollectionscene select[data-name="type"]').select_option(
        "JOURNAL"
    )
    page.locator('#createcollectionscene input[data-name="displayname"]').fill(
        "Test Journal"
    )
    page.locator('#createcollectionscene input[data-name="description"]').fill(
        "Journal Description"
    )
    page.click('#createcollectionscene button[data-name="submit"]')

    page.hover("article:not(.hidden)")
    page.click('article:not(.hidden) a[data-name="share"]', force=True, strict=True)
    page.click('button[data-name="sharebytoken"]')

    # Verify property override fieldset is hidden
    expect(page.locator('fieldset[data-name="properties_override"]')).to_be_hidden()

    # Create the share
    page.click('#newshare button[data-name="submit"]')

    # Verify the share was created
    expect(
        page.locator("tr[data-name='sharetokenrowtemplate']:not(.hidden)")
    ).to_have_count(1)


def test_edit_share_by_token(page: Page, radicale_server: str) -> None:
    login(page, radicale_server)
    create_collection(page, radicale_server)
    page.hover("article:not(.hidden)")
    page.click('article:not(.hidden) a[data-name="share"]', force=True, strict=True)

    # Create RO share
    page.click('button[data-name="sharebytoken"]')
    page.click('#newshare button[data-name="submit"]')
    expect(
        page.locator("tr[data-name='sharetokenrowtemplate']:not(.hidden) img[alt='RO']")
    ).to_be_visible()

    # Edit to RW
    page.click('tr:not(.hidden) button[data-name="edit"]')
    expect(page.locator("#newshare h1")).to_have_text("Edit Share")
    page.click('label[for="newshare_attr_permissions_rw"]')
    page.click('#newshare button[data-name="submit"]')

    # Verify RW
    expect(
        page.locator("tr[data-name='sharetokenrowtemplate']:not(.hidden) img[alt='RW']")
    ).to_be_visible()


def test_edit_share_by_map(page: Page, radicale_server: str) -> None:
    login(page, radicale_server)
    create_collection(page, radicale_server)
    page.hover("article:not(.hidden)")
    page.click('article:not(.hidden) a[data-name="share"]', force=True, strict=True)

    # Create RO map share
    page.click('button[data-name="sharebymap"]')
    page.locator('input[data-name="shareuser"]').fill("max")
    page.locator('input[data-name="sharehref"]').fill("mapped")
    page.click('#newshare button[data-name="submit"]')
    expect(
        page.locator("tr[data-name='sharemaprowtemplate']:not(.hidden) img[alt='RO']")
    ).to_be_visible()

    # Edit map share
    page.click('tr:not(.hidden) button[data-name="edit"]')
    expect(page.locator("#newshare h1")).to_have_text("Edit Share")
    expect(page.locator('input[data-name="shareuser"]')).to_be_disabled()
    expect(page.locator('input[data-name="sharehref"]')).to_be_disabled()

    # Change permissions and enabled status
    page.click('label[for="newshare_attr_permissions_rw"]')
    page.uncheck('input[data-name="enabled"]')
    page.click('#newshare button[data-name="submit"]')

    # Verify changes
    expect(
        page.locator("tr[data-name='sharemaprowtemplate']:not(.hidden) img[alt='RW']")
    ).to_be_visible()
    # If disabled, it might not show up or show differently, but our current UI doesn't visually distinguish enabled/disabled in the list yet
    # Let's verify by re-opening edit scene
    page.click('tr:not(.hidden) button[data-name="edit"]')
    expect(page.locator('input[data-name="enabled"]')).not_to_be_checked()
    page.click('#newshare button[data-name="cancel"]')


def test_share_by_map_validation(page: Page, radicale_server: str) -> None:
    login(page, radicale_server)
    create_collection(page, radicale_server)
    page.hover("article:not(.hidden)")
    page.click('article:not(.hidden) a[data-name="share"]', force=True, strict=True)

    page.click('button[data-name="sharebymap"]')

    # Try empty user
    page.locator('input[data-name="shareuser"]').fill("")
    page.locator('input[data-name="sharehref"]').fill("1234")
    page.click('#newshare button[data-name="submit"]')
    expect(page.locator('#newshare [data-name="error"]:not(.hidden)')).to_contain_text(
        "Share User is empty"
    )

    # Try logged in user
    page.locator('input[data-name="shareuser"]').fill("admin")
    page.click('#newshare button[data-name="submit"]')
    expect(page.locator('#newshare [data-name="error"]:not(.hidden)')).to_contain_text(
        "Share User cannot be admin"
    )

    # Valid user
    page.locator('input[data-name="shareuser"]').fill("max")
    page.click('#newshare button[data-name="submit"]')

    # Verify success
    expect(
        page.locator("tr[data-name='sharemaprowtemplate']:not(.hidden)")
    ).to_have_count(1)
