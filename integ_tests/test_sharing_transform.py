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
Integration tests for transform shares (issue #2234):
1. Delete transform share directly from incoming collection card.
2. Edit transform share configuration (summary template, max age) via Web UI.
"""

import pathlib
import re
from typing import Any, Generator
from urllib.parse import urlparse

import pytest
import requests
from playwright.sync_api import BrowserContext, Page, expect

from integ_tests.common import (SHARING_HTPASSWD, Config, login,
                                start_radicale_server)


@pytest.fixture
def radicale_server(tmp_path: pathlib.Path) -> Generator[str, Any, None]:
    yield from start_radicale_server(tmp_path, SHARING_HTPASSWD)


def _setup_addressbook_with_contact(
    page: Page, radicale_server: str, config: Config
) -> str:
    """Creates an Addressbook collection with a contact and returns its path."""
    login(page, radicale_server, config)

    # 1. Create Addressbook
    page.click('a[data-name="new"]')
    page.locator('#createcollectionscene select[data-name="type"]').select_option(
        "ADDRESSBOOK"
    )
    page.locator('#createcollectionscene input[data-name="displayname"]').fill(
        "Contacts"
    )
    page.click('#createcollectionscene button[data-name="submit"]')
    expect(page.locator("#createcollectionscene")).to_be_hidden()

    # Get addressbook href
    url_input = page.locator("article:not(.hidden) input[data-name='url']").first
    ab_path = urlparse(url_input.input_value()).path

    # Upload a contact with birthday
    vcf = """BEGIN:VCARD
VERSION:3.0
UID:contact-alice-123
FN:Alice Wonderland
BDAY:1990-05-15
END:VCARD
"""
    req = requests.Session()
    req.trust_env = False
    put_resp = req.put(
        f"{radicale_server}{ab_path}alice.vcf",
        auth=(config.admin_username, "admi$pass#word"),
        data=vcf,
        headers={"Content-Type": "text/vcard"},
    )
    assert put_resp.status_code in (201, 204), f"PUT contact failed: {put_resp.status_code}"

    return ab_path


def test_transform_share_delete_from_card(
    context: BrowserContext, page: Page, radicale_server: str
) -> None:
    """
    The delete button is visible on incoming/virtual bday share cards,
    and clicking it deletes the transform share.
    """
    config = SHARING_HTPASSWD
    _setup_addressbook_with_contact(page, radicale_server, config)

    # Create bday share via Share scene on Contacts
    page.hover("article:not(.hidden)")
    page.click('article:not(.hidden) a[data-name="share"]', force=True)
    expect(page.locator("#sharecollectionscene")).to_be_visible()

    page.click('button[data-name="sharebymap"]')
    page.click('label[for="newshare_conv_bday"]')
    page.locator('input[data-name="shareuser"]').fill(config.admin_username)
    page.locator('input[data-name="sharehref"]').fill("bday-cal")
    page.click('#createeditsharescene button[data-name="submit"]')
    expect(page.locator("tr[data-name='sharemaprowtemplate']:not(.hidden)")).to_have_count(1)

    # Close share scene and return to collection list
    page.click('#sharecollectionscene button[data-name="cancel"]')
    expect(page.locator("#sharecollectionscene")).to_be_hidden()

    # We now see the transformed share, thus we have 2 cards
    articles = page.locator("article:not(.hidden)")
    expect(articles).to_have_count(2)

    bday_article = articles.filter(
        has=page.locator("[data-name='transformed-from']:not(.hidden)")
    )
    expect(bday_article).to_be_visible()

    # Check delete button on the transformed card is visible
    delete_btn = bday_article.locator("a[data-name='delete']")
    expect(delete_btn).not_to_have_class(re.compile(r"\bhidden\b"))

    # Click delete button on the card
    bday_article.hover()
    delete_btn.click(force=True)
    expect(page.locator("#deleteconfirmationscene")).to_be_visible()

    # Confirm deletion
    page.fill("#deleteconfirmationscene input[data-name='confirmationtxt']", "DELETE")
    page.click("#deleteconfirmationscene button[data-name='delete']")
    expect(page.locator("#deleteconfirmationscene")).to_be_hidden()

    # The bday card should be gone
    expect(page.locator("article:not(.hidden)")).to_have_count(1)
    expect(page.locator("[data-name='transformed-from']:not(.hidden)")).to_have_count(0)

    # Verify virtual collection path returns 404
    req = requests.Session()
    req.trust_env = False
    get_resp = req.get(
        f"{radicale_server}/{config.admin_username}/bday-cal/",
        auth=(config.admin_username, "admi$pass#word"),
    )
    assert get_resp.status_code == 404, f"Expected 404, got {get_resp.status_code}"


def test_transform_share_edit_config(
    context: BrowserContext, page: Page, radicale_server: str, tmp_path: pathlib.Path
) -> None:
    """
    Editing an existing map-type bday share via WebUI properly updates
    conversion_bday_summary_template and conversion_bday_age_max.
    """
    config = SHARING_HTPASSWD
    _setup_addressbook_with_contact(page, radicale_server, config)

    # Create bday share with initial template and age max
    page.hover("article:not(.hidden)")
    page.click('article:not(.hidden) a[data-name="share"]', force=True)
    expect(page.locator("#sharecollectionscene")).to_be_visible()

    page.click('button[data-name="sharebymap"]')
    page.click('label[for="newshare_conv_bday"]')
    page.locator('input[data-name="shareuser"]').fill(config.admin_username)
    page.locator('input[data-name="sharehref"]').fill("bday-cal")
    page.locator("#newshare_config_conversion_bday_summary_template").fill("{fn} ({age} years)")
    page.locator("#newshare_config_conversion_bday_age_max").fill("5")
    page.click('#createeditsharescene button[data-name="submit"]')
    expect(page.locator("tr[data-name='sharemaprowtemplate']:not(.hidden)")).to_have_count(1)

    req = requests.Session()
    req.trust_env = False
    bday_cal_url = f"{radicale_server}/{config.admin_username}/bday-cal/"

    # Verify initial calendar output: with age_max=5, 1990+5 is far in the past, so current year event has no age
    resp1 = req.get(bday_cal_url, auth=(config.admin_username, "admi$pass#word"))
    assert resp1.status_code == 200
    assert "Alice Wonderland (36 years)" not in resp1.text

    # Edit the share via WebUI in the share list
    page.click("tr[data-name='sharemaprowtemplate']:not(.hidden) button[data-name='edit']", strict=True)
    expect(page.locator("#createeditsharescene h1")).to_have_text("Edit Share")

    # Verify input values are loaded
    expect(page.locator("#newshare_config_conversion_bday_summary_template")).to_have_value(
        "{fn} ({age} years)"
    )
    expect(page.locator("#newshare_config_conversion_bday_age_max")).to_have_value("5")

    # Update age_max to 50
    page.locator("#newshare_config_conversion_bday_age_max").fill("50")
    page.click('#createeditsharescene button[data-name="submit"]')
    expect(page.locator("#createeditsharescene")).to_be_hidden()

    # Verify updated calendar output reflects age_max=50 (current year 2026 - 1990 = 36)
    resp2 = req.get(bday_cal_url, auth=(config.admin_username, "admi$pass#word"))
    if resp2.status_code != 200:
        print("\n--- RADICALE LOG ---\n", (tmp_path / "radicale.log").read_text())
    assert resp2.status_code == 200
    assert "Alice Wonderland (36 years)" in resp2.text, f"Expected 36 years in:\n{resp2.text}"

    # Now edit again and update summary template
    page.click("tr[data-name='sharemaprowtemplate']:not(.hidden) button[data-name='edit']", strict=True)
    expect(page.locator("#createeditsharescene h1")).to_have_text("Edit Share")

    page.locator("#newshare_config_conversion_bday_summary_template").fill("{fn}'s Special Birthday")
    page.click('#createeditsharescene button[data-name="submit"]')
    expect(page.locator("#createeditsharescene")).to_be_hidden()

    resp3 = req.get(bday_cal_url, auth=(config.admin_username, "admi$pass#word"))
    assert resp3.status_code == 200
    assert "SUMMARY:Alice Wonderland's Special Birthday" in resp3.text

    # Now edit again and CLEAR summary template (verify #DEL# resets to default template)
    page.click("tr[data-name='sharemaprowtemplate']:not(.hidden) button[data-name='edit']", strict=True)
    expect(page.locator("#createeditsharescene h1")).to_have_text("Edit Share")

    page.locator("#newshare_config_conversion_bday_summary_template").fill("")
    page.click('#createeditsharescene button[data-name="submit"]')
    expect(page.locator("#createeditsharescene")).to_be_hidden()

    resp4 = req.get(bday_cal_url, auth=(config.admin_username, "admi$pass#word"))
    assert resp4.status_code == 200
    # Default template is "[{n:f} {n:g}|{fn}|{nickname}] ({year}) (BDAY)"
    assert "Alice Wonderland's Special Birthday" not in resp4.text
    assert "Alice Wonderland (1990) (BDAY)" in resp4.text


def test_transform_share_overlay_properties(
    context: BrowserContext, page: Page, radicale_server: str
) -> None:
    """
    Issue #2272:
    1. Creating a bday transform share with overlay properties (displayname, description, color)
       uses CALENDAR properties and succeeds without 400 error.
    2. Overridden displayname does not append default '(BDAY)' suffix.
    3. Re-opening Edit Share loads existing overlay properties.
    4. Editing overlay properties via Edit Share updates the share.
    5. Editing the collection card for a transformed share has the collection type
       selector disabled / locked to the current type, and PROPPATCH updates properties.
    """
    config = SHARING_HTPASSWD
    _setup_addressbook_with_contact(page, radicale_server, config)

    # 1. Open Share modal on Contacts
    page.hover("article:not(.hidden)")
    page.click('article:not(.hidden) a[data-name="share"]', force=True)
    expect(page.locator("#sharecollectionscene")).to_be_visible()

    # 2. Share by map with bday conversion and overlay properties
    page.click('button[data-name="sharebymap"]')
    page.click('label[for="newshare_conv_bday"]')
    page.locator('input[data-name="shareuser"]').fill(config.admin_username)
    page.locator('input[data-name="sharehref"]').fill("bday-cal")

    # Set overlay properties
    page.locator('details[data-name="properties_override"] summary').click()
    page.check('input[data-name="displayname_override_enabled"]')
    page.locator('input[data-name="displayname_override"]').fill("Alice Custom Birthdays")
    page.check('input[data-name="description_override_enabled"]')
    page.locator('input[data-name="description_override"]').fill("Alice Birthday Reminders")
    page.check('input[data-name="color_override_enabled"]')
    page.locator('input[data-name="color_override"]').fill("#336699")

    page.click('#createeditsharescene button[data-name="submit"]')
    expect(page.locator("#createeditsharescene")).to_be_hidden()
    expect(page.locator("tr[data-name='sharemaprowtemplate']:not(.hidden)")).to_have_count(1)

    # Close share scene
    page.click('#sharecollectionscene button[data-name="cancel"]')
    expect(page.locator("#sharecollectionscene")).to_be_hidden()

    # 3. Verify card on collection list
    articles = page.locator("article:not(.hidden)")
    expect(articles).to_have_count(2)
    bday_article = articles.filter(
        has=page.locator("[data-name='transformed-from']:not(.hidden)")
    )
    expect(bday_article).to_be_visible()

    # Custom displayname must NOT include "(BDAY)"
    title_el = bday_article.locator("[data-name='title']")
    expect(title_el).to_have_text("Alice Custom Birthdays")
    desc_el = bday_article.locator("[data-name='description']")
    expect(desc_el).to_have_text("Alice Birthday Reminders")

    # Verify color on the collection card in the UI (#336699 -> rgb(51, 102, 153))
    color_bar = bday_article.locator("[data-name='color']")
    expect(color_bar).to_have_css("background-color", "rgb(51, 102, 153)")

    # Verify via PROPFIND request
    req = requests.Session()
    req.trust_env = False
    bday_cal_url = f"{radicale_server}/{config.admin_username}/bday-cal/"
    propfind_xml = """<?xml version="1.0" encoding="utf-8" ?>
<D:propfind xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav" xmlns:ICAL="http://apple.com/ns/ical/">
  <D:prop>
    <D:displayname/>
    <C:calendar-description/>
    <ICAL:calendar-color/>
  </D:prop>
</D:propfind>"""
    resp = req.request("PROPFIND", bday_cal_url, auth=(config.admin_username, "admi$pass#word"), data=propfind_xml, headers={"Depth": "0"})
    assert resp.status_code == 207
    assert "Alice Custom Birthdays" in resp.text
    assert "(BDAY)" not in resp.text
    assert "Alice Birthday Reminders" in resp.text
    assert "#336699ff" in resp.text

    # 4. Re-open Edit Share and verify overlay properties are loaded
    contacts_article = articles.filter(
        has_not=page.locator("[data-name='transformed-from']:not(.hidden)")
    )
    contacts_article.hover()
    contacts_article.locator('a[data-name="share"]').click(force=True)
    expect(page.locator("#sharecollectionscene")).to_be_visible()

    page.click("tr[data-name='sharemaprowtemplate']:not(.hidden) button[data-name='edit']", strict=True)
    expect(page.locator("#createeditsharescene h1")).to_have_text("Edit Share")

    expect(page.locator('input[data-name="displayname_override_enabled"]')).to_be_checked()
    expect(page.locator('input[data-name="displayname_override"]')).to_have_value("Alice Custom Birthdays")
    expect(page.locator('input[data-name="description_override_enabled"]')).to_be_checked()
    expect(page.locator('input[data-name="description_override"]')).to_have_value("Alice Birthday Reminders")
    expect(page.locator('input[data-name="color_override_enabled"]')).to_be_checked()
    expect(page.locator('input[data-name="color_override"]')).to_have_value("#336699")

    # Update displayname via Edit Share
    page.locator('input[data-name="displayname_override"]').fill("Updated Alice Birthdays")
    page.click('#createeditsharescene button[data-name="submit"]')
    expect(page.locator("#createeditsharescene")).to_be_hidden()

    page.click('#sharecollectionscene button[data-name="cancel"]')
    expect(page.locator("#sharecollectionscene")).to_be_hidden()

    expect(bday_article.locator("[data-name='title']")).to_have_text("Updated Alice Birthdays")

    # 5. Test editing from the card: type selector must be disabled / locked to Calendar
    bday_article.hover()
    bday_article.locator('a[data-name="edit"]').click(force=True)
    expect(page.locator("#editcollectionscene")).to_be_visible()

    type_select = page.locator('#editcollectionscene select[data-name="type"]')
    expect(type_select).to_be_disabled()
    expect(type_select.locator("option")).to_have_count(1)

    # Verify color input in edit modal matches existing color
    expect(page.locator('#editcollectionscene input[data-name="color"]')).to_have_value("#336699")

    # Edit displayname and color from card
    page.locator('#editcollectionscene input[data-name="displayname"]').fill("Renamed From Card")
    page.locator('#editcollectionscene input[data-name="color"]').fill("#224466")
    page.click('#editcollectionscene button[data-name="submit"]')
    expect(page.locator("#editcollectionscene")).to_be_hidden()

    expect(bday_article.locator("[data-name='title']")).to_have_text("Renamed From Card")
    # Verify updated color on card in UI (#224466 -> rgb(34, 68, 102))
    expect(color_bar).to_have_css("background-color", "rgb(34, 68, 102)")

    resp2 = req.request("PROPFIND", bday_cal_url, auth=(config.admin_username, "admi$pass#word"), data=propfind_xml, headers={"Depth": "0"})
    assert resp2.status_code == 207
    assert "Renamed From Card" in resp2.text
    assert "#224466ff" in resp2.text
