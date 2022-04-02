# This file is part of Radicale - CalDAV and CardDAV server
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

import errno
import os
import pickle
import sys
from typing import Iterable, Iterator, TextIO, cast

import radicale.item as radicale_item
from radicale import pathutils
from radicale.storage.multifilesystem.base import CollectionBase
from radicale.storage.multifilesystem.cache import CollectionPartCache
from radicale.storage.multifilesystem.get import CollectionPartGet
from radicale.storage.multifilesystem.history import CollectionPartHistory


class CollectionPartUpload(CollectionPartGet, CollectionPartCache,
                           CollectionPartHistory, CollectionBase):

    def upload(self, href: str, item: radicale_item.Item
               ) -> radicale_item.Item:
        if not pathutils.is_safe_filesystem_path_component(href):
            raise pathutils.UnsafePathError(href)
        try:
            self._store_item_cache(href, item)
        except Exception as e:
            raise ValueError("Failed to store item %r in collection %r: %s" %
                             (href, self.path, e)) from e
        path = pathutils.path_to_filesystem(self._filesystem_path, href)
        with self._atomic_write(path, newline="") as fo:
            f = cast(TextIO, fo)
            f.write(item.serialize())
        # Clean the cache after the actual item is stored, or the cache entry
        # will be removed again.
        self._clean_item_cache()
        # Track the change
        self._update_history_etag(href, item)
        self._clean_history()
        uploaded_item = self._get(href, verify_href=False)
        if uploaded_item is None:
            raise RuntimeError("Storage modified externally")
        return uploaded_item

    def _upload_all_nonatomic(self, items: Iterable[radicale_item.Item],
                              suffix: str = "") -> None:
        """Upload a new set of items non-atomic"""
        def is_safe_free_href(href: str) -> bool:
            return (pathutils.is_safe_filesystem_path_component(href) and
                    not os.path.lexists(
                        os.path.join(self._filesystem_path, href)))

        def get_safe_free_hrefs(uid: str) -> Iterator[str]:
            for href in [uid if uid.lower().endswith(suffix.lower())
                         else uid + suffix,
                         radicale_item.get_etag(uid).strip('"') + suffix]:
                if is_safe_free_href(href):
                    yield href
            yield radicale_item.find_available_uid(is_safe_free_href, suffix)

        cache_folder = os.path.join(self._filesystem_path,
                                    ".Radicale.cache", "item")
        self._storage._makedirs_synced(cache_folder)
        for item in items:
            uid = item.uid
            try:
                cache_content = self._item_cache_content(item)
            except Exception as e:
                raise ValueError(
                    "Failed to store item %r in temporary collection %r: %s" %
                    (uid, self.path, e)) from e
            for href in get_safe_free_hrefs(uid):
                try:
                    f = open(os.path.join(self._filesystem_path, href),
                             "w", newline="", encoding=self._encoding)
                except OSError as e:
                    if (sys.platform != "win32" and e.errno == errno.EINVAL or
                            sys.platform == "win32" and e.errno == 123):
                        # not a valid filename
                        continue
                    raise
                break
            else:
                raise RuntimeError("No href found for item %r in temporary "
                                   "collection %r" % (uid, self.path))
            with f:
                f.write(item.serialize())
                f.flush()
                self._storage._fsync(f)
            with open(os.path.join(cache_folder, href), "wb") as fb:
                pickle.dump(cache_content, fb)
                fb.flush()
                self._storage._fsync(fb)
        self._storage._sync_directory(cache_folder)
        self._storage._sync_directory(self._filesystem_path)
