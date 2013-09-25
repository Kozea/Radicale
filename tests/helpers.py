# -*- coding: utf-8 -*-
#
# This file is part of Radicale Server - Calendar Server
# Copyright © 2008 Nicolas Kandel
# Copyright © 2008 Pascal Halter
# Copyright © 2008-2013 Guillaume Ayoub
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


def get_file_content(file_name):
    try:
        with open(os.path.join(EXAMPLES_FOLDER, file_name)) as fd:
            return fd.read()
    except IOError:
        print("Couldn't open the file %s" % file_name)
