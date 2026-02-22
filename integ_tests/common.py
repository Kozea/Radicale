import os
import pathlib
import socket
import subprocess
import sys
import time
from typing import Any, Generator

from playwright.sync_api import Page


def get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start_radicale_server(tmp_path: pathlib.Path) -> Generator[str, Any, None]:
    port = get_free_port()
    config_path = tmp_path / "config"
    user_path = tmp_path / "users"
    storage_path = tmp_path / "collections"

    # Create a local config file
    with open(config_path, "w") as f:
        f.write(
            f"""[server]
hosts = 127.0.0.1:{port}
[storage]
filesystem_folder = {storage_path}
[auth]
type = htpasswd
htpasswd_filename = {user_path}
[web]
type = internal
[sharing]
type = csv
collection_by_map = true
collection_by_token = true
permit_create_token = true
permit_create_map = true

"""
        )
    with open(user_path, "w") as f:
        f.write(
            """admin:adminpassword
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


def login(page: Page, radicale_server: str) -> None:
    page.goto(radicale_server)
    page.fill('#loginscene input[data-name="user"]', "admin")
    page.fill('#loginscene input[data-name="password"]', "adminpassword")
    page.click('button:has-text("Next")')


def create_collection(page: Page, radicale_server: str) -> None:
    page.click('.fabcontainer a[data-name="new"]')
    page.click('#createcollectionscene button[data-name="submit"]')
