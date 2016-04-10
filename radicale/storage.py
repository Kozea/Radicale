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

This module loads the storage backend, according to the storage configuration.

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
from hashlib import md5
from random import randint
from uuid import uuid4

import vobject

from . import config, log


def _load():
    """Load the storage manager chosen in configuration."""
    storage_type = config.get("storage", "type")
    if storage_type == "multifilesystem":
        module = sys.modules[__name__]
    else:
        __import__(storage_type)
        module = sys.modules[storage_type]
    sys.modules[__name__].Collection = module.Collection


FOLDER = os.path.expanduser(config.get("storage", "filesystem_folder"))
FILESYSTEM_ENCODING = sys.getfilesystemencoding()
STORAGE_ENCODING = config.get("encoding", "stock")


def serialize(tag, headers=(), items=()):
    """Return a text corresponding to given collection ``tag``.

    The text may have the given ``headers`` and ``items`` added around the
    items if needed (ie. for calendars).

    """
    items = sorted(items, key=lambda x: x.name)
    if tag == "VADDRESSBOOK":
        lines = [item.text.strip() for item in items]
    else:
        lines = ["BEGIN:%s" % tag]
        for part in (headers, items):
            if part:
                lines.append("\r\n".join(item.text.strip() for item in part))
        lines.append("END:%s" % tag)
    lines.append("")
    return "\r\n".join(lines)


def sanitize_path(path):
    """Make path absolute with leading slash to prevent access to other data.

    Preserve a potential trailing slash.

    """
    trailing_slash = "/" if path.endswith("/") else ""
    path = posixpath.normpath(path)
    new_path = "/"
    for part in path.split("/"):
        if not part or part in (".", ".."):
            continue
        new_path = posixpath.join(new_path, part)
    trailing_slash = "" if new_path.endswith("/") else trailing_slash
    return new_path + trailing_slash


def is_safe_filesystem_path_component(path):
    """Check if path is a single component of a filesystem path.

    Check that the path is safe to join too.

    """
    return (
        path and not os.path.splitdrive(path)[0] and
        not os.path.split(path)[0] and path not in (os.curdir, os.pardir))


def path_to_filesystem(path):
    """Convert path to a local filesystem path relative to base_folder.

    Conversion is done in a secure manner, or raises ``ValueError``.

    """
    sane_path = sanitize_path(path).strip("/")
    safe_path = FOLDER
    if not sane_path:
        return safe_path
    for part in sane_path.split("/"):
        if not is_safe_filesystem_path_component(part):
            log.LOGGER.debug(
                "Can't translate path safely to filesystem: %s", path)
            raise ValueError("Unsafe path")
        safe_path = os.path.join(safe_path, part)
    return safe_path


class Item(object):
    """Internal iCal item."""
    def __init__(self, text, name=None):
        """Initialize object from ``text`` and different ``kwargs``."""
        self.component = vobject.readOne(text)
        self._name = name

        if not self.component.name:
            # Header
            self._name = next(self.component.lines()).name.lower()
            return

        # We must synchronize the name in the text and in the object.
        # An item must have a name, determined in order by:
        #
        # - the ``name`` parameter
        # - the ``X-RADICALE-NAME`` iCal property (for Events, Todos, Journals)
        # - the ``UID`` iCal property (for Events, Todos, Journals)
        # - the ``TZID`` iCal property (for Timezones)
        if not self._name:
            for line in self.component.lines():
                if line.name in ("X-RADICALE-NAME", "UID", "TZID"):
                    self._name = line.value
                    if line.name == "X-RADICALE-NAME":
                        break

        if self._name:
            # Leading and ending brackets that may have been put by Outlook.
            # Slashes are mostly unwanted when saving collections on disk.
            self._name = self._name.strip("{}").replace("/", "_")
        else:
            self._name = uuid4().hex

        if not hasattr(self.component, "x_radicale_name"):
            self.component.add("X-RADICALE-NAME")
        self.component.x_radicale_name.value = self._name

    def __hash__(self):
        return hash(self.text)

    def __eq__(self, item):
        return isinstance(item, Item) and self.text == item.text

    @property
    def etag(self):
        """Item etag.

        Etag is mainly used to know if an item has changed.

        """
        etag = md5()
        etag.update(self.text.encode("utf-8"))
        return '"%s"' % etag.hexdigest()

    @property
    def name(self):
        """Item name.

        Name is mainly used to give an URL to the item.

        """
        return self._name

    @property
    def text(self):
        """Item serialized text."""
        return self.component.serialize()


class Header(Item):
    """Internal header class."""


class Timezone(Item):
    """Internal timezone class."""
    tag = "VTIMEZONE"


class Component(Item):
    """Internal main component of a collection."""


