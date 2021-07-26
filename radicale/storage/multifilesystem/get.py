# This file is part of Radicale Server - Calendar Server
# Copyright © 2014 Jean-Marc Martins
# Copyright © 2012-2017 Guillaume Ayoub
# Copyright © 2017-2018 Unrud <unrud@outlook.com>
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

import os
import sys
import time

import vobject

import radicale.item as radicale_item
from radicale import pathutils
from radicale.log import logger


class CollectionGetMixin:
    def __init__(self):
        super().__init__()
        self._item_cache_cleaned = False

    def _list(self):
        for entry in os.scandir(self._filesystem_path):
            if not entry.is_file():
                continue
            href = entry.name
            if not pathutils.is_safe_filesystem_path_component(href):
                if not href.startswith(".Radicale"):
                    logger.debug("Skipping item %r in %r", href, self.path)
                continue
            yield href

    def _get(self, href, verify_href=True):
        if verify_href:
            try:
                if not pathutils.is_safe_filesystem_path_component(href):
                    raise pathutils.UnsafePathError(href)
                path = pathutils.path_to_filesystem(
                    self._filesystem_path, href)
            except ValueError as e:
                logger.debug(
                    "Can't translate name %r safely to filesystem in %r: %s",
                    href, self.path, e, exc_info=True)
                return None
        else:
            path = os.path.join(self._filesystem_path, href)
        try:
            with open(path, "rb") as f:
                raw_text = f.read()
        except (FileNotFoundError, IsADirectoryError):
            return None
        except PermissionError:
            # Windows raises ``PermissionError`` when ``path`` is a directory
            if (sys.platform == "win32" and
                    os.path.isdir(path) and os.access(path, os.R_OK)):
                return None
            raise
        # The hash of the component in the file system. This is used to check,
        # if the entry in the cache is still valid.
        input_hash = self._item_cache_hash(raw_text)
        cache_hash, uid, etag, text, name, tag, start, end = \
            self._load_item_cache(href, input_hash)
        if input_hash != cache_hash:
            with self._acquire_cache_lock("item"):
                # Lock the item cache to prevent multpile processes from
                # generating the same data in parallel.
                # This improves the performance for multiple requests.
                if self._storage._lock.locked == "r":
                    # Check if another process created the file in the meantime
                    cache_hash, uid, etag, text, name, tag, start, end = \
                        self._load_item_cache(href, input_hash)
                if input_hash != cache_hash:
                    try:
                        vobject_items = list(vobject.readComponents(
                            raw_text.decode(self._encoding)))
                        radicale_item.check_and_sanitize_items(
                            vobject_items, tag=self.tag)
                        vobject_item, = vobject_items
                        temp_item = radicale_item.Item(
                            collection=self, vobject_item=vobject_item)
                        cache_hash, uid, etag, text, name, tag, start, end = \
                            self._store_item_cache(
                                href, temp_item, input_hash)
                    except Exception as e:
                        raise RuntimeError("Failed to load item %r in %r: %s" %
                                           (href, self.path, e)) from e
                    # Clean cache entries once after the data in the file
                    # system was edited externally.
                    if not self._item_cache_cleaned:
                        self._item_cache_cleaned = True
                        self._clean_item_cache()
        last_modified = time.strftime(
            "%a, %d %b %Y %H:%M:%S GMT",
            time.gmtime(os.path.getmtime(path)))
        # Don't keep reference to ``vobject_item``, because it requires a lot
        # of memory.
        return radicale_item.Item(
            collection=self, href=href, last_modified=last_modified, etag=etag,
            text=text, uid=uid, name=name, component_name=tag,
            time_range=(start, end))

    def get_multi(self, hrefs):
        # It's faster to check for file name collissions here, because
        # we only need to call os.listdir once.
        files = None
        for href in hrefs:
            if files is None:
                # List dir after hrefs returned one item, the iterator may be
                # empty and the for-loop is never executed.
                files = os.listdir(self._filesystem_path)
            path = os.path.join(self._filesystem_path, href)
            if (not pathutils.is_safe_filesystem_path_component(href) or
                    href not in files and os.path.lexists(path)):
                logger.debug(
                    "Can't translate name safely to filesystem: %r", href)
                yield (href, None)
            else:
                yield (href, self._get(href, verify_href=False))

    def get_all(self):
        # We don't need to check for collissions, because the the file names
        # are from os.listdir.
        return (self._get(href, verify_href=False) for href in self._list())
