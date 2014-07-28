# -*- coding: utf-8 -*-
#
# This file is part of Radicale Server - Calendar Server
# Copyright © 2014 Jorg
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
LMDB storage backend.

The LMDB store uses the LMDB ‘Lightning’ Database. see http://symas.com/mdb/
and lmdb python bindings, see  http://lmdb.readthedocs.org/en/release/

Each Collection is stored as key value store. The collection tracks its content 
and last modification date. 

Items are also stored as key values stores as well as headers and 
properties. The item names are uses as keys in a Collection store.

There are two utilities that convert a filesystem store into a lmdb store 
and vice versa(lmdbimport and lmdbexport). One could run a import and export 
and then compare the original files with the exported versions by means of 
the ics_diff utility. The ics_diff utility can be found in the vobject module. 
see http://vobject.skyhouseconsulting.com/

"""

import os
import time
import re
from contextlib import contextmanager
from .. import config, ical , log

import lmdb

DB_PATH = os.path.expanduser(config.get("storage", "db_path"))
MAP_SIZE = 1048576 * 400
env = lmdb.open(DB_PATH, map_size=MAP_SIZE, max_dbs=10000000)

def key2name(db_key, item_type):
    """Extact the item name from the db_key """
    name = re.sub(r'^.*' + item_type.__name__ + '#', '', db_key)
    name = re.sub(r'\.db$', '', name)
    return name

def type_from_key(db_key):
    """Extact the item type from the db_key """
    return db_key.split("#")[1]

def load_item(db_key, type=None):
    """Loads an item from the database. """
    if not type:
        item_types = {}
        for item_type in [ical.Event, ical.Todo, ical.Journal, ical.Card,
                           ical.Timezone]:
            item_types[item_type.__name__] = item_type
                    
        item_type = item_types[type_from_key(db_key)]
    else:
        item_type = type
        
    db = env.open_db(name=encode_name(db_key), create=False)
    with env.begin(write=False, db=db) as txn:
        text = "\n".join(
                     "%s:%s" % (key.decode("utf-8").split(':',1)[1] , 
                                value.decode("utf-8")) 
                         for key, value in txn.cursor().iternext())
     
    return item_type(text, key2name(db_key, item_type))


def encode_name(name):
    """db names must be encoded."""
    return name.encode("utf-8")


class Collection(ical.Collection):
    """Collection stored in a lmbd key value store."""
    def __init__(self, path, principal=False):
        super(Collection, self).__init__(path, principal)
        with env.begin(write=False) as txn:
            self._is_existing_db = txn.cursor().set_key(encode_name(self.path + ".db"))

    def __del__(self):
        env.sync()

    @property
    def _subdb(self):
        """Return the database for the collection. """
        return env.open_db(name=encode_name(self.path+".db"), create=False)

    def  _touch(self):
        """Update the last modified date to now."""
        with env.begin(write=True, db=self._subdb) as txn:
            txn.put("last_modified", 
                   time.strftime("%a, %d %b %Y %H:%M:%S +0000", time.gmtime()))

    
    def _query(self, item_types):
        """Get collection's items matching ``item_types``."""
        item_objects = []
        if not self._is_existing_db:
            return item_objects
            
        for item_type in item_types:
            with env.begin(write=False, db=self._subdb) as txn:
                key = item_type.__name__
                key = key.encode('utf-8') 
                cursor = txn.cursor() 
                if cursor.set_range(key):
                    for key2, value in cursor.iternext():
                        if not key2.startswith(key):
                            break
                        item_objects.append(load_item(value.decode("utf-8"), type=item_type))
                
        return item_objects
    
    def get_item(self, name):
        """Get collection item called ``name``."""
        if self._is_existing_db:
            with env.begin(write=False, db=self._subdb) as txn:
                cursor = txn.cursor()
                if cursor.set_key(name):
                    return load_item(cursor.value().decode("utf-8"))
            
    def _delete_item(self, item):
        """Remove an item from the database. """                        
        if item:
            item_key = "/items/" + self.path + "#" +  \
                item.__class__.__name__ + '#'  + item.name + ".db"
            db = env.open_db(name=encode_name(item_key), create=False)
            with env.begin(write=True) as txn:
                txn.drop(db)

            with env.begin(write=True, db=self._subdb) as txn:
                key = item.__class__.__name__ + "#" + item_key
                key = key.encode("utf-8")
                cursor = txn.cursor()
                for kn in (key, item.name.encode("utf-8")):
                    if cursor.set_key(kn):
                        txn.delete(kn)
                    else:
                        log.LOGGER.error(
                    "key not found: '%s' in collection '%s'" % (kn, self.path))
        
    def remove(self, name):
        """Remove object named ``name`` from collection."""
        self._delete_item(self.get_item(name))


    def append(self, name, text):
        """Append items from ``text`` to collection.

        If ``name`` is given, give this name to new items in ``text``.

        """
        items = []
        
        for new_item in self._parse(
                text, (ical.Timezone, ical.Event, ical.Todo, ical.Journal,
                       ical.Card), name):
            if not self.get_item(new_item.name):
                items.append(new_item)

        self.write(items=items)        

    def save(self, text):
        """Save the text into the collection."""
        raise NotImplementedError

    def write(self, headers=None, items=None):
        """Persist the items and headers to the database. """
        # create the database ..
        env.open_db(name=encode_name(self.path+".db"), create=True)
        self._is_existing_db = True
        
        self._touch()
        
        headers = headers or self.headers or (
            ical.Header("PRODID:-//Radicale//NONSGML Radicale Server//EN"),
            ical.Header("VERSION:%s" % self.version))

        items = items if items is not None else []
        
        for item in items: 
            item_key = "/items/" + self.path + "#" +  \
                item.__class__.__name__ + '#'  + item.name + ".db"
            item_db = env.open_db(name=encode_name(item_key)) 
            with env.begin(write=True, db=item_db) as txn:
                for (i, line) in enumerate(ical.unfold(item.text), start=100):
                    k, v = line.split(":", 1)
                    key = str(i) + ":" + k
                    txn.put( key.encode("utf-8"), v.encode("utf-8"))
         
            with env.begin(write=True, db=self._subdb) as txn:
                key = item.__class__.__name__ +  "#" + item_key
                txn.put( key.encode("utf-8") , item_key.encode("utf-8"))
                txn.put( item.name.encode("utf-8") , item_key.encode("utf-8") )
                    
        headerdb = env.open_db(name=encode_name(self.path + ".header.db"))
        with env.begin(write=True, db=headerdb) as txn:
            for header in headers:
                for line in ical.unfold(header.text):
                    k, v = line.split(":", 1)
                    txn.put( k.encode("utf-8"), v.encode("utf-8"))
                             

    def delete(self):
        """Delete the collection."""
        for item in self.items:
            self._delete_item(item)    

        for dbname in [".header.db", ".props.db", ".db"]:
            db = env.open_db(name=encode_name(self.path + dbname), create=False)     
            with env.begin(write=True, db=db) as txn:
                txn.drop(db)

    @property
    def text(self):
        return ical.serialize(self.tag, self.headers, self.items)
        
    @property
    def headers(self):
        headers = []
        headerdb = env.open_db(name=encode_name(self.path + ".header.db"))
        with env.begin(write=False, db=headerdb) as txn:
            for key, value in txn.cursor().iternext():
                headers.append(ical.Header("%s:%s" % (key.decode("utf-8") 
                                                    , value.decode("utf-8"))))
        
        return headers


    @property
    def exists(self):
        """``True`` if the collection exists on the storage, else ``False``."""
        if self._has_children(self.path):
            return True
        
        with env.begin(write=False) as txn:
            return txn.cursor().set_key(encode_name(self.path + ".db"))
       
    @classmethod
    def children(cls, path):
        """Yield the children of the collection at local ``path``."""
        with env.begin(write=False) as txn:
            cursor = txn.cursor()
            if cursor.set_range(encode_name(path + '/')):
                for key in cursor.iternext(values=False):
                    key_name = key.decode('utf-8')
                    if not key_name.startswith(path):
                        break
                    if key_name.endswith(".props.db"):
                        yield cls(re.sub(r"\.props\.db$", "", key_name))

    @classmethod
    def _has_children(cls, path):
        """Check if a collection has children. """
        try:
            next(cls.children(path))
        except StopIteration:
            return False
                
        return True        

    @classmethod
    def is_node(cls, path):
        """Return ``True`` if relative ``path`` is a node.

        A node is a WebDAV collection whose members are other collections.
        == directory
        """
        if not path:
            return True
        
        if cls._has_children(path):
            return True
        
        return False
        
        with env.begin(write=False) as txn:
            value =  not txn.cursor().set_key(path + ".db")
            return value


    @classmethod
    def is_leaf(cls, path):
        """Return ``True`` if relative ``path`` is a leaf.

        A leaf is a WebDAV collection whose members are not collections.
        == file - .props
        """
        if not path:
            return False

        if cls._has_children(path):
            return False

        return True
    

    @property
    def last_modified(self):
        """Get the last time the collection has been modified.

        The date is formatted according to rfc1123-5.2.14.

        """
        if self._is_existing_db:
            with env.begin(write=False, db=self._subdb) as txn:
                return txn.get("last_modified")
            
        return time.strftime("%a, %d %b %Y %H:%M:%S +0000", time.gmtime())        
         
    @property
    @contextmanager
    def props(self):
        """Get the collection properties."""
        properties = {}
        with env.begin(write=False) as txn:
            if txn.cursor().set_key(encode_name(self.path + ".props.db")):
                propsdb = env.open_db(name=encode_name(self.path + ".props.db"), create=False)

                with env.begin(write=False, db=propsdb) as txn:
                    for key, value in txn.cursor().iternext(): 
                        properties[key.decode("utf-8")] = value.decode("utf-8")
#             else:
#                 if self._is_existing_db:
#                     print ("no properties found for existing '%s'" % self.path)
#                 else:                        
#                     print ("no properties found for '%s'" % self.path)
        old_properties = properties.copy()
        yield properties
        # On exit
        if old_properties != properties:
            if not self._is_existing_db:
                return
            
            self._touch()
            propsdb = env.open_db(name=encode_name(self.path + ".props.db"), create=True)                    
            with env.begin(write=True, db=propsdb) as txn:
                for key in properties:
                    if properties[key]:
                        txn.put(key.encode("utf-8"), properties[key].encode("utf-8"))
                    else:
                        txn.put(key.encode("utf-8"), None)
            
    @property
    def etag(self):
        return '"%s"' % hash(self.last_modified)


    @property
    def items(self):
        return self._query(
           (ical.Timezone, ical.Event, ical.Todo, ical.Journal, ical.Card, ))

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
