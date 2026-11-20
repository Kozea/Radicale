# This file is part of Radicale - CalDAV and CardDAV server
# Copyright © 2026-2026 oliviasculley <olivia@sculley.dev>
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

"""A socket stored under an item name is not an item."""

import os
import socket
import sys
import tempfile

import pytest

from radicale import config, storage

pytestmark = pytest.mark.skipif(
    not hasattr(socket, "AF_UNIX"),
    reason="This platform has no unix-socket inode")


def test_readable_socket_is_not_an_item():
    with tempfile.TemporaryDirectory(prefix="rc", dir="/tmp") as folder:
        configuration = config.load()
        configuration.update({
            "storage": {"filesystem_folder": folder,
                        "filesystem_fsync": False},
        }, "test", privileged=True)
        storage_ = storage.load(configuration)
        with storage_.acquire_lock("w"):
            collection = storage_.create_collection(
                "/user/cal/", props={"tag": "VCALENDAR"})[0]
            storage_._use_mtime_and_size_for_item_cache = True
            sock_path = os.path.join(collection._filesystem_path, "sock.ics")
            sun_path_max = 104 if sys.platform == "darwin" else 108
            assert len(os.fsencode(sock_path)) < sun_path_max
            sock = socket.socket(socket.AF_UNIX)
            try:
                sock.bind(sock_path)
                os.chmod(sock_path, 0o644)
                assert os.access(sock_path, os.R_OK)
                assert collection._get("sock.ics") is None
            finally:
                sock.close()
                if os.path.exists(sock_path):
                    os.chmod(sock_path, 0o600)
                    os.remove(sock_path)
