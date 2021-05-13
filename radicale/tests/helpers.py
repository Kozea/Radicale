# This file is part of Radicale Server - Calendar Server
# Copyright © 2008 Nicolas Kandel
# Copyright © 2008 Pascal Halter
# Copyright © 2008-2017 Guillaume Ayoub
# Copyright © 2017-2019 Unrud <unrud@outlook.com>
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
Radicale Helpers module.

This module offers helpers to use in tests.

"""

import os

EXAMPLES_FOLDER = os.path.join(os.path.dirname(__file__), "static")


def get_file_path(file_name):
    return os.path.join(EXAMPLES_FOLDER, file_name)


def get_file_content(file_name):
    with open(get_file_path(file_name), encoding="utf-8") as fd:
        return fd.read()


def configuration_to_dict(configuration):
    """Convert configuration to a dict with raw values."""
    return {section: {option: configuration.get_raw(section, option)
                      for option in configuration.options(section)
                      if not option.startswith("_")}
            for section in configuration.sections()
            if not section.startswith("_")}
