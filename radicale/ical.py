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
Radicale collection classes.

Define the main classes of a collection as seen from the server.

"""

import os
import posixpath
import hashlib
from uuid import uuid4
from random import randint
from contextlib import contextmanager


def serialize(tag, headers=(), items=()):
    """Return a text corresponding to given collection ``tag``.

    The text may have the given ``headers`` and ``items`` added around the
    items if needed (ie. for calendars).

    """
    if tag == "VADDRESSBOOK":
        lines = [item.text for item in items]
    else:
        lines = ["BEGIN:%s" % tag]
        for part in (headers, items):
            if part:
                lines.append("\n".join(item.text for item in part))
        lines.append("END:%s\n" % tag)
    return "\n".join(lines)


def unfold(text):
    """Unfold multi-lines attributes.

    Read rfc5545-3.1 for info.

    """
    lines = []
    for line in text.splitlines():
        if lines and (line.startswith(" ") or line.startswith("\t")):
            lines[-1] += line[1:]
        else:
            lines.append(line)
    return lines


class Item(object):
    """Internal iCal item."""
    def __init__(self, text, name=None):
        """Initialize object from ``text`` and different ``kwargs``."""
        self.text = text
        self._name = name

        # We must synchronize the name in the text and in the object.
        # An item must have a name, determined in order by:
        #
        # - the ``name`` parameter
        # - the ``X-RADICALE-NAME`` iCal property (for Events, Todos, Journals)
        # - the ``UID`` iCal property (for Events, Todos, Journals)
        # - the ``TZID`` iCal property (for Timezones)
        if not self._name:
            for line in unfold(self.text):
                if line.startswith("X-RADICALE-NAME:"):
                    self._name = line.replace("X-RADICALE-NAME:", "").strip()
                    break
                elif line.startswith("TZID:"):
                    self._name = line.replace("TZID:", "").strip()
                    break
                elif line.startswith("UID:"):
                    self._name = line.replace("UID:", "").strip()
                    # Do not break, a ``X-RADICALE-NAME`` can appear next

        if self._name:
            # Remove brackets that may have been put by Outlook
            self._name = self._name.strip("{}")
            if "\nX-RADICALE-NAME:" in text:
                for line in unfold(self.text):
                    if line.startswith("X-RADICALE-NAME:"):
                        self.text = self.text.replace(
                            line, "X-RADICALE-NAME:%s" % self._name)
            else:
                self.text = self.text.replace(
                    "\nEND:", "\nX-RADICALE-NAME:%s\nEND:" % self._name)
        else:
            # workaround to get unicode on both python2 and 3
            self._name = uuid4().hex.encode("ascii").decode("ascii")
            self.text = self.text.replace(
                "\nEND:", "\nX-RADICALE-NAME:%s\nEND:" % self._name)

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
        split_path = path.split("/")
        self.path = path if path != "." else ""
        if principal and split_path and self.is_node(self.path):
            # Already existing principal collection
            self.owner = split_path[0]
        elif len(split_path) > 1:
            # URL with at least one folder
            self.owner = split_path[0]
        else:
            self.owner = None
        self.is_principal = principal

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

        # First do normpath and then strip, to prevent access to FOLDER/../
        sane_path = posixpath.normpath(path.replace(os.sep, "/")).strip("/")
        attributes = sane_path.split("/")
        if not attributes:
            return []

        # Try to guess if the path leads to a collection or an item
        if (cls.is_leaf("/".join(attributes[:-1])) or not
                path.endswith(("/", "/caldav", "/carddav"))):
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

        Return a list of items.

        """
        item_tags = {}
        for item_type in item_types:
            item_tags[item_type.tag] = item_type

        items = {}

        lines = unfold(text)
        in_item = False

        for line in lines:
            if line.startswith("BEGIN:") and not in_item:
                item_tag = line.replace("BEGIN:", "").strip()
                if item_tag in item_tags:
                    in_item = True
                    item_lines = []

            if in_item:
                item_lines.append(line)
                if line.startswith("END:%s" % item_tag):
                    in_item = False
                    item_type = item_tags[item_tag]
                    item_text = "\n".join(item_lines)
                    item_name = None if item_tag == "VTIMEZONE" else name
                    item = item_type(item_text, item_name)
                    if item.name in items:
                        text = "\n".join((item.text, items[item.name].text))
                        items[item.name] = item_type(text, item.name)
                    else:
                        items[item.name] = item

        return list(items.values())

    def get_item(self, name):
        """Get collection item called ``name``."""
        for item in self.items:
            if item.name == name:
                return item

    def append(self, name, text):
        """Append items from ``text`` to collection.

        If ``name`` is given, give this name to new items in ``text``.

        """
        items = self.items

        for new_item in self._parse(
                text, (Timezone, Event, Todo, Journal, Card), name):
            if new_item.name not in (item.name for item in items):
                items.append(new_item)

        self.write(items=items)

    def remove(self, name):
        """Remove object named ``name`` from collection."""
        components = [
            component for component in self.components
            if component.name != name]

        items = self.timezones + components
        self.write(items=items)

    def replace(self, name, text):
        """Replace content by ``text`` in collection objet called ``name``."""
        self.remove(name)
        self.append(name, text)

    def write(self, headers=None, items=None):
        """Write collection with given parameters."""
        headers = headers or self.headers or (
            Header("PRODID:-//Radicale//NONSGML Radicale Server//EN"),
            Header("VERSION:%s" % self.version))
        items = items if items is not None else self.items

        text = serialize(self.tag, headers, items)
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
            if "A:calendar-color" not in props:
                props["A:calendar-color"] = "#%x" % randint(0, 255 ** 3 - 1)
            return props["A:calendar-color"]

    @property
    def headers(self):
        """Find headers items in collection."""
        header_lines = []

        lines = unfold(self.text)
        for header in ("PRODID", "VERSION"):
            for line in lines:
                if line.startswith("%s:" % header):
                    header_lines.append(Header(line))
                    break

        return header_lines

    @property
    def items(self):
        """Get list of all items in collection."""
        return self._parse(self.text, (Event, Todo, Journal, Card, Timezone))

    @property
    def components(self):
        """Get list of all components in collection."""
        return self._parse(self.text, (Event, Todo, Journal, Card))

    @property
    def events(self):
        """Get list of ``Event`` items in calendar."""
        return self._parse(self.text, (Event,))

    @property
    def todos(self):
        """Get list of ``Todo`` items in calendar."""
        return self._parse(self.text, (Todo,))

    @property
    def journals(self):
        """Get list of ``Journal`` items in calendar."""
        return self._parse(self.text, (Journal,))

    @property
    def timezones(self):
        """Get list of ``Timezone`` items in calendar."""
        return self._parse(self.text, (Timezone,))

    @property
    def cards(self):
        """Get list of ``Card`` items in address book."""
        return self._parse(self.text, (Card,))

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
