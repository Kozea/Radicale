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
import hashlib
from contextlib import contextmanager
import os.path

# GAE
from google.appengine.ext import ndb  # @UnresolvedImport

# project
from .. import ical # @UnresolvedImport

tag_class = {'VEVENT':ical.Event,
             'VCARD':ical.Card,
             'VTODO':ical.Todo,
             'VJOURNAL':ical.Journal,
             'VTIMEZONE':ical.Timezone}

class ItemContainerAppengine(ndb.Model):
    '''
    Container for Item
    
    This class is private to this module
    
    The key name (self.key.string_id()) MUST be the name the item
    (this way we do not have to maintain the name as a separate property and we can get items from
    their names efficiently)
    
    The entity MUST be a child (in the sense of the AppEngine datastore) of its CollectionContainerAppengine, because:
    1. this will ensure no name collision (eg: two items with same name but in different collections)
    2. when a transaction is involved, all entities (eg the item and its collection) must be in the same entity group 
    '''
  
    def get_item(self):
        #FIXME: is it ok to always encode in utf-8 ?
        item_name = self.key.string_id()
        ItemSubClass = tag_class[ self.tag ] #FIXME: should we default to ical.Item?
        return ItemSubClass(self.item_text.decode('utf-8'), item_name)
    
    def set_item(self, item):
        '''
        important: self.put() must be called explicitly after this 
        '''
        item_name = self.key.string_id()
        if not (item_name == item._name):
            raise Exception('The entity key is not the name')
        self.item_text = item.text.encode('utf-8')

    # the actual item (private, use accessors above) 
    item_text = ndb.BlobProperty() # size limit 1Mb (or 32Mb? not very clear from docs)
    
    @property
    def tag( self ):
        #FIXME: do we really need to unfold the entire text? would not a simple regex do just as well?
        lines = ical.unfold(self.item_text)
        for line in lines:
            if line.startswith("BEGIN:"):
                tag = line.replace("BEGIN:", "").strip()
                return tag

class CollectionContainerAppengine(ndb.Model):
    '''
    Container for a Collection.
    
    This class is private to this module. Use the Collection below only.
    
    The key name (self.key.string_id()) MUST be the name of the collection
    
    The hierarchy of collections MUST be mirrored in the AppEngine datastore
    (this is needed for transactions)
    
    Because we want to avoid queries as much as possible, all subcollections and items are explicitly tracked into lists.
    
    When using this class, we MUST make sure that any modification occur in a transaction 
    or we will end up with inconsistent representations in case of concurrent writes
    '''

    # children (that are collections themselves)
    subcollections = ndb.KeyProperty(repeated=True) # kind=CollectionContainerAppengine (circular)
    
    # { name:etag } for all items in this collection, split by tag
    events = ndb.JsonProperty( default={} )
    cards = ndb.JsonProperty( default={} )
    todos = ndb.JsonProperty( default={} )
    journals = ndb.JsonProperty( default={} )
    timezones = ndb.JsonProperty( default={} )

    def tag_bin(self, tag):
        if tag=='VEVENT':
            return self.events
        elif tag=='VCARD':
            return self.cards
        elif tag=='VTODO':
            return self.todos
        elif tag=='VJOURNAL':
            return self.journals
        elif tag=='VTIMEZONE':
            return self.timezones
        else:
            raise NotImplementedError #FIXME: can this happen?
    
    # collection properties, ex: {"tag": "VADDRESSBOOK"}
    props = ndb.JsonProperty( default={} )
    
    #TODO: is that really used?
    last_modified = ndb.DateTimeProperty(auto_now=True)  # auto_now: set property to current date/time when entity is created and whenever it is updated.

