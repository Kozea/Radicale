# This file is part of Radicale Server - Calendar Server
# Copyright © 2021 Unrud <unrud@outlook.com>
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
The multifilesystem backend without file-based locking.
"""

import threading
from collections import deque
from typing import Deque, Dict, Iterator, Tuple

from radicale import config, pathutils, types
from radicale.storage import multifilesystem


class RwLock(pathutils.RwLock):

    _cond: threading.Condition

    def __init__(self) -> None:
        super().__init__("")
        self._cond = threading.Condition(self._lock)

    @types.contextmanager
    def acquire(self, mode: str, user: str = "") -> Iterator[None]:
        if mode not in "rw":
            raise ValueError("Invalid mode: %r" % mode)
        with self._cond:
            self._cond.wait_for(lambda: not self._writer and (
                                    mode == "r" or self._readers == 0))
            if mode == "r":
                self._readers += 1
                self._cond.notify()
            else:
                self._writer = True
        try:
            yield
        finally:
            with self._cond:
                if mode == "r":
                    self._readers -= 1
                self._writer = False
                self._cond.notify()


class Collection(multifilesystem.Collection):

    _storage: "Storage"

    @types.contextmanager
    def _acquire_cache_lock(self, ns: str = "") -> Iterator[None]:
        if self._storage._lock.locked == "w":
            yield
            return
        key = (self.path, ns)
        with self._storage._cache_lock:
            waiters = self._storage._cache_locks.get(key)
            if waiters is None:
                self._storage._cache_locks[key] = waiters = deque()
            wait = bool(waiters)
            waiter = threading.Lock()
            waiter.acquire()
            waiters.append(waiter)
        if wait:
            waiter.acquire()
        try:
            yield
        finally:
            with self._storage._cache_lock:
                removedWaiter = waiters.popleft()
                assert removedWaiter is waiter
                if waiters:
                    waiters[0].release()
                else:
                    removedWaiters = self._storage._cache_locks.pop(key)
                    assert removedWaiters is waiters


class Storage(multifilesystem.Storage):

    _collection_class = Collection

    _cache_lock: threading.Lock
    _cache_locks: Dict[Tuple[str, str], Deque[threading.Lock]]

    def __init__(self, configuration: config.Configuration) -> None:
        super().__init__(configuration)
        self._lock = RwLock()
        self._cache_lock = threading.Lock()
        self._cache_locks = {}
