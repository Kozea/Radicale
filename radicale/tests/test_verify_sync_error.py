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

"""verify-storage fails when collection sync raises ValueError."""

import logging

from radicale import config
from radicale import item as radicale_item
from radicale import storage
from radicale.storage import multifilesystem


def _event():
    text = (
        "BEGIN:VCALENDAR\r\nVERSION:2.0\r\n"
        "BEGIN:VEVENT\r\nUID:event1\r\nSUMMARY:Event\r\n"
        "DTSTART:20130901T160000Z\r\nDTEND:20130901T170000Z\r\n"
        "END:VEVENT\r\nEND:VCALENDAR\r\n")
    return radicale_item.Item(collection_path="", text=text)


def test_verify_fails_when_sync_raises_valueerror(tmp_path, monkeypatch, caplog):
    caplog.set_level(logging.ERROR)
    configuration = config.load()
    configuration.update({
        "storage": {"filesystem_folder": str(tmp_path),
                    "filesystem_fsync": False},
    }, "test", privileged=True)
    storage_ = storage.load(configuration)
    with storage_.acquire_lock("w"):
        storage_.create_collection(
            "/user/cal/", items=[_event()], props={"tag": "VCALENDAR"})

    def boom_sync(self, old_token=""):
        raise ValueError("sync-boom")

    monkeypatch.setattr(multifilesystem.Collection, "sync", boom_sync)
    assert storage_.verify() is False
    assert "sync-boom" in caplog.text
    assert "Invalid collection" in caplog.text
