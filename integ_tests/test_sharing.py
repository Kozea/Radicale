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
from playwright.sync_api import BrowserContext, Page, expect

from integ_tests.common import (SHARING_HTPASSWD, SHARING_XREMOTE, Config,
                                create_collection, login,
                                start_radicale_server)


@pytest.fixture(params=[SHARING_HTPASSWD, SHARING_XREMOTE], ids=lambda c: c.name)
def config(request: pytest.FixtureRequest) -> Config:
    return request.param


@pytest.fixture
def radicale_server(
    tmp_path: pathlib.Path, config: Config
) -> Generator[str, Any, None]:
    yield from start_radicale_server(tmp_path, config)


def test_create_and_delete_share_by_key(
    context: BrowserContext, page: Page, radicale_server: str, config: Config
) -> None:
    login(page, radicale_server, config, context=context)
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
        page.locator(
            "tr[data-name='sharetokenrowtemplate']:not(.hidden) span[data-name='ro']"
        )
    ).to_be_visible()
    page.click('tr:not(.hidden) button[data-name="delete"]', strict=True)
    page.click('#deleteconfirmationscene button[data-name="delete"]')
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
        page.locator(
            "tr[data-name='sharetokenrowtemplate']:not(.hidden) span[data-name='rw']"
        )
    ).to_be_visible()
    page.click('tr:not(.hidden) button[data-name="delete"]', strict=True)
    page.click('#deleteconfirmationscene button[data-name="delete"]')
    expect(
        page.locator("tr[data-name='sharetokenrowtemplate']:not(.hidden)")
    ).to_have_count(0)


def test_create_and_delete_share_by_map(
    context: BrowserContext, page: Page, radicale_server: str, config: Config
) -> None:
    login(page, radicale_server, config, context=context)
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
        page.locator(
            "tr[data-name='sharemaprowtemplate']:not(.hidden) span[data-name='ro']"
        )
    ).to_be_visible()
    page.click('tr:not(.hidden) button[data-name="delete"]', strict=True)
    page.click('#deleteconfirmationscene button[data-name="delete"]')
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
        page.locator(
            "tr[data-name='sharemaprowtemplate']:not(.hidden) span[data-name='rw']"
        )
    ).to_be_visible()
    page.click('tr:not(.hidden) button[data-name="delete"]', strict=True)
    page.click('#deleteconfirmationscene button[data-name="delete"]')
    expect(
        page.locator("tr[data-name='sharemaprowtemplate']:not(.hidden)")
    ).to_have_count(0)


def test_share_with_property_overrides(
    context: BrowserContext, page: Page, radicale_server: str, config: Config
) -> None:
    login(page, radicale_server, config, context=context)
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

    # Verify property override is closed by default
    expect(
        page.locator('input[data-name="displayname_override_enabled"]')
    ).not_to_be_visible()
    page.click('details[data-name="properties_override"] summary')

    # Verify defaults
    expect(page.locator('input[data-name="displayname_override"]')).to_have_value(
        "Test Collection"
    )
    expect(page.locator('input[data-name="description_override"]')).to_have_value(
        "Original Description"
    )
    expect(page.locator('input[data-name="color_override"]')).to_have_value("#ff0000")
    expect(page.locator('input[data-name="displayname_override"]')).to_be_disabled()
    expect(page.locator('input[data-name="description_override"]')).to_be_disabled()
    expect(page.locator('input[data-name="color_override"]')).to_be_disabled()

    # Set overrides
    page.click('label[for="newshare_attr_displayname_enabled"]')
    page.locator('input[data-name="displayname_override"]').fill(
        "Overridden Displayname"
    )
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


