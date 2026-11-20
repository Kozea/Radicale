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

"""verify-storage fails when two items share a UID."""

import os

from radicale import config
from radicale import item as radicale_item
from radicale import storage


def _event(uid):
    text = (
        "BEGIN:VCALENDAR\r\nVERSION:2.0\r\n"
        "BEGIN:VEVENT\r\nUID:%s\r\nSUMMARY:Event\r\n"
        "DTSTART:20130901T160000Z\r\nDTEND:20130901T170000Z\r\n"
        "END:VEVENT\r\nEND:VCALENDAR\r\n" % uid)
    return radicale_item.Item(collection_path="", text=text)


def test_verify_fails_on_a_uid_conflict(tmp_path, caplog):
    import logging
    caplog.set_level(logging.ERROR)
    configuration = config.load()
    configuration.update({
        "storage": {"filesystem_folder": str(tmp_path),
                    "filesystem_fsync": False},
    }, "test", privileged=True)
    storage_ = storage.load(configuration)
    with storage_.acquire_lock("w"):
        collection = storage_.create_collection(
            "/user/cal/", items=[_event("same")],
            props={"tag": "VCALENDAR"})[0]
    source = os.path.join(collection._filesystem_path, "event.ics")
    names = os.listdir(collection._filesystem_path)
    original = [name for name in names if name.endswith(".ics")][0]
    source = os.path.join(collection._filesystem_path, original)
    copy = os.path.join(collection._filesystem_path, "copy.ics")
    with open(source, "r", encoding="utf-8") as handle:
        text = handle.read()
    with open(copy, "w", encoding="utf-8") as handle:
        handle.write(text)
    assert storage_.verify() is False
    assert "UID conflict" in caplog.text
