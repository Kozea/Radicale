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

import base64
import os
import posixpath
from typing import Callable, ContextManager, Iterator, Optional, Set, cast

from radicale import pathutils, types
from radicale.log import logger
from radicale.storage import multifilesystem
from radicale.storage.multifilesystem.base import StorageBase


@types.contextmanager
def _null_child_context_manager(path: str,
                                href: Optional[str]) -> Iterator[None]:
    yield


class StoragePartDiscover(StorageBase):

    def discover(
            self, path: str, depth: str = "0",
            child_context_manager: Optional[
            Callable[[str, Optional[str]], ContextManager[None]]] = None,
            user_groups: Set[str] = set([])
            ) -> Iterator[types.CollectionOrItem]:
        # assert isinstance(self, multifilesystem.Storage)
        if child_context_manager is None:
            child_context_manager = _null_child_context_manager
        # Path should already be sanitized
        sane_path = pathutils.strip_path(path)
        attributes = sane_path.split("/") if sane_path else []

        folder = self._get_collection_root_folder()
        # Create the root collection
        self._makedirs_synced(folder)
        try:
            filesystem_path = pathutils.path_to_filesystem(folder, sane_path)
        except ValueError as e:
            # Path is unsafe
            logger.debug("Unsafe path %r requested from storage: %s",
                         sane_path, e, exc_info=True)
            return

        # Check if the path exists and if it leads to a collection or an item
        href: Optional[str]
        if not os.path.isdir(filesystem_path):
            if attributes and os.path.isfile(filesystem_path):
                href = attributes.pop()
            else:
                return
        else:
            href = None

        sane_path = "/".join(attributes)
        collection = self._collection_class(
            cast(multifilesystem.Storage, self),
            pathutils.unstrip_path(sane_path, True))

        if href:
            item = collection._get(href)
            if item is not None:
                yield item
            return

        yield collection

        if depth == "0":
            return

        for href in collection._list():
            with child_context_manager(sane_path, href):
                item = collection._get(href)
                if item is not None:
                    yield item

        for entry in os.scandir(filesystem_path):
            if not entry.is_dir():
                continue
            href = entry.name
            if not pathutils.is_safe_filesystem_path_component(href):
                if not href.startswith(".Radicale"):
                    logger.debug("Skipping collection %r in %r",
                                 href, sane_path)
                continue
            sane_child_path = posixpath.join(sane_path, href)
            child_path = pathutils.unstrip_path(sane_child_path, True)
            with child_context_manager(sane_child_path, None):
                yield self._collection_class(
                    cast(multifilesystem.Storage, self), child_path)
        for group in user_groups:
            href = base64.b64encode(group.encode('utf-8')).decode('ascii')
            logger.debug(f"searching for group calendar {group} {href}")
            sane_child_path = f"GROUPS/{href}"
            if not os.path.isdir(pathutils.path_to_filesystem(folder, sane_child_path)):
                continue
            child_path = f"/GROUPS/{href}/"
            with child_context_manager(sane_child_path, None):
                yield self._collection_class(
                    cast(multifilesystem.Storage, self), child_path)
