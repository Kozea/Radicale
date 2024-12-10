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

import os

from radicale import item as radicale_item
from radicale import pathutils, storage
from radicale.storage import multifilesystem
from radicale.storage.multifilesystem.base import StorageBase


class StoragePartMove(StorageBase):

    def move(self, item: radicale_item.Item,
             to_collection: storage.BaseCollection, to_href: str) -> None:
        if not pathutils.is_safe_filesystem_path_component(to_href):
            raise pathutils.UnsafePathError(to_href)
        assert isinstance(to_collection, multifilesystem.Collection)
        assert isinstance(item.collection, multifilesystem.Collection)
        assert item.href
        os.replace(pathutils.path_to_filesystem(
                       item.collection._filesystem_path, item.href),
                   pathutils.path_to_filesystem(
                       to_collection._filesystem_path, to_href))
        self._sync_directory(to_collection._filesystem_path)
        if item.collection._filesystem_path != to_collection._filesystem_path:
            self._sync_directory(item.collection._filesystem_path)
        # Move the item cache entry
        cache_folder = self._get_collection_cache_subfolder(item.collection._filesystem_path, ".Radicale.cache", "item")
        to_cache_folder = self._get_collection_cache_subfolder(to_collection._filesystem_path, ".Radicale.cache", "item")
        self._makedirs_synced(to_cache_folder)
        try:
            os.replace(os.path.join(cache_folder, item.href),
                       os.path.join(to_cache_folder, to_href))
        except FileNotFoundError:
            pass
        else:
            self._makedirs_synced(to_cache_folder)
            if cache_folder != to_cache_folder:
                self._makedirs_synced(cache_folder)
        # Track the change
        to_collection._update_history_etag(to_href, item)
        item.collection._update_history_etag(item.href, None)
        to_collection._clean_history()
        if item.collection._filesystem_path != to_collection._filesystem_path:
            item.collection._clean_history()
