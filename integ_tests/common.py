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
Common utilities for integration tests for radicale
"""

import os
import pathlib
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Generator, Optional

from playwright.sync_api import BrowserContext, Page, expect


class AuthType(Enum):
    HTPASSWD = "htpasswd"
    XREMOTE = "http_x_remote_user"


class SharingType(Enum):
    SHARING = "sharing"
    NOSHARING = "nosharing"


@dataclass(frozen=True)
class Config:
    name: str
    auth_type: AuthType
    sharing_type: SharingType
    extra_config: str = ""


SHARING_HTPASSWD = Config(
    name="sharing_htpasswd",
    auth_type=AuthType.HTPASSWD,
    sharing_type=SharingType.SHARING,
)

SHARING_XREMOTE = Config(
    name="sharing_xremote",
    auth_type=AuthType.XREMOTE,
    sharing_type=SharingType.SHARING,
)

NOSHARE_HTPASSWD = Config(
    name="noshare_htpasswd",
    auth_type=AuthType.HTPASSWD,
    sharing_type=SharingType.NOSHARING,
)


def get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start_radicale_server(
    tmp_path: pathlib.Path, config: Config = SHARING_HTPASSWD
) -> Generator[str, Any, None]:
    port = get_free_port()
    config_path = tmp_path / "config"
    user_path = tmp_path / "users"
    storage_path = tmp_path / "collections"

    sharing_path = tmp_path / "sharing.csv"

    with open(config_path, "w") as f:
        f.write(
            f"""[server]
hosts = 127.0.0.1:{port}
[storage]
filesystem_folder = {storage_path}
[auth]
type = {config.auth_type.value}
"""
        )
        if config.auth_type == AuthType.HTPASSWD:
            f.write(f"htpasswd_filename = {user_path}\n")
            f.write("htpasswd_encryption = plain\n")

        f.write(
            """[web]
type = internal
[headers]
Content-Security-Policy = default-src 'self'; object-src 'none'
"""
        )
        if config.sharing_type == SharingType.SHARING:
            f.write(
                f"""[sharing]
type = csv
collection_by_map = true
collection_by_token = true
permit_create_token = true
permit_create_map = true
permit_properties_overlay = true
collection_by_bday = true
permit_create_bday = true
database_path = {sharing_path}
"""
            )

        f.write(f"\n{config.extra_config}\n")

    if config.auth_type == AuthType.HTPASSWD:
        with open(user_path, "w") as f:
            f.write(
                """admin:admi$pass#word
max:maxpassword

"""
            )

    env = os.environ.copy()
    # Ensure the radicale package is in PYTHONPATH
    # Assuming this test file is in <repo>/integ_tests/
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


def login(
    page: Page,
    radicale_server: str,
    config: Config = SHARING_HTPASSWD,
    context: Optional[BrowserContext] = None,
) -> None:
    if config.auth_type == AuthType.XREMOTE:
        if context is None:
            raise ValueError("context is required for http_x_remote_user login")
        context.set_extra_http_headers({"X-Remote-User": "admin"})

    page.goto(radicale_server)

    if config.auth_type == AuthType.HTPASSWD:
        page.fill('#loginscene input[data-name="user"]', "admin")
        page.fill('#loginscene input[data-name="password"]', "admi$pass#word")
        page.click('button:has-text("Next")')

    expect(page.locator("#collectionsscene")).to_be_visible()


def create_collection(page: Page, radicale_server: str) -> None:
    page.click('.fabcontainer a[data-name="new"]')
    page.click('#createcollectionscene button[data-name="submit"]')
