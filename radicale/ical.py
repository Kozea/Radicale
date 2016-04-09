# This file is part of Radicale Server - Calendar Server
# Copyright © 2008 Nicolas Kandel
# Copyright © 2008 Pascal Halter
# Copyright © 2008-2016 Guillaume Ayoub
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
Radicale collection classes.

Define the main classes of a collection as seen from the server.

"""

import hashlib
import os
import posixpath
import re
from contextlib import contextmanager
from random import randint
from uuid import uuid4

import vobject


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


def clean_name(name):
    """Clean an item name by removing slashes and leading/ending brackets."""
    # Remove leading and ending brackets that may have been put by Outlook
    name = name.strip("{}")
    # Remove slashes, mostly unwanted when saving on filesystems
    name = name.replace("/", "_")
    return name


def unfold(text):
    """Unfold multi-lines attributes.

    Read rfc5545-3.1 for info.

    """
    return re.sub('\r\n( |\t)', '', text).splitlines()


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
            self._name = clean_name(self._name)
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
        md5 = hashlib.md5()
        md5.update(self.text.encode("utf-8"))
        return '"%s"' % md5.hexdigest()

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


class Collection(object):
    """Internal collection item.

    This class must be overridden and replaced by a storage backend.

    """
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

    def save(self, text):
        """Save the text into the collection."""
        raise NotImplementedError

    def delete(self):
        """Delete the collection."""
        raise NotImplementedError

    @property
    def text(self):
        """Collection as plain text."""
        raise NotImplementedError

    @classmethod
    def children(cls, path):
        """Yield the children of the collection at local ``path``."""
        raise NotImplementedError

    @classmethod
    def is_node(cls, path):
        """Return ``True`` if relative ``path`` is a node.

        A node is a WebDAV collection whose members are other collections.

        """
        raise NotImplementedError

    @classmethod
    def is_leaf(cls, path):
        """Return ``True`` if relative ``path`` is a leaf.

        A leaf is a WebDAV collection whose members are not collections.

        """
        raise NotImplementedError

    @property
    def last_modified(self):
        """Get the last time the collection has been modified.

        The date is formatted according to rfc1123-5.2.14.

        """
        raise NotImplementedError

    @property
    @contextmanager
    def props(self):
        """Get the collection properties."""
        raise NotImplementedError

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

    def remove(self, name):
        """Remove object named ``name`` from collection."""
        if name in self.items:
            del self.items[name]
        self.write()

    def replace(self, name, text):
        """Replace content by ``text`` in collection objet called ``name``."""
        self.remove(name)
        self.append(name, text)

    def write(self):
        """Write collection with given parameters."""
        text = serialize(self.tag, self.headers, self.items.values())
        self.save(text)

    def set_mimetype(self, mimetype):
        """Set the mimetype of the collection."""
        with self.props as props:
            if "tag" not in props:
                if mimetype == "text/vcard":
                    props["tag"] = "VADDRESSBOOK"
                else:
                    props["tag"] = "VCALENDAR"

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
        md5 = hashlib.md5()
        md5.update(self.text.encode("utf-8"))
        return '"%s"' % md5.hexdigest()

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
    def headers(self):
        """Find headers items in collection."""
        header_lines = []

        lines = unfold(self.text)[1:]
        for line in lines:
            if line.startswith(("BEGIN:", "END:")):
                break
            header_lines.append(Header(line))

        return header_lines or (
            Header("PRODID:-//Radicale//NONSGML Radicale Server//EN"),
            Header("VERSION:%s" % self.version))

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
