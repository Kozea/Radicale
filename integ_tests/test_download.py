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
Integration tests for download page
"""

import pathlib
from typing import Any, Generator

import pytest
from playwright.sync_api import BrowserContext, Page

from integ_tests.common import (NOSHARE_HTPASSWD, SHARING_HTPASSWD,
                                SHARING_XREMOTE, Config, login,
                                start_radicale_server)


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


def test_download_addressbook(
    context: BrowserContext, page: Page, radicale_server: str, config: Config
) -> None:
    login(page, radicale_server, config, context=context)
    page.click('.fabcontainer a[data-name="new"]')

    # an address book is created
    page.select_option('#createcollectionscene select[data-name="type"]', "ADDRESSBOOK")
    page.locator('#createcollectionscene input[data-name="displayname"]').fill("Abname")
    page.click('#createcollectionscene button[data-name="submit"]')

    # Start waiting for the download
    with page.expect_download() as download_info:
        # Perform the action that initiates download
        page.hover("article:not(.hidden)")
        page.click('article:not(.hidden) a[data-name="download"]')

    download = download_info.value
    assert download.suggested_filename == "Abname.vcf"


def test_download_calendar_uses_displayname_ics(
    context: BrowserContext, page: Page, radicale_server: str, config: Config
) -> None:
    login(page, radicale_server, config, context=context)
    page.click('.fabcontainer a[data-name="new"]')

    # a calendar is created
    page.select_option('#createcollectionscene select[data-name="type"]', "CALENDAR")
    page.locator('#createcollectionscene input[data-name="displayname"]').fill(
        "Calname"
    )
    page.click('#createcollectionscene button[data-name="submit"]')

    # Start waiting for the download
    with page.expect_download() as download_info:
        # Perform the action that initiates download
        page.hover("article:not(.hidden)")
        page.click('article:not(.hidden) a[data-name="download"]')

    download = download_info.value
    assert download.suggested_filename == "Calname.ics"
