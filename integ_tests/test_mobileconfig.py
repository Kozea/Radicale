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
Integration tests for mobileconfig download feature
"""

import pathlib
import plistlib
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


def test_mobileconfig_button_visible_and_downloads_file(
    context: BrowserContext, page: Page, radicale_server: str, config: Config
) -> None:
    login(page, radicale_server, config, context=context)
    expect(page.locator("#collectionsscene")).to_be_visible()

    mobileconfig_btn = page.locator('#collectionsscene a[data-name="mobileconfig"]')
    expect(mobileconfig_btn).to_be_visible()

    with page.expect_download() as download_info:
        mobileconfig_btn.click()

    expect(page.locator("#collectionsscene")).to_be_visible()
    expect(page.locator("#loginscene")).to_be_hidden()

    download = download_info.value
    assert download.suggested_filename.endswith(".mobileconfig")

    download_path = download.path()
    with open(download_path, "rb") as f:
        parsed = plistlib.load(f)

    assert parsed["PayloadType"] == "Configuration"
    assert parsed["PayloadVersion"] == 1
    assert parsed["PayloadDisplayName"] == "Radicale Calendar+Contacts"
    assert parsed["PayloadIdentifier"] == f"org.radicale.mobileconfig.{config.admin_username}"
    assert isinstance(parsed["PayloadContent"], list)
    assert len(parsed["PayloadContent"]) == 2

    caldav_payload = next(
        p for p in parsed["PayloadContent"] if p["PayloadType"] == "com.apple.caldav.account"
    )
    carddav_payload = next(
        p for p in parsed["PayloadContent"] if p["PayloadType"] == "com.apple.cardddav.account"
    )

    assert caldav_payload["CalDAVAccountDescription"] == "Radicale Calendar"
    assert caldav_payload["CalDAVUsername"] == config.admin_username
    assert carddav_payload["CalDAVAccountDescription"] == "Radicale Contacts"
    assert carddav_payload["CalDAVUsername"] == config.admin_username
