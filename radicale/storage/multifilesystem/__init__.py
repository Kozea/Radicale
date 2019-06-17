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

import contextlib
import os
import time
from itertools import chain
from tempfile import NamedTemporaryFile

from radicale import pathutils, storage
from radicale.storage.multifilesystem.cache import CollectionCacheMixin
from radicale.storage.multifilesystem.create_collection import \
    CollectionCreateCollectionMixin
from radicale.storage.multifilesystem.delete import CollectionDeleteMixin
from radicale.storage.multifilesystem.discover import CollectionDiscoverMixin
from radicale.storage.multifilesystem.get import CollectionGetMixin
from radicale.storage.multifilesystem.history import CollectionHistoryMixin
from radicale.storage.multifilesystem.lock import CollectionLockMixin
from radicale.storage.multifilesystem.meta import CollectionMetaMixin
from radicale.storage.multifilesystem.move import CollectionMoveMixin
from radicale.storage.multifilesystem.sync import CollectionSyncMixin
from radicale.storage.multifilesystem.upload import CollectionUploadMixin
from radicale.storage.multifilesystem.verify import CollectionVerifyMixin


class Collection(
        CollectionCacheMixin, CollectionCreateCollectionMixin,
        CollectionDeleteMixin, CollectionDiscoverMixin, CollectionGetMixin,
        CollectionHistoryMixin, CollectionLockMixin, CollectionMetaMixin,
        CollectionMoveMixin, CollectionSyncMixin, CollectionUploadMixin,
        CollectionVerifyMixin, storage.BaseCollection):
    """Collection stored in several files per calendar."""

    @classmethod
    def static_init(cls):
        folder = cls.configuration.get("storage", "filesystem_folder")
        cls._makedirs_synced(folder)
        super().static_init()

    def __init__(self, path, filesystem_path=None):
        folder = self._get_collection_root_folder()
        # Path should already be sanitized
        self.path = pathutils.strip_path(path)
        self._encoding = self.configuration.get("encoding", "stock")
        if filesystem_path is None:
            filesystem_path = pathutils.path_to_filesystem(folder, self.path)
        self._filesystem_path = filesystem_path
        self._etag_cache = None
        super().__init__()

    @classmethod
    def _get_collection_root_folder(cls):
        filesystem_folder = cls.configuration.get(
            "storage", "filesystem_folder")
        return os.path.join(filesystem_folder, "collection-root")

    @contextlib.contextmanager
    def _atomic_write(self, path, mode="w", newline=None, sync_directory=True,
                      replace_fn=os.replace):
        directory = os.path.dirname(path)
        tmp = NamedTemporaryFile(
            mode=mode, dir=directory, delete=False, prefix=".Radicale.tmp-",
            newline=newline, encoding=None if "b" in mode else self._encoding)
        try:
            yield tmp
            tmp.flush()
            try:
                self._fsync(tmp.fileno())
            except OSError as e:
                raise RuntimeError("Fsync'ing file %r failed: %s" %
                                   (path, e)) from e
            tmp.close()
            replace_fn(tmp.name, path)
        except BaseException:
            tmp.close()
            os.remove(tmp.name)
            raise
        if sync_directory:
            self._sync_directory(directory)

    @classmethod
    def _fsync(cls, fd):
        if cls.configuration.get("internal", "filesystem_fsync"):
            pathutils.fsync(fd)

    @classmethod
    def _sync_directory(cls, path):
        """Sync directory to disk.

        This only works on POSIX and does nothing on other systems.

        """
        if not cls.configuration.get("internal", "filesystem_fsync"):
            return
        if os.name == "posix":
            try:
                fd = os.open(path, 0)
                try:
                    cls._fsync(fd)
                finally:
                    os.close(fd)
            except OSError as e:
                raise RuntimeError("Fsync'ing directory %r failed: %s" %
                                   (path, e)) from e

    @classmethod
    def _makedirs_synced(cls, filesystem_path):
        """Recursively create a directory and its parents in a sync'ed way.

        This method acts silently when the folder already exists.

        """
        if os.path.isdir(filesystem_path):
            return
        parent_filesystem_path = os.path.dirname(filesystem_path)
        # Prevent infinite loop
        if filesystem_path != parent_filesystem_path:
            # Create parent dirs recursively
            cls._makedirs_synced(parent_filesystem_path)
        # Possible race!
        os.makedirs(filesystem_path, exist_ok=True)
        cls._sync_directory(parent_filesystem_path)

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
        if self._lock.locked == "w" or self._etag_cache is None:
            self._etag_cache = super().etag
        return self._etag_cache