def test_share_journal_no_overrides(
    context: BrowserContext, page: Page, radicale_server: str, config: Config
) -> None:
    login(page, radicale_server, config, context=context)
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

    # Verify property override visibility
    expect(page.locator('details[data-name="properties_override"]')).to_be_visible()
    expect(
        page.locator('input[data-name="displayname_override_enabled"]')
    ).not_to_be_visible()
    page.click('details[data-name="properties_override"] summary')

    expect(
        page.locator('input[data-name="displayname_override_enabled"]')
    ).to_be_visible()
    expect(
        page.locator('input[data-name="description_override_enabled"]')
    ).to_be_hidden()
    expect(page.locator('input[data-name="color_override_enabled"]')).to_be_hidden()

    # Create the share
    page.click('#newshare button[data-name="submit"]')

    # Verify the share was created
    expect(
        page.locator("tr[data-name='sharetokenrowtemplate']:not(.hidden)")
    ).to_have_count(1)


def test_edit_share_by_token(
    context: BrowserContext, page: Page, radicale_server: str, config: Config
) -> None:
    login(page, radicale_server, config, context=context)
    create_collection(page, radicale_server)
    page.hover("article:not(.hidden)")
    page.click('article:not(.hidden) a[data-name="share"]', force=True, strict=True)

    # Create RO share
    page.click('button[data-name="sharebytoken"]')
    page.click('#newshare button[data-name="submit"]')
    expect(
        page.locator(
            "tr[data-name='sharetokenrowtemplate']:not(.hidden) span[data-name='ro']"
        )
    ).to_be_visible()

    # Edit to RW
    page.click('tr:not(.hidden) button[data-name="edit"]')
    expect(page.locator("#newshare h1")).to_have_text("Edit Share")
    page.click('label[for="newshare_attr_permissions_rw"]')
    page.click('#newshare button[data-name="submit"]')

    # Verify RW
    expect(
        page.locator(
            "tr[data-name='sharetokenrowtemplate']:not(.hidden) span[data-name='rw']"
        )
    ).to_be_visible()


def test_edit_share_by_map(
    context: BrowserContext, page: Page, radicale_server: str, config: Config
) -> None:
    login(page, radicale_server, config, context=context)
    create_collection(page, radicale_server)
    page.hover("article:not(.hidden)")
    page.click('article:not(.hidden) a[data-name="share"]', force=True, strict=True)

    # Create RO map share
    page.click('button[data-name="sharebymap"]')
    page.locator('input[data-name="shareuser"]').fill("max")
    page.locator('input[data-name="sharehref"]').fill("mapped")
    page.click('#newshare button[data-name="submit"]')
    expect(
        page.locator(
            "tr[data-name='sharemaprowtemplate']:not(.hidden) span[data-name='ro']"
        )
    ).to_be_visible()

    # Edit map share
    page.click('tr:not(.hidden) button[data-name="edit"]')
    expect(page.locator("#newshare h1")).to_have_text("Edit Share")
    expect(page.locator('input[data-name="shareuser"]')).to_be_disabled()
    expect(page.locator('input[data-name="sharehref"]')).to_be_disabled()

    # Change permissions and enabled status
    page.click('label[for="newshare_attr_permissions_rw"]')
    page.uncheck('#newshare input[data-name="enabled"]')
    page.click('#newshare button[data-name="submit"]')

    # Verify changes
    expect(
        page.locator(
            "tr[data-name='sharemaprowtemplate']:not(.hidden) span[data-name='rw']"
        )
    ).to_be_visible()
    # If disabled, it might not show up or show differently, but our current UI doesn't visually distinguish enabled/disabled in the list yet
    # Let's verify by re-opening edit scene
    page.click('tr:not(.hidden) button[data-name="edit"]')
    expect(page.locator('#newshare input[data-name="enabled"]')).not_to_be_checked()
    page.click('#newshare button[data-name="cancel"]')


def test_share_by_map_validation(
    context: BrowserContext, page: Page, radicale_server: str, config: Config
) -> None:
    login(page, radicale_server, config, context=context)
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


