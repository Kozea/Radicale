import pathlib
from typing import Any, Generator

import pytest
from playwright.sync_api import Page, expect

from integ_tests.common import create_collection, login, start_radicale_server


@pytest.fixture
def radicale_server(tmp_path: pathlib.Path) -> Generator[str, Any, None]:
    yield from start_radicale_server(tmp_path)


def test_create_and_delete_share_by_key(page: Page, radicale_server: str) -> None:
    login(page, radicale_server)
    create_collection(page, radicale_server)
    page.hover("article:not(.hidden)")
    page.click('article:not(.hidden) a[data-name="share"]', force=True, strict=True)

    expect(
        page.locator("tr[data-name='sharetokenrowtemplate']:not(.hidden)")
    ).to_have_count(0)

    page.click('button[data-name="sharebytoken"]')
    page.click('#newshare button[data-name="submit"]')
    expect(
        page.locator("tr[data-name='sharetokenrowtemplate']:not(.hidden)")
    ).to_have_count(1)
    expect(
        page.locator("tr[data-name='sharetokenrowtemplate']:not(.hidden) img[alt='RO']")
    ).to_be_visible()
    page.once("dialog", lambda dialog: dialog.accept())
    page.click('tr:not(.hidden) button[data-name="delete"]', strict=True)
    expect(
        page.locator("tr[data-name='sharetokenrowtemplate']:not(.hidden)")
    ).to_have_count(0)
    page.click('button[data-name="sharebytoken"]')
    page.click('label[for="newshare_attr_permissions_rw"]')
    page.click('#newshare button[data-name="submit"]')
    expect(
        page.locator("tr[data-name='sharetokenrowtemplate']:not(.hidden)")
    ).to_have_count(1)
    expect(
        page.locator("tr[data-name='sharetokenrowtemplate']:not(.hidden) img[alt='RW']")
    ).to_be_visible()
    page.once("dialog", lambda dialog: dialog.accept())
    page.click('tr:not(.hidden) button[data-name="delete"]', strict=True)
    expect(
        page.locator("tr[data-name='sharetokenrowtemplate']:not(.hidden)")
    ).to_have_count(0)


def test_create_and_delete_share_by_map(page: Page, radicale_server: str) -> None:
    login(page, radicale_server)
    create_collection(page, radicale_server)
    page.hover("article:not(.hidden)")
    page.click('article:not(.hidden) a[data-name="share"]', force=True, strict=True)

    expect(
        page.locator("tr[data-name='sharemaprowtemplate']:not(.hidden)")
    ).to_have_count(0)

    page.click('button[data-name="sharebymap"]')
    page.locator('input[data-name="shareuser"]').fill("max")
    page.locator('input[data-name="sharehref"]').fill("1234")
    page.click('#newshare button[data-name="submit"]')
    expect(
        page.locator("tr[data-name='sharemaprowtemplate']:not(.hidden)")
    ).to_have_count(1)
    expect(
        page.locator("tr[data-name='sharemaprowtemplate']:not(.hidden) img[alt='RO']")
    ).to_be_visible()
    page.once("dialog", lambda dialog: dialog.accept())
    page.click('tr:not(.hidden) button[data-name="delete"]', strict=True)
    expect(
        page.locator("tr[data-name='sharemaprowtemplate']:not(.hidden)")
    ).to_have_count(0)
    page.click('button[data-name="sharebymap"]')
    page.click('label[for="newshare_attr_permissions_rw"]')
    page.locator('input[data-name="shareuser"]').fill("max")
    page.locator('input[data-name="sharehref"]').fill("1234")
    page.click('#newshare button[data-name="submit"]')
    expect(
        page.locator("tr[data-name='sharemaprowtemplate']:not(.hidden)")
    ).to_have_count(1)
    expect(
        page.locator("tr[data-name='sharemaprowtemplate']:not(.hidden) img[alt='RW']")
    ).to_be_visible()
    page.once("dialog", lambda dialog: dialog.accept())
    page.click('tr:not(.hidden) button[data-name="delete"]', strict=True)
    expect(
        page.locator("tr[data-name='sharemaprowtemplate']:not(.hidden)")
    ).to_have_count(0)
