# -*- coding: utf-8 -*-
#
# This file is part of Radicale Server - Calendar Server
# Copyright © 2012-2013 Guillaume Ayoub
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
Google AppEngine (GAE) storage backend (NDB datastore).

for details, see:
https://developers.google.com/appengine/
https://developers.google.com/appengine/docs/python/ndb/
"""

# python
import logging
import os
import hashlib
from contextlib import contextmanager

# GAE
from google.appengine.ext import ndb  # @UnresolvedImport

# project
from .. import ical


class ItemContainerAppengine(ndb.Model):
    '''
    Container for Item and some metadata
    
    The key name (self.key.string_id()) MUST be: path_of_collection/name_of_item
    
    name_of_item shall not contain a slash
    '''
    
    # some optional application-specific metadata
    metadata = ndb.JsonProperty()
   
    def get(self):
        unused_collection_path, item_name = self.key.string_id().rsplit('/', 1)
        return ical.Item(self.item_text.decode('utf-8'), item_name)
    
    def set(self, item):
        if not self.item_text == item.text:
            unused_collection_path, item_name = self.key.string_id().rsplit('/', 1)
            if not (item_name == item._name):
                raise Exception('inconsistent key and name')
            self.item_text = item.text.encode('utf-8')
            self.put()  # write modified entity to datastore

    # the actual item (private, use accessors above) 
    item_text = ndb.BlobProperty()

class CollectionContainerAppengine(ndb.Model):
    '''
    Container for the stored portion of a Collection.
    
    This class is private to this module. 
    It is used by appengine.Collection which derives from ical.Collection
    
    The key name (self.key.string_id()) MUST be: path_of_collection (without leading or trailing slash)
    '''

    # children (that are collections themselves)
    children = ndb.KeyProperty(repeated=True) # kind=CollectionContainerAppengine (circular)
    
    # properties
    # (None for nodes)
    props = ndb.JsonProperty()

    # {name:etags} for all items in this collection
    # (None for nodes)
    etags = ndb.JsonProperty()
    
    # is that really used?
    last_modified = ndb.DateTimeProperty(auto_now=True)  # Set property to current date/time when entity is created and whenever it is updated.
    

class Collection(ical.Collection):
    """
    Collection stored in datastore object
    """
    
    def create(self, props={}): # this is used to explicitly create the collection (think: "mkdir")
        assert( self._key )
        
        CollectionContainerAppengine(key=self._key, props=props).put()
        
    @property
    def _key(self):
        if self.path:
            return ndb.Key('CollectionContainerAppengine', self.path)
        else:
            return None

    @property
    def _entity(self):
        if self._key: 
            return self._key.get()
        else:
            return None

    def _get_item_container_key(self, name):
        assert( self._key )
        return ndb.Key('ItemContainerAppengine', os.path.join(self._key.string_id(), name))
    
    def get_item(self, name): # get an item
        container = self._get_item_container_key(name).get()
        if not container:
            item = None
        else:
            item = container.get()
        return item
    
    @property
    def headers(self): # from multifilesystem, this does not seem to be as in 
        # filesystem where all items where parsed?
        return (
            ical.Header("PRODID:-//Radicale//NONSGML Radicale Server//EN"),
            ical.Header("VERSION:%s" % self.version))

    def delete(self): # delete the collection
        assert( self._key )
        
        with self.etags as etags:
            etags_copy = etags
        self._key.delete() # delete the collection
        
        # then, remove all the items (normally nobody should be able to add new ones at this point)
        for name in etags_copy:
            self.remove(name) 
        

    def remove(self, name): # remove an existing item
        with self.etags as etags:
            key = self._get_item_container_key(name)
            if key.get(): # if it exists...
                del etags[key.string_id()]
                key.delete()

    def replace(self, name, text):
        with self.etags as etags:  
            item = ical.Item(text=text, name=name)
            # get existing item container and set item 
            container = self._get_item_container_key(item.name).get()
            container.set(item)
            etags[item.name] = item.etag

    def append(self, name, text):
        with self.etags as etags:  
            item = ical.Item(text=text, name=name)
            # create new item container and set item
            container = ItemContainerAppengine(key=self._get_item_container_key(item.name))
            container.set(item)
            etags[item.name] = item.etag    

    @classmethod
    def children(cls, path):
        collection_container = cls(path)._entity
        if not collection_container:
            raise StopIteration
        else:
            for child_key in collection_container.children:
                yield cls(child_key.string_id())

    @property
    def exists(self):
        return self._entity is not None

    @classmethod
    def is_node(cls, path):
        entity = cls(path)._entity
        return entity and entity.children

    @classmethod
    def is_leaf(cls, path):
        entity = cls(path)._entity
        return entity and (not entity.children)

    @property
    def last_modified(self):
        return self._entity.last_modified.strftime("%a, %d %b %Y %H:%M:%S +0000")

    @property
    @contextmanager
    def props(self):
        if not self._entity:
            yield {}
        else:
            # On enter
            properties = self._entity.props
            if not properties: properties = {}
            old_properties = properties.copy()
            yield properties
            
            # On exit
            if old_properties != properties:
                self._entity.props = properties
                self._entity.put()

    @property
    @contextmanager
    def etags(self): # name->etag map for every item in the collection
        if not self._entity:
            yield {}
        else:
            # On enter
            etags = self._entity.etags
            if not etags: etags = {}
            old_etags = etags.copy()
            yield etags
             
            # On exit
            if old_etags != etags:
                self._entity.etags = etags
                self._entity.put()

    @property
    def etag(self): # this is etag for the entire collection
        with self.etags as etags:
            md5 = hashlib.md5()
            md5.update( ''.join(etags.values()) )
            return '"%s"' % md5.hexdigest()

    
    #
    #
    # we really hate to define the methods below because they act on the global collection and will not scale
    #
    #

    def save(self, text): 
        # noscale
        # mutlifilesystem seems to define only the lower level: write
        raise NotImplementedError
    
    def write(self, headers=None, items=None):
        # nocscale
        raise NotImplementedError

    @property
    def text(self):
        logging.critical('#### NOSCALE: Collection.text()')
        
        assert( self._entity )
        
        out = []
        
        with self.etags as etags:
            for name in etags:
                out.append( self.get_item(name).text )
                
        return '\n'.join( out )

