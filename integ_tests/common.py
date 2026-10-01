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
import re
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
    admin_username: str = "admin"
    user_username: str = "max"
    permit_properties_overlay: bool = True


SHARING_HTPASSWD = Config(
    name="sharing_htpasswd",
    auth_type=AuthType.HTPASSWD,
    sharing_type=SharingType.SHARING,
)

SHARING_HTPASSWD_NO_OVERLAY = Config(
    name="sharing_htpasswd_no_overlay",
    auth_type=AuthType.HTPASSWD,
    sharing_type=SharingType.SHARING,
    permit_properties_overlay=False,
)

SHARING_HTPASSWD_USERSWITHDOMAIN = Config(
    name="sharing_htpasswd_userswithdomain",
    auth_type=AuthType.HTPASSWD,
    sharing_type=SharingType.SHARING,
    admin_username="admin@domain.tld",
    user_username="max@domain.tld",
)

SHARING_HTGROUP = Config(
    name="sharing_htgroup",
    auth_type=AuthType.HTPASSWD,
    sharing_type=SharingType.SHARING,
    extra_config="[group]\ntype = htgroup\nhtgroup_filename = {group_path}\n",
)

SHARING_HTGROUP_USERSWITHDOMAIN = Config(
    name="sharing_htgroup_userswithdomain",
    auth_type=AuthType.HTPASSWD,
    sharing_type=SharingType.SHARING,
    extra_config="[group]\ntype = htgroup\nhtgroup_filename = {group_path}\n",
    admin_username="admin@domain.tld",
    user_username="max@domain.tld",
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
    group_path = tmp_path / "groups"
    storage_path = tmp_path / "collections"

    sharing_path = tmp_path / "sharing.csv"

    # Set up test htgroup file
    with open(group_path, "w") as f:
        f.write("group1: max user max@domain.tld user@domain.tld\n")
        f.write("group2: max user max@domain.tld user@domain.tld\n")
        f.write("editors: admin max admin@domain.tld max@domain.tld\n")

    extra_config = config.extra_config.replace("{group_path}", str(group_path))

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
permit_properties_overlay = {str(config.permit_properties_overlay).lower()}
database_path = {sharing_path}
"""
            )

        f.write(f"\n{extra_config}\n")

    if config.auth_type == AuthType.HTPASSWD:
        with open(user_path, "w") as f:
            f.write(f"{config.admin_username}:admi$pass#word\n")
            f.write(f"{config.user_username}:userpassword\n")

    env = os.environ.copy()
    # Ensure the radicale package is in PYTHONPATH
    # Assuming this test file is in <repo>/integ_tests/
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    env["PYTHONPATH"] = repo_root + os.pathsep + env.get("PYTHONPATH", "")

    # Run the server
    log_file = (tmp_path / "radicale.log").open("w+", encoding="utf-8")
    process = subprocess.Popen(
        [sys.executable, "-m", "radicale", "--config", str(config_path)],
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )

    # Wait for the server to start listening
    start_time = time.time()
    while time.time() - start_time < 10:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                break
        except (OSError, ConnectionRefusedError):
            if process.poll() is not None:
                log_file.seek(0)
                stderr = log_file.read()
                raise RuntimeError(
                    f"Radicale failed to start (code {process.returncode}):\n{stderr}"
                )
            time.sleep(0.1)
    else:
        process.terminate()
        process.wait(timeout=5)
        raise RuntimeError("Timeout waiting for Radicale to start")

    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        # Cleanup
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        log_file.close()


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
        page.fill('#loginscene input[data-name="user"]', config.admin_username)
        page.fill('#loginscene input[data-name="password"]', "admi$pass#word")
        page.click('button:has-text("Next")')

    expect(page.locator("#collectionsscene")).to_be_visible()


def create_collection(page: Page, radicale_server: str) -> None:
    page.click('.fabcontainer a[data-name="new"]')
    page.click('#createcollectionscene button[data-name="submit"]')


def create_named_collection(page: Page, name: str) -> None:
    page.click('.fabcontainer a[data-name="new"]')
    page.fill('#createcollectionscene input[data-name="displayname"]', name)
    page.click('#createcollectionscene button[data-name="submit"]')
    expect(page.locator("#createcollectionscene")).to_be_hidden()


def share_collection_to_user(
    page: Page,
    collection_title: Optional[str] = None,
    recipient: str = "max",
    share_href: str = "shared",
    permissions: str = "ro",
    allow_properties_write: bool = False,
) -> None:
    if collection_title:
        article = page.locator("article:not(.hidden)").filter(
            has=page.locator(
                "[data-name='title']",
                has_text=re.compile(f"^{re.escape(collection_title)}$"),
            )
        )
    else:
        article = page.locator("article:not(.hidden)").first
    article.hover()
    article.locator("a[data-name='share']").click(force=True)
    expect(page.locator("#sharecollectionscene")).to_be_visible()
    page.click('button[data-name="sharebymap"]')
    page.locator('input[data-name="shareuser"]').fill(recipient)
    page.locator('input[data-name="sharehref"]').fill(share_href)
    if permissions == "rw":
        page.check("#newshare_attr_permissions_rw")
    if allow_properties_write:
        page.check("#newshare_attr_properties_write_allow")
    page.click('#createeditsharescene button[data-name="submit"]')
    expect(
        page.locator("tr[data-name='sharemaprowtemplate']:not(.hidden)")
    ).to_have_count(1)
    page.click('#sharecollectionscene button[data-name="cancel"]')
    expect(page.locator("#sharecollectionscene")).to_be_hidden()
