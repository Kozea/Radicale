import pathlib
from typing import Any, Generator

import pytest
from playwright.sync_api import Page, expect

from integ_tests.common import login, start_radicale_server


@pytest.fixture
def radicale_server(tmp_path: pathlib.Path) -> Generator[str, Any, None]:
    yield from start_radicale_server(tmp_path)


def test_index_html_loads(page: Page, radicale_server: str) -> None:
    """Test that the index.html loads from the server."""
    console_msgs: list[str] = []
    page.on("console", lambda msg: console_msgs.append(msg.text))
    page.goto(radicale_server)
    expect(page).to_have_title("Radicale Web Interface")
    # There should be no errors on the console
    assert len(console_msgs) == 0


def test_user_login_works(page: Page, radicale_server: str) -> None:
    """Test that the login form works."""
    login(page, radicale_server)

    # After login, we should see the collections list (which is empty)
    expect(
        page.locator('span[data-name="user"]', has_text="admin's Collections")
    ).to_be_visible()
