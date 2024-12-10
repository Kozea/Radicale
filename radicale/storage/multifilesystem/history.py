# This file is part of Radicale - CalDAV and CardDAV server
# Copyright © 2014 Jean-Marc Martins
# Copyright © 2012-2017 Guillaume Ayoub
# Copyright © 2017-2019 Unrud <unrud@outlook.com>
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

import binascii
import contextlib
import os
import pickle
from typing import BinaryIO, Optional, cast

import radicale.item as radicale_item
from radicale import pathutils
from radicale.log import logger
from radicale.storage import multifilesystem
from radicale.storage.multifilesystem.base import CollectionBase


class CollectionPartHistory(CollectionBase):

    _max_sync_token_age: int

    def __init__(self, storage_: "multifilesystem.Storage", path: str,
                 filesystem_path: Optional[str] = None) -> None:
        super().__init__(storage_, path, filesystem_path)
        self._max_sync_token_age = storage_.configuration.get(
            "storage", "max_sync_token_age")

    def _update_history_etag(self, href, item):
        """Updates and retrieves the history etag from the history cache.

        The history cache contains a file for each current and deleted item
        of the collection. These files contain the etag of the item (empty
        string for deleted items) and a history etag, which is a hash over
        the previous history etag and the etag separated by "/".
        """
        history_folder = self._storage._get_collection_cache_subfolder(self._filesystem_path, ".Radicale.cache", "history")
        try:
            with open(os.path.join(history_folder, href), "rb") as f:
                cache_etag, history_etag = pickle.load(f)
        except (FileNotFoundError, pickle.UnpicklingError, ValueError) as e:
            if isinstance(e, (pickle.UnpicklingError, ValueError)):
                logger.warning(
                    "Failed to load history cache entry %r in %r: %s",
                    href, self.path, e, exc_info=True)
            cache_etag = ""
            # Initialize with random data to prevent collisions with cleaned
            # expired items.
            history_etag = binascii.hexlify(os.urandom(16)).decode("ascii")
        etag = item.etag if item else ""
        if etag != cache_etag:
            self._storage._makedirs_synced(history_folder)
            history_etag = radicale_item.get_etag(
                history_etag + "/" + etag).strip("\"")
            # Race: Other processes might have created and locked the file.
            with contextlib.suppress(PermissionError), self._atomic_write(
                    os.path.join(history_folder, href), "wb") as fo:
                fb = cast(BinaryIO, fo)
                pickle.dump([etag, history_etag], fb)
        return history_etag

    def _get_deleted_history_hrefs(self):
        """Returns the hrefs of all deleted items that are still in the
        history cache."""
        history_folder = self._storage._get_collection_cache_subfolder(self._filesystem_path, ".Radicale.cache", "history")
        with contextlib.suppress(FileNotFoundError):
            for entry in os.scandir(history_folder):
                href = entry.name
                if not pathutils.is_safe_filesystem_path_component(href):
                    continue
                if os.path.isfile(os.path.join(self._filesystem_path, href)):
                    continue
                yield href

    def _clean_history(self):
        # Delete all expired history entries of deleted items.
        history_folder = self._storage._get_collection_cache_subfolder(self._filesystem_path, ".Radicale.cache", "history")
        self._clean_cache(history_folder, self._get_deleted_history_hrefs(),
                          max_age=self._max_sync_token_age)
