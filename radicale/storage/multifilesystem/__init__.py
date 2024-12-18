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

"""
Storage backend that stores data in the file system.

Uses one folder per collection and one file per collection entry.

"""

import os
import sys
import time
from typing import ClassVar, Iterator, Optional, Type

from radicale import config
from radicale.log import logger
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

# 999 second, 999 ms, 999 us, 999 ns
MTIME_NS_TEST: int = 999999999999


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

    def _analyse_mtime(self):
        # calculate and display mtime resolution
        path = os.path.join(self._filesystem_folder, ".Radicale.mtime_test")
        try:
            with open(path, "w") as f:
                f.write("mtime_test")
                f.close
        except Exception as e:
            logger.error("Storage item mtime resolution test not possible, cannot write file: %r (%s)", path, e)
            raise
        # set mtime_ns for tests
        os.utime(path, times=None, ns=(MTIME_NS_TEST, MTIME_NS_TEST))
        logger.debug("Storage item mtime resoultion test set: %d" % MTIME_NS_TEST)
        mtime_ns = os.stat(path).st_mtime_ns
        logger.debug("Storage item mtime resoultion test get: %d" % mtime_ns)
        # start analysis
        precision = 1
        mtime_ns_test = MTIME_NS_TEST
        while mtime_ns > 0:
            if mtime_ns == mtime_ns_test:
                break
            factor = 2
            if int(mtime_ns / factor) == int(mtime_ns_test / factor):
                precision = precision * factor
                break
            factor = 5
            if int(mtime_ns / factor) == int(mtime_ns_test / factor):
                precision = precision * factor
                break
            precision = precision * 10
            mtime_ns = int(mtime_ns / 10)
            mtime_ns_test = int(mtime_ns_test / 10)
        unit = "ns"
        precision_unit = precision
        if precision >= 1000000000:
            precision_unit = int(precision / 1000000000)
            unit = "s"
        elif precision >= 1000000:
            precision_unit = int(precision / 1000000)
            unit = "ms"
        elif precision >= 1000:
            precision_unit = int(precision / 1000)
            unit = "us"
        os.remove(path)
        return (precision, precision_unit, unit)

    def __init__(self, configuration: config.Configuration) -> None:
        super().__init__(configuration)
        logger.info("Storage location: %r", self._filesystem_folder)
        self._makedirs_synced(self._filesystem_folder)
        logger.info("Storage location subfolder: %r", self._get_collection_root_folder())
        logger.info("Storage cache subfolder usage for 'item': %s", self._use_cache_subfolder_for_item)
        logger.info("Storage cache subfolder usage for 'history': %s", self._use_cache_subfolder_for_history)
        logger.info("Storage cache subfolder usage for 'sync-token': %s", self._use_cache_subfolder_for_synctoken)
        logger.info("Storage cache use mtime and size for 'item': %s", self._use_mtime_and_size_for_item_cache)
        (precision, precision_unit, unit) = self._analyse_mtime()
        if precision >= 100000000:
            # >= 100 ms
            logger.warning("Storage item mtime resolution test result: %d %s (VERY RISKY ON PRODUCTION SYSTEMS)" % (precision_unit, unit))
        elif precision >= 10000000:
            # >= 10 ms
            logger.warning("Storage item mtime resolution test result: %d %s (RISKY ON PRODUCTION SYSTEMS)" % (precision_unit, unit))
        else:
            logger.info("Storage item mtime resolution test result: %d %s" % (precision_unit, unit))
            if self._use_mtime_and_size_for_item_cache is False:
                logger.info("Storage cache using mtime and size for 'item' may be an option in case of performance issues")
        logger.debug("Storage cache action logging: %s", self._debug_cache_actions)
        if self._use_cache_subfolder_for_item is True or self._use_cache_subfolder_for_history is True or self._use_cache_subfolder_for_synctoken is True:
            logger.info("Storage cache subfolder: %r", self._get_collection_cache_folder())
            self._makedirs_synced(self._get_collection_cache_folder())
        if sys.platform != "win32":
            if not self._folder_umask:
                # retrieve current umask by setting a dummy umask
                current_umask = os.umask(0o0022)
                logger.info("Storage folder umask (from system): '%04o'", current_umask)
                # reset to original
                os.umask(current_umask)
            else:
                try:
                    config_umask = int(self._folder_umask, 8)
                except Exception:
                    logger.critical("storage folder umask defined but invalid: '%s'", self._folder_umask)
                    raise
                logger.info("storage folder umask defined: '%04o'", config_umask)
                self._config_umask = config_umask
