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
Integration tests for upload page
"""

import pathlib
import re
from typing import Any, Generator

import pytest
from playwright.sync_api import BrowserContext, Page, expect

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


def test_upload_zero_files(
    context: BrowserContext, page: Page, radicale_server: str, config: Config
) -> None:
    login(page, radicale_server, config, context=context)
    page.click('.fabcontainer a[data-name="upload"]')

    # Click upload without selecting files
    page.click('#uploadcollectionscene button[data-name="submit"]')

    # Check for error message at the bottom of the scene
    error_locator = page.locator('#uploadcollectionscene > span[data-name="error"]')
    expect(error_locator).to_be_visible()
    expect(error_locator).to_contain_text("Please select at least one file")


def test_upload_one_file_custom_href(
    context: BrowserContext,
    page: Page,
    radicale_server: str,
    config: Config,
    tmp_path: pathlib.Path,
) -> None:
    login(page, radicale_server, config, context=context)

    # Create a fake file to upload
    test_file = tmp_path / "test.ics"
    test_file.write_text("BEGIN:VCALENDAR\nVERSION:2.0\nEND:VCALENDAR")

    page.click('.fabcontainer a[data-name="upload"]')

    # Upload 1 file and set custom href
    page.set_input_files(
        '#uploadcollectionscene input[data-name="uploadfile"]', str(test_file)
    )
    page.fill('#uploadcollectionscene input[data-name="href"]', "testcollection")
    page.click('#uploadcollectionscene button[data-name="submit"]')

    # Wait for upload to complete in the list item
    expect(
        page.locator('#uploadcollectionscene li:not(.hidden) [data-name="success"]')
    ).to_be_visible()

    # Close scene
    page.click('#uploadcollectionscene button[data-name="close"]')

    # Verify 1 collection exists with "testcollection" in url
    expect(page.locator("article:not(.hidden)")).to_have_count(1)
    expect(page.locator('article:not(.hidden) input[data-name="url"]')).to_have_value(
        re.compile(r".*testcollection/.*")
    )


def test_upload_two_files(
    context: BrowserContext,
    page: Page,
    radicale_server: str,
    config: Config,
    tmp_path: pathlib.Path,
) -> None:
    login(page, radicale_server, config, context=context)

    # Create two fake files
    file1 = tmp_path / "test1.ics"
    file1.write_text("BEGIN:VCALENDAR\nVERSION:2.0\nEND:VCALENDAR")
    file2 = tmp_path / "test2.ics"
    file2.write_text("BEGIN:VCALENDAR\nVERSION:2.0\nEND:VCALENDAR")

    page.click('.fabcontainer a[data-name="upload"]')

    # Upload 2 files
    page.set_input_files(
        '#uploadcollectionscene input[data-name="uploadfile"]', [str(file1), str(file2)]
    )

    # HREF field should be hidden
    expect(
        page.locator('#uploadcollectionscene input[data-name="href"]')
    ).to_be_hidden()
    expect(
        page.locator('#uploadcollectionscene [data-name="hreflimitmsg"]')
    ).to_be_visible()

    page.click('#uploadcollectionscene button[data-name="submit"]')

    # Wait for uploads to complete
    # Wait until 2 entries in the upload list show success
    expect(
        page.locator('#uploadcollectionscene li:not(.hidden) [data-name="success"]')
    ).to_have_count(2)

    # Close scene
    page.click('#uploadcollectionscene button[data-name="close"]')
    # Verify 2 collections exist
    expect(page.locator("article:not(.hidden)")).to_have_count(2)
