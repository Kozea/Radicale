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
import logging
import os
import shlex
import signal
import subprocess
import sys
from typing import Iterator

from radicale import config, pathutils, types
from radicale.log import logger
from radicale.storage.multifilesystem.base import CollectionBase, StorageBase


class CollectionPartLock(CollectionBase):

    @types.contextmanager
    def _acquire_cache_lock(self, ns: str = "") -> Iterator[None]:
        if self._storage._lock.locked == "w":
            yield
            return
        cache_folder = os.path.join(self._filesystem_path, ".Radicale.cache")
        self._storage._makedirs_synced(cache_folder)
        lock_path = os.path.join(cache_folder,
                                 ".Radicale.lock" + (".%s" % ns if ns else ""))
        lock = pathutils.RwLock(lock_path)
        with lock.acquire("w"):
            yield


class StoragePartLock(StorageBase):

    _lock: pathutils.RwLock
    _hook: str

    def __init__(self, configuration: config.Configuration) -> None:
        super().__init__(configuration)
        lock_path = os.path.join(self._filesystem_folder, ".Radicale.lock")
        self._lock = pathutils.RwLock(lock_path)
        self._hook = configuration.get("storage", "hook")

    @types.contextmanager
    def acquire_lock(self, mode: str, user: str = "") -> Iterator[None]:
        with self._lock.acquire(mode):
            yield
            # execute hook
            if mode == "w" and self._hook:
                debug = logger.isEnabledFor(logging.DEBUG)
                # Use new process group for child to prevent terminals
                # from sending SIGINT etc.
                preexec_fn = None
                creationflags = 0
                if sys.platform == "win32":
                    creationflags |= subprocess.CREATE_NEW_PROCESS_GROUP
                else:
                    # Process group is also used to identify child processes
                    preexec_fn = os.setpgrp
                command = self._hook % {
                    "user": shlex.quote(user or "Anonymous")}
                logger.debug("Executing storage hook: '%s'" % command)
                try:
                    p = subprocess.Popen(
                        command, stdin=subprocess.DEVNULL,
                        stdout=subprocess.PIPE if debug else subprocess.DEVNULL,
                        stderr=subprocess.PIPE if debug else subprocess.DEVNULL,
                        shell=True, universal_newlines=True, preexec_fn=preexec_fn,
                        cwd=self._filesystem_folder, creationflags=creationflags)
                except Exception as e:
                    logger.error("Execution of storage hook not successful on 'Popen': %s" % e)
                    return
                logger.debug("Executing storage hook started 'Popen'")
                try:
                    stdout_data, stderr_data = p.communicate()
                except BaseException as e:  # e.g. KeyboardInterrupt or SystemExit
                    logger.error("Execution of storage hook not successful on 'communicate': %s" % e)
                    p.kill()
                    p.wait()
                    return
                finally:
                    if sys.platform != "win32":
                        # Kill remaining children identified by process group
                        with contextlib.suppress(OSError):
                            os.killpg(p.pid, signal.SIGKILL)
                logger.debug("Executing storage hook finished")
                if stdout_data:
                    logger.debug("Captured stdout from storage hook:\n%s", stdout_data)
                if stderr_data:
                    logger.debug("Captured stderr from storage hook:\n%s", stderr_data)
                if p.returncode != 0:
                    logger.error("Execution of storage hook not successful: %s" % subprocess.CalledProcessError(p.returncode, p.args))
                    return
