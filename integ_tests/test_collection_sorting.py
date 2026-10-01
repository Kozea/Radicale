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

from integ_tests.common import (SHARING_HTPASSWD, create_named_collection,
                                login, share_collection_to_user,
                                start_radicale_server)


@pytest.fixture
def radicale_server(tmp_path: pathlib.Path) -> Generator[str, Any, None]:
    yield from start_radicale_server(tmp_path, SHARING_HTPASSWD)


def test_collection_sorting(page: Page, radicale_server: str) -> None:
    config = SHARING_HTPASSWD

    # 1. Admin logs in and creates "Z" and "A"
    login(page, radicale_server, config)
    create_named_collection(page, "Z")
    create_named_collection(page, "A")

    # 2. Admin shares "M" to "max"
    create_named_collection(page, "M")
    share_collection_to_user(page, "M", config.user_username, "M")

    # 3. Admin logs out
    page.click('a[data-name="logout"]')
    expect(page.locator("#loginscene")).to_be_visible()

    # 4. Max logs in
    page.fill('#loginscene input[data-name="user"]', config.user_username)
    page.fill('#loginscene input[data-name="password"]', "userpassword")
    page.click('button:has-text("Next")')
    expect(page.locator("#collectionsscene")).to_be_visible()
    expect(page.locator("#loadingscene")).to_be_hidden()

    # Verify incoming share card is immediately visible as disabled
    article_m_disabled = page.locator("article:not(.hidden)").filter(
        has=page.locator("[data-name='shared-by-owner']", has_text=config.admin_username)
    )
    expect(article_m_disabled).to_be_visible()
    expect(article_m_disabled).to_have_class(re.compile(r"\bshare-disabled\b"))
    expect(article_m_disabled).not_to_have_class(re.compile(r"\bshare-hidden\b"))
    expect(article_m_disabled.locator("a[data-name='download']")).to_be_hidden()
    expect(article_m_disabled.locator("a[data-name='edit']")).to_be_hidden()

    # 5. Max creates his own "B" and "Y"
    create_named_collection(page, "Y")
    create_named_collection(page, "B")

    # 6. Max enables and shows the shared collection "M" via card toggles
    article_m = page.locator("article:not(.hidden)").filter(
        has=page.locator("[data-name='shared-by-owner']", has_text=config.admin_username)
    )
    expect(article_m).to_be_visible()
    article_m.hover()
    en_btn = article_m.locator('button[data-name="enabled"]')
    sh_btn = article_m.locator('button[data-name="shown"]')
    en_btn.click(force=True)
    expect(sh_btn).not_to_be_disabled()
    sh_btn.click(force=True)
    expect(sh_btn).not_to_be_disabled()

    # Verify enabled/shown incoming card no longer has share-disabled or share-hidden
    expect(article_m).not_to_have_class(re.compile(r"\bshare-disabled\b"))
    expect(article_m).not_to_have_class(re.compile(r"\bshare-hidden\b"))

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


def test_incoming_share_disabled_and_hidden_css(page: Page, radicale_server: str) -> None:
    config = SHARING_HTPASSWD

    # 1. Admin creates collection "SharedItem" and shares to max
    login(page, radicale_server, config)
    create_named_collection(page, "SharedItem")
    share_collection_to_user(page, "SharedItem", config.user_username, "shared-item")

    # 2. Admin logs out
    page.click('a[data-name="logout"]')
    expect(page.locator("#loginscene")).to_be_visible()

    # 3. Max logs in
    page.fill('#loginscene input[data-name="user"]', config.user_username)
    page.fill('#loginscene input[data-name="password"]', "userpassword")
    page.click('button:has-text("Next")')
    expect(page.locator("#collectionsscene")).to_be_visible()
    expect(page.locator("#loadingscene")).to_be_hidden()

    # 4. Initially disabled: card visible with share-disabled
    shared_article = page.locator("article:not(.hidden)").filter(
        has=page.locator("[data-name='shared-by-owner']", has_text=config.admin_username)
    )
    expect(shared_article).to_be_visible()
    expect(shared_article).to_have_class(re.compile(r"\bshare-disabled\b"))
    expect(shared_article).not_to_have_class(re.compile(r"\bshare-hidden\b"))
    expect(shared_article.locator("a[data-name='download']")).to_be_hidden()
    expect(shared_article.locator("a[data-name='edit']")).to_be_hidden()

    # 5. Max enables share but leaves shown unchecked -> share-hidden
    shared_article.hover()
    en_btn = shared_article.locator('button[data-name="enabled"]')
    sh_btn = shared_article.locator('button[data-name="shown"]')
    en_btn.click(force=True)
    expect(en_btn).not_to_be_disabled()

    expect(shared_article).to_be_visible()
    expect(shared_article).to_have_class(re.compile(r"\bshare-hidden\b"))
    expect(shared_article).not_to_have_class(re.compile(r"\bshare-disabled\b"))

    # 6. Max enables shown -> normal card (neither share-disabled nor share-hidden)
    sh_btn.click(force=True)
    expect(sh_btn).not_to_be_disabled()

    expect(shared_article).to_be_visible()
    expect(shared_article).not_to_have_class(re.compile(r"\bshare-disabled\b"))
    expect(shared_article).not_to_have_class(re.compile(r"\bshare-hidden\b"))