class Collection(ical.Collection):
    """
    Collection stored in datastore object. 
    
    This is the only class you want to use from this module.
    """
    
    @ndb.transactional
    def create(self, props={}): 
        '''
        create the collection, 
        if there are parents they must be created explicitly before 
        (think: "mkdir")
        '''
        assert( self.path ) # make sure the path is not None
        
        key_pairs = self._get_key_pairs()
        
        # create the collection
        container_key = ndb.Key( pairs=key_pairs )
        container = CollectionContainerAppengine(key=container_key, props=props)
        container.put() # note: since we are in a transaction, this will be rolled back if the parent does not exist
        
        container_key_parent = container_key.parent()
        if container_key_parent: # if need be, register the new child with its parent
            container_parent = container_key_parent.get()
            if not container_parent:
                raise Exception('Error creating Collection path=%s. Parent does not exist. Please create it first.'%(self.path))
            container_parent.subcollections.append( container_key )
            container_parent.put()
        
    def _get_key_pairs(self):
        if self.path:
            assert( self.path==self.path.strip('/') ) # no leading or trailing /
            return [ ('CollectionContainerAppengine', name) for name in self.path.split('/') ]
        else:
            return []

    # let's not make the container a property:
    # we need to be very explicit about when when we actually
    # get stuff from the datastore in the context of transactions
    def _get_container(self):
        key_pairs = self._get_key_pairs()
        if key_pairs: 
            return ndb.Key( pairs=key_pairs ).get()
        else:
            return None

    def _get_item_container_key(self, name):
        return ndb.Key( pairs=(self._get_key_pairs() + [ ('ItemContainerAppengine', name) ]) )
    
    def get_item(self, name): # get an item
        container = self._get_item_container_key(name).get()
        if not container:
            return None
        else:
            return container.get_item()
    
    @property
    def headers(self): 
        # from multifilesystem, this does not seem to be as in 
        # filesystem where all items where parsed?
        #FIXME: can somebody validate this?
        return (
            ical.Header("PRODID:-//Radicale//NONSGML Radicale Server//EN"),
            ical.Header("VERSION:%s" % self.version))

    @ndb.transactional
    def delete(self): 
        '''
        delete the collection
        the collection must not have subcollections
        however it can have items ; in that case those will be come inaccessible and should be removed AFTER the collection
        has been removed using delete_items()
        (if we would delete the items before deleting the collection there would be a risk that somebody create new items 
        in between)
        '''
        container = self._get_container()
        assert( container ) # make sure it actually exists
        
        # IMPORTANT
        #
        #FIXME: utilmately (once the code has stabilized) we should try to be the less rirgorous we can
        # and just do nothing when requested something that does no harm (like deleting something that does not exist anyway)
        #
        #
        
        if container.subcollections:
            raise Exception('Error deleting Collection path=%s. Collection has subcollections (it is a node), please remove subcollections first.'%(self.path, ))

        if container.key.parent(): # this collection has a parent
            container_parent = container.key.parent().get()
            if not container_parent:
                raise Exception('Error deleting Collection path=%s. Parent does not exist. Something went wrong.'%(self.path))

            container_parent.subcollections.remove( container.key )
            container_parent.put() # save the modified parent

        # delete the collection
        container.key.delete() 
        
    def delete_items(self):
        '''
        in the context of AppEngine, this should be performed in some background task 
        (https://developers.google.com/appengine/docs/python/taskqueue/)
        
        the collection should have been already deleted using delete() (see discussion there)
        '''
        key_pairs = self._get_key_pairs()
        if key_pairs: 
            container_key = ndb.Key( pairs=key_pairs )
         
            for item_container_key in ItemContainerAppengine.query(ancestor=container_key).iter(keys_only=True):
                item_container_key.delete()

    @ndb.transactional
    def remove(self, name): 
        '''
        remove an existing item       
        '''
        item_container_key = self._get_item_container_key(name)
        item_container = item_container_key.get()
        if item_container: # if it actually exists...
            item_container_key.delete()

            collection_container = self._get_container()
            del collection_container.tag_bin( item_container.tag )[name]
            collection_container.put()

    @ndb.transactional
    def replace(self, name, text):
        item = ical.Item(text=text, name=name)

        item_container_key = self._get_item_container_key(item.name)
        item_container = item_container_key.get()
        assert( item_container )
        item_container.set_item(item) 
        item_container.put()
        
        collection_container = self._get_container()
        collection_container.tag_bin( item_container.tag )[name] = item.etag
        collection_container.put()

    @ndb.transactional
    def append(self, name, text):
        item = ical.Item(text=text, name=name)

        item_container_key = self._get_item_container_key(item.name)
        item_container = ItemContainerAppengine(key=item_container_key)
        item_container.set_item(item) # this performs the put() to datastore
        item_container.put()
        
        collection_container = self._get_container()
        collection_container.tag_bin( item_container.tag )[name] = item.etag
        collection_container.put()

    @classmethod
    def children(cls, path):
        collection_container = cls(path)._get_container()
        if not collection_container: # collection does not exist
            raise StopIteration
        else:
            for subcollection_key in collection_container.subcollections:
                path = os.path.join( path, subcollection_key.string_id() )
                yield cls(path)

    @property
    def exists(self):
        return self._get_container() is not None

    @classmethod
    def is_node(cls, path):
        container = cls(path)._get_container()
        return container and container.subcollections

    @classmethod
    def is_leaf(cls, path):
        container = cls(path)._get_container()
        return container and (not container.subcollections)

    @property
    def last_modified(self):
        return self._get_container().last_modified.strftime("%a, %d %b %Y %H:%M:%S +0000")

    # we cannot make this a transaction
    # this means that in case of concurrent access there is a risk
    # that we put() a modified version of props that is stale
    #FIXME: how bad is that?
    #
    @property
    @contextmanager
    def props(self):
        container = self._get_container()
        if not container:
            yield {}
        else:
            # On enter
            properties = container.props
            if not properties: properties = {}
            old_properties = properties.copy()
            yield properties
            
            # On exit
            if old_properties != properties:
                container.props = properties
                container.put()

    @property
    def items_name_etag(self): 
        '''
        { item_name:etag } for every item in the collection
        '''
        container = self._get_container()
        if not container:
            return {}
        else:
            return dict( container.events.items()
                         + container.cards.items()
                         + container.todos.items()
                         + container.journals.items()
                         + container.timezones.items() )

    @property
    def etag(self):
        '''
        this is etag for the entire collection
        (obtained by hashing all items' etags)
        '''

        md5 = hashlib.md5()
        md5.update( ''.join(self.items_name_etag.values()) )
        return '"%s"' % md5.hexdigest()


    #
    #
    # we really hate to define the methods below because they act on the global collection and will not scale
    # on very large collections there might also is a risk we go over the 60s limit for appengine requests?
    # (probably not though...)
    #

    @property
    def items(self):
        """Get list of all items in collection."""
        logging.critical('#### NOSCALE: Collection.items()')
        container = self._get_container()
        if not container: return []
        else: return [ self.get_item(name) for name in (container.events.keys() + container.todos.keys() + container.journals.keys() + container.cards.keys() + container.timezones.keys())]
 
    @property
    def components(self):
        """Get list of all components in collection."""
        logging.critical('#### NOSCALE: Collection.components()')
        container = self._get_container()
        if not container: return []
        else: return [ self.get_item(name) for name in (container.events.keys() + container.todos.keys() + container.journals.keys() + container.cards.keys())]
 
    @property
    def events(self):
        """Get list of ``Event`` items in calendar."""
        logging.critical('#### NOSCALE: Collection.events()')
        container = self._get_container()
        if not container: return []
        else: return [ self.get_item(name) for name in container.events.keys() ]
 
    @property
    def todos(self):
        """Get list of ``Todo`` items in calendar."""
        logging.critical('#### NOSCALE: Collection.todos()')
        container = self._get_container()
        if not container: return []
        else: return [ self.get_item(name) for name in container.todos.keys() ]
 
    @property
    def journals(self):
        """Get list of ``Journal`` items in calendar."""
        logging.critical('#### NOSCALE: Collection.journals()')
        container = self._get_container()
        if not container: return []
        else: return [ self.get_item(name) for name in container.journals.keys() ]
 
    @property
    def timezones(self):
        """Get list of ``Timezone`` items in calendar."""
        logging.critical('#### NOSCALE: Collection.timezones()')
        container = self._get_container()
        if not container: return []
        else: return [ self.get_item(name) for name in container.timezones.keys() ]
 
    @property
    def cards(self):
        """Get list of ``Card`` items in address book."""
        container = self._get_container()
        if not container: return []
        else: return [ self.get_item(name) for name in container.cards.keys() ]

    def write(self, headers=None, items=None):
        # nocscale
        raise NotImplementedError

    @property
    def text(self):
        # nocscale
        raise NotImplementedError

#         container = self._get_container()
#         if not container:
#             return ""
#         
#         out = []
#         
#         for item_container_key in ItemContainerAppengine.query(ancestor=container.key).iter(keys_only=True):   
#             out.append( item_container_key.get().get_item().text )
#                 
#         return '\n'.join( out )


