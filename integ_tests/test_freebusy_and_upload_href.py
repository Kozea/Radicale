# This file is part of Radicale - CalDAV and CardDAV server
# Copyright © 2026-2026 oliviasculley <olivia@sculley.dev>
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

"""Web UI outcomes for the free/busy link and upload HREF checks.

A plain calendar shows a read-only free/busy URL. An address book, a
journal, and a birthday transform of an address book do not. Upload of
one file rejects an empty HREF and a leading slash, and accepts a
one-character HREF.
"""

import pathlib
import xml.etree.ElementTree as ET
from typing import Any, Generator
from urllib.parse import urlparse

import pytest
import requests
from playwright.sync_api import Browser, BrowserContext, Page, expect

from integ_tests.common import SHARING_HTPASSWD, Config, start_radicale_server
from integ_tests.conftest import INSECURE_HOST

MINIMAL_CALENDAR = "BEGIN:VCALENDAR\nVERSION:2.0\nEND:VCALENDAR\n"


def _set_value(page: Page, selector: str, value: str, dispatch_input: bool = True) -> None:
    """Set an input's value inside the page.

    Playwright's keyboard fill does not change input values in this
    environment. Dispatching ``input`` runs the same listeners a typed
    value would, including the HREF cleaner.
    """
    page.locator(selector).evaluate(
        """(el, args) => {
            el.value = args.value;
            if (args.dispatchInput) {
                el.dispatchEvent(new Event("input", { bubbles: true }));
            }
        }""",
        {"value": value, "dispatchInput": dispatch_input},
    )


def _login(page: Page, radicale_server: str, config: Config, context: BrowserContext) -> None:
    page.goto(radicale_server)
    _set_value(page, '#loginscene input[data-name="user"]', config.admin_username)
    _set_value(
        page, '#loginscene input[data-name="password"]', "admi$pass#word")
    page.click('#loginscene form[data-name="form"] button[type="submit"]')
    expect(page.locator("#collectionsscene")).to_be_visible()


@pytest.fixture
def radicale_server(tmp_path: pathlib.Path) -> Generator[str, Any, None]:
    yield from start_radicale_server(tmp_path, SHARING_HTPASSWD)


def _create(page: Page, collection_type: str, displayname: str) -> None:
    page.click('.fabcontainer a[data-name="new"]')
    page.select_option(
        '#createcollectionscene select[data-name="type"]', collection_type)
    _set_value(
        page, '#createcollectionscene input[data-name="displayname"]',
        displayname)
    page.click('#createcollectionscene button[data-name="submit"]')
    expect(page.locator("#createcollectionscene")).to_be_hidden()


def _article(page: Page, displayname: str):
    return page.locator("article:not(.hidden)").filter(
        has=page.locator("[data-name=title]", has_text=displayname))


def _collection_count(server: str, config: Config) -> int:
    """Number of collections stored under the logged-in principal."""
    path = "/%s/" % config.admin_username
    response = requests.request(
        "PROPFIND",
        server + path,
        auth=(config.admin_username, "admi$pass#word"),
        headers={"Depth": "1"},
        data="<?xml version='1.0' encoding='utf-8'?>"
             "<propfind xmlns='DAV:'><prop><resourcetype/></prop></propfind>",
    )
    assert response.status_code == 207, response.text
    root = ET.fromstring(response.content)
    responses = root.findall(".//{DAV:}response")
    # The principal response itself is one element.
    return len(responses) - 1


def test_freebusy_url_on_calendar_hidden_on_other_types(
    context: BrowserContext, page: Page, radicale_server: str
) -> None:
    """Calendar types show the free/busy URL; other types do not."""
    config = SHARING_HTPASSWD
    _login(page, radicale_server, config, context)
    assert page.evaluate("() => window.isSecureContext") is True

    _create(page, "CALENDAR", "Plain")
    _create(page, "CALENDAR_JOURNAL", "Mixed")
    _create(page, "ADDRESSBOOK", "People")
    _create(page, "JOURNAL", "Notes")

    for name in ("Plain", "Mixed"):
        card = _article(page, name)
        expect(card.locator("[data-name=freebusy-url-wrapper]")).to_be_visible()
        url = card.locator("input[data-name=url]").input_value()
        freebusy = card.locator("input[data-name=freebusy-url]")
        expect(freebusy).to_have_attribute("readonly", "")
        expect(freebusy).to_have_value(url + "?view=freebusy")
        print("freebusy url %s" % freebusy.input_value())
        assert urlparse(url).path.endswith("/")
        assert "?view=freebusy" not in url

    for name in ("People", "Notes"):
        card = _article(page, name)
        wrapper = card.locator("[data-name=freebusy-url-wrapper]")
        expect(wrapper).to_be_hidden()
        print("address-book wrapper hidden" if name == "People"
              else "non-calendar wrapper hidden", name,
              wrapper.get_attribute("class"))
        url = card.locator("input[data-name=url]").input_value()
        assert url.startswith(radicale_server + "/")
        assert "?view=freebusy" not in url