def test_incoming_share_card_toggles(page: Page, radicale_server: str) -> None:
    config = SHARING_HTPASSWD

    # 1. Admin creates collection "SharedItem" and shares to max
    login(page, radicale_server, config)
    create_named_collection(page, "SharedItem")
    share_collection_to_user(page, "SharedItem", config.user_username, "shared-item")

    # 2. Admin logs out
    page.click('a[data-name="logout"]')
    expect(page.locator("#loginscene")).to_be_visible()

    # 3. Max logs in and creates his own collection
    page.fill('#loginscene input[data-name="user"]', config.user_username)
    page.fill('#loginscene input[data-name="password"]', "userpassword")
    page.click('button:has-text("Next")')
    expect(page.locator("#collectionsscene")).to_be_visible()
    expect(page.locator("#loadingscene")).to_be_hidden()

    create_named_collection(page, "OwnCollection")

    # 4. Check initial incoming share card state
    shared_article = page.locator("article:not(.hidden)").filter(
        has=page.locator("[data-name='shared-by-owner']", has_text=config.admin_username)
    )
    expect(shared_article).to_be_visible()
    expect(shared_article).to_have_class(re.compile(r"\bshare-disabled\b"))
    expect(shared_article).not_to_have_class(re.compile(r"\bshare-hidden\b"))

    enabled_btn = shared_article.locator('button[data-name="enabled"]')
    shown_btn = shared_article.locator('button[data-name="shown"]')
    expect(enabled_btn).to_have_attribute("title", "Disabled")
    expect(enabled_btn).to_have_class(re.compile(r"\binactive\b"))
    expect(enabled_btn.locator("img")).to_have_attribute("src", re.compile(r"minus-circle\.svg"))
    expect(shown_btn).to_be_disabled()
    expect(shown_btn).to_have_attribute("title", "Hidden")
    expect(shown_btn).to_have_class(re.compile(r"\binactive\b"))

    initial_titles = page.locator("article:not(.hidden) [data-name='title']").all_text_contents()
    initial_titles = [t.strip() for t in initial_titles if t.strip()]

    # 5. Click enabled button on the card -> should become enabled, but still hidden
    shared_article.hover()
    enabled_btn.click(force=True)
    expect(shared_article).not_to_have_class(re.compile(r"\bshare-disabled\b"))
    expect(shared_article).to_have_class(re.compile(r"\bshare-hidden\b"))
    expect(enabled_btn).to_have_attribute("title", "Enabled")
    expect(enabled_btn).to_have_class(re.compile(r"\bactive\b"))
    expect(enabled_btn).to_have_class(re.compile(r"\bgreen\b"))
    expect(enabled_btn.locator("img")).to_have_attribute("src", re.compile(r"check-circle\.svg"))
    expect(shown_btn).not_to_be_disabled()
    expect(shown_btn).to_have_attribute("title", "Hidden")
    expect(shown_btn).to_have_class(re.compile(r"\binactive\b"))

    # Order should NOT have changed
    titles_after_enable = page.locator("article:not(.hidden) [data-name='title']").all_text_contents()
    titles_after_enable = [t.strip() for t in titles_after_enable if t.strip()]
    assert titles_after_enable == initial_titles

    # 6. Click shown button on the card -> should become visible
    shared_article.hover()
    shown_btn.click(force=True)
    expect(shared_article).not_to_have_class(re.compile(r"\bshare-disabled\b"))
    expect(shared_article).not_to_have_class(re.compile(r"\bshare-hidden\b"))
    expect(shown_btn).to_have_attribute("title", "Shown")
    expect(shown_btn).to_have_class(re.compile(r"\bactive\b"))
    expect(shown_btn).to_have_class(re.compile(r"\bgreen\b"))
    expect(shared_article.locator("a[data-name='download']")).to_be_visible()

    # Order should NOT have changed
    titles_after_shown = page.locator("article:not(.hidden) [data-name='title']").all_text_contents()
    titles_after_shown = [t.strip() for t in titles_after_shown if t.strip()]
    assert titles_after_shown == initial_titles

    # Verify spacing between visible buttons is equal (8px gap)
    shared_article.hover()
    visible_shared_buttons = [
        btn for btn in shared_article.locator("ul li:not(.hidden) > *").all()
        if btn.is_visible()
    ]
    assert len(visible_shared_buttons) >= 3
    for i in range(len(visible_shared_buttons) - 1):
        box_cur = visible_shared_buttons[i].bounding_box()
        box_next = visible_shared_buttons[i + 1].bounding_box()
        assert box_cur is not None and box_next is not None
        gap = box_next["x"] - (box_cur["x"] + box_cur["width"])
        assert abs(gap - 8.0) <= 1.0, f"Expected gap ~8px, got {gap}"

    # 7. Test in dark mode
    page.emulate_media(color_scheme="dark")
    expect(enabled_btn).to_be_visible()
    expect(shown_btn).to_be_visible()
    expect(enabled_btn.locator("img")).to_have_attribute("src", re.compile(r"check-circle\.svg"))

    # 8. Click shown button again -> should become hidden again
    shared_article.hover()
    shown_btn.click(force=True)
    expect(shared_article).to_have_class(re.compile(r"\bshare-hidden\b"))
    expect(shown_btn).to_have_attribute("title", "Hidden")
    expect(shown_btn).to_have_class(re.compile(r"\binactive\b"))

    # Order should NOT have changed
    titles_after_hide = page.locator("article:not(.hidden) [data-name='title']").all_text_contents()
    titles_after_hide = [t.strip() for t in titles_after_hide if t.strip()]
    assert titles_after_hide == initial_titles

    # 9. Click enabled button again -> should become disabled again
    shared_article.hover()
    enabled_btn.click(force=True)
    expect(shared_article).to_have_class(re.compile(r"\bshare-disabled\b"))
    expect(shared_article).not_to_have_class(re.compile(r"\bshare-hidden\b"))
    expect(enabled_btn).to_have_attribute("title", "Disabled")
    expect(enabled_btn).to_have_class(re.compile(r"\binactive\b"))
    expect(enabled_btn.locator("img")).to_have_attribute("src", re.compile(r"minus-circle\.svg"))
    expect(shown_btn).to_be_disabled()

    # Order should NOT have changed
    titles_after_disable = page.locator("article:not(.hidden) [data-name='title']").all_text_contents()
    titles_after_disable = [t.strip() for t in titles_after_disable if t.strip()]
    assert titles_after_disable == initial_titles


