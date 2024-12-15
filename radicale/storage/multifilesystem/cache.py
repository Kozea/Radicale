# This file is part of Radicale - CalDAV and CardDAV server
# Copyright © 2014 Jean-Marc Martins
# Copyright © 2012-2017 Guillaume Ayoub
# Copyright © 2017-2021 Unrud <unrud@outlook.com>
# Copyright © 2024-2024 Peter Bieringer <pb@bieringer.de>
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

import contextlib
import os
import pickle
import time
from hashlib import sha256
from typing import BinaryIO, Iterable, NamedTuple, Optional, cast

import radicale.item as radicale_item
from radicale import pathutils, storage
from radicale.log import logger
from radicale.storage.multifilesystem.base import CollectionBase

CacheContent = NamedTuple("CacheContent", [
    ("uid", str), ("etag", str), ("text", str), ("name", str), ("tag", str),
    ("start", int), ("end", int)])


class CollectionPartCache(CollectionBase):

    def _clean_cache(self, folder: str, names: Iterable[str],
                     max_age: int = 0) -> None:
        """Delete all ``names`` in ``folder`` that are older than ``max_age``.
        """
        age_limit: Optional[float] = None
        if max_age is not None and max_age > 0:
            age_limit = time.time() - max_age
        modified = False
        for name in names:
            if not pathutils.is_safe_filesystem_path_component(name):
                continue
            if age_limit is not None:
                try:
                    # Race: Another process might have deleted the file.
                    mtime = os.path.getmtime(os.path.join(folder, name))
                except FileNotFoundError:
                    continue
                if mtime > age_limit:
                    continue
            logger.debug("Found expired item in cache: %r", name)
            # Race: Another process might have deleted or locked the
            # file.
            try:
                os.remove(os.path.join(folder, name))
            except (FileNotFoundError, PermissionError):
                continue
            modified = True
        if modified:
            self._storage._sync_directory(folder)

    @staticmethod
    def _item_cache_hash(raw_text: bytes) -> str:
        _hash = sha256()
        _hash.update(storage.CACHE_VERSION)
        _hash.update(raw_text)
        return _hash.hexdigest()

    @staticmethod
    def _item_cache_mtime_and_size(size: int, raw_text: int) -> str:
        return str(storage.CACHE_VERSION.decode()) + "size=" + str(size) + ";mtime=" + str(raw_text)

    def _item_cache_content(self, item: radicale_item.Item) -> CacheContent:
        return CacheContent(item.uid, item.etag, item.serialize(), item.name,
                            item.component_name, *item.time_range)

    def _store_item_cache(self, href: str, item: radicale_item.Item,
                          cache_hash: str = "") -> CacheContent:
        if not cache_hash:
            if self._storage._use_mtime_and_size_for_item_cache is True:
                raise RuntimeError("_store_item_cache called without cache_hash is not supported if [storage] use_mtime_and_size_for_item_cache is True")
            else:
                cache_hash = self._item_cache_hash(
                    item.serialize().encode(self._encoding))
        cache_folder = self._storage._get_collection_cache_subfolder(self._filesystem_path, ".Radicale.cache", "item")
        content = self._item_cache_content(item)
        self._storage._makedirs_synced(cache_folder)
        # Race: Other processes might have created and locked the file.
        # TODO: better fix for "mypy"
        with contextlib.suppress(PermissionError), self._atomic_write(  # type: ignore
                os.path.join(cache_folder, href), "wb") as fo:
            fb = cast(BinaryIO, fo)
            pickle.dump((cache_hash, *content), fb)
        return content

    def _load_item_cache(self, href: str, cache_hash: str
                         ) -> Optional[CacheContent]:
        cache_folder = self._storage._get_collection_cache_subfolder(self._filesystem_path, ".Radicale.cache", "item")
        path = os.path.join(cache_folder, href)
        try:
            with open(path, "rb") as f:
                hash_, *remainder = pickle.load(f)
                if hash_ and hash_ == cache_hash:
                    if self._storage._debug_cache_actions is True:
                        logger.debug("Item cache match     : %r with hash %r", path, cache_hash)
                    return CacheContent(*remainder)
                else:
                    if self._storage._debug_cache_actions is True:
                        logger.debug("Item cache no match  : %r with hash %r", path, cache_hash)
        except FileNotFoundError:
            if self._storage._debug_cache_actions is True:
                logger.debug("Item cache not found : %r with hash %r", path, cache_hash)
            pass
        except (pickle.UnpicklingError, ValueError) as e:
            logger.warning("Failed to load item cache entry %r in %r: %s",
                           href, self.path, e, exc_info=True)
        return None

    def _clean_item_cache(self) -> None:
        cache_folder = self._storage._get_collection_cache_subfolder(self._filesystem_path, ".Radicale.cache", "item")
        self._clean_cache(cache_folder, (
            e.name for e in os.scandir(cache_folder) if not
            os.path.isfile(os.path.join(self._filesystem_path, e.name))))
