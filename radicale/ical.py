# -*- coding: utf-8 -*-
#
# This file is part of Radicale Server - Calendar Server
# Copyright © 2008-2011 Guillaume Ayoub
# Copyright © 2008 Nicolas Kandel
# Copyright © 2008 Pascal Halter
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
Radicale calendar classes.

Define the main classes of a calendar as seen from the server.

"""

import codecs
from contextlib import contextmanager
import json
import os
import posixpath
import time
import uuid

from radicale import config


FOLDER = os.path.expanduser(config.get("storage", "folder"))


# This function overrides the builtin ``open`` function for this module
# pylint: disable=W0622
def open(path, mode="r"):
    """Open file at ``path`` with ``mode``, automagically managing encoding."""
    return codecs.open(path, mode, config.get("encoding", "stock"))
# pylint: enable=W0622


def serialize(tag, headers=(), items=()):
    """Return a collection text corresponding to given ``tag``.

    The collection has the given ``headers`` and ``items``.

    """
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
            if "\nX-RADICALE-NAME:" in text:
                for line in unfold(self.text):
                    if line.startswith("X-RADICALE-NAME:"):
                        self.text = self.text.replace(
                            line, "X-RADICALE-NAME:%s" % self._name)
            else:
                self.text = self.text.replace(
                    "\nUID:", "\nX-RADICALE-NAME:%s\nUID:" % self._name)
        else:
            self._name = str(uuid.uuid4())
            self.text = self.text.replace(
                "\nEND:", "\nUID:%s\nEND:" % self._name)

    @property
    def etag(self):
        """Item etag.

        Etag is mainly used to know if an item has changed.

        """
        return '"%s"' % hash(self.text)

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
    """Internal collection item."""
    def __init__(self, path, principal=False):
        """Initialize the collection.

        ``path`` must be the normalized relative path of the collection, using
        the slash as the folder delimiter, with no leading nor trailing slash.

        """
        self.encoding = "utf-8"
        split_path = path.split("/")
        self.path = os.path.join(FOLDER, path.replace("/", os.sep))
        self.props_path = self.path + '.props'
        if principal and split_path and os.path.isdir(self.path):
            # Already existing principal collection
            self.owner = split_path[0]
        elif len(split_path) > 1:
            # URL with at least one folder
            self.owner = split_path[0]
        else:
            self.owner = None
        self.local_path = path if path != '.' else ''
        self.is_principal = principal

    @classmethod
    def from_path(cls, path, depth="infinite", include_container=True):
        """Return a list of collections and items under the given ``path``.

        If ``depth`` is "0", only the actual object under ``path`` is
        returned. Otherwise, also sub-items are appended to the result. If
        ``include_container`` is ``True`` (the default), the containing object
        is included in the result.

        The ``path`` is relative to the storage folder.

        """
        # First do normpath and then strip, to prevent access to FOLDER/../
        sane_path = posixpath.normpath(path.replace(os.sep, "/")).strip("/")
        attributes = sane_path.split("/")
        if not attributes:
            return None
        if not (os.path.isfile(os.path.join(FOLDER, *attributes)) or
                path.endswith("/")):
            attributes.pop()

        result = []

        path = "/".join(attributes)
        abs_path = os.path.join(FOLDER, path.replace("/", os.sep))
        principal = len(attributes) <= 1
        if os.path.isdir(abs_path):
            if depth == "0":
                result.append(cls(path, principal))
            else:
                if include_container:
                    result.append(cls(path, principal))
                try:
                    for filename in next(os.walk(abs_path))[2]:
                        if cls.is_collection(os.path.join(abs_path, filename)):
                            result.append(cls(os.path.join(path, filename)))
                except StopIteration:
                    # Directory does not exist yet
                    pass
        else:
            if depth == "0":
                result.append(cls(path))
            else:
                collection = cls(path, principal)
                if include_container:
                    result.append(collection)
                result.extend(collection.components)
        return result

    def is_collection(self, path):
        """Return ``True`` if there is a collection file under ``path``."""
        beginning_string = 'BEGIN:%s' % self.tag
        with open(path) as stream:
            beginning_string = stream.read(len(beginning_string))

    @property
    def items(self):
        """Get list of all items in collection."""
        return self._parse(self.text, (Card, Event, Todo, Journal, Timezone))

    @property
    def components(self):
        """Get list of all components in collection."""
        return self._parse(self.text, (Card, Event, Todo, Journal))

    @property
    def events(self):
        """Get list of ``Event`` items in collection."""
        return self._parse(self.text, (Event,))

    @property
    def cards(self):
        """Get list of all cards in collection."""
        return self._parse(self.text, (Card,))

    @property
    def todos(self):
        """Get list of ``Todo`` items in collection."""
        return self._parse(self.text, (Todo,))

    @property
    def journals(self):
        """Get list of ``Journal`` items in collection."""
        return self._parse(self.text, (Journal,))

    @property
    def timezones(self):
        """Get list of ``Timezome`` items in collection."""
        return self._parse(self.text, (Timezone,))

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
        """Get calendar item called ``name``."""
        for item in self.items:
            if item.name == name:
                return item

    def append(self, name, text):
        """Append items from ``text`` to calendar.

        If ``name`` is given, give this name to new items in ``text``.

        """
        items = self.items

        for new_item in self._parse(
            text, (Timezone, Event, Todo, Journal), name):
            if new_item.name not in (item.name for item in items):
                items.append(new_item)

        self.write(items=items)

    def delete(self):
        """Delete the calendar."""
        os.remove(self.path)
        os.remove(self.props_path)

    def remove(self, name):
        """Remove object named ``name`` from calendar."""
        components = [
            component for component in self.components
            if component.name != name]

        items = self.timezones + components
        self.write(items=items)

    def replace(self, name, text):
        """Replace content by ``text`` in objet named ``name`` in calendar."""
        self.remove(name)
        self.append(name, text)

    def write(self, headers=None, items=None):
        """Write calendar with given parameters."""
        headers = headers or self.headers or (
            Header("PRODID:-//Radicale//NONSGML Radicale Server//EN"),
            Header("VERSION:2.0"))
        items = items if items is not None else self.items

        self._create_dirs(self.path)

        text = serialize(self.tag, headers, items)
        return open(self.path, "w").write(text)

    @staticmethod
    def _create_dirs(path):
        """Create folder if absent."""
        if not os.path.exists(os.path.dirname(path)):
            os.makedirs(os.path.dirname(path))

    @property
    def tag(self):
        """Type of the collection."""
        with self.props as props:
            if "tag" not in props:
                try:
                    props["tag"] = open(self.path).readlines()[0][6:].rstrip()
                except IOError:
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
        return '"%s"' % hash(self.text)

    @property
    def name(self):
        """Collection name."""
        with self.props as props:
            return props.get('D:displayname',
                self.path.split(os.path.sep)[-1])

    @property
    def text(self):
        """Collection as plain text."""
        try:
            return open(self.path).read()
        except IOError:
            return ""

    @property
    def headers(self):
        """Find headers items in collection."""
        header_lines = []

        lines = unfold(self.text)
        for line in lines:
            if line.startswith("PRODID:"):
                header_lines.append(Header(line))
        for line in lines:
            if line.startswith("VERSION:"):
                header_lines.append(Header(line))

        return header_lines

    @property
    def last_modified(self):
        """Get the last time the collection has been modified.

        The date is formatted according to rfc1123-5.2.14.

        """
        # Create calendar if needed
        if not os.path.exists(self.path):
            self.write()

        modification_time = time.gmtime(os.path.getmtime(self.path))
        return time.strftime("%a, %d %b %Y %H:%M:%S +0000", modification_time)

    @property
    @contextmanager
    def props(self):
        """Get the collection properties."""
        # On enter
        properties = {}
        if os.path.exists(self.props_path):
            with open(self.props_path) as prop_file:
                properties.update(json.load(prop_file))
        yield properties
        # On exit
        self._create_dirs(self.props_path)
        with open(self.props_path, 'w') as prop_file:
            json.dump(properties, prop_file)

    @property
    def owner_url(self):
        """Get the collection URL according to its owner."""
        if self.owner:
            return "/%s/" % self.owner
        else:
            return None

    @property
    def url(self):
        """Get the standard collection URL."""
        return "/%s/" % self.local_path
