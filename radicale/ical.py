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


def serialize(headers=(), timezones=(), events=(), todos=()):
    items = ["BEGIN:VCALENDAR"]
    for part in (headers, timezones, todos, events):
        if part:
            items.append("\n".join(item.text for item in part))
    items.append("END:VCALENDAR")
    return "\n".join(items)


class Header(object):
    """Internal header class."""
    def __init__(self, text):
        """Initialize header from ``text``."""
        self.text = text


class Event(object):
    """Internal event class."""
    tag = "VEVENT"

    def __init__(self, text):
        """Initialize event from ``text``."""
        self.text = text

    @property
    def etag(self):
        """Etag from event."""
        return '"%s"' % hash(self.text)


class Todo(object):
    """Internal todo class."""
    # This is not a TODO!
    # pylint: disable-msg=W0511
    tag = "VTODO"
    # pylint: enable-msg=W0511

    def __init__(self, text):
        """Initialize todo from ``text``."""
        self.text = text

    @property
    def etag(self):
        """Etag from todo."""
        return '"%s"' % hash(self.text)


class Timezone(object):
    """Internal timezone class."""
    tag = "VTIMEZONE"

    def __init__(self, text):
        """Initialize timezone from ``text``."""
        lines = text.splitlines()
        for line in lines:
            if line.startswith("TZID:"):
                self.name = line.replace("TZID:", "")
                break

        self.text = text


class Calendar(object):
    """Internal calendar class."""
    def __init__(self, path):
        """Initialize the calendar with ``cal`` and ``user`` parameters."""
        # TODO: Use properties from the calendar configuration
        self.encoding = "utf-8"
        self.owner = path.split("/")[0]
        self.path = os.path.join(FOLDER, path.replace("/", os.path.sep))
        self.ctag = self.etag

    @staticmethod
    def _parse(text, obj):
        """Find ``obj.tag`` items in ``text`` text.

        Return a list of items of type ``obj``.

        """
        items = []

        lines = text.splitlines()
        in_item = False
        item_lines = []

        for line in lines:
            if line.startswith("BEGIN:%s" % obj.tag):
                in_item = True
                item_lines = []

            if in_item:
                item_lines.append(line)
                if line.startswith("END:%s" % obj.tag):
                    items.append(obj("\n".join(item_lines)))

        return items

    def append(self, text):
        """Append ``text`` to calendar."""
        self.ctag = self.etag

        timezones = self.timezones
        events = self.events
        todos = self.todos

        for new_timezone in self._parse(text, Timezone):
            if new_timezone.name not in [timezone.name
                                         for timezone in timezones]:
                timezones.append(new_timezone)

        for new_event in self._parse(text, Event):
            if new_event.etag not in [event.etag for event in events]:
                events.append(new_event)

        for new_todo in self._parse(text, Todo):
            if new_todo.etag not in [todo.etag for todo in todos]:
                todos.append(new_todo)

        self.write(timezones=timezones, events=events, todos=todos)

    def remove(self, etag):
        """Remove object named ``etag`` from the calendar."""
        self.ctag = self.etag
        todos = [todo for todo in self.todos if todo.etag != etag]
        events = [event for event in self.events if event.etag != etag]

        self.write(todos=todos, events=events)

    def replace(self, etag, text):
        """Replace objet named ``etag`` by ``text`` in the calendar."""
        self.ctag = self.etag
        self.remove(etag)
        self.append(text)

    def write(self, headers=None, timezones=None, events=None, todos=None):
        """Write calendar with given parameters."""
        headers = headers or self.headers or (
            Header("PRODID:-//Radicale//NONSGML Radicale Server//EN"),
            Header("VERSION:2.0"))
        timezones = timezones or self.timezones
        events = events or self.events
        todos = todos or self.todos

        # Create folder if absent
        if not os.path.exists(os.path.dirname(self.path)):
            os.makedirs(os.path.dirname(self.path))
        
        text = serialize(headers, timezones, events, todos)
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
    def events(self):
        """Get list of ``Event`` items in calendar."""
        return self._parse(self.text, Event)

    @property
    def todos(self):
        """Get list of ``Todo`` items in calendar."""
        return self._parse(self.text, Todo)

    @property
    def timezones(self):
        """Get list of ``Timezome`` items in calendar."""
        return self._parse(self.text, Timezone)
