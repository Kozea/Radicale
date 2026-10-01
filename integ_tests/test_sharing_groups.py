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
from typing import Any, Generator
from urllib.parse import urlparse

import pytest
from playwright.sync_api import Page, expect

from integ_tests.common import (SHARING_HTGROUP,
                                SHARING_HTGROUP_USERSWITHDOMAIN, Config,
                                create_collection, login,
                                share_collection_to_user,
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
    share_collection_to_user(page, recipient=share_user, share_href=share_href)

    # 3. Admin logs out
    page.click('a[data-name="logout"]')

    # 4. Member user (max) logs in
    page.fill(
        '#loginscene input[data-name="user"]', radicale_server_config.user_username
    )
    page.fill('#loginscene input[data-name="password"]', "userpassword")
    page.click('button:has-text("Next")')

    # 5. Verify shared collection is displayed on user's collections page
    article = page.locator("article:not(.hidden)").first
    expect(article.locator('[data-name="shared-by"]')).to_be_visible()
    expect(article.locator('[data-name="shared-by-owner"]')).to_have_text(
        radicale_server_config.admin_username
    )
    enabled_btn = article.locator('button[data-name="enabled"]')
    shown_btn = article.locator('button[data-name="shown"]')
    expect(enabled_btn).to_be_disabled()
    expect(shown_btn).to_be_disabled()
    expect(enabled_btn).to_have_attribute(
        "title", "Group and domain shares cannot be disabled"
    )
    expect(shown_btn).to_have_attribute(
        "title", "Group and domain shares cannot be hidden"
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

    # 6. Member user verifies permissions badge and has write access on the collection (edit button visible)
    article = page.locator("article:not(.hidden)").first
    expect(article.locator('[data-name="permissions"] [data-name="rw"]')).to_be_visible()
    expect(article.locator('[data-name="permissions"] [data-name="ro"]')).to_be_hidden()
    article.hover()
    expect(article.locator('a[data-name="edit"]')).to_be_visible()
    expect(article.locator('a[data-name="share"]')).to_be_hidden()
    expect(article.locator('a[data-name="delete"]')).to_be_hidden()


@pytest.mark.parametrize(
    "radicale_server_config,share_user,share_href",
    [
        (SHARING_HTGROUP, ":editors", "shared_editors_group"),
        (SHARING_HTGROUP_USERSWITHDOMAIN, "@domain.tld", "shared_domain_realm"),
    ],
    ids=["group_with_owner", "realm_with_owner"],
)
def test_sharing_by_group_including_owner_does_not_duplicate_in_ui(
    page: Page,
    radicale_server: str,
    radicale_server_config: Config,
    share_user: str,
    share_href: str,
) -> None:
    """Test that sharing to a group/realm that includes the owner:
    1. Does not show the collection twice in the owner's main collections list.
    2. Displays correctly for other group members without duplication.
    """
    # 1. Admin logs in and creates a collection
    login(page, radicale_server, radicale_server_config)
    create_collection(page, radicale_server)

    # Verify admin has 1 collection
    expect(page.locator("article:not(.hidden)")).to_have_count(1)

    # 2. Admin creates a share for group/realm which includes admin
    share_collection_to_user(page, recipient=share_user, share_href=share_href)

    # 3. Verify admin still sees only 1 collection (not duplicated)
    expect(page.locator("article:not(.hidden)")).to_have_count(1)
    article = page.locator("article:not(.hidden)").first
    expect(article.locator('[data-name="shared-by"]')).to_be_hidden()

    # 4. Admin logs out
    page.click('a[data-name="logout"]')

    # 5. Member user logs in
    page.fill(
        '#loginscene input[data-name="user"]', radicale_server_config.user_username
    )
    page.fill('#loginscene input[data-name="password"]', "userpassword")
    page.click('button:has-text("Next")')

    # 6. Member user sees 1 collection (the shared one)
    expect(page.locator("article:not(.hidden)")).to_have_count(1)
    user_article = page.locator("article:not(.hidden)").first
    expect(user_article.locator('[data-name="shared-by"]')).to_be_visible()
    expect(user_article.locator('[data-name="shared-by-owner"]')).to_have_text(
        radicale_server_config.admin_username
    )


@pytest.mark.parametrize(
    "radicale_server_config,share_user",
    [
        (SHARING_HTGROUP, ":editors"),
        (SHARING_HTGROUP_USERSWITHDOMAIN, "@domain.tld"),
    ],
    ids=["group_with_owner_same_href", "realm_with_owner_same_href"],
)
def test_sharing_by_group_including_owner_same_href_shown_in_ui(
    page: Page,
    radicale_server: str,
    radicale_server_config: Config,
    share_user: str,
) -> None:
    """Test for issue #2250:
    When a collection is shared with a group/realm including the owner,
    and Share Href is the same as the collection's Href:
    1. The collection remains visible in the owner's web UI.
    2. Owner has full edit/share/delete options and no 'shared-by' or 'transformed-from' badges.
    3. Group members see the shared collection without duplication.
    """
    # 1. Admin logs in and creates a collection
    login(page, radicale_server, radicale_server_config)
    create_collection(page, radicale_server)

    # Extract the collection's name/href
    expect(page.locator("article:not(.hidden)")).to_have_count(1)
    collection_url = page.locator(
        "article:not(.hidden) input[data-name='url']"
    ).input_value()
    coll_name = urlparse(collection_url).path.strip("/").split("/")[-1]

    # 2. Admin creates a share with share_href equal to coll_name
    share_collection_to_user(page, recipient=share_user, share_href=coll_name)

    # 3. Verify admin STILL sees 1 collection (does not disappear!)
    expect(page.locator("article:not(.hidden)")).to_have_count(1)
    article = page.locator("article:not(.hidden)").first
    expect(article.locator('[data-name="shared-by"]')).to_be_hidden()
    expect(article.locator('[data-name="transformed-from"]')).to_be_hidden()
    article.hover()
    expect(article.locator('a[data-name="share"]')).to_be_visible()
    expect(article.locator('a[data-name="delete"]')).to_be_visible()

    # 4. Admin logs out
    page.click('a[data-name="logout"]')

    # 5. Member user logs in
    page.fill(
        '#loginscene input[data-name="user"]', radicale_server_config.user_username
    )
    page.fill('#loginscene input[data-name="password"]', "userpassword")
    page.click('button:has-text("Next")')

    # 6. Member user sees 1 collection (the shared one)
    expect(page.locator("article:not(.hidden)")).to_have_count(1)
    user_article = page.locator("article:not(.hidden)").first
    expect(user_article.locator('[data-name="shared-by"]')).to_be_visible()
    expect(user_article.locator('[data-name="shared-by-owner"]')).to_have_text(
        radicale_server_config.admin_username
    )
