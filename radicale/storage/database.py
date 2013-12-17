# -*- coding: utf-8 -*-
#
# This file is part of Radicale Server - Calendar Server
# Copyright © 2013 Guillaume Ayoub
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
SQLAlchemy storage backend.

"""

import time
from datetime import datetime
from contextlib import contextmanager
from sqlalchemy import create_engine, Column, Unicode, Integer, ForeignKey
from sqlalchemy import func
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.ext.declarative import declarative_base

from .. import config, ical


# These are classes, not constants
# pylint: disable=C0103
Base = declarative_base()
Session = sessionmaker()
Session.configure(bind=create_engine(config.get("storage", "database_url")))
# pylint: enable=C0103


class DBCollection(Base):
    """Table of collections."""
    __tablename__ = "collection"

    path = Column(Unicode, primary_key=True)
    parent_path = Column(Unicode, ForeignKey("collection.path"))

    parent = relationship(
        "DBCollection", backref="children", remote_side=[path])


class DBItem(Base):
    """Table of collection's items."""
    __tablename__ = "item"

    name = Column(Unicode, primary_key=True)
    tag = Column(Unicode)
    collection_path = Column(Unicode, ForeignKey("collection.path"))

    collection = relationship("DBCollection", backref="items")


class DBHeader(Base):
    """Table of item's headers."""
    __tablename__ = "header"

    name = Column(Unicode, primary_key=True)
    value = Column(Unicode)
    collection_path = Column(
        Unicode, ForeignKey("collection.path"), primary_key=True)

    collection = relationship("DBCollection", backref="headers")


class DBLine(Base):
    """Table of item's lines."""
    __tablename__ = "line"

    name = Column(Unicode)
    value = Column(Unicode)
    item_name = Column(Unicode, ForeignKey("item.name"))
    timestamp = Column(
        Integer, default=lambda: time.time() * 10 ** 6, primary_key=True)

    item = relationship("DBItem", backref="lines", order_by=timestamp)


class DBProperty(Base):
    """Table of collection's properties."""
    __tablename__ = "property"

    name = Column(Unicode, primary_key=True)
    value = Column(Unicode)
    collection_path = Column(
        Unicode, ForeignKey("collection.path"), primary_key=True)

    collection = relationship(
        "DBCollection", backref="properties", cascade="delete")


class Collection(ical.Collection):
    """Collection stored in a database."""
    def __init__(self, path, principal=False):
        self.session = Session()
        super(Collection, self).__init__(path, principal)

    def __del__(self):
        self.session.commit()

    def _query(self, item_types):
        """Get collection's items matching ``item_types``."""
        item_objects = []
        for item_type in item_types:
            items = (
                self.session.query(DBItem)
                .filter_by(collection_path=self.path, tag=item_type.tag)
                .order_by(DBItem.name).all())
            for item in items:
                text = "\n".join(
                    "%s:%s" % (line.name, line.value) for line in item.lines)
                item_objects.append(item_type(text, item.name))
        return item_objects

    @property
    def _modification_time(self):
        """Collection's last modification time."""
        timestamp = (
            self.session.query(func.max(DBLine.timestamp))
            .join(DBItem).filter_by(collection_path=self.path).first()[0])
        if timestamp:
            return datetime.fromtimestamp(float(timestamp) / 10 ** 6)
        else:
            return datetime.now()

    @property
    def _db_collection(self):
        """Collection's object mapped to the table line."""
        return self.session.query(DBCollection).get(self.path)

    def write(self, headers=None, items=None):
        headers = headers or self.headers or (
            ical.Header("PRODID:-//Radicale//NONSGML Radicale Server//EN"),
            ical.Header("VERSION:%s" % self.version))
        items = items if items is not None else self.items

        if self._db_collection:
            for item in self._db_collection.items:
                for line in item.lines:
                    self.session.delete(line)
                self.session.delete(item)
            for header in self._db_collection.headers:
                self.session.delete(header)
        else:
            db_collection = DBCollection()
            db_collection.path = self.path
            db_collection.parent_path = "/".join(self.path.split("/")[:-1])
            self.session.add(db_collection)

        for header in headers:
            db_header = DBHeader()
            db_header.name, db_header.value = header.text.split(":", 1)
            db_header.collection_path = self.path
            self.session.add(db_header)

        for item in items:
            db_item = DBItem()
            db_item.name = item.name
            db_item.tag = item.tag
            db_item.collection_path = self.path
            self.session.add(db_item)

            for line in ical.unfold(item.text):
                db_line = DBLine()
                db_line.name, db_line.value = line.split(":", 1)
                db_line.item_name = item.name
                self.session.add(db_line)

    def delete(self):
        self.session.delete(self._db_collection)

    @property
    def text(self):
        return ical.serialize(self.tag, self.headers, self.items)

    @property
    def etag(self):
        return '"%s"' % hash(self._modification_time)

    @property
    def headers(self):
        headers = (
            self.session.query(DBHeader)
            .filter_by(collection_path=self.path)
            .order_by(DBHeader.name).all())
        return [
            ical.Header("%s:%s" % (header.name, header.value))
            for header in headers]

    @classmethod
    def children(cls, path):
        session = Session()
        children = (
            session.query(DBCollection)
            .filter_by(parent_path=path or "").all())
        collections = [cls(child.path) for child in children]
        session.close()
        return collections

    @classmethod
    def is_node(cls, path):
        if not path:
            return True
        session = Session()
        result = (
            session.query(DBCollection)
            .filter_by(parent_path=path or "").count() > 0)
        session.close()
        return result

    @classmethod
    def is_leaf(cls, path):
        if not path:
            return False
        session = Session()
        result = (
            session.query(DBItem)
            .filter_by(collection_path=path or "").count() > 0)
        session.close()
        return result

    @property
    def last_modified(self):
        return time.strftime(
            "%a, %d %b %Y %H:%M:%S +0000", self._modification_time.timetuple())

    @property
    @contextmanager
    def props(self):
        # On enter
        properties = {}
        db_properties = (
            self.session.query(DBProperty)
            .filter_by(collection_path=self.path).all())
        for prop in db_properties:
            properties[prop.name] = prop.value
        old_properties = properties.copy()
        yield properties
        # On exit
        if self._db_collection and old_properties != properties:
            for prop in db_properties:
                self.session.delete(prop)
            for name, value in properties.items():
                prop = DBProperty()
                prop.name = name
                prop.value = value
                prop.collection_path = self.path
                self.session.add(prop)

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
