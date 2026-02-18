import os
import socket
import subprocess
import sys
import time

import pytest
from playwright.sync_api import Page, expect


def get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def radicale_server(tmp_path):
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
                stdout, stderr = process.communicate()
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


def test_index_html_loads(page: Page, radicale_server):
    """Test that the index.html loads from the server."""
    console_msgs = []
    page.on("console", lambda msg: console_msgs.append(msg.text))
    page.goto(radicale_server)
    expect(page).to_have_title("Radicale Web Interface")
    # There should be no errors on the console
    assert len(console_msgs) == 0


def test_user_login_works(page: Page, radicale_server):
    """Test that the login form works."""
    page.goto(radicale_server)
    # Fill in the login form
    page.fill('#loginscene input[data-name="user"]', "admin")
    page.fill('#loginscene input[data-name="password"]', "adminpassword")
    page.click('button:has-text("Next")')

    # After login, we should see the collections list (which is empty)
    expect(
        page.locator('span[data-name="user"]', has_text="admin's Collections")
    ).to_be_visible()
