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

import contextlib
import os
import pickle
import time
from hashlib import sha256

from radicale import pathutils, storage
from radicale.log import logger


class CollectionCacheMixin:
    def _clean_cache(self, folder, names, max_age=None):
        """Delete all ``names`` in ``folder`` that are older than ``max_age``.
        """
        age_limit = time.time() - max_age if max_age is not None else None
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
    def _item_cache_hash(raw_text):
        _hash = sha256()
        _hash.update(storage.CACHE_VERSION)
        _hash.update(raw_text)
        return _hash.hexdigest()

    def _item_cache_content(self, item, cache_hash=None):
        text = item.serialize()
        if cache_hash is None:
            cache_hash = self._item_cache_hash(text.encode(self._encoding))
        return (cache_hash, item.uid, item.etag, text, item.name,
                item.component_name, *item.time_range)

    def _store_item_cache(self, href, item, cache_hash=None):
        cache_folder = os.path.join(self._filesystem_path, ".Radicale.cache",
                                    "item")
        content = self._item_cache_content(item, cache_hash)
        self._storage._makedirs_synced(cache_folder)
        # Race: Other processes might have created and locked the file.
        with contextlib.suppress(PermissionError), self._atomic_write(
                os.path.join(cache_folder, href), "wb") as f:
            pickle.dump(content, f)
        return content

    def _load_item_cache(self, href, input_hash):
        cache_folder = os.path.join(self._filesystem_path, ".Radicale.cache",
                                    "item")
        cache_hash = uid = etag = text = name = tag = start = end = None
        try:
            with open(os.path.join(cache_folder, href), "rb") as f:
                cache_hash, *content = pickle.load(f)
                if cache_hash == input_hash:
                    uid, etag, text, name, tag, start, end = content
        except FileNotFoundError:
            pass
        except (pickle.UnpicklingError, ValueError) as e:
            logger.warning("Failed to load item cache entry %r in %r: %s",
                           href, self.path, e, exc_info=True)
        return cache_hash, uid, etag, text, name, tag, start, end

    def _clean_item_cache(self):
        cache_folder = os.path.join(self._filesystem_path, ".Radicale.cache",
                                    "item")
        self._clean_cache(cache_folder, (
            e.name for e in os.scandir(cache_folder) if not
            os.path.isfile(os.path.join(self._filesystem_path, e.name))))