class Event(Component):
    """Internal event class."""
    tag = "VEVENT"
    mimetype = "text/calendar"


class Todo(Component):
    """Internal todo class."""
    tag = "VTODO"  # pylint: disable=W0511
    mimetype = "text/calendar"


class Journal(Component):
    """Internal journal class."""
    tag = "VJOURNAL"
    mimetype = "text/calendar"


class Card(Component):
    """Internal card class."""
    tag = "VCARD"
    mimetype = "text/vcard"


class Collection:
    """Collection stored in several files per calendar."""
    def __init__(self, path, principal=False):
        """Initialize the collection.

        ``path`` must be the normalized relative path of the collection, using
        the slash as the folder delimiter, with no leading nor trailing slash.

        """
        self.encoding = "utf-8"
        # path should already be sanitized
        self.path = sanitize_path(path).strip("/")
        split_path = self.path.split("/")
        if principal and split_path and self.is_node(self.path):
            # Already existing principal collection
            self.owner = split_path[0]
        elif len(split_path) > 1:
            # URL with at least one folder
            self.owner = split_path[0]
        else:
            self.owner = None
        self.is_principal = principal
        self._items = None

    @classmethod
    def from_path(cls, path, depth="1", include_container=True):
        """Return a list of collections and items under the given ``path``.

        If ``depth`` is "0", only the actual object under ``path`` is
        returned.

        If ``depth`` is anything but "0", it is considered as "1" and direct
        children are included in the result. If ``include_container`` is
        ``True`` (the default), the containing object is included in the
        result.

        The ``path`` is relative.

        """
        # path == None means wrong URL
        if path is None:
            return []

        # path should already be sanitized
        sane_path = sanitize_path(path).strip("/")
        attributes = sane_path.split("/")
        if not attributes:
            return []

        # Try to guess if the path leads to a collection or an item
        if cls.is_leaf("/".join(attributes[:-1])):
            attributes.pop()

        result = []
        path = "/".join(attributes)

        principal = len(attributes) <= 1
        if cls.is_node(path):
            if depth == "0":
                result.append(cls(path, principal))
            else:
                if include_container:
                    result.append(cls(path, principal))
                for child in cls.children(path):
                    result.append(child)
        else:
            if depth == "0":
                result.append(cls(path))
            else:
                collection = cls(path, principal)
                if include_container:
                    result.append(collection)
                result.extend(collection.components)
        return result

    @property
    def _filesystem_path(self):
        """Absolute path of the file at local ``path``."""
        return path_to_filesystem(self.path)

    @property
    def _props_path(self):
        """Absolute path of the file storing the collection properties."""
        return self._filesystem_path + ".props"

    def _create_dirs(self):
        """Create folder storing the collection if absent."""
        if not os.path.exists(self._filesystem_path):
            os.makedirs(self._filesystem_path)

    def set_mimetype(self, mimetype):
        self._create_dirs()
        with self.props as props:
            if "tag" not in props:
                if mimetype == "text/vcard":
                    props["tag"] = "VADDRESSBOOK"
                else:
                    props["tag"] = "VCALENDAR"

    @property
    def exists(self):
        """``True`` if the collection exists on the storage, else ``False``."""
        return self.is_node(self.path) or self.is_leaf(self.path)

    @staticmethod
    def _parse(text, item_types, name=None):
        """Find items with type in ``item_types`` in ``text``.

        If ``name`` is given, give this name to new items in ``text``.

        Return a dict of items.

        """
        item_tags = {item_type.tag: item_type for item_type in item_types}
        items = {}
        root = next(vobject.readComponents(text))
        components = (
            root.components() if root.name in ("VADDRESSBOOK", "VCALENDAR")
            else (root,))
        for component in components:
            item_name = None if component.name == "VTIMEZONE" else name
            item_type = item_tags[component.name]
            item = item_type(component.serialize(), item_name)
            if item.name in items:
                text = "\r\n".join((item.text, items[item.name].text))
                items[item.name] = item_type(text, item.name)
            else:
                items[item.name] = item

        return items

    def save(self, text):
        self._create_dirs()
        item_types = (Timezone, Event, Todo, Journal, Card)
        for name, component in self._parse(text, item_types).items():
            if not is_safe_filesystem_path_component(name):
                log.LOGGER.debug(
                    "Can't tranlate name safely to filesystem, "
                    "skipping component: %s", name)
                continue
            filename = os.path.join(self._filesystem_path, name)
            with open(filename, "w", encoding=STORAGE_ENCODING) as fd:
                fd.write(component.text)

    @property
    def headers(self):
        return (
            Header("PRODID:-//Radicale//NONSGML Radicale Server//EN"),
            Header("VERSION:%s" % self.version))

    def delete(self):
        shutil.rmtree(self._filesystem_path)
        os.remove(self._props_path)

    def remove(self, name):
        if not is_safe_filesystem_path_component(name):
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
        components = (Timezone, Event, Todo, Journal, Card)
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
                with open(path, encoding=STORAGE_ENCODING) as fd:
                    items.update(self._parse(fd.read(), components))
            except (OSError, IOError) as e:
                log.LOGGER.warning(
                    "Error while reading item %r: %r" % (path, e))

        return serialize(
            self.tag, self.headers, sorted(items.values(), key=lambda x: x.name))

    @classmethod
    def children(cls, path):
        filesystem_path = path_to_filesystem(path)
        _, directories, files = next(os.walk(filesystem_path))
        for path in directories + files:
            # Check that the local path can be translated into an internal path
            if not path or posixpath.split(path)[0] or path in (".", ".."):
                log.LOGGER.debug("Skipping unsupported filename: %s", path)
                continue
            relative_path = posixpath.join(path, path)
            if cls.is_node(relative_path) or cls.is_leaf(relative_path):
                yield cls(relative_path)

    @classmethod
    def is_node(cls, path):
        filesystem_path = path_to_filesystem(path)
        return (
            os.path.isdir(filesystem_path) and
            not os.path.exists(filesystem_path + ".props"))

    @classmethod
    def is_leaf(cls, path):
        filesystem_path = path_to_filesystem(path)
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
        if old_properties != properties:
            with open(self._props_path, "w") as prop_file:
                json.dump(properties, prop_file)

    def append(self, name, text):
        """Append items from ``text`` to collection.

        If ``name`` is given, give this name to new items in ``text``.

        """
        new_items = self._parse(
            text, (Timezone, Event, Todo, Journal, Card), name)
        for new_item in new_items.values():
            if new_item.name not in self.items:
                self.items[new_item.name] = new_item
        self.write()

    def replace(self, name, text):
        """Replace content by ``text`` in collection objet called ``name``."""
        self.remove(name)
        self.append(name, text)

    def write(self):
        """Write collection with given parameters."""
        text = serialize(self.tag, self.headers, self.items.values())
        self.save(text)

    @property
    def tag(self):
        """Type of the collection."""
        with self.props as props:
            if "tag" not in props:
                try:
                    tag = open(self.path).readlines()[0][6:].rstrip()
                except IOError:
                    if self.path.endswith((".vcf", "/carddav")):
                        props["tag"] = "VADDRESSBOOK"
                    else:
                        props["tag"] = "VCALENDAR"
                else:
                    if tag in ("VADDRESSBOOK", "VCARD"):
                        props["tag"] = "VADDRESSBOOK"
                    else:
                        props["tag"] = "VCALENDAR"
            return props["tag"]

    @property
    def mimetype(self):
        """Mimetype of the collection."""
        if self.tag == "VADDRESSBOOK":
            return "text/vcard"
        elif self.tag == "VCALENDAR":
            return "text/calendar"

    @property
    def resource_type(self):
        """Resource type of the collection."""
        if self.tag == "VADDRESSBOOK":
            return "addressbook"
        elif self.tag == "VCALENDAR":
            return "calendar"

    @property
    def etag(self):
        """Etag from collection."""
        etag = md5()
        etag.update(self.text.encode("utf-8"))
        return '"%s"' % etag.hexdigest()

    @property
    def name(self):
        """Collection name."""
        with self.props as props:
            return props.get("D:displayname", self.path.split(os.path.sep)[-1])

    @property
    def color(self):
        """Collection color."""
        with self.props as props:
            if "ICAL:calendar-color" not in props:
                props["ICAL:calendar-color"] = "#%x" % randint(0, 255 ** 3 - 1)
            return props["ICAL:calendar-color"]

    @property
    def items(self):
        """Get list of all items in collection."""
        if self._items is None:
            self._items = self._parse(
                self.text, (Event, Todo, Journal, Card, Timezone))
        return self._items

    @property
    def timezones(self):
        """Get list of all timezones in collection."""
        return [
            item for item in self.items.values() if item.tag == Timezone.tag]

    @property
    def components(self):
        """Get list of all components in collection."""
        tags = [item_type.tag for item_type in (Event, Todo, Journal, Card)]
        return [item for item in self.items.values() if item.tag in tags]

    @property
    def owner_url(self):
        """Get the collection URL according to its owner."""
        return "/%s/" % self.owner if self.owner else None

    @property
    def url(self):
        """Get the standard collection URL."""
        return "%s/" % self.path

    @property
    def version(self):
        """Get the version of the collection type."""
        return "3.0" if self.tag == "VADDRESSBOOK" else "2.0"
