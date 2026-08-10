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
Integration tests for group and realm sharing support in the Web UI.
"""

import pathlib
import re
from typing import Any, Generator

import pytest
from playwright.sync_api import Page, expect

from integ_tests.common import (SHARING_HTGROUP,
                                SHARING_HTGROUP_USERSWITHDOMAIN, Config,
                                create_collection, login,
                                start_radicale_server)


@pytest.fixture
def radicale_server(
    tmp_path: pathlib.Path, radicale_server_config: Config
) -> Generator[str, Any, None]:
    yield from start_radicale_server(tmp_path, radicale_server_config)


@pytest.mark.parametrize(
    "radicale_server_config,share_user,share_href",
    [
        (SHARING_HTGROUP, ":group1", "shared_group"),
        (SHARING_HTGROUP_USERSWITHDOMAIN, "@domain.tld", "shared_realm"),
    ],
    ids=["group", "realm"],
)
def test_sharing_by_group_or_realm_in_ui(
    page: Page,
    radicale_server: str,
    radicale_server_config: Config,
    share_user: str,
    share_href: str,
) -> None:
    """Test sharing-by-group and sharing-by-realm in UI:
    User contains group reference ':group1' or realm '@domain.tld',
    and the backend creates the map share with PathOrToken prefix '/{user}/'.
    """
    # 1. Admin logs in and creates a collection
    login(page, radicale_server, radicale_server_config)
    create_collection(page, radicale_server)

    # 2. Admin opens share scene and creates share-by-group or share-by-realm
    page.hover("article:not(.hidden)")
    page.click('article:not(.hidden) a[data-name="share"]', force=True, strict=True)
    page.click('button[data-name="sharebymap"]')
    page.locator('input[data-name="shareuser"]').fill(share_user)
    page.locator('input[data-name="sharehref"]').fill(share_href)
    page.click('#createeditsharescene button[data-name="submit"]')

    # Verify share map row is displayed
    expect(
        page.locator("tr[data-name='sharemaprowtemplate']:not(.hidden)")
    ).to_have_count(1)
    page.click('#sharecollectionscene button[data-name="cancel"]')

    # 3. Admin logs out
    page.click('a[data-name="logout"]')

    # 4. Member user (max) logs in
    page.fill(
        '#loginscene input[data-name="user"]', radicale_server_config.user_username
    )
    page.fill('#loginscene input[data-name="password"]', "userpassword")
    page.click('button:has-text("Next")')

    # 5. User checks incoming shares scene
    page.click('a[data-name="incomingshares"]')
    expect(page.locator("#incomingsharingscene")).to_be_visible()
    row = page.locator("tr[data-name='incomingsharerowtemplate']:not(.hidden)")
    expect(row).to_have_count(1)

    expect(
        row.locator("input[data-name='pathortoken']")
    ).to_have_value(re.compile(rf".*{share_href}/"))

    # a) Check for the emoji and title in the share type column
    expected_emoji = "👥" if share_user.startswith(":") else "🌐"
    expected_title = "Group share" if share_user.startswith(":") else "Domain share"
    expect(row.locator("td[data-name='sharetype']")).to_have_text(expected_emoji)
    expect(row.locator("td[data-name='sharetype']")).to_have_attribute(
        "title", expected_title
    )
    expect(row.locator("td[data-name='owner']")).to_have_attribute(
        "title", radicale_server_config.admin_username
    )
    expect(row.locator("td[data-name='owner']")).to_contain_text(
        radicale_server_config.admin_username[:10]
    )

    # b) Check that the enabled and shown buttons (checkboxes) are disabled
    enabled_cb = row.locator("input[data-name='enabled']")
    shown_cb = row.locator("input[data-name='shown']")
    expect(enabled_cb).to_be_disabled()
    expect(shown_cb).to_be_disabled()
    expect(enabled_cb).to_have_attribute(
        "title", "Group and domain shares cannot be disabled"
    )
    expect(shown_cb).to_have_attribute(
        "title", "Group and domain shares cannot be hidden"
    )

    page.click('#incomingsharingscene button[data-name="close"]')
    expect(page.locator("#incomingsharingscene")).to_be_hidden()

    # 6. Verify shared collection is displayed on user's collections page
    article = page.locator("article:not(.hidden)").first
    expect(article.locator('[data-name="shared-by"]')).to_be_visible()
    expect(article.locator('[data-name="shared-by-owner"]')).to_have_text(
        radicale_server_config.admin_username
    )


@pytest.mark.parametrize(
    "radicale_server_config,share_user,share_href",
    [
        (SHARING_HTGROUP, ":group1", "shared_group_edit"),
        (SHARING_HTGROUP_USERSWITHDOMAIN, "@domain.tld", "shared_realm_edit"),
    ],
    ids=["group", "realm"],
)
def test_update_sharing_by_group_or_realm_in_ui(
    page: Page,
    radicale_server: str,
    radicale_server_config: Config,
    share_user: str,
    share_href: str,
) -> None:
    """Test updating an existing group or realm share in UI (changing RO to RW)."""
    # 1. Admin logs in and creates a collection
    login(page, radicale_server, radicale_server_config)
    create_collection(page, radicale_server)

    # 2. Admin creates a share-by-group or realm (initially readonly)
    page.hover("article:not(.hidden)")
    page.click('article:not(.hidden) a[data-name="share"]', force=True, strict=True)
    page.click('button[data-name="sharebymap"]')
    page.locator('input[data-name="shareuser"]').fill(share_user)
    page.locator('input[data-name="sharehref"]').fill(share_href)
    page.click('#createeditsharescene button[data-name="submit"]')

    # Verify initial share is readonly
    map_row = page.locator("tr[data-name='sharemaprowtemplate']:not(.hidden)")
    expect(map_row).to_have_count(1)
    expect(map_row.locator('[data-name="ro"]')).to_be_visible()
    expect(map_row.locator('[data-name="rw"]')).to_be_hidden()

    # 3. Admin edits the share and changes to Read/Write
    map_row.locator('button[data-name="edit"]').click()
    expect(page.locator("#createeditsharescene")).to_be_visible()
    expect(page.locator('input[data-name="shareuser"]')).to_be_disabled()
    expect(page.locator('input[data-name="shareuser"]')).to_have_value(share_user)
    expect(page.locator("#newshare_attr_permissions_ro")).to_be_checked()

    page.locator("label[for='newshare_attr_permissions_rw']").click()
    expect(page.locator("#newshare_attr_permissions_rw")).to_be_checked()
    page.click('#createeditsharescene button[data-name="submit"]')

    # Verify updated share now displays rw
    expect(map_row.locator('[data-name="rw"]')).to_be_visible()
    expect(map_row.locator('[data-name="ro"]')).to_be_hidden()
    page.click('#sharecollectionscene button[data-name="cancel"]')

    # 4. Admin logs out
    page.click('a[data-name="logout"]')

    # 5. Member user logs in
    page.fill(
        '#loginscene input[data-name="user"]', radicale_server_config.user_username
    )
    page.fill('#loginscene input[data-name="password"]', "userpassword")
    page.click('button:has-text("Next")')

    # 6. User verifies incoming share permissions
    page.click('a[data-name="incomingshares"]')
    expect(page.locator("#incomingsharingscene")).to_be_visible()
    incoming_row = page.locator(
        "tr[data-name='incomingsharerowtemplate']:not(.hidden)"
    )
    expect(incoming_row).to_have_count(1)
    expect(incoming_row.locator('[data-name="rw"]')).to_be_visible()
    expect(incoming_row.locator('[data-name="ro"]')).to_be_hidden()
    page.click('#incomingsharingscene button[data-name="close"]')

    # 7. Member user has write access on the collection (edit button visible)
    article = page.locator("article:not(.hidden)").first
    article.hover()
    expect(article.locator('a[data-name="edit"]')).to_be_visible()
    expect(article.locator('a[data-name="share"]')).to_be_hidden()
    expect(article.locator('a[data-name="delete"]')).to_be_hidden()
