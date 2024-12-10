# This file is part of Radicale - CalDAV and CardDAV server
# Copyright © 2014 Jean-Marc Martins
# Copyright © 2012-2017 Guillaume Ayoub
# Copyright © 2017-2018 Unrud <unrud@outlook.com>
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
from tempfile import TemporaryDirectory
from typing import Optional

from radicale import pathutils, storage
from radicale.storage.multifilesystem.base import CollectionBase
from radicale.storage.multifilesystem.history import CollectionPartHistory


class CollectionPartDelete(CollectionPartHistory, CollectionBase):

    def delete(self, href: Optional[str] = None) -> None:
        if href is None:
            # Delete the collection
            parent_dir = os.path.dirname(self._filesystem_path)
            try:
                os.rmdir(self._filesystem_path)
            except OSError:
                with TemporaryDirectory(prefix=".Radicale.tmp-", dir=parent_dir
                                        ) as tmp:
                    os.rename(self._filesystem_path, os.path.join(
                        tmp, os.path.basename(self._filesystem_path)))
                    self._storage._sync_directory(parent_dir)
            else:
                self._storage._sync_directory(parent_dir)
        else:
            # Delete an item
            if not pathutils.is_safe_filesystem_path_component(href):
                raise pathutils.UnsafePathError(href)
            path = pathutils.path_to_filesystem(self._filesystem_path, href)
            if not os.path.isfile(path):
                raise storage.ComponentNotFoundError(href)
            os.remove(path)
            self._storage._sync_directory(os.path.dirname(path))
            # Track the change
            self._update_history_etag(href, None)
            self._clean_history()
            # Remove item from cache
            cache_folder = self._storage._get_collection_cache_subfolder(os.path.dirname(path), ".Radicale.cache", "item")
            cache_file = os.path.join(cache_folder, os.path.basename(path))
            if os.path.isfile(cache_file):
                os.remove(cache_file)
                self._storage._sync_directory(cache_folder)
