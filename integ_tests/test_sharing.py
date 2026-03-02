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

    page.click('button[data-name="sharebytoken_ro"]')
    expect(
        page.locator("tr[data-name='sharetokenrowtemplate']:not(.hidden)")
    ).to_have_count(1)
    expect(
        page.locator("tr[data-name='sharetokenrowtemplate']:not(.hidden) img[alt='RO']")
    ).to_be_visible()
    page.click('tr:not(.hidden) button[data-name="delete"]', strict=True)
    expect(
        page.locator("tr[data-name='sharetokenrowtemplate']:not(.hidden)")
    ).to_have_count(0)
    page.click('button[data-name="sharebytoken_rw"]')
    expect(
        page.locator("tr[data-name='sharetokenrowtemplate']:not(.hidden)")
    ).to_have_count(1)
    expect(
        page.locator("tr[data-name='sharetokenrowtemplate']:not(.hidden) img[alt='RW']")
    ).to_be_visible()
    page.click('tr:not(.hidden) button[data-name="delete"]', strict=True)
    expect(
        page.locator("tr[data-name='sharetokenrowtemplate']:not(.hidden)")
    ).to_have_count(0)
