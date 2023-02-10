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

"""
Storage backend that stores data in the file system.

Uses one folder per collection and one file per collection entry.

"""

import os
import time
from typing import ClassVar, Iterator, Optional, Type

from radicale import config
from radicale.storage.multifilesystem.base import CollectionBase, StorageBase
from radicale.storage.multifilesystem.cache import CollectionPartCache
from radicale.storage.multifilesystem.create_collection import \
    StoragePartCreateCollection
from radicale.storage.multifilesystem.delete import CollectionPartDelete
from radicale.storage.multifilesystem.discover import StoragePartDiscover
from radicale.storage.multifilesystem.get import CollectionPartGet
from radicale.storage.multifilesystem.history import CollectionPartHistory
from radicale.storage.multifilesystem.lock import (CollectionPartLock,
                                                   StoragePartLock)
from radicale.storage.multifilesystem.meta import CollectionPartMeta
from radicale.storage.multifilesystem.move import StoragePartMove
from radicale.storage.multifilesystem.sync import CollectionPartSync
from radicale.storage.multifilesystem.upload import CollectionPartUpload
from radicale.storage.multifilesystem.verify import StoragePartVerify


class Collection(
        CollectionPartDelete, CollectionPartMeta, CollectionPartSync,
        CollectionPartUpload, CollectionPartGet, CollectionPartCache,
        CollectionPartLock, CollectionPartHistory, CollectionBase):

    _etag_cache: Optional[str]

    def __init__(self, storage_: "Storage", path: str,
                 filesystem_path: Optional[str] = None) -> None:
        super().__init__(storage_, path, filesystem_path)
        self._etag_cache = None

    @property
    def path(self) -> str:
        return self._path

    @property
    def last_modified(self) -> str:
        def relevant_files_iter() -> Iterator[str]:
            yield self._filesystem_path
            if os.path.exists(self._props_path):
                yield self._props_path
            for href in self._list():
                yield os.path.join(self._filesystem_path, href)
        last = max(map(os.path.getmtime, relevant_files_iter()))
        return time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime(last))

    @property
    def etag(self) -> str:
        # reuse cached value if the storage is read-only
        if self._storage._lock.locked == "w" or self._etag_cache is None:
            self._etag_cache = super().etag
        return self._etag_cache


class Storage(
        StoragePartCreateCollection, StoragePartLock, StoragePartMove,
        StoragePartVerify, StoragePartDiscover, StorageBase):

    _collection_class: ClassVar[Type[Collection]] = Collection

    def __init__(self, configuration: config.Configuration) -> None:
        super().__init__(configuration)
        self._makedirs_synced(self._filesystem_folder)
