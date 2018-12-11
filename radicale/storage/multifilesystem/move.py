# This file is part of Radicale Server - Calendar Server
# Copyright © 2014 Jean-Marc Martins
# Copyright © 2012-2017 Guillaume Ayoub
# Copyright © 2017-2018 Unrud<unrud@outlook.com>
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

from radicale import pathutils


class CollectionMoveMixin:
    @classmethod
    def move(cls, item, to_collection, to_href):
        if not pathutils.is_safe_filesystem_path_component(to_href):
            raise pathutils.UnsafePathError(to_href)
        collection = item.collection
        if collection._share:
            assert collection._share.item_writethrough
            base_collection = collection._base_collection
        else:
            base_collection = collection
        if to_collection._share:
            assert to_collection._share.item_writethrough
            base_to_collection = to_collection._base_collection
        else:
            base_to_collection = to_collection
        os.replace(
            pathutils.path_to_filesystem(
                base_collection._filesystem_path, item.href),
            pathutils.path_to_filesystem(
                base_to_collection._filesystem_path, to_href))
        cls._sync_directory(base_to_collection._filesystem_path)
        if (base_collection._filesystem_path !=
                base_to_collection._filesystem_path):
            cls._sync_directory(base_collection._filesystem_path)
        # Move the item cache entry
        cache_folder = os.path.join(base_collection._filesystem_path,
                                    ".Radicale.cache", "item")
        to_cache_folder = os.path.join(base_to_collection._filesystem_path,
                                       ".Radicale.cache", "item")
        cls._makedirs_synced(to_cache_folder)
        try:
            os.replace(os.path.join(cache_folder, item.href),
                       os.path.join(to_cache_folder, to_href))
        except FileNotFoundError:
            pass
        else:
            cls._makedirs_synced(to_cache_folder)
            if cache_folder != to_cache_folder:
                cls._makedirs_synced(cache_folder)
        # Track the change
        to_collection._update_history_etag(to_href, item)
        collection._update_history_etag(item.href, None)
        to_collection._clean_history()
        if collection._filesystem_path != to_collection._filesystem_path:
            collection._clean_history()
