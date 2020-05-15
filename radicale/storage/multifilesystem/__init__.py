# This file is part of Radicale Server - Calendar Server
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

import contextlib
import os
import time
from itertools import chain
from tempfile import TemporaryDirectory

from radicale import pathutils, storage
from radicale.storage.multifilesystem.cache import CollectionCacheMixin
from radicale.storage.multifilesystem.create_collection import \
    StorageCreateCollectionMixin
from radicale.storage.multifilesystem.delete import CollectionDeleteMixin
from radicale.storage.multifilesystem.discover import StorageDiscoverMixin
from radicale.storage.multifilesystem.get import CollectionGetMixin
from radicale.storage.multifilesystem.history import CollectionHistoryMixin
from radicale.storage.multifilesystem.lock import (CollectionLockMixin,
                                                   StorageLockMixin)
from radicale.storage.multifilesystem.meta import CollectionMetaMixin
from radicale.storage.multifilesystem.move import StorageMoveMixin
from radicale.storage.multifilesystem.sync import CollectionSyncMixin
from radicale.storage.multifilesystem.upload import CollectionUploadMixin
from radicale.storage.multifilesystem.verify import StorageVerifyMixin


class Collection(
        CollectionCacheMixin, CollectionDeleteMixin, CollectionGetMixin,
        CollectionHistoryMixin, CollectionLockMixin, CollectionMetaMixin,
        CollectionSyncMixin, CollectionUploadMixin, storage.BaseCollection):

    def __init__(self, storage_, path, filesystem_path=None):
        self._storage = storage_
        folder = self._storage._get_collection_root_folder()
        # Path should already be sanitized
        self._path = pathutils.strip_path(path)
        self._encoding = self._storage.configuration.get("encoding", "stock")
        if filesystem_path is None:
            filesystem_path = pathutils.path_to_filesystem(folder, self.path)
        self._filesystem_path = filesystem_path
        self._etag_cache = None
        super().__init__()

    @property
    def path(self):
        return self._path

    @contextlib.contextmanager
    def _atomic_write(self, path, mode="w", newline=None):
        parent_dir, name = os.path.split(path)
        # Do not use mkstemp because it creates with permissions 0o600
        with TemporaryDirectory(
                prefix=".Radicale.tmp-", dir=parent_dir) as tmp_dir:
            with open(os.path.join(tmp_dir, name), mode, newline=newline,
                      encoding=None if "b" in mode else self._encoding) as tmp:
                yield tmp
                tmp.flush()
                self._storage._fsync(tmp)
            os.replace(os.path.join(tmp_dir, name), path)
        self._storage._sync_directory(parent_dir)

    @property
    def last_modified(self):
        relevant_files = chain(
            (self._filesystem_path,),
            (self._props_path,) if os.path.exists(self._props_path) else (),
            (os.path.join(self._filesystem_path, h) for h in self._list()))
        last = max(map(os.path.getmtime, relevant_files))
        return time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime(last))

    @property
    def etag(self):
        # reuse cached value if the storage is read-only
        if self._storage._lock.locked == "w" or self._etag_cache is None:
            self._etag_cache = super().etag
        return self._etag_cache


class Storage(
        StorageCreateCollectionMixin, StorageDiscoverMixin, StorageLockMixin,
        StorageMoveMixin, StorageVerifyMixin, storage.BaseStorage):

    _collection_class = Collection

    def __init__(self, configuration):
        super().__init__(configuration)
        folder = configuration.get("storage", "filesystem_folder")
        self._makedirs_synced(folder)

    def _get_collection_root_folder(self):
        filesystem_folder = self.configuration.get(
            "storage", "filesystem_folder")
        return os.path.join(filesystem_folder, "collection-root")

    def _fsync(self, f):
        if self.configuration.get("storage", "_filesystem_fsync"):
            try:
                pathutils.fsync(f.fileno())
            except OSError as e:
                raise RuntimeError("Fsync'ing file %r failed: %s" %
                                   (f.name, e)) from e

    def _sync_directory(self, path):
        """Sync directory to disk.

        This only works on POSIX and does nothing on other systems.

        """
        if not self.configuration.get("storage", "_filesystem_fsync"):
            return
        if os.name == "posix":
            try:
                fd = os.open(path, 0)
                try:
                    pathutils.fsync(fd)
                finally:
                    os.close(fd)
            except OSError as e:
                raise RuntimeError("Fsync'ing directory %r failed: %s" %
                                   (path, e)) from e

    def _makedirs_synced(self, filesystem_path):
        """Recursively create a directory and its parents in a sync'ed way.

        This method acts silently when the folder already exists.

        """
        if os.path.isdir(filesystem_path):
            return
        parent_filesystem_path = os.path.dirname(filesystem_path)
        # Prevent infinite loop
        if filesystem_path != parent_filesystem_path:
            # Create parent dirs recursively
            self._makedirs_synced(parent_filesystem_path)
        # Possible race!
        os.makedirs(filesystem_path, exist_ok=True)
        self._sync_directory(parent_filesystem_path)
