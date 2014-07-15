# -*- coding: utf-8 -*-
#
# This file is part of Radicale Server - Calendar Server
# Copyright © 2013 Guillaume Ayoub
# Copyright © 2013 Jean-Marc Martins
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
Multi files per calendar filesystem storage backend.

"""

import os
import shutil
import time
import sys

from . import filesystem
from .. import ical  # @UnresolvedImport

from contextlib import contextmanager
import hashlib
import json
import traceback
import logging
mylogger = logging.getLogger('mylogger')
mylogger.setLevel(logging.DEBUG)

def get_traceback():
    return '\n'.join( [ '\t'.join([str(element) for element in elements]) for elements in traceback.extract_stack()[:-2] if 'Radicale' in elements[0]] )

class Collection(filesystem.Collection):
    """Collection stored in several files per calendar."""
    def _create_dirs(self):
        if not os.path.exists(self._path):
            os.makedirs(self._path)

    @property
    def headers(self):
        return (
            ical.Header("PRODID:-//Radicale//NONSGML Radicale Server//EN"),
            ical.Header("VERSION:%s" % self.version))

    def write(self, headers=None, items=None):
        with self.etags as etags:
            self._create_dirs()
            headers = headers or self.headers
            items = items if items is not None else self.items
            timezones = list(set(i for i in items if isinstance(i, ical.Timezone)))
            components = [i for i in items if isinstance(i, ical.Component)]
            mylogger.info('ww')
            for component in components:
                etags[component.name] = component.etag
                text = ical.serialize(self.tag, headers, [component] + timezones)
                name = (
                    component.name if sys.version_info[0] >= 3 else
                    component.name.encode(filesystem.FILESYSTEM_ENCODING))
                path = os.path.join(self._path, name)
                with filesystem.open(path, "w") as fd:
                    mylogger.info('write: ' + name)
                    fd.write(text)
            mylogger.info('ww')
            mylogger.info( get_traceback() )
        

    def delete(self):
        shutil.rmtree(self._path)

    def remove(self, name):
        with self.etags as etags:
            if os.path.exists(os.path.join(self._path, name)):
                mylogger.info('remove (SCALE): ' + str([name]))
                os.remove(os.path.join(self._path, name))
                del etags[name]

#SCALE
    def replace(self, name, text):
        """
        Eric: touch only the file we should touch
        note: this is called by replace
        """
        with self.etags as etags:  
            item = ical.Item( text=text, name=name )
            etags[item.name] = item.etag
            text = '\n'.join( ical.unfold(item.text) )
            with filesystem.open(os.path.join(self._path, name), "w") as fd:
                mylogger.info( 'replace (SCALE): ' + name )
                fd.write(text)

#SCALE
#previously replacing was done by removing then appending, was there a reason for that?
    def append(self, name, text):
        self.replace(name, text)

# #noscale
#     def get_item(self, item_name):
#         mylogger.info('get_item (noscale): ' + item_name)
#         res = super(Collection, self).get_item(item_name)
#         mylogger.info('get_item (noscale), [res]='+str([res]))
#         return res

#SCALE
    def get_item(self, item_name):
        mylogger.info('get_item (SCALE): ' + item_name)
        filename_absolute = os.path.join(self._path, item_name)
        if os.path.isfile(filename_absolute):
            with filesystem.open(filename_absolute, "r") as fd:
                text = fd.read()
                item = ical.Item( text=text, name=item_name )
        else: # file does not exist
            item = None
        mylogger.info('get_item, (SCALE) [res]='+str([item]))
        return item

#SCALE
    @property
    def etag(self):
        with self.etags as etags:
            md5 = hashlib.md5()
            md5.update( json.dumps(etags) )
            return '"%s"' % md5.hexdigest()

    @property
    def _etags_path(self):
        """Absolute path of the file storing the collection properties."""
        return self._path + ".etags"

    @property
    @contextmanager
    def etags(self):
        """
        keep a separate cache file with etags of all items that are direct children of the collection
        this will be useful when responding to PROPFIND requests that often only request etags
        (without this we would have ot read all the items each time)
        """
        # On enter
        etags = {}
        if os.path.exists(self._etags_path):
            with open(self._etags_path) as etag_file:
                etags.update(json.load(etag_file))
        old_etags = etags.copy()
        yield etags
        # On exit
        self._create_dirs()
        if old_etags != etags:
            with open(self._etags_path, "w") as etag_file:
                json.dump(etags, etag_file)
    
    @property
    def text(self):
        components = (
            ical.Timezone, ical.Event, ical.Todo, ical.Journal, ical.Card)
        items = set()
        try:
            mylogger.info('rr')
            for filename in os.listdir(self._path):
                if filename=='.DS_Store':
                    continue
                mylogger.info('read: '+filename)
                with filesystem.open(os.path.join(self._path, filename)) as fd:
                    items.update(self._parse(fd.read(), components))
            mylogger.info('rr')
            mylogger.info( get_traceback() )
        except IOError:
            return ""
        else:
            return ical.serialize(
                self.tag, self.headers, sorted(items, key=lambda x: x.name))

    @classmethod
    def is_node(cls, path):
        path = os.path.join(filesystem.FOLDER, path.replace("/", os.sep))
        return os.path.isdir(path) and not os.path.exists(path + ".props")

    @classmethod
    def is_leaf(cls, path):
        path = os.path.join(filesystem.FOLDER, path.replace("/", os.sep))
        return os.path.isdir(path) and os.path.exists(path + ".props")

    @property
    def last_modified(self):
        last = max([
            os.path.getmtime(os.path.join(self._path, filename))
            for filename in os.listdir(self._path)] or [0])
        return time.strftime("%a, %d %b %Y %H:%M:%S +0000", time.gmtime(last))
