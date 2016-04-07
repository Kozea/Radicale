# This file is part of Radicale Server - Calendar Server
# Copyright © 2014 Jean-Marc Martins
# Copyright © 2012-2016 Guillaume Ayoub
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
Storage backends.

This module loads the storage backend, according to the storage
configuration.

Default storage uses one folder per collection and one file per collection
entry.

"""

import json
import os
import posixpath
import shutil
import sys
import time
from contextlib import contextmanager

from . import config, ical, log, pathutils


def _load():
    """Load the storage manager chosen in configuration."""
    storage_type = config.get("storage", "type")
    if storage_type == "multifilesystem":
        module = sys.modules[__name__]
    else:
        __import__(storage_type)
        module = sys.modules[storage_type]
    ical.Collection = module.Collection


FOLDER = os.path.expanduser(config.get("storage", "filesystem_folder"))
FILESYSTEM_ENCODING = sys.getfilesystemencoding()


@contextmanager
def _open(path, mode="r"):
    """Open a file at ``path`` with encoding set in the configuration."""
    abs_path = os.path.join(FOLDER, path.replace("/", os.sep))
    with open(abs_path, mode, encoding=config.get("encoding", "stock")) as fd:
        yield fd


class Collection(ical.Collection):
    """Collection stored in several files per calendar."""
    @property
    def _filesystem_path(self):
        """Absolute path of the file at local ``path``."""
        return pathutils.path_to_filesystem(self.path, FOLDER)

    @property
    def _props_path(self):
        """Absolute path of the file storing the collection properties."""
        return self._filesystem_path + ".props"

    def _create_dirs(self):
        """Create folder storing the collection if absent."""
        if not os.path.exists(self._filesystem_path):
            os.makedirs(self._filesystem_path)

    def save(self, text):
        self._create_dirs()
        item_types = (
            ical.Timezone, ical.Event, ical.Todo, ical.Journal, ical.Card)
        for name, component in self._parse(text, item_types).items():
            if not pathutils.is_safe_filesystem_path_component(name):
                # TODO: Timezones with slashes can't be saved
                log.LOGGER.debug(
                    "Can't tranlate name safely to filesystem, "
                    "skipping component: %s", name)
                continue
            filename = os.path.join(self._filesystem_path, name)
            with _open(filename, "w") as fd:
                fd.write(component.text)

    @property
    def headers(self):
        return (
            ical.Header("PRODID:-//Radicale//NONSGML Radicale Server//EN"),
            ical.Header("VERSION:%s" % self.version))

    def delete(self):
        shutil.rmtree(self._filesystem_path)
        os.remove(self._props_path)

    def remove(self, name):
        if not pathutils.is_safe_filesystem_path_component(name):
            log.LOGGER.debug(
                "Can't tranlate name safely to filesystem, "
                "skipping component: %s", name)
            return
        if name in self.items:
            del self.items[name]
        filesystem_path = os.path.join(self._filesystem_path, name)
        if os.path.exists(filesystem_path):
            os.remove(filesystem_path)

    @property
    def text(self):
        components = (
            ical.Timezone, ical.Event, ical.Todo, ical.Journal, ical.Card)
        items = {}
        try:
            filenames = os.listdir(self._filesystem_path)
        except (OSError, IOError) as e:
            log.LOGGER.info(
                "Error while reading collection %r: %r" % (
                    self._filesystem_path, e))
            return ""

        for filename in filenames:
            path = os.path.join(self._filesystem_path, filename)
            try:
                with _open(path) as fd:
                    items.update(self._parse(fd.read(), components))
            except (OSError, IOError) as e:
                log.LOGGER.warning(
                    "Error while reading item %r: %r" % (path, e))

        return ical.serialize(
            self.tag, self.headers, sorted(items.values(), key=lambda x: x.name))

    @classmethod
    def children(cls, path):
        filesystem_path = pathutils.path_to_filesystem(path, FOLDER)
        _, directories, files = next(os.walk(filesystem_path))
        for filename in directories + files:
            # make sure that the local filename can be translated
            # into an internal path
            if not pathutils.is_safe_path_component(filename):
                log.LOGGER.debug("Skipping unsupported filename: %s", filename)
                continue
            rel_filename = posixpath.join(path, filename)
            if cls.is_node(rel_filename) or cls.is_leaf(rel_filename):
                yield cls(rel_filename)

    @classmethod
    def is_node(cls, path):
        filesystem_path = pathutils.path_to_filesystem(path, FOLDER)
        return (
            os.path.isdir(filesystem_path) and
            not os.path.exists(filesystem_path + ".props"))

    @classmethod
    def is_leaf(cls, path):
        filesystem_path = pathutils.path_to_filesystem(path, FOLDER)
        return (
            os.path.isdir(filesystem_path) and
            os.path.exists(filesystem_path + ".props"))

    @property
    def last_modified(self):
        last = max([
            os.path.getmtime(os.path.join(self._filesystem_path, filename))
            for filename in os.listdir(self._filesystem_path)] or [0])
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
        self._create_dirs()
        if old_properties != properties:
            with open(self._props_path, "w") as prop_file:
                json.dump(properties, prop_file)
