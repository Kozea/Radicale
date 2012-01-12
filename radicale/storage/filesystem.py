# -*- coding: utf-8 -*-
#
# This file is part of Radicale Server - Calendar Server
# Copyright © 2012 Guillaume Ayoub
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
Filesystem storage backend.

"""

import codecs
import os
import json
import time
from contextlib import contextmanager

from radicale import config, ical


FOLDER = os.path.expanduser(config.get("storage", "filesystem_folder"))


# This function overrides the builtin ``open`` function for this module
# pylint: disable=W0622
def open(path, mode="r"):
    abs_path = os.path.join(FOLDER, path.replace("/", os.sep))
    return codecs.open(abs_path, mode, config.get("encoding", "stock"))
# pylint: enable=W0622


class Calendar(ical.Calendar):
    @property
    def _path(self):
        """Absolute path of the file at local ``path``."""
        return os.path.join(FOLDER, self.path.replace("/", os.sep))

    @property
    def _props_path(self):
        """Absolute path of the file storing the calendar properties."""
        return self._path + ".props"

    def _create_dirs(self):
        """Create folder storing the calendar if absent."""
        if not os.path.exists(os.path.dirname(self._path)):
            os.makedirs(os.path.dirname(self._path))

    def save(self, text):
        self._create_dirs()
        open(self._path, "w").write(text)

    def delete(self):
        os.remove(self._path)
        os.remove(self._props_path)

    @property
    def text(self):
        try:
            return open(self._path).read()
        except IOError:
            return ""

    @classmethod
    def children(cls, path):
        abs_path = os.path.join(FOLDER, path.replace("/", os.sep))
        for filename in next(os.walk(abs_path))[2]:
            if cls.is_collection(path):
                yield cls(path)

    @classmethod
    def is_collection(cls, path):
        abs_path = os.path.join(FOLDER, path.replace("/", os.sep))
        return os.path.isdir(abs_path)

    @classmethod
    def is_item(cls, path):
        abs_path = os.path.join(FOLDER, path.replace("/", os.sep))
        return os.path.isfile(abs_path)

    @property
    def last_modified(self):
        # Create calendar if needed
        if not os.path.exists(self._path):
            self.write()

        modification_time = time.gmtime(os.path.getmtime(self._path))
        return time.strftime("%a, %d %b %Y %H:%M:%S +0000", modification_time)

    @property
    @contextmanager
    def props(self):
        # On enter
        properties = {}
        if os.path.exists(self._props_path):
            with open(self._props_path) as prop_file:
                properties.update(json.load(prop_file))
        yield properties
        # On exit
        self._create_dirs()
        with open(self._props_path, 'w') as prop_file:
            json.dump(properties, prop_file)


ical.Calendar = Calendar
