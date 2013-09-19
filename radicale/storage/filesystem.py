# -*- coding: utf-8 -*-
#
# This file is part of Radicale Server - Calendar Server
# Copyright © 2012-2013 Guillaume Ayoub
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
import posixpath
import json
import time
import sys
from contextlib import contextmanager
from .. import config, ical


FOLDER = os.path.expanduser(config.get("storage", "filesystem_folder"))
FILESYSTEM_ENCODING = sys.getfilesystemencoding()

try:
    from dulwich.repo import Repo
    GIT_REPOSITORY = Repo(FOLDER)
except:
    GIT_REPOSITORY = None


# This function overrides the builtin ``open`` function for this module
# pylint: disable=W0622
@contextmanager
def open(path, mode="r"):
    """Open a file at ``path`` with encoding set in the configuration."""
    # On enter
    abs_path = os.path.join(FOLDER, path.replace("/", os.sep))
    with codecs.open(abs_path, mode, config.get("encoding", "stock")) as fd:
        yield fd
    # On exit
    if GIT_REPOSITORY and mode == "w":
        path = os.path.relpath(abs_path, FOLDER)
        GIT_REPOSITORY.stage([path])
        committer = config.get("git", "committer")
        GIT_REPOSITORY.do_commit("Commit by Radicale", committer=committer)
# pylint: enable=W0622


class Collection(ical.Collection):
    """Collection stored in a flat ical file."""
    @property
    def _path(self):
        """Absolute path of the file at local ``path``."""
        return os.path.join(FOLDER, self.path.replace("/", os.sep))

    @property
    def _props_path(self):
        """Absolute path of the file storing the collection properties."""
        return self._path + ".props"

    def _create_dirs(self):
        """Create folder storing the collection if absent."""
        if not os.path.exists(os.path.dirname(self._path)):
            os.makedirs(os.path.dirname(self._path))

    def save(self, text):
        self._create_dirs()
        with open(self._path, "w") as fd:
            fd.write(text)

    def delete(self):
        os.remove(self._path)
        os.remove(self._props_path)

    @property
    def text(self):
        try:
            with open(self._path) as fd:
                return fd.read()
        except IOError:
            return ""

    @classmethod
    def children(cls, path):
        abs_path = os.path.join(FOLDER, path.replace("/", os.sep))
        _, directories, files = next(os.walk(abs_path))
        for filename in directories + files:
            rel_filename = posixpath.join(path, filename)
            if cls.is_node(rel_filename) or cls.is_leaf(rel_filename):
                yield cls(rel_filename)

    @classmethod
    def is_node(cls, path):
        abs_path = os.path.join(FOLDER, path.replace("/", os.sep))
        return os.path.isdir(abs_path)

    @classmethod
    def is_leaf(cls, path):
        abs_path = os.path.join(FOLDER, path.replace("/", os.sep))
        return os.path.isfile(abs_path) and not abs_path.endswith(".props")

    @property
    def last_modified(self):
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
        old_properties = properties.copy()
        yield properties
        # On exit
        self._create_dirs()
        if old_properties != properties:
            with open(self._props_path, "w") as prop_file:
                json.dump(properties, prop_file)