def test_create_and_delete_share_by_bday(
    context: BrowserContext, page: Page, radicale_server: str, config: Config
) -> None:
    login(page, radicale_server, config, context=context)
    # create collection of type ADDRESSBOOK for bday (bday only works with ADDRESSBOOK)
    page.click('a[data-name="new"]')
    page.locator('#createcollectionscene select[data-name="type"]').select_option(
        "ADDRESSBOOK"
    )
    page.locator('#createcollectionscene input[data-name="displayname"]').fill(
        "Addressbook For Bday"
    )
    page.click('#createcollectionscene button[data-name="submit"]')

    page.hover("article:not(.hidden)")
    page.click('article:not(.hidden) a[data-name="share"]', force=True, strict=True)

    expect(
        page.locator("tr[data-name='sharebdayrowtemplate']:not(.hidden)")
    ).to_have_count(0)

    page.click('button[data-name="sharebybday"]')

    # verify user is auto-filled with current user (admin)
    expect(page.locator('input[data-name="shareuser"]')).to_have_value("admin")
    page.locator('input[data-name="sharehref"]').fill("bdaymapped")

    # verify that the permissions section is hidden entirely
    expect(page.locator("input#newshare_attr_permissions_ro")).to_be_hidden()
    expect(page.locator("input#newshare_attr_permissions_rw")).to_be_hidden()

    page.click('#newshare button[data-name="submit"]')
    expect(
        page.locator("tr[data-name='sharebdayrowtemplate']:not(.hidden)")
    ).to_have_count(1)

    # verify no permissions pill in the bday row
    expect(
        page.locator(
            "tr[data-name='sharebdayrowtemplate']:not(.hidden) span[data-name='ro']"
        )
    ).to_have_count(0)

    # Close the share scene and verify the virtual bday calendar is now in the collections list
    page.click('#sharecollectionscene button[data-name="cancel"]')
    expect(page.locator("#sharecollectionscene")).to_be_hidden()

    # The virtual calendar (bdaymapped) should appear as its own article
    # after the cache was invalidated following the self-share
    expect(page.locator("article:not(.hidden)")).to_have_count(2)

    # Delete the bday share by re-opening the share scene
    page.hover("article:not(.hidden) >> nth=0")
    page.click('article:not(.hidden) >> nth=0 >> a[data-name="share"]', force=True)
    page.click(
        "tr[data-name='sharebdayrowtemplate']:not(.hidden) button[data-name='delete']",
        strict=True,
    )
    page.click('#deleteconfirmationscene button[data-name="delete"]')
    expect(
        page.locator("tr[data-name='sharebdayrowtemplate']:not(.hidden)")
    ).to_have_count(0)


def test_bday_section_hidden_for_calendar(
    context: BrowserContext, page: Page, radicale_server: str, config: Config
) -> None:
    """Verify the bday calendar section is hidden for CALENDAR collections."""
    login(page, radicale_server, config, context=context)

    page.click('a[data-name="new"]')
    page.locator('#createcollectionscene select[data-name="type"]').select_option(
        "CALENDAR"
    )
    page.locator('#createcollectionscene input[data-name="displayname"]').fill(
        "My Calendar"
    )
    page.click('#createcollectionscene button[data-name="submit"]')

    page.hover("article:not(.hidden)")
    page.click('article:not(.hidden) a[data-name="share"]', force=True, strict=True)

    expect(page.locator("#sharecollectionscene")).to_be_visible()
    expect(page.locator("div[data-name='sharebybday']")).to_be_hidden()
    page.click('#sharecollectionscene button[data-name="cancel"]')


def test_bday_section_visible_for_addressbook(
    context: BrowserContext, page: Page, radicale_server: str, config: Config
) -> None:
    """Verify the bday calendar section is visible for ADDRESSBOOK collections."""
    login(page, radicale_server, config, context=context)

    page.click('a[data-name="new"]')
    page.locator('#createcollectionscene select[data-name="type"]').select_option(
        "ADDRESSBOOK"
    )
    page.locator('#createcollectionscene input[data-name="displayname"]').fill(
        "My Addressbook"
    )
    page.click('#createcollectionscene button[data-name="submit"]')

    page.hover("article:not(.hidden)")
    page.click('article:not(.hidden) a[data-name="share"]', force=True, strict=True)

    expect(page.locator("#sharecollectionscene")).to_be_visible()
    expect(page.locator("div[data-name='sharebybday']")).to_be_visible()
    page.click('#sharecollectionscene button[data-name="cancel"]')
