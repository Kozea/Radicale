# This file is part of Radicale - CalDAV and CardDAV server
# Copyright © 2014 Jean-Marc Martins
# Copyright © 2012-2017 Guillaume Ayoub
# Copyright © 2017-2022 Unrud <unrud@outlook.com>
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
import sys
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
        self._skip_broken_item = storage_.configuration.get("storage", "skip_broken_item")
        if filesystem_path is None:
            filesystem_path = pathutils.path_to_filesystem(folder, self.path)
        self._filesystem_path = filesystem_path

    # TODO: better fix for "mypy"
    @types.contextmanager  # type: ignore
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
    _filesystem_cache_folder: str
    _filesystem_fsync: bool
    _use_cache_subfolder_for_item: bool
    _use_cache_subfolder_for_history: bool
    _use_cache_subfolder_for_synctoken: bool
    _use_mtime_and_size_for_item_cache: bool
    _debug_cache_actions: bool
    _folder_umask: str
    _config_umask: int

    def __init__(self, configuration: config.Configuration) -> None:
        super().__init__(configuration)
        self._filesystem_folder = configuration.get(
            "storage", "filesystem_folder")
        self._filesystem_fsync = configuration.get(
            "storage", "_filesystem_fsync")
        self._filesystem_cache_folder = configuration.get(
            "storage", "filesystem_cache_folder")
        self._use_cache_subfolder_for_item = configuration.get(
            "storage", "use_cache_subfolder_for_item")
        self._use_cache_subfolder_for_history = configuration.get(
            "storage", "use_cache_subfolder_for_history")
        self._use_cache_subfolder_for_synctoken = configuration.get(
            "storage", "use_cache_subfolder_for_synctoken")
        self._use_mtime_and_size_for_item_cache = configuration.get(
            "storage", "use_mtime_and_size_for_item_cache")
        self._folder_umask = configuration.get(
            "storage", "folder_umask")
        self._debug_cache_actions = configuration.get(
            "logging", "storage_cache_actions_on_debug")

    def _get_collection_root_folder(self) -> str:
        return os.path.join(self._filesystem_folder, "collection-root")

    def _get_collection_cache_folder(self) -> str:
        if self._filesystem_cache_folder:
            return os.path.join(self._filesystem_cache_folder, "collection-cache")
        else:
            return os.path.join(self._filesystem_folder, "collection-cache")

    def _get_collection_cache_subfolder(self, path, folder, subfolder) -> str:
        if (self._use_cache_subfolder_for_item is True) and (subfolder == "item"):
            path = path.replace(self._get_collection_root_folder(), self._get_collection_cache_folder())
        elif (self._use_cache_subfolder_for_history is True) and (subfolder == "history"):
            path = path.replace(self._get_collection_root_folder(), self._get_collection_cache_folder())
        elif (self._use_cache_subfolder_for_synctoken is True) and (subfolder == "sync-token"):
            path = path.replace(self._get_collection_root_folder(), self._get_collection_cache_folder())
        return os.path.join(path, folder, subfolder)

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
        if sys.platform != "win32":
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
        if sys.platform != "win32" and self._folder_umask:
            oldmask = os.umask(self._config_umask)
        # Prevent infinite loop
        if filesystem_path != parent_filesystem_path:
            # Create parent dirs recursively
            self._makedirs_synced(parent_filesystem_path)
        # Possible race!
        os.makedirs(filesystem_path, exist_ok=True)
        self._sync_directory(parent_filesystem_path)
        if sys.platform != "win32" and self._folder_umask:
            os.umask(oldmask)
