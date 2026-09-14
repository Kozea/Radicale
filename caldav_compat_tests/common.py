# This file is part of Radicale - CalDAV and CardDAV server
# Copyright © 2026-2026 Arnav S <172543153+theofficialtruck@users.noreply.github.com>
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
Common utilities for the caldav-server-tester based compatibility tests.

Starts a real Radicale server (subprocess, listening on a free localhost
port) so that a genuine ``caldav.davclient.DAVClient`` can talk to it over
HTTP, the same way ``integ_tests/common.py`` does for the Playwright-based
integration tests.
"""

import os
import pathlib
import socket
import subprocess
import sys
import time
from typing import Any, Generator


def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start_radicale_server(
    tmp_path: pathlib.Path,
    username: str = "tester",
    password: str = "testpassword",
) -> Generator[str, Any, None]:
    """Start a Radicale server backed by a temporary filesystem storage.

    Yields the base URL of the running server. The username/password are
    for a single htpasswd-authenticated user.
    """
    port = get_free_port()
    config_path = tmp_path / "config"
    user_path = tmp_path / "users"
    storage_path = tmp_path / "collections"

    with open(user_path, "w") as f:
        f.write(f"{username}:{password}\n")

    with open(config_path, "w") as f:
        f.write(
            f"""[server]
hosts = 127.0.0.1:{port}
[storage]
filesystem_folder = {storage_path}
[auth]
type = htpasswd
htpasswd_filename = {user_path}
htpasswd_encryption = plain
[web]
type = internal
"""
        )

    env = os.environ.copy()
    # Ensure the radicale package is in PYTHONPATH
    # Assuming this test file is in <repo>/caldav_compat_tests/
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    env["PYTHONPATH"] = repo_root + os.pathsep + env.get("PYTHONPATH", "")

    log_path = tmp_path / "server.log"
    with open(log_path, "wb") as log_file:
        # Redirect to a file rather than PIPE: nothing reads the pipes while
        # the server runs, and an unread PIPE can fill its OS buffer and
        # deadlock the child before it gets to bind the listening socket.
        process = subprocess.Popen(
            [sys.executable, "-m", "radicale", "--config", str(config_path)],
            env=env,
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )

        start_time = time.time()
        while time.time() - start_time < 10:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                    break
            except (OSError, ConnectionRefusedError):
                if process.poll() is not None:
                    raise RuntimeError(
                        f"Radicale failed to start (code {process.returncode}):\n"
                        f"{log_path.read_text(errors='replace')}"
                    )
                time.sleep(0.1)
        else:
            process.terminate()
            process.wait()
            raise RuntimeError(
                f"Timeout waiting for Radicale to start:\n{log_path.read_text(errors='replace')}"
            )

        try:
            yield f"http://127.0.0.1:{port}/"
        finally:
            process.terminate()
            process.wait()
