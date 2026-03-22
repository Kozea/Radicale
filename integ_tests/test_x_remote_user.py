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
Integration test for X-Remote-User authentication
"""

import os
import pathlib
import socket
import subprocess
import sys
import time
from typing import Any, Generator

import pytest
from playwright.sync_api import BrowserContext, Page, expect

from integ_tests.common import create_collection, get_free_port


def start_radicale_server_remote(tmp_path: pathlib.Path) -> Generator[str, Any, None]:
    port = get_free_port()
    config_path = tmp_path / "config"
    storage_path = tmp_path / "collections"

    # Create a local config file with http_x_remote_user auth
    with open(config_path, "w") as f:
        f.write(
            f"""[server]
hosts = 127.0.0.1:{port}
[storage]
filesystem_folder = {storage_path}
[auth]
type = http_x_remote_user
[web]
type = internal
[headers]
Content-Security-Policy = default-src 'self'; object-src 'none'
[sharing]
type = csv
collection_by_map = true
collection_by_token = true
permit_create_token = true
permit_create_map = true
permit_properties_overlay = true
collection_by_bday = true
permit_create_bday = true

"""
        )

    env = os.environ.copy()
    # Ensure the radicale package is in PYTHONPATH
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    env["PYTHONPATH"] = repo_root + os.pathsep + env.get("PYTHONPATH", "")

    # Run the server
    process = subprocess.Popen(
        [sys.executable, "-m", "radicale", "--config", str(config_path)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Wait for the server to start listening
    start_time = time.time()
    while time.time() - start_time < 10:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                break
        except (OSError, ConnectionRefusedError):
            if process.poll() is not None:
                _stdout, stderr = process.communicate()
                raise RuntimeError(
                    f"Radicale failed to start (code {process.returncode}):\n{stderr.decode()}"
                )
            time.sleep(0.1)
    else:
        process.terminate()
        process.wait()
        raise RuntimeError("Timeout waiting for Radicale to start")

    yield f"http://127.0.0.1:{port}"

    # Cleanup
    process.terminate()
    process.wait()


@pytest.fixture
def radicale_server(tmp_path: pathlib.Path) -> Generator[str, Any, None]:
    yield from start_radicale_server_remote(tmp_path)


def test_index_html_loads(
    context: BrowserContext, page: Page, radicale_server: str
) -> None:
    """Test that the index.html loads from the server with remote user."""
    context.set_extra_http_headers({"X-Remote-User": "admin"})
    console_msgs: list[str] = []
    page.on("console", lambda msg: console_msgs.append(msg.text))
    page.goto(radicale_server)
    expect(page).to_have_title("Radicale Web Interface")
    # There should be no errors on the console, except for the expected 401 from initial auto-login check
    errors = [msg for msg in console_msgs if "401 (Unauthorized)" not in msg]
    assert len(errors) == 0


def test_user_authenticated(
    context: BrowserContext, page: Page, radicale_server: str
) -> None:
    """Test that the user is automatically authenticated via X-Remote-User."""
    context.set_extra_http_headers({"X-Remote-User": "admin"})
    page.goto(radicale_server)

    # The login page should be skipped entirely if authenticated.
    # After auto-login, we should see the collections list (which is empty)
    expect(
        page.locator(
            '#logoutview span[data-name="user"]', has_text="admin's Collections"
        )
    ).to_be_visible()
    expect(page.locator('#logoutview a[data-name="logout"]')).to_be_hidden()


def test_create_collection_works(
    context: BrowserContext, page: Page, radicale_server: str
) -> None:
    """Test creating a collection with remote user."""
    context.set_extra_http_headers({"X-Remote-User": "admin"})
    page.goto(radicale_server)

    # Wait for auto-login
    expect(
        page.locator(
            '#logoutview span[data-name="user"]', has_text="admin's Collections"
        )
    ).to_be_visible()

    create_collection(page, radicale_server)

    # Verify that the new collection exists afterwards
    # By default it's called "Untitled Collection" or similar?
    # Let's check what create_collection does.
    # It clicks .fabcontainer a[data-name="new"] and then #createcollectionscene button[data-name="submit"]

    expect(page.locator("article:not(.hidden)")).to_have_count(1)
    # The title might be the HREF if no display name is set
    expect(page.locator("article:not(.hidden) .title")).to_be_visible()
