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

import os
from tempfile import TemporaryDirectory
from typing import IO, AnyStr, ClassVar, Iterator, Optional, Type

from radicale import config, pathutils, storage, types
from radicale.storage import multifilesystem  # noqa:F401


class CollectionBase(storage.BaseCollection):

    _storage: "multifilesystem.Storage"
    _path: str
    _encoding: str
    _filesystem_path: str

    def __init__(self, storage_: "multifilesystem.Storage", path: str,
                 filesystem_path: Optional[str] = None) -> None:
        super().__init__()
        self._storage = storage_
        folder = storage_._get_collection_root_folder()
        # Path should already be sanitized
        self._path = pathutils.strip_path(path)
        self._encoding = storage_.configuration.get("encoding", "stock")
        if filesystem_path is None:
            filesystem_path = pathutils.path_to_filesystem(folder, self.path)
        self._filesystem_path = filesystem_path

    @types.contextmanager
    def _atomic_write(self, path: str, mode: str = "w",
                      newline: Optional[str] = None) -> Iterator[IO[AnyStr]]:
        # TODO: Overload with Literal when dropping support for Python < 3.8
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


class StorageBase(storage.BaseStorage):

    _collection_class: ClassVar[Type["multifilesystem.Collection"]]

    _filesystem_folder: str
    _filesystem_fsync: bool

    def __init__(self, configuration: config.Configuration) -> None:
        super().__init__(configuration)
        self._filesystem_folder = configuration.get(
            "storage", "filesystem_folder")
        self._filesystem_fsync = configuration.get(
            "storage", "_filesystem_fsync")

    def _get_collection_root_folder(self) -> str:
        return os.path.join(self._filesystem_folder, "collection-root")

    def _fsync(self, f: IO[AnyStr]) -> None:
        if self._filesystem_fsync:
            try:
                pathutils.fsync(f.fileno())
            except OSError as e:
                raise RuntimeError("Fsync'ing file %r failed: %s" %
                                   (f.name, e)) from e

    def _sync_directory(self, path: str) -> None:
        """Sync directory to disk.

        This only works on POSIX and does nothing on other systems.

        """
        if not self._filesystem_fsync:
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

    def _makedirs_synced(self, filesystem_path: str) -> None:
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
