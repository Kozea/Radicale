# -*- coding: utf-8 -*-
#
# This file is part of Radicale Server - Calendar Server
# Copyright © 2008-2010 Guillaume Ayoub
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

import os
import codecs

from radicale import config


FOLDER = os.path.expanduser(config.get("storage", "folder"))
    

# This function overrides the builtin ``open`` function for this module
# pylint: disable-msg=W0622
def open(path, mode="r"):
    """Open file at ``path`` with ``mode``, automagically managing encoding."""
    return codecs.open(path, mode, config.get("encoding", "stock"))
# pylint: enable-msg=W0622


def serialize(headers=(), items=()):
    """Return an iCal text corresponding to given ``headers`` and ``items``."""
    lines = ["BEGIN:VCALENDAR"]
    for part in (headers, items):
        if part:
            lines.append("\n".join(item.text for item in part))
    lines.append("END:VCALENDAR")
    return "\n".join(lines)


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
        # - the ``X-RADICALE-NAME`` iCal property (for Events and Todos)
        # - the ``UID`` iCal property (for Events and Todos)
        # - the ``TZID`` iCal property (for Timezones)
        if not self._name:
            for line in self.text.splitlines():
                if line.startswith("X-RADICALE-NAME:"):
                    self._name = line.replace("X-RADICALE-NAME:", "").strip()
                    break
                elif line.startswith("TZID:"):
                    self._name = line.replace("TZID:", "").strip()
                    break
                elif line.startswith("UID:"):
                    self._name = line.replace("UID:", "").strip()
                    # Do not break, a ``X-RADICALE-NAME`` can appear next

        if "\nX-RADICALE-NAME:" in text:
            for line in self.text.splitlines():
                if line.startswith("X-RADICALE-NAME:"):
                    self.text = self.text.replace(
                        line, "X-RADICALE-NAME:%s" % self._name)
        else:
            self.text = self.text.replace(
                "\nUID:", "\nX-RADICALE-NAME:%s\nUID:" % self._name)

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


class Event(Item):
    """Internal event class."""
    tag = "VEVENT"


class Todo(Item):
    """Internal todo class."""
    # This is not a TODO!
    # pylint: disable-msg=W0511
    tag = "VTODO"
    # pylint: enable-msg=W0511


class Timezone(Item):
    """Internal timezone class."""
    tag = "VTIMEZONE"


class Calendar(object):
    """Internal calendar class."""
    def __init__(self, path):
        """Initialize the calendar with ``cal`` and ``user`` parameters."""
        # TODO: Use properties from the calendar configuration
        self.encoding = "utf-8"
        self.owner = path.split("/")[0]
        self.path = os.path.join(FOLDER, path.replace("/", os.path.sep))

    @staticmethod
    def _parse(text, item_types, name=None):
        """Find items with type in ``item_types`` in ``text`` text.

        If ``name`` is given, give this name to new items in ``text``.

        Return a list of items.

        """
        item_tags = {}
        for item_type in item_types:
            item_tags[item_type.tag] = item_type

        items = []

        lines = text.splitlines()
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
                    items.append(item_type(item_text, item_name))

        return items

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

        for new_item in self._parse(text, (Timezone, Event, Todo), name):
            if new_item.name not in (item.name for item in items):
                items.append(new_item)

        self.write(items=items)

    def remove(self, name):
        """Remove object named ``name`` from calendar."""
        todos = [todo for todo in self.todos if todo.name != name]
        events = [event for event in self.events if event.name != name]

        items = self.timezones + todos + events
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
        items = items or self.items

        # Create folder if absent
        if not os.path.exists(os.path.dirname(self.path)):
            os.makedirs(os.path.dirname(self.path))
        
        text = serialize(headers, items)
        return open(self.path, "w").write(text)

    @property
    def etag(self):
        """Etag from calendar."""
        return '"%s"' % hash(self.text)

    @property
    def text(self):
        """Calendar as plain text."""
        try:
            return open(self.path).read()
        except IOError:
            return ""

    @property
    def headers(self):
        """Find headers items in calendar."""
        header_lines = []

        lines = self.text.splitlines()
        for line in lines:
            if line.startswith("PRODID:"):
                header_lines.append(Header(line))
        for line in lines:
            if line.startswith("VERSION:"):
                header_lines.append(Header(line))

        return header_lines

    @property
    def items(self):
        """Get list of all items in calendar."""
        return self._parse(self.text, (Event, Todo, Timezone))

    @property
    def events(self):
        """Get list of ``Event`` items in calendar."""
        return self._parse(self.text, (Event,))

    @property
    def todos(self):
        """Get list of ``Todo`` items in calendar."""
        return self._parse(self.text, (Todo,))

    @property
    def timezones(self):
        """Get list of ``Timezome`` items in calendar."""
        return self._parse(self.text, (Timezone,))
