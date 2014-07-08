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

import datetime
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
        self._create_dirs()
        headers = headers or self.headers
        items = items if items is not None else self.items
        timezones = list(set(i for i in items if isinstance(i, ical.Timezone)))
        components = [i for i in items if isinstance(i, ical.Component)]
        mylogger.info('ww')
        for component in components:
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
        self.mark_modified()

    def delete(self):
        shutil.rmtree(self._path)

    def remove(self, name):
        if os.path.exists(os.path.join(self._path, name)):
            mylogger.info('remove (SCALE): ' + name)
            os.remove(os.path.join(self._path, name))
        self.mark_modified()

#SCALE
    def replace(self, name, text):
        """
        Eric: touch only the file we should touch
        note: this is called by replace
        """        
        item = ical.Item( text=text, name=name )
        text = '\n'.join( ical.unfold(item.text) )
        with filesystem.open(os.path.join(self._path, name), "w") as fd:
            mylogger.info( 'replace (SCALE): ' + name )
            fd.write(text)
        self.mark_modified()

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
    def mark_modified(self):
        os.utime( self._path, None ) # this will not work on windows: directories cannot be given a time
        mylogger.info('mark_modified, (SCALE) etag='+self.etag)

#SCALE
    @property
    def etag(self):
        '''
        use last modified date as etag 
        (instead of hashing content of all items)
        '''
        st_mtime = os.stat(self._path).st_mtime # time of most recent content modification,
        return '"%s"' % st_mtime

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
