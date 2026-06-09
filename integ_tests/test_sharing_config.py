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
Integration tests for sharing actions configurations
"""

import pathlib
from typing import Any, Generator

import pytest
from playwright.sync_api import BrowserContext, Page, expect

from integ_tests.common import (SHARING_HTPASSWD, SHARING_XREMOTE, Config,
                                login, start_radicale_server)


@pytest.fixture(params=[SHARING_HTPASSWD, SHARING_XREMOTE])
def config(request: pytest.FixtureRequest) -> Config:
    return request.param


@pytest.fixture
def radicale_server(
    tmp_path: pathlib.Path, config: Config
) -> Generator[str, Any, None]:
    yield from start_radicale_server(tmp_path, config)


def _create_addressbook_and_open_share(
    context: BrowserContext, page: Page, radicale_server: str, config: Config, name: str
) -> None:
    login(page, radicale_server, config, context=context)

    # create collection of type ADDRESSBOOK for bday (bday only works with ADDRESSBOOK)
    page.click('a[data-name="new"]')
    page.locator('#createcollectionscene select[data-name="type"]').select_option(
        "ADDRESSBOOK"
    )
    page.locator('#createcollectionscene input[data-name="displayname"]').fill(name)
    page.click('#createcollectionscene button[data-name="submit"]')

    # Open share scene
    page.hover("article:not(.hidden)")
    page.click('article:not(.hidden) a[data-name="share"]', force=True, strict=True)

    # Click Share by Map
    page.click('button[data-name="sharebymap"]')


def test_sharing_config_save_and_reload(
    context: BrowserContext, page: Page, radicale_server: str, config: Config
) -> None:
    _create_addressbook_and_open_share(
        context, page, radicale_server, config, "Addressbook for Save and Reload"
    )

    # Config details should be hidden initially
    expect(page.locator("details[data-name='config']")).to_be_hidden()

    # Select Birthday conversion
    page.click('label[for="newshare_conv_bday"]')

    # Config details should now be visible and open
    expect(page.locator("details[data-name='config']")).to_be_visible()
    expect(page.locator("details[data-name='config']")).to_have_attribute("open", "")

    # Fill share map fields (user and href)
    page.locator('input[data-name="shareuser"]').fill("max")
    page.locator('input[data-name="sharehref"]').fill("mapped-bday-reload")

    # Verify all 5 config properties are present
    expect(
        page.locator("#newshare_config_conversion_bday_summary_template")
    ).to_be_visible()
    expect(
        page.locator("#newshare_config_conversion_bday_description_template")
    ).to_be_visible()
    expect(
        page.locator("#newshare_config_conversion_bday_alarm_trigger_template")
    ).to_be_visible()
    expect(page.locator("#newshare_config_conversion_bday_categories")).to_be_visible()
    expect(page.locator("#newshare_config_conversion_bday_age_max")).to_be_visible()

    # Set some config values
    page.locator("#newshare_config_conversion_bday_summary_template").fill(
        "{fn} Birthday"
    )
    page.locator("#newshare_config_conversion_bday_age_max").fill("120")

    # Save
    page.click('#createeditsharescene button[data-name="submit"]')

    # Verify share created
    expect(
        page.locator("tr[data-name='sharemaprowtemplate']:not(.hidden)")
    ).to_have_count(1)

    # Re-open share in edit mode
    page.click(
        "tr[data-name='sharemaprowtemplate']:not(.hidden) button[data-name='edit']",
        strict=True,
    )

    # Verify values are populated correctly in the inputs
    expect(
        page.locator("#newshare_config_conversion_bday_summary_template")
    ).to_have_value("{fn} Birthday")
    expect(page.locator("#newshare_config_conversion_bday_age_max")).to_have_value(
        "120"
    )

    page.click('#createeditsharescene button[data-name="cancel"]')


def test_sharing_config_delete_checkbox(
    context: BrowserContext, page: Page, radicale_server: str, config: Config
) -> None:
    _create_addressbook_and_open_share(
        context, page, radicale_server, config, "Addressbook for Delete Checkbox"
    )

    # Select Birthday conversion
    page.click('label[for="newshare_conv_bday"]')

    # Fill share map fields (user and href)
    page.locator('input[data-name="shareuser"]').fill("max")
    page.locator('input[data-name="sharehref"]').fill("mapped-bday-delete")

    # Set config values
    page.locator("#newshare_config_conversion_bday_summary_template").fill(
        "{fn} Birthday"
    )
    page.locator("#newshare_config_conversion_bday_age_max").fill("120")

    # Check delete checkbox for summary template
    page.click(
        "label[for='newshare_config_del_conversion_bday_summary_template']", strict=True
    )
    expect(
        page.locator("#newshare_config_conversion_bday_summary_template")
    ).to_be_disabled()

    # Uncheck delete checkbox for summary template
    page.click(
        "label[for='newshare_config_del_conversion_bday_summary_template']", strict=True
    )
    expect(
        page.locator("#newshare_config_conversion_bday_summary_template")
    ).to_be_enabled()

    # Check it again to save deletion
    page.click(
        "label[for='newshare_config_del_conversion_bday_summary_template']", strict=True
    )

    # Save
    page.click('#createeditsharescene button[data-name="submit"]')

    # Verify share created
    expect(
        page.locator("tr[data-name='sharemaprowtemplate']:not(.hidden)")
    ).to_have_count(1)

    # Re-open share in edit mode
    page.click(
        "tr[data-name='sharemaprowtemplate']:not(.hidden) button[data-name='edit']",
        strict=True,
    )

    # Verify that the summary template checkbox is checked, input is disabled and empty (since it was deleted)
    expect(
        page.locator("#newshare_config_del_conversion_bday_summary_template")
    ).to_be_checked()
    expect(
        page.locator("#newshare_config_conversion_bday_summary_template")
    ).to_be_disabled()
    expect(
        page.locator("#newshare_config_conversion_bday_summary_template")
    ).to_have_value("")
    expect(page.locator("#newshare_config_conversion_bday_age_max")).to_have_value(
        "120"
    )

    page.click('#createeditsharescene button[data-name="cancel"]')


def test_sharing_config_conversion_none(
    context: BrowserContext, page: Page, radicale_server: str, config: Config
) -> None:
    _create_addressbook_and_open_share(
        context, page, radicale_server, config, "Addressbook for Conversion None"
    )

    # Select Birthday conversion
    page.click('label[for="newshare_conv_bday"]')

    # Fill share map fields (user and href)
    page.locator('input[data-name="shareuser"]').fill("max")
    page.locator('input[data-name="sharehref"]').fill("mapped-bday-none")

    # Set some config values
    page.locator("#newshare_config_conversion_bday_summary_template").fill(
        "{fn} Birthday"
    )
    page.locator("#newshare_config_conversion_bday_age_max").fill("120")

    # Save
    page.click('#createeditsharescene button[data-name="submit"]')

    # Verify share created
    expect(
        page.locator("tr[data-name='sharemaprowtemplate']:not(.hidden)")
    ).to_have_count(1)

    # Re-open share in edit mode
    page.click(
        "tr[data-name='sharemaprowtemplate']:not(.hidden) button[data-name='edit']",
        strict=True,
    )

    # Change conversion back to None
    page.click('label[for="newshare_conv_none"]')
    expect(page.locator("details[data-name='config']")).to_be_hidden()

    # Save
    page.click('#createeditsharescene button[data-name="submit"]')

    # Re-open share in edit mode once more
    page.click(
        "tr[data-name='sharemaprowtemplate']:not(.hidden) button[data-name='edit']",
        strict=True,
    )

    # Change conversion back to Birthday
    page.click('label[for="newshare_conv_bday"]')

    # Config fields should be empty and enabled, delete checkboxes unchecked
    expect(
        page.locator("#newshare_config_conversion_bday_summary_template")
    ).to_have_value("")
    expect(
        page.locator("#newshare_config_conversion_bday_summary_template")
    ).to_be_enabled()
    expect(
        page.locator("#newshare_config_del_conversion_bday_summary_template")
    ).not_to_be_checked()

    expect(page.locator("#newshare_config_conversion_bday_age_max")).to_have_value("")
    expect(page.locator("#newshare_config_conversion_bday_age_max")).to_be_enabled()
    expect(
        page.locator("#newshare_config_del_conversion_bday_age_max")
    ).not_to_be_checked()

    page.click('#createeditsharescene button[data-name="cancel"]')


def test_sharing_config_invalid_integer(
    context: BrowserContext, page: Page, radicale_server: str, config: Config
) -> None:
    _create_addressbook_and_open_share(
        context, page, radicale_server, config, "Addressbook for Invalid Int"
    )

    # Select Birthday conversion
    page.click('label[for="newshare_conv_bday"]')

    # Fill share map fields (user and href)
    page.locator('input[data-name="shareuser"]').fill("max")
    page.locator('input[data-name="sharehref"]').fill("mapped-bday-invalid")

    # Set summary template (valid)
    page.locator("#newshare_config_conversion_bday_summary_template").fill(
        "{fn} Birthday"
    )

    # Set invalid integer for age_max (which has type 'int')
    page.locator("#newshare_config_conversion_bday_age_max").fill("foo")

    # Verify that there is some error message shown
    expect(page.locator("#createeditsharescene [data-name='error']")).not_to_be_empty()
    expect(page.locator("#createeditsharescene [data-name='error']")).to_contain_text(
        "Max age must be an integer"
    )

    # Click submit button
    page.click('#createeditsharescene button[data-name="submit"]')

    # Verify we are still on the edit share scene (submit is blocked)
    expect(page.locator("#createeditsharescene")).to_be_visible()
    expect(page.locator("#createeditsharescene [data-name='error']")).to_contain_text(
        "Max age must be an integer"
    )

    # Fill valid integer now
    page.locator("#newshare_config_conversion_bday_age_max").fill("120")

    # Verify error is cleared
    expect(page.locator("#createeditsharescene [data-name='error']")).to_be_empty()

    # Save
    page.click('#createeditsharescene button[data-name="submit"]')

    # Verify share created successfully
    expect(
        page.locator("tr[data-name='sharemaprowtemplate']:not(.hidden)")
    ).to_have_count(1)

    # Cancel/Close share collection scene
    page.click('#sharecollectionscene button[data-name="cancel"]')
