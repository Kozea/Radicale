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

"""Hexdump lead marks follow the UTF-8 length prefixes."""

from radicale import utils


def test_data_to_special_marks_utf8_lead_lengths():
    assert utils.dataToSpecial(bytes([0xf0]), 1) == "4"
    assert utils.dataToSpecial(bytes([0xf7]), 1) == "4"
    assert utils.dataToSpecial(bytes([0xf8]), 1) == "."
    assert utils.dataToSpecial(bytes([0xff]), 1) == "."
    assert utils.dataToSpecial(bytes([0xe0]), 1) == "3"
    assert utils.dataToSpecial(bytes([0xef]), 1) == "3"
    assert utils.dataToSpecial(bytes([0xc2]), 1) == "2"
    assert utils.dataToSpecial(bytes([0xdf]), 1) == "2"
    assert utils.dataToSpecial(bytes([0x80]), 1) == "."
