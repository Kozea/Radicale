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
import logging
import os
import shlex
import signal
import subprocess
import sys

from radicale import pathutils
from radicale.log import logger


class CollectionLockMixin:
    def _acquire_cache_lock(self, ns=""):
        if self._storage._lock.locked == "w":
            return contextlib.ExitStack()
        cache_folder = os.path.join(self._filesystem_path, ".Radicale.cache")
        self._storage._makedirs_synced(cache_folder)
        lock_path = os.path.join(cache_folder,
                                 ".Radicale.lock" + (".%s" % ns if ns else ""))
        lock = pathutils.RwLock(lock_path)
        return lock.acquire("w")


class StorageLockMixin:

    def __init__(self, configuration):
        super().__init__(configuration)
        folder = self.configuration.get("storage", "filesystem_folder")
        lock_path = os.path.join(folder, ".Radicale.lock")
        self._lock = pathutils.RwLock(lock_path)

    @contextlib.contextmanager
    def acquire_lock(self, mode, user=""):
        with self._lock.acquire(mode):
            yield
            # execute hook
            hook = self.configuration.get("storage", "hook")
            if mode == "w" and hook:
                folder = self.configuration.get("storage", "filesystem_folder")
                debug = logger.isEnabledFor(logging.DEBUG)
                popen_kwargs = dict(
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE if debug else subprocess.DEVNULL,
                    stderr=subprocess.PIPE if debug else subprocess.DEVNULL,
                    shell=True, universal_newlines=True, cwd=folder)
                # Use new process group for child to prevent terminals
                # from sending SIGINT etc.
                if os.name == "posix":
                    # Process group is also used to identify child processes
                    popen_kwargs["preexec_fn"] = os.setpgrp
                elif sys.platform == "win32":
                    popen_kwargs["creationflags"] = (
                        subprocess.CREATE_NEW_PROCESS_GROUP)
                command = hook % {"user": shlex.quote(user or "Anonymous")}
                logger.debug("Running storage hook")
                p = subprocess.Popen(command, **popen_kwargs)
                try:
                    stdout_data, stderr_data = p.communicate()
                except BaseException:  # e.g. KeyboardInterrupt or SystemExit
                    p.kill()
                    p.wait()
                    raise
                finally:
                    if os.name == "posix":
                        # Kill remaining children identified by process group
                        with contextlib.suppress(OSError):
                            os.killpg(p.pid, signal.SIGKILL)
                if stdout_data:
                    logger.debug("Captured stdout from hook:\n%s", stdout_data)
                if stderr_data:
                    logger.debug("Captured stderr from hook:\n%s", stderr_data)
                if p.returncode != 0:
                    raise subprocess.CalledProcessError(p.returncode, p.args)
