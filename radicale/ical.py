# -*- coding: utf-8 -*-
#
# This file is part of Radicale Server - Calendar Server
# Copyright © 2008 Nicolas Kandel
# Copyright © 2008 Pascal Halter
# Copyright © 2008-2015 Guillaume Ayoub
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
import re
from uuid import uuid4
from random import randint
from contextlib import contextmanager
import log


def serialize(tag=None, headers=(), items=()):
    """Return a text corresponding to given collection ``tag``.

    The text may have the given ``headers`` and ``items`` added around the
    items if needed (ie. for calendars).

    If no ``tag'' is given, items will be serialized without surrounding
    collection delimiters.

    """
    items = sorted(items, key=lambda x: x.name)

    # Helper to sort item texts while preserving the position of BEGIN: and END: lines
    def sortitem(text):
        ret = []
        buf = []
        for line in text.splitlines():
            if line.startswith(("BEGIN:", "END:")):
                ret.extend(sorted(buf))
                buf = []
                ret.append(line)
            else:
                buf.append(line)
        ret.extend(sorted(buf))
        return "\n".join(ret)

    if tag == "VADDRESSBOOK" or tag is None:
        lines = []
        for item in items:
            lines.append(sortitem(item.text))
    else:
        lines = ["BEGIN:%s" % tag]
        for part in (headers, items):
            if part:
                for item in part:
                    lines.append(sortitem(item.text))
        lines.append("END:%s\n" % tag)
    return "\n".join(lines)


def unfold(text):
    """Unfold multi-lines attributes.

    Read rfc5545-3.1 for info.

    """
    return re.sub('\r\n( |\t)', '', text).splitlines()


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

    def save(self, text, message=None):
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
        multiitems = {}

        lines = unfold(text)
        in_item = False

        for line in lines:
            if line.startswith("BEGIN:") and not in_item:
                item_tag = line.replace("BEGIN:", "").strip()
                if item_tag in item_tags:
                    in_item = True
                    item_lines = []

            if in_item:
                # Thow away PRODID to minimize diff between modifications
                if not line.startswith("PRODID:"):
                    item_lines.append(line)
                if line.startswith("END:%s" % item_tag):
                    in_item = False
                    item_type = item_tags[item_tag]
                    item_text = "\n".join(item_lines)
                    item_name = None if item_tag == "VTIMEZONE" else name
                    item = item_type(item_text, item_name)
                    if item.name in items:
                        # Collect items with colliding UIDs for later merging
                        if item.name not in multiitems:
                            multiitems[item.name] = [items[item.name]]
                        multiitems[item.name].append(item)
                    else:
                        items[item.name] = item

        # Join UID collisions into single items, use serialize() to ensure correct sort order
        for mname, mitems in multiitems.iteritems():
            text = serialize(items=mitems)
            jointitem = items[mname].__class__(text, mname)
            items[mname] = jointitem

        return items

    def append(self, name, text, do_write=True):
        """Append items from ``text`` to collection.

        If ``name`` is given, give this name to new items in ``text``.

        """
        new_items = self._parse(
            text, (Timezone, Event, Todo, Journal, Card), name)
        for new_item in new_items.values():
            if new_item.name not in self.items:
                self.items[new_item] = new_item
        if do_write:
            self.write(message="Add %s" % name)

    def remove(self, name, do_write=True):
        """Remove object named ``name`` from collection."""
        if name in self.items:
            del self.items[name]
        if do_write:
            self.write(message="Remove %s" % name)

    def replace(self, name, text):
        """Replace content by ``text`` in collection object called ``name``."""
        self.remove(name, do_write=False)
        self.append(name, text, do_write=False)

        self.write(message="Modify %s" % name)

    def write(self, message=None):
        """Write collection with given parameters."""
        text = serialize(self.tag, self.headers, self.items.values())
        log.LOGGER.info(message)
        self.save(text, message=message)

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
