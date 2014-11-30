# -*- coding: utf-8 -*-
#
# This file is part of Radicale Server - Calendar Server
# Copyright © 2014 Jean-Marc Martins
# Copyright © 2014-2015 Guillaume Ayoub
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
import shutil
import time
import sys

from . import filesystem
from .. import ical
from .. import log


class Collection(filesystem.Collection):
    """Collection stored in several files per calendar."""
    def _create_dirs(self):
        if not os.path.exists(self._path):
            os.makedirs(self._path)

    @property
    def headers(self):
        return (
            ical.Header("PRODID:-//Radicale//NONSGML Radicale Server//EN"),
            ical.Header("VERSION:%s" % self.version))

    def write(self):
        self._create_dirs()
        for component in self.components:
            text = ical.serialize(
                self.tag, self.headers, [component] + self.timezones)
            name = (
                component.name if sys.version_info[0] >= 3 else
                component.name.encode(filesystem.FILESYSTEM_ENCODING))
            path = os.path.join(self._path, name)
            with filesystem.open(path, "w") as fd:
                fd.write(text)

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
            filenames = os.listdir(self._path)
        except (OSError, IOError) as e:
            log.LOGGER.info('Error while reading collection %r: %r'
                            % (self._path, e))
            return ""

        for filename in filenames:
            path = os.path.join(self._path, filename)
            try:
                with filesystem.open(path) as fd:
                    items.update(self._parse(fd.read(), components))
            except (OSError, IOError) as e:
                log.LOGGER.warning('Error while reading item %r: %r'
                                   % (path, e))

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
