# This file is part of Radicale - CalDAV and CardDAV server
# Copyright © 2014 Jean-Marc Martins
# Copyright © 2012-2017 Guillaume Ayoub
# Copyright © 2017-2018 Unrud <unrud@outlook.com>
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

from typing import Iterator, Optional, Set

from radicale import pathutils, storage, types
from radicale.log import logger
from radicale.storage.multifilesystem.base import StorageBase
from radicale.storage.multifilesystem.discover import StoragePartDiscover


class StoragePartVerify(StoragePartDiscover, StorageBase):

    def verify(self) -> bool:
        item_errors = collection_errors = 0

        @types.contextmanager
        def exception_cm(sane_path: str, href: Optional[str]
                         ) -> Iterator[None]:
            nonlocal item_errors, collection_errors
            try:
                yield
            except Exception as e:
                if href is not None:
                    item_errors += 1
                    name = "item %r in %r" % (href, sane_path)
                else:
                    collection_errors += 1
                    name = "collection %r" % sane_path
                logger.error("Invalid %s: %s", name, e, exc_info=True)

        remaining_sane_paths = [""]
        while remaining_sane_paths:
            sane_path = remaining_sane_paths.pop(0)
            path = pathutils.unstrip_path(sane_path, True)
            logger.debug("Verifying collection %r", sane_path)
            with exception_cm(sane_path, None):
                saved_item_errors = item_errors
                collection: Optional[storage.BaseCollection] = None
                uids: Set[str] = set()
                has_child_collections = False
                for item in self.discover(path, "1", exception_cm):
                    if not collection:
                        assert isinstance(item, storage.BaseCollection)
                        collection = item
                        collection.get_meta()
                        continue
                    if isinstance(item, storage.BaseCollection):
                        has_child_collections = True
                        remaining_sane_paths.append(item.path)
                    elif item.uid in uids:
                        logger.error("Invalid item %r in %r: UID conflict %r",
                                     item.href, sane_path, item.uid)
                    else:
                        uids.add(item.uid)
                        logger.debug("Verified item %r in %r",
                                     item.href, sane_path)
                assert collection
                if item_errors == saved_item_errors:
                    collection.sync()
                if has_child_collections and collection.tag:
                    logger.error("Invalid collection %r: %r must not have "
                                 "child collections", sane_path,
                                 collection.tag)
        return item_errors == 0 and collection_errors == 0