def test_freebusy_copy_writes_url_in_secure_context(
    context: BrowserContext, page: Page, radicale_server: str
) -> None:
    """The copy control writes the free/busy URL when the page is secure."""
    config = SHARING_HTPASSWD
    context.grant_permissions(["clipboard-read", "clipboard-write"])
    _login(page, radicale_server, config, context)
    assert page.evaluate("() => window.isSecureContext") is True
    _create(page, "CALENDAR", "Plain")

    card = _article(page, "Plain")
    url = card.locator("input[data-name=url]").input_value()
    copy_button = card.locator("button[data-name=copy-freebusy-url]")
    expect(copy_button).to_be_visible()
    copy_button.click()
    expect(copy_button).to_have_attribute("title", "Copied!")
    copied = page.evaluate("() => navigator.clipboard.readText()")
    assert copied == url + "?view=freebusy"


def test_freebusy_copy_hidden_when_not_secure(
    browser: Browser, tmp_path: pathlib.Path
) -> None:
    """The copy control stays hidden when the origin is not a secure context."""
    config = SHARING_HTPASSWD
    server = None
    generator = start_radicale_server(tmp_path, config)
    try:
        server = next(generator)
        insecure = server.replace("127.0.0.1", INSECURE_HOST, 1)
        context = browser.new_context()
        page = context.new_page()
        try:
            _login(page, insecure, config, context)
            assert page.evaluate("() => window.isSecureContext") is False
            _create(page, "CALENDAR", "Plain")
            card = _article(page, "Plain")
            url = card.locator("input[data-name=url]").input_value()
            expect(card.locator("[data-name=freebusy-url-wrapper]")).to_be_visible()
            expect(card.locator("input[data-name=freebusy-url]")).to_have_value(
                url + "?view=freebusy")
            expect(card.locator("button[data-name=copy-freebusy-url]")).to_be_hidden()
        finally:
            context.close()
    finally:
        generator.close()


def test_transform_calendar_hides_freebusy_url(
    context: BrowserContext, page: Page, radicale_server: str
) -> None:
    """A birthday transform is a calendar card and still hides the free/busy URL."""
    config = SHARING_HTPASSWD
    _login(page, radicale_server, config, context)
    _create(page, "ADDRESSBOOK", "People")

    page.hover("article:not(.hidden)")
    page.click('article:not(.hidden) a[data-name="share"]', force=True)
    expect(page.locator("#sharecollectionscene")).to_be_visible()
    page.click('button[data-name="sharebymap"]')
    page.locator("#newshare_conv_bday").wait_for(state="attached")
    # Headless Chromium lays this details content out at 0x0, so a pointer
    # click never lands. Checking the radio and firing change runs the same
    # handler as a click on the Birthday label.
    page.locator("#newshare_conv_bday").evaluate(
        """(el) => {
            el.checked = true;
            el.dispatchEvent(new Event("change", { bubbles: true }));
        }"""
    )
    _set_value(page, 'input[data-name="shareuser"]', config.admin_username)
    _set_value(page, 'input[data-name="sharehref"]', "bday-cal")
    page.click('#createeditsharescene button[data-name="submit"]')
    expect(page.locator(
        "tr[data-name='sharemaprowtemplate']:not(.hidden)")).to_have_count(1)
    page.click('#sharecollectionscene button[data-name="cancel"]')
    expect(page.locator("#sharecollectionscene")).to_be_hidden()

    source = page.locator("article:not(.hidden)").filter(
        has=page.locator("[data-name=transformed-from].hidden"))
    expect(source).to_have_count(1)
    expect(source.locator("[data-name=freebusy-url-wrapper]")).to_be_hidden()
    transformed = page.locator("article:not(.hidden)").filter(
        has=page.locator("[data-name=transformed-from]:not(.hidden)"))
    expect(transformed).to_have_count(1)
    expect(transformed.locator("[data-name=freebusy-url-wrapper]")).to_be_hidden()
    assert "?view=freebusy" not in transformed.locator(
        "input[data-name=url]").input_value()


