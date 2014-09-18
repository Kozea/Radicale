# -*- coding: utf-8 -*-
#
# This file is part of Radicale Server - Calendar Server
# Copyright © 2013 Guillaume Ayoub
# Copyright © 2013 Jean-Marc Martins
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
Multi files per calendar filesystem storage backend.

"""

import os
import json
import shutil
import time
import sys

from contextlib import contextmanager
from . import filesystem
from .. import ical


def _to_filesystem_name(name):
    if sys.version_info[0] >= 3:
        return name
    else:
        return name.encode(filesystem.FILESYSTEM_ENCODING)

class Collection(filesystem.Collection):
    """Collection stored in several files per calendar."""
    def _create_dirs(self):
        if not os.path.exists(self._path):
            os.makedirs(self._path)

    def save(self, text, message=None):
        """Save the text into the collection.

        This method is not used for multifilesystem as we don't operate on one
        unique file.

        """

    @property
    def headers(self):
        return (
            ical.Header("PRODID:-//Radicale//NONSGML Radicale Server//EN"),
            ical.Header("VERSION:%s" % self.version))

    def _write_item(self, name, text, must_not_exist):
        self._create_dirs()

        fs_name = _to_filesystem_name(name)
        path = os.path.join(self._path, fs_name)

        if os.path.exists(path):
            if must_not_exist:
                return

        # Still parse to make sure we handle the items correctly
        items = self._parse(
                text, (ical.Timezone, ical.Event, ical.Todo, ical.Journal, ical.Card), name)
        new_text = ical.serialize(self.tag, self.headers, items)
        with filesystem.open(path, "w") as fd:
            fd.write(new_text)

    def append(self, name, text):
        self._write_item(name, text, True)

    def replace(self, name, text):
        self._write_item(name, text, False)

    def write(self, headers=None, items=None, message=None):
        """Write collection with given parameters.

        This method is not used for multifilesystem as we don't operate on one
        unique file.

        """

    def delete(self):
        shutil.rmtree(self._path)
        os.remove(self._props_path)

    def remove(self, name):
        if os.path.exists(os.path.join(self._path, name)):
            os.remove(os.path.join(self._path, name))

    @property
    def text(self):
        components = (
            ical.Timezone, ical.Event, ical.Todo, ical.Journal, ical.Card)
        items = set()
        try:
            for filename in os.listdir(self._path):
                with filesystem.open(os.path.join(self._path, filename)) as fd:
                    items.update(self._parse(fd.read(), components))
        except IOError:
            return ""
        else:
            return ical.serialize(
                self.tag, self.headers, sorted(items, key=lambda x: x.name))

    @classmethod
    def is_node(cls, path):
        path = os.path.join(filesystem.FOLDER, path.replace("/", os.sep))
        return os.path.isdir(path) and not os.path.exists(path + ".props")

    @classmethod
    def is_leaf(cls, path):
        path = os.path.join(filesystem.FOLDER, path.replace("/", os.sep))
        return os.path.isdir(path) and os.path.exists(path + ".props")

    @property
    def last_modified(self):
        last = max([
            os.path.getmtime(os.path.join(self._path, filename))
            for filename in os.listdir(self._path)] or [0])
        return time.strftime("%a, %d %b %Y %H:%M:%S +0000", time.gmtime(last))

    @property
    @contextmanager
    def props(self):
        # On enter
        properties = {}
        if os.path.exists(self._props_path):
            with open(self._props_path) as prop_file:
                properties.update(json.load(prop_file))
        old_properties = properties.copy()
        yield properties
        # On exit
        if os.path.exists(self._props_path):
          self._create_dirs()
          if old_properties != properties:
              with open(self._props_path, "w") as prop_file:
                  json.dump(properties, prop_file)
