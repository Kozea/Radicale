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

import os
import pickle
import sys
from typing import Iterable, Set, TextIO, cast

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
        """Upload a new set of items.

        This takes a list of vobject items and
        uploads them nonatomic and without existence checks.

        """
        cache_folder = os.path.join(self._filesystem_path,
                                    ".Radicale.cache", "item")
        self._storage._makedirs_synced(cache_folder)
        hrefs: Set[str] = set()
        for item in items:
            uid = item.uid
            try:
                cache_content = self._item_cache_content(item)
            except Exception as e:
                raise ValueError(
                    "Failed to store item %r in temporary collection %r: %s" %
                    (uid, self.path, e)) from e
            href_candidate_funtions = []
            if os.name == "posix" or sys.platform == "win32":
                href_candidate_funtions.append(
                    lambda: uid if uid.lower().endswith(suffix.lower())
                    else uid + suffix)
            href_candidate_funtions.extend((
                lambda: radicale_item.get_etag(uid).strip('"') + suffix,
                lambda: radicale_item.find_available_uid(hrefs.__contains__,
                                                         suffix)))
            href = f = None
            while href_candidate_funtions:
                href = href_candidate_funtions.pop(0)()
                if href in hrefs:
                    continue
                if not pathutils.is_safe_filesystem_path_component(href):
                    if not href_candidate_funtions:
                        raise pathutils.UnsafePathError(href)
                    continue
                try:
                    f = open(pathutils.path_to_filesystem(
                        self._filesystem_path, href),
                        "w", newline="", encoding=self._encoding)
                    break
                except OSError as e:
                    if href_candidate_funtions and (
                            os.name == "posix" and e.errno == 22 or
                            sys.platform == "win32" and e.errno == 123):
                        continue
                    raise
            assert href is not None and f is not None
            with f:
                f.write(item.serialize())
                f.flush()
                self._storage._fsync(f)
            hrefs.add(href)
            with open(os.path.join(cache_folder, href), "wb") as fb:
                pickle.dump(cache_content, fb)
                fb.flush()
                self._storage._fsync(fb)
        self._storage._sync_directory(cache_folder)
        self._storage._sync_directory(self._filesystem_path)