def _open_upload(page: Page, tmp_path: pathlib.Path) -> pathlib.Path:
    calendar = tmp_path / "one.ics"
    calendar.write_text(MINIMAL_CALENDAR)
    page.click('.fabcontainer a[data-name="upload"]')
    page.set_input_files(
        '#uploadcollectionscene input[data-name="uploadfile"]', str(calendar))
    return calendar


def _set_href(page: Page, value: str, clean: bool) -> None:
    """Put ``value`` in the upload HREF field.

    ``clean`` false leaves a slash in place so submit-time validation can
    reject it. The input cleaner would remove that slash on a typed event.
    """
    _set_value(
        page, '#uploadcollectionscene input[data-name="href"]', value,
        dispatch_input=clean)


def _assert_no_collection(page: Page, server: str) -> None:
    error = page.locator('#uploadcollectionscene > span[data-name="error"]')
    expect(error).to_be_visible()
    expect(page.locator(
        '#uploadcollectionscene li:not(.hidden) [data-name="success"]')).to_have_count(0)
    page.click('#uploadcollectionscene button[data-name="close"]')
    expect(page.locator("article:not(.hidden)")).to_have_count(0)
    assert _collection_count(server, SHARING_HTPASSWD) == 0


def test_upload_href_empty_and_slash_rejected_minimal_accepted(
    context: BrowserContext,
    page: Page,
    radicale_server: str,
    tmp_path: pathlib.Path,
) -> None:
    """One selected file: empty and leading-slash HREFs create nothing.

    A single allowed character is the shortest HREF the form accepts.
    """
    config = SHARING_HTPASSWD
    _login(page, radicale_server, config, context)

    _open_upload(page, tmp_path)
    _set_href(page, "", clean=True)
    page.click('#uploadcollectionscene button[data-name="submit"]')
    error = page.locator('#uploadcollectionscene > span[data-name="error"]')
    expect(error).to_contain_text("HREF is empty")
    print("rejected href", error.text_content(), "collections",
          _collection_count(radicale_server, config))
    _assert_no_collection(page, radicale_server)

    _open_upload(page, tmp_path)
    _set_href(page, "   ", clean=True)
    page.click('#uploadcollectionscene button[data-name="submit"]')
    expect(page.locator(
        '#uploadcollectionscene > span[data-name="error"]')).to_contain_text(
            "HREF is empty")
    _assert_no_collection(page, radicale_server)

    _open_upload(page, tmp_path)
    _set_href(page, "/calendar", clean=False)
    page.click('#uploadcollectionscene button[data-name="submit"]')
    error = page.locator('#uploadcollectionscene > span[data-name="error"]')
    expect(error).to_contain_text("HREF cannot start with /")
    print("rejected href", error.text_content(), "collections",
          _collection_count(radicale_server, config))
    _assert_no_collection(page, radicale_server)

    _open_upload(page, tmp_path)
    _set_href(page, "cal/endar", clean=False)
    page.click('#uploadcollectionscene button[data-name="submit"]')
    expect(page.locator(
        '#uploadcollectionscene > span[data-name="error"]')).to_contain_text(
            "HREF is invalid")
    _assert_no_collection(page, radicale_server)

    _open_upload(page, tmp_path)
    _set_href(page, "a", clean=True)
    page.click('#uploadcollectionscene button[data-name="submit"]')
    success = page.locator(
        '#uploadcollectionscene li:not(.hidden) [data-name="success"]')
    expect(success).to_have_text("Uploaded Successfully!")
    expect(success).not_to_have_class("hidden")
    expect(page.locator(
        '#uploadcollectionscene li:not(.hidden) [data-name="error"]')).to_have_class(
            "error hidden")
    page.click('#uploadcollectionscene button[data-name="close"]')
    expect(page.locator("article:not(.hidden)")).to_have_count(1)
    expect(page.locator('article:not(.hidden) input[data-name="url"]')).to_have_value(
        radicale_server + "/%s/a/" % config.admin_username)
    assert _collection_count(radicale_server, config) == 1
