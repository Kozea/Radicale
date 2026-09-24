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
Integration tests for issue #2234:
1. Verify edit button is hidden on collection cards when user lacks proppatch permissions.
2. Verify proppatch 403 error displays on the standard error line and does not close the dialog.
"""

import pathlib
import re
from typing import Any, Generator
from urllib.parse import urlparse

import pytest
import requests
from playwright.sync_api import BrowserContext, Page, Route, expect

from integ_tests.common import (SHARING_HTPASSWD, SHARING_HTPASSWD_NO_OVERLAY,
                                login, start_radicale_server)


@pytest.fixture
def radicale_server(tmp_path: pathlib.Path) -> Generator[str, Any, None]:
    yield from start_radicale_server(tmp_path, SHARING_HTPASSWD)


@pytest.fixture
def radicale_server_no_overlay(tmp_path: pathlib.Path) -> Generator[str, Any, None]:
    yield from start_radicale_server(tmp_path, SHARING_HTPASSWD_NO_OVERLAY)


def test_edit_button_hidden_when_no_proppatch_permission(
    context: BrowserContext, page: Page, radicale_server_no_overlay: str
) -> None:
    """
    Verify requirement (b):
    If the user lacks proppatch permissions (e.g. permit_properties_overlay is False
    and the share does not have 'P' permission), the edit button on the card is hidden.
    """
    config = SHARING_HTPASSWD_NO_OVERLAY

    login(page, radicale_server_no_overlay, config, context=context)

    # 1. Create an Addressbook collection
    page.click('a[data-name="new"]')
    page.locator('#createcollectionscene select[data-name="type"]').select_option(
        "ADDRESSBOOK"
    )
    page.locator('#createcollectionscene input[data-name="displayname"]').fill(
        "Contacts"
    )
    page.click('#createcollectionscene button[data-name="submit"]')
    expect(page.locator("#createcollectionscene")).to_be_hidden()

    collection_url = page.locator(
        "article:not(.hidden) input[data-name='url']"
    ).input_value()
    path_mapped = urlparse(collection_url).path

    # 2. Create map share with Conversion=bday (permissions default to 'r', overlay disabled)
    resp = requests.post(
        f"{radicale_server_no_overlay}/.sharing/v1/map/create",
        auth=(config.admin_username, "admi$pass#word"),
        data={
            "PathMapped": path_mapped,
            "PathOrToken": f"/{config.admin_username}/bday/",
            "User": config.admin_username,
            "Conversion": "bday",
        },
    )
    assert resp.status_code == 200, f"API create failed: {resp.status_code} {resp.text}"

    requests.post(
        f"{radicale_server_no_overlay}/.sharing/v1/map/enable",
        auth=(config.admin_username, "admi$pass#word"),
        data={"PathOrToken": f"/{config.admin_username}/bday/"},
    )
    requests.post(
        f"{radicale_server_no_overlay}/.sharing/v1/map/unhide",
        auth=(config.admin_username, "admi$pass#word"),
        data={"PathOrToken": f"/{config.admin_username}/bday/"},
    )

    # Refresh collection list
    login(page, radicale_server_no_overlay, config, context=context)

    articles = page.locator("article:not(.hidden)")
    expect(articles).to_have_count(2)

    contacts_article = articles.filter(
        has_not=page.locator("[data-name='transformed-from']:not(.hidden)")
    )
    bday_article = articles.filter(
        has=page.locator("[data-name='transformed-from']:not(.hidden)")
    )
    expect(contacts_article).to_be_visible()
    expect(bday_article).to_be_visible()

    # The owner collection has WRITE_PROPERTIES, so its edit button is not hidden
    contacts_edit = contacts_article.locator("a[data-name='edit']")
    expect(contacts_edit).not_to_have_class(re.compile(r"\bhidden\b"))

    # The bday share lacks WRITE_PROPERTIES, so its edit button must be hidden
    bday_edit = bday_article.locator("a[data-name='edit']")
    expect(bday_edit).to_have_class(re.compile(r"\bhidden\b"))


def test_proppatch_403_shows_error_and_does_not_close_dialog(
    context: BrowserContext, page: Page, radicale_server: str
) -> None:
    """
    Verify requirement (a):
    On a 403 error during PROPPATCH, the error is shown on the standard error line
    and the dialog is not closed.
    """
    config = SHARING_HTPASSWD

    login(page, radicale_server, config, context=context)

    # 1. Create a collection
    page.click('a[data-name="new"]')
    page.locator('#createcollectionscene input[data-name="displayname"]').fill(
        "Test Calendar"
    )
    page.click('#createcollectionscene button[data-name="submit"]')
    expect(page.locator("#createcollectionscene")).to_be_hidden()

    # 2. Open edit dialog
    article = page.locator("article:not(.hidden)").first
    article.hover()
    article.locator("a[data-name='edit']").click()
    expect(page.locator("#editcollectionscene")).to_be_visible()

    # 3. Intercept PROPPATCH to simulate a 403 Forbidden response
    def handle_route(route: Route) -> None:
        if route.request.method == "PROPPATCH":
            route.fulfill(status=403, body="Forbidden")
        else:
            route.continue_()

    page.route("**/*", handle_route)

    # 4. Fill in new display name and click Save
    page.fill(
        '#editcollectionscene input[data-name="displayname"]', "New Calendar Name"
    )
    page.click('#editcollectionscene button[data-name="submit"]')

    # 5. Verify the dialog remains open
    expect(page.locator("#editcollectionscene")).to_be_visible()

    # 6. Verify the error is shown on the error line
    error_span = page.locator('#editcollectionscene span[data-name="error"]').first
    expect(error_span).to_be_visible()
    expect(error_span).to_contain_text("403")
