# -*- coding: utf-8 -*-
#
# This file is part of Radicale Server - Calendar Server
# Copyright © 2014 Okami <okami@fuzetsu.info>
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
Django storage backend.

"""

import time
from datetime import datetime
from contextlib import contextmanager

from django.db.models import Q

from .. import ical
from ..models import DBCollection, DBItem, DBHeader, DBLine, DBProperty


class Collection(ical.Collection):
    """Collection stored in a django database."""

    def _query(self, item_types):
        """Get collection's items matching ``item_types``."""
        item_objects = []
        for item_type in item_types:
            items = (
                DBItem.objects
                .filter(collection__path=self.path, tag=item_type.tag)
                .order_by('name'))
            for item in items:
                text = '\n'.join(map(
                    lambda x: '%s:%s' % x,
                    item.lines.values_list('name', 'value')))
                item_objects.append(item_type(text, item.name))
        return item_objects

    @property
    def _modification_time(self):
        """Collection's last modification time."""
        lines = DBLine.objects.filter(item__collection__path=self.path)
        if lines.exists():
            return lines.latest('timestamp').timestamp
        else:
            return datetime.now()

    @property
    def _db_collection(self):
        """Collection's object mapped to the table line."""
        db_collection = DBCollection.objects.filter(path=self.path)
        if db_collection.exists():
            return db_collection.get()

    def write(self, headers=None, items=None):
        headers = headers or self.headers or (
            ical.Header("PRODID:-//Radicale//NONSGML Radicale Server//EN"),
            ical.Header("VERSION:%s" % self.version))
        items = items if items is not None else self.items

        if self._db_collection:
            for item in self._db_collection.items.all():
                item.lines.all().delete()
                item.delete()
            self._db_collection.headers.all().delete()
        else:
            db_collection = DBCollection()
            db_collection.path = self.path
            parent, created = DBCollection.objects.get_or_create(
                path='/'.join(self.path.split('/')[:-1]))
            db_collection.parent = parent
            db_collection.save()

        for header in headers:
            db_header = DBHeader()
            db_header.name, db_header.value = header.text.split(":", 1)
            db_header.collection = self._db_collection
            db_header.save()

        for item in items:
            db_item = DBItem()
            db_item.name = item.name
            db_item.tag = item.tag
            db_item.collection = self._db_collection
            db_item.save()

            for line in ical.unfold(item.text):
                db_line = DBLine()
                db_line.name, db_line.value = line.split(":", 1)
                db_line.item = db_item
                db_line.save()

    def delete(self):
        self._db_collection.delete()

    @property
    def text(self):
        return ical.serialize(self.tag, self.headers, self.items)

    @property
    def etag(self):
        return '"%s"' % hash(self._modification_time)

    @property
    def headers(self):
        headers = (
            DBHeader.objects
            .filter(collection__path=self.path)
            .order_by('name'))
        return [
            ical.Header("%s:%s" % x)
            for x in headers.values_list('name', 'value')]

    @classmethod
    def children(cls, path):
        children = (
            DBCollection.objects
            .filter(Q(parent__path=path or '')))
        collections = [cls(child.path) for child in children]
        return collections

    @classmethod
    def is_node(cls, path):
        if not path:
            return True
        result = (
            DBCollection.objects
            .filter(Q(parent__path=path or ''))
            .count() > 0)
        return result

    @classmethod
    def is_leaf(cls, path):
        if not path:
            return False
        result = (
            DBItem.objects
            .filter(
                Q(collection__path=path or ''))
            .count() > 0)
        return result

    @property
    def last_modified(self):
        return time.strftime(
            "%a, %d %b %Y %H:%M:%S +0000", self._modification_time.timetuple())

    @property
    @contextmanager
    def props(self):
        # On enter
        db_properties = (
            DBProperty.objects
            .filter(collection__path=self.path))
        properties = dict(db_properties.values_list('name', 'value'))
        old_properties = properties.copy()
        yield properties
        # On exit
        if self._db_collection and old_properties != properties:
            db_properties.all().delete()
            for name, value in properties.items():
                prop = DBProperty()
                prop.name = name
                prop.value = value
                prop.collection = self._db_collection
                prop.save()

    @property
    def items(self):
        return self._query(
            (ical.Event, ical.Todo, ical.Journal, ical.Card, ical.Timezone))

    @property
    def components(self):
        return self._query((ical.Event, ical.Todo, ical.Journal, ical.Card))

    @property
    def events(self):
        return self._query((ical.Event,))

    @property
    def todos(self):
        return self._query((ical.Todo,))

    @property
    def journals(self):
        return self._query((ical.Journal,))

    @property
    def timezones(self):
        return self._query((ical.Timezone,))

    @property
    def cards(self):
        return self._query((ical.Card,))

    def save(self):
        """Save the text into the collection.

        This method is not used for databases.

        """
