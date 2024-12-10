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

import contextlib
import itertools
import os
import pickle
from hashlib import sha256
from typing import BinaryIO, Iterable, Tuple, cast

from radicale.log import logger
from radicale.storage.multifilesystem.base import CollectionBase
from radicale.storage.multifilesystem.cache import CollectionPartCache
from radicale.storage.multifilesystem.history import CollectionPartHistory


class CollectionPartSync(CollectionPartCache, CollectionPartHistory,
                         CollectionBase):

    def sync(self, old_token: str = "") -> Tuple[str, Iterable[str]]:
        # The sync token has the form http://radicale.org/ns/sync/TOKEN_NAME
        # where TOKEN_NAME is the sha256 hash of all history etags of present
        # and past items of the collection.
        def check_token_name(token_name: str) -> bool:
            if len(token_name) != 64:
                return False
            for c in token_name:
                if c not in "0123456789abcdef":
                    return False
            return True

        old_token_name = ""
        if old_token:
            # Extract the token name from the sync token
            if not old_token.startswith("http://radicale.org/ns/sync/"):
                raise ValueError("Malformed token: %r" % old_token)
            old_token_name = old_token[len("http://radicale.org/ns/sync/"):]
            if not check_token_name(old_token_name):
                raise ValueError("Malformed token: %r" % old_token)
        # Get the current state and sync-token of the collection.
        state = {}
        token_name_hash = sha256()
        # Find the history of all existing and deleted items
        for href, item in itertools.chain(
                ((item.href, item) for item in self.get_all()),
                ((href, None) for href in self._get_deleted_history_hrefs())):
            history_etag = self._update_history_etag(href, item)
            state[href] = history_etag
            token_name_hash.update((href + "/" + history_etag).encode())
        token_name = token_name_hash.hexdigest()
        token = "http://radicale.org/ns/sync/%s" % token_name
        if token_name == old_token_name:
            # Nothing changed
            return token, ()
        token_folder = self._storage._get_collection_cache_subfolder(self._filesystem_path, ".Radicale.cache", "sync-token")
        token_path = os.path.join(token_folder, token_name)
        old_state = {}
        if old_token_name:
            # load the old token state
            old_token_path = os.path.join(token_folder, old_token_name)
            try:
                # Race: Another process might have deleted the file.
                with open(old_token_path, "rb") as f:
                    old_state = pickle.load(f)
            except (FileNotFoundError, pickle.UnpicklingError,
                    ValueError) as e:
                if isinstance(e, (pickle.UnpicklingError, ValueError)):
                    logger.warning(
                        "Failed to load stored sync token %r in %r: %s",
                        old_token_name, self.path, e, exc_info=True)
                    # Delete the damaged file
                    with contextlib.suppress(FileNotFoundError,
                                             PermissionError):
                        os.remove(old_token_path)
                raise ValueError("Token not found: %r" % old_token)
        # write the new token state or update the modification time of
        # existing token state
        if not os.path.exists(token_path):
            self._storage._makedirs_synced(token_folder)
            try:
                # Race: Other processes might have created and locked the file.
                # TODO: better fix for "mypy"
                with self._atomic_write(token_path, "wb") as fo:  # type: ignore
                    fb = cast(BinaryIO, fo)
                    pickle.dump(state, fb)
            except PermissionError:
                pass
            else:
                # clean up old sync tokens and item cache
                self._clean_cache(token_folder, os.listdir(token_folder),
                                  max_age=self._max_sync_token_age)
                self._clean_history()
        else:
            # Try to update the modification time
            with contextlib.suppress(FileNotFoundError):
                # Race: Another process might have deleted the file.
                os.utime(token_path)
        changes = []
        # Find all new, changed and deleted (that are still in the item cache)
        # items
        for href, history_etag in state.items():
            if history_etag != old_state.get(href):
                changes.append(href)
        # Find all deleted items that are no longer in the item cache
        for href, history_etag in old_state.items():
            if href not in state:
                changes.append(href)
        return token, changes