def test_four_tier_collection_sorting_on_refresh(
    page: Page, radicale_server: str
) -> None:
    config = SHARING_HTPASSWD

    # 1. Admin creates 4 collections to be shared
    login(page, radicale_server, config)
    for title in ["Dis", "Hid", "VisB", "VisA"]:
        create_named_collection(page, title)
        share_collection_to_user(page, title, config.user_username, title)

    # 2. Admin logs out
    page.click('a[data-name="logout"]')
    expect(page.locator("#loginscene")).to_be_visible()

    # 3. Max logs in and creates 2 owned collections
    page.fill('#loginscene input[data-name="user"]', config.user_username)
    page.fill('#loginscene input[data-name="password"]', "userpassword")
    page.click('button:has-text("Next")')
    expect(page.locator("#collectionsscene")).to_be_visible()
    expect(page.locator("#loadingscene")).to_be_hidden()

    create_named_collection(page, "OwnB")
    create_named_collection(page, "OwnA")

    # 4. Max configures the shared collections via card toggles:
    # - VisA, VisB: enable and show (Tier 2)
    # - Hid: enable only (Tier 3)
    # - Dis: remain disabled (Tier 4)
    for title in ["VisA", "VisB"]:
        art = page.locator("article:not(.hidden)").filter(
            has=page.locator(
                "[data-name='title']",
                has_text=re.compile(f"^{re.escape(title)}$"),
            )
        )
        art.hover()
        en_btn = art.locator('button[data-name="enabled"]')
        en_btn.click(force=True)
        expect(en_btn).not_to_be_disabled()
        expect(en_btn).to_have_attribute("title", "Enabled")
        sh_btn = art.locator('button[data-name="shown"]')
        expect(sh_btn).not_to_be_disabled()
        sh_btn.click(force=True)
        expect(sh_btn).not_to_be_disabled()
        expect(sh_btn).to_have_attribute("title", "Shown")

    art_hid = page.locator("article:not(.hidden)").filter(
        has=page.locator(
            "[data-name='title']",
            has_text=re.compile(r"^Hid$"),
        )
    )
    art_hid.hover()
    en_btn_hid = art_hid.locator('button[data-name="enabled"]')
    en_btn_hid.click(force=True)
    expect(en_btn_hid).not_to_be_disabled()
    expect(en_btn_hid).to_have_attribute("title", "Enabled")
    sh_btn_hid = art_hid.locator('button[data-name="shown"]')
    expect(sh_btn_hid).not_to_be_disabled()
    expect(art_hid).to_have_class(re.compile(r"\bshare-hidden\b"))

    # 5. Refresh via nav button
    page.click('a[data-name="refresh"]')
    expect(page.locator("#collectionsscene")).to_be_visible()
    expect(page.locator("#loadingscene")).to_be_hidden()

    # 6. Verify initial 4-tier sort order
    # Tier 1: OwnA, OwnB
    # Tier 2: VisA, VisB
    # Tier 3: Hid
    # Tier 4: Dis
    expected_order_1 = ["OwnA", "OwnB", "VisA", "VisB", "Hid", "Dis"]
    expect(page.locator("article:not(.hidden) [data-name='title']")).to_have_count(6)
    titles_1 = [
        t.strip()
        for t in page.locator(
            "article:not(.hidden) [data-name='title']"
        ).all_text_contents()
        if t.strip()
    ]
    assert titles_1 == expected_order_1, f"Expected {expected_order_1}, got {titles_1}"

    # 7. Toggle on cards:
    # On VisA: toggle shown off (Tier 2 -> Tier 3)
    art_visa = page.locator("article:not(.hidden)").filter(
        has=page.locator(
            "[data-name='title']",
            has_text=re.compile(r"^VisA$"),
        )
    )
    art_visa.hover()
    sh_btn_visa = art_visa.locator('button[data-name="shown"]')
    sh_btn_visa.click(force=True)
    expect(sh_btn_visa).not_to_be_disabled()
    expect(sh_btn_visa).to_have_attribute("title", "Hidden")

    # On Dis: toggle enabled on (Tier 4 -> Tier 3)
    art_dis = page.locator("article:not(.hidden)").filter(
        has=page.locator(
            "[data-name='title']",
            has_text=re.compile(r"^Dis$"),
        )
    )
    art_dis.hover()
    en_btn_dis = art_dis.locator('button[data-name="enabled"]')
    en_btn_dis.click(force=True)
    expect(en_btn_dis).not_to_be_disabled()
    expect(en_btn_dis).to_have_attribute("title", "Enabled")
    sh_btn_dis = art_dis.locator('button[data-name="shown"]')
    expect(sh_btn_dis).not_to_be_disabled()

    # Assert DOM order has NOT changed before refresh
    titles_before_refresh = [
        t.strip()
        for t in page.locator(
            "article:not(.hidden) [data-name='title']"
        ).all_text_contents()
        if t.strip()
    ]
    assert titles_before_refresh == expected_order_1

    # 8. Refresh via nav button
    page.click('a[data-name="refresh"]')
    expect(page.locator("#collectionsscene")).to_be_visible()
    expect(page.locator("#loadingscene")).to_be_hidden()

    # 9. Verify updated 4-tier sort order:
    # Tier 1: OwnA, OwnB
    # Tier 2: VisB
    # Tier 3: Dis, Hid, VisA (alphabetical within Tier 3)
    # Tier 4: (none)
    expected_order_2 = ["OwnA", "OwnB", "VisB", "Dis", "Hid", "VisA"]
    titles_2 = [
        t.strip()
        for t in page.locator(
            "article:not(.hidden) [data-name='title']"
        ).all_text_contents()
        if t.strip()
    ]
    assert titles_2 == expected_order_2, f"Expected {expected_order_2}, got {titles_2}"

    # 10. Also verify full browser page reload preserves the order
    page.reload()
    page.fill('#loginscene input[data-name="user"]', config.user_username)
    page.fill('#loginscene input[data-name="password"]', "userpassword")
    page.click('button:has-text("Next")')
    expect(page.locator("#collectionsscene")).to_be_visible()
    expect(page.locator("#loadingscene")).to_be_hidden()

    titles_after_reload = [
        t.strip()
        for t in page.locator(
            "article:not(.hidden) [data-name='title']"
        ).all_text_contents()
        if t.strip()
    ]
    assert titles_after_reload == expected_order_2
