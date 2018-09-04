# This file is part of Radicale Server - Calendar Server
# Copyright © 2014 Jean-Marc Martins
# Copyright © 2012-2017 Guillaume Ayoub
# Copyright © 2017-2018 Unrud<unrud@outlook.com>
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

import binascii
import contextlib
import json
import logging
import os
import pickle
import posixpath
import shlex
import subprocess
import time
from contextlib import contextmanager
from hashlib import md5
from itertools import chain
from tempfile import NamedTemporaryFile, TemporaryDirectory

import vobject

from radicale import item as radicale_item
from radicale import pathutils, storage
from radicale.item import filter as radicale_filter
from radicale.log import logger


class Collection(storage.BaseCollection):
    """Collection stored in several files per calendar."""

    @classmethod
    def static_init(cls):
        # init storage lock
        folder = os.path.expanduser(cls.configuration.get(
            "storage", "filesystem_folder"))
        cls._makedirs_synced(folder)
        lock_path = os.path.join(folder, ".Radicale.lock")
        cls._lock = pathutils.RwLock(lock_path)

    def __init__(self, path, filesystem_path=None):
        folder = self._get_collection_root_folder()
        # Path should already be sanitized
        self.path = pathutils.strip_path(path)
        self._encoding = self.configuration.get("encoding", "stock")
        if filesystem_path is None:
            filesystem_path = pathutils.path_to_filesystem(folder, self.path)
        self._filesystem_path = filesystem_path
        self._props_path = os.path.join(
            self._filesystem_path, ".Radicale.props")
        self._meta_cache = None
        self._etag_cache = None
        self._item_cache_cleaned = False

    @classmethod
    def _get_collection_root_folder(cls):
        filesystem_folder = os.path.expanduser(
            cls.configuration.get("storage", "filesystem_folder"))
        return os.path.join(filesystem_folder, "collection-root")

    @contextmanager
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
        if cls.configuration.getboolean("internal", "filesystem_fsync"):
            pathutils.fsync(fd)

    @classmethod
    def _sync_directory(cls, path):
        """Sync directory to disk.

        This only works on POSIX and does nothing on other systems.

        """
        if not cls.configuration.getboolean("internal", "filesystem_fsync"):
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

    @classmethod
    def discover(cls, path, depth="0", child_context_manager=(
                 lambda path, href=None: contextlib.ExitStack())):
        # Path should already be sanitized
        sane_path = pathutils.strip_path(path)
        attributes = sane_path.split("/") if sane_path else []

        folder = cls._get_collection_root_folder()
        # Create the root collection
        cls._makedirs_synced(folder)
        try:
            filesystem_path = pathutils.path_to_filesystem(folder, sane_path)
        except ValueError as e:
            # Path is unsafe
            logger.debug("Unsafe path %r requested from storage: %s",
                         sane_path, e, exc_info=True)
            return

        # Check if the path exists and if it leads to a collection or an item
        if not os.path.isdir(filesystem_path):
            if attributes and os.path.isfile(filesystem_path):
                href = attributes.pop()
            else:
                return
        else:
            href = None

        sane_path = "/".join(attributes)
        collection = cls(pathutils.unstrip_path(sane_path, True))

        if href:
            yield collection._get(href)
            return

        yield collection

        if depth == "0":
            return

        for href in collection._list():
            with child_context_manager(sane_path, href):
                yield collection._get(href)

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
            with child_context_manager(sane_child_path):
                yield cls(child_path)

    @classmethod
    def verify(cls):
        item_errors = collection_errors = 0

        @contextlib.contextmanager
        def exception_cm(sane_path, href=None):
            nonlocal item_errors, collection_errors
            try:
                yield
            except Exception as e:
                if href:
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
            with exception_cm(sane_path):
                saved_item_errors = item_errors
                collection = None
                uids = set()
                has_child_collections = False
                for item in cls.discover(path, "1", exception_cm):
                    if not collection:
                        collection = item
                        collection.get_meta()
                        continue
                    if isinstance(item, storage.BaseCollection):
                        has_child_collections = True
                        remaining_sane_paths.append(item.path)
                    elif item.uid in uids:
                        cls.logger.error(
                            "Invalid item %r in %r: UID conflict %r",
                            item.href, sane_path, item.uid)
                    else:
                        uids.add(item.uid)
                        logger.debug("Verified item %r in %r",
                                     item.href, sane_path)
                if item_errors == saved_item_errors:
                    collection.sync()
                if has_child_collections and collection.get_meta("tag"):
                    cls.logger.error("Invalid collection %r: %r must not have "
                                     "child collections", sane_path,
                                     collection.get_meta("tag"))
        return item_errors == 0 and collection_errors == 0

    @classmethod
    def create_collection(cls, href, items=None, props=None):
        folder = cls._get_collection_root_folder()

        # Path should already be sanitized
        sane_path = pathutils.strip_path(href)
        filesystem_path = pathutils.path_to_filesystem(folder, sane_path)

        if not props:
            cls._makedirs_synced(filesystem_path)
            return cls(pathutils.unstrip_path(sane_path, True))

        parent_dir = os.path.dirname(filesystem_path)
        cls._makedirs_synced(parent_dir)

        # Create a temporary directory with an unsafe name
        with TemporaryDirectory(
                prefix=".Radicale.tmp-", dir=parent_dir) as tmp_dir:
            # The temporary directory itself can't be renamed
            tmp_filesystem_path = os.path.join(tmp_dir, "collection")
            os.makedirs(tmp_filesystem_path)
            self = cls(pathutils.unstrip_path(sane_path, True),
                       filesystem_path=tmp_filesystem_path)
            self.set_meta(props)
            if items is not None:
                if props.get("tag") == "VCALENDAR":
                    self._upload_all_nonatomic(items, suffix=".ics")
                elif props.get("tag") == "VADDRESSBOOK":
                    self._upload_all_nonatomic(items, suffix=".vcf")

            # This operation is not atomic on the filesystem level but it's
            # very unlikely that one rename operations succeeds while the
            # other fails or that only one gets written to disk.
            if os.path.exists(filesystem_path):
                os.rename(filesystem_path, os.path.join(tmp_dir, "delete"))
            os.rename(tmp_filesystem_path, filesystem_path)
            cls._sync_directory(parent_dir)

        return cls(pathutils.unstrip_path(sane_path, True))

    def _upload_all_nonatomic(self, items, suffix=""):
        """Upload a new set of items.

        This takes a list of vobject items and
        uploads them nonatomic and without existence checks.

        """
        cache_folder = os.path.join(self._filesystem_path,
                                    ".Radicale.cache", "item")
        self._makedirs_synced(cache_folder)
        hrefs = set()
        for item in items:
            uid = item.uid
            try:
                cache_content = self._item_cache_content(item)
            except Exception as e:
                raise ValueError(
                    "Failed to store item %r in temporary collection %r: %s" %
                    (uid, self.path, e)) from e
            href_candidates = []
            if os.name in ("nt", "posix"):
                href_candidates.append(
                    lambda: uid if uid.lower().endswith(suffix.lower())
                    else uid + suffix)
            href_candidates.extend((
                lambda: radicale_item.get_etag(uid).strip('"') + suffix,
                lambda: radicale_item.find_available_uid(hrefs.__contains__,
                                                         suffix)))
            href = None

            def replace_fn(source, target):
                nonlocal href
                while href_candidates:
                    href = href_candidates.pop(0)()
                    if href in hrefs:
                        continue
                    if not pathutils.is_safe_filesystem_path_component(href):
                        if not href_candidates:
                            raise pathutils.UnsafePathError(href)
                        continue
                    try:
                        return os.replace(source, pathutils.path_to_filesystem(
                            self._filesystem_path, href))
                    except OSError as e:
                        if href_candidates and (
                                os.name == "posix" and e.errno == 22 or
                                os.name == "nt" and e.errno == 123):
                            continue
                        raise

            with self._atomic_write(os.path.join(self._filesystem_path, "ign"),
                                    newline="", sync_directory=False,
                                    replace_fn=replace_fn) as f:
                f.write(item.serialize())
            hrefs.add(href)
            with self._atomic_write(os.path.join(cache_folder, href), "wb",
                                    sync_directory=False) as f:
                pickle.dump(cache_content, f)
        self._sync_directory(cache_folder)
        self._sync_directory(self._filesystem_path)

    @classmethod
    def move(cls, item, to_collection, to_href):
        if not pathutils.is_safe_filesystem_path_component(to_href):
            raise pathutils.UnsafePathError(to_href)
        os.replace(
            pathutils.path_to_filesystem(
                item.collection._filesystem_path, item.href),
            pathutils.path_to_filesystem(
                to_collection._filesystem_path, to_href))
        cls._sync_directory(to_collection._filesystem_path)
        if item.collection._filesystem_path != to_collection._filesystem_path:
            cls._sync_directory(item.collection._filesystem_path)
        # Move the item cache entry
        cache_folder = os.path.join(item.collection._filesystem_path,
                                    ".Radicale.cache", "item")
        to_cache_folder = os.path.join(to_collection._filesystem_path,
                                       ".Radicale.cache", "item")
        cls._makedirs_synced(to_cache_folder)
        try:
            os.replace(os.path.join(cache_folder, item.href),
                       os.path.join(to_cache_folder, to_href))
        except FileNotFoundError:
            pass
        else:
            cls._makedirs_synced(to_cache_folder)
            if cache_folder != to_cache_folder:
                cls._makedirs_synced(cache_folder)
        # Track the change
        to_collection._update_history_etag(to_href, item)
        item.collection._update_history_etag(item.href, None)
        to_collection._clean_history_cache()
        if item.collection._filesystem_path != to_collection._filesystem_path:
            item.collection._clean_history_cache()

    @classmethod
    def _clean_cache(cls, folder, names, max_age=None):
        """Delete all ``names`` in ``folder`` that are older than ``max_age``.
        """
        age_limit = time.time() - max_age if max_age is not None else None
        modified = False
        for name in names:
            if not pathutils.is_safe_filesystem_path_component(name):
                continue
            if age_limit is not None:
                try:
                    # Race: Another process might have deleted the file.
                    mtime = os.path.getmtime(os.path.join(folder, name))
                except FileNotFoundError:
                    continue
                if mtime > age_limit:
                    continue
            logger.debug("Found expired item in cache: %r", name)
            # Race: Another process might have deleted or locked the
            # file.
            try:
                os.remove(os.path.join(folder, name))
            except (FileNotFoundError, PermissionError):
                continue
            modified = True
        if modified:
            cls._sync_directory(folder)

    def _update_history_etag(self, href, item):
        """Updates and retrieves the history etag from the history cache.

        The history cache contains a file for each current and deleted item
        of the collection. These files contain the etag of the item (empty
        string for deleted items) and a history etag, which is a hash over
        the previous history etag and the etag separated by "/".
        """
        history_folder = os.path.join(self._filesystem_path,
                                      ".Radicale.cache", "history")
        try:
            with open(os.path.join(history_folder, href), "rb") as f:
                cache_etag, history_etag = pickle.load(f)
        except (FileNotFoundError, pickle.UnpicklingError, ValueError) as e:
            if isinstance(e, (pickle.UnpicklingError, ValueError)):
                logger.warning(
                    "Failed to load history cache entry %r in %r: %s",
                    href, self.path, e, exc_info=True)
            cache_etag = ""
            # Initialize with random data to prevent collisions with cleaned
            # expired items.
            history_etag = binascii.hexlify(os.urandom(16)).decode("ascii")
        etag = item.etag if item else ""
        if etag != cache_etag:
            self._makedirs_synced(history_folder)
            history_etag = radicale_item.get_etag(
                history_etag + "/" + etag).strip("\"")
            try:
                # Race: Other processes might have created and locked the file.
                with self._atomic_write(os.path.join(history_folder, href),
                                        "wb") as f:
                    pickle.dump([etag, history_etag], f)
            except PermissionError:
                pass
        return history_etag

    def _get_deleted_history_hrefs(self):
        """Returns the hrefs of all deleted items that are still in the
        history cache."""
        history_folder = os.path.join(self._filesystem_path,
                                      ".Radicale.cache", "history")
        try:
            for entry in os.scandir(history_folder):
                href = entry.name
                if not pathutils.is_safe_filesystem_path_component(href):
                    continue
                if os.path.isfile(os.path.join(self._filesystem_path, href)):
                    continue
                yield href
        except FileNotFoundError:
            pass

    def _clean_history_cache(self):
        # Delete all expired cache entries of deleted items.
        history_folder = os.path.join(self._filesystem_path,
                                      ".Radicale.cache", "history")
        self._clean_cache(history_folder, self._get_deleted_history_hrefs(),
                          max_age=self.configuration.getint(
                              "storage", "max_sync_token_age"))

    def sync(self, old_token=None):
        # The sync token has the form http://radicale.org/ns/sync/TOKEN_NAME
        # where TOKEN_NAME is the md5 hash of all history etags of present and
        # past items of the collection.
        def check_token_name(token_name):
            if len(token_name) != 32:
                return False
            for c in token_name:
                if c not in "0123456789abcdef":
                    return False
            return True

        old_token_name = None
        if old_token:
            # Extract the token name from the sync token
            if not old_token.startswith("http://radicale.org/ns/sync/"):
                raise ValueError("Malformed token: %r" % old_token)
            old_token_name = old_token[len("http://radicale.org/ns/sync/"):]
            if not check_token_name(old_token_name):
                raise ValueError("Malformed token: %r" % old_token)
        # Get the current state and sync-token of the collection.
        state = {}
        token_name_hash = md5()
        # Find the history of all existing and deleted items
        for href, item in chain(
                ((item.href, item) for item in self.get_all()),
                ((href, None) for href in self._get_deleted_history_hrefs())):
            history_etag = self._update_history_etag(href, item)
            state[href] = history_etag
            token_name_hash.update((href + "/" + history_etag).encode("utf-8"))
        token_name = token_name_hash.hexdigest()
        token = "http://radicale.org/ns/sync/%s" % token_name
        if token_name == old_token_name:
            # Nothing changed
            return token, ()
        token_folder = os.path.join(self._filesystem_path,
                                    ".Radicale.cache", "sync-token")
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
                    try:
                        os.remove(old_token_path)
                    except (FileNotFoundError, PermissionError):
                        pass
                raise ValueError("Token not found: %r" % old_token)
        # write the new token state or update the modification time of
        # existing token state
        if not os.path.exists(token_path):
            self._makedirs_synced(token_folder)
            try:
                # Race: Other processes might have created and locked the file.
                with self._atomic_write(token_path, "wb") as f:
                    pickle.dump(state, f)
            except PermissionError:
                pass
            else:
                # clean up old sync tokens and item cache
                self._clean_cache(token_folder, os.listdir(token_folder),
                                  max_age=self.configuration.getint(
                                      "storage", "max_sync_token_age"))
                self._clean_history_cache()
        else:
            # Try to update the modification time
            try:
                # Race: Another process might have deleted the file.
                os.utime(token_path)
            except FileNotFoundError:
                pass
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

    def _list(self):
        for entry in os.scandir(self._filesystem_path):
            if not entry.is_file():
                continue
            href = entry.name
            if not pathutils.is_safe_filesystem_path_component(href):
                if not href.startswith(".Radicale"):
                    logger.debug("Skipping item %r in %r", href, self.path)
                continue
            yield href

    def _item_cache_hash(self, raw_text):
        _hash = md5()
        _hash.update(storage.CACHE_VERSION)
        _hash.update(raw_text)
        return _hash.hexdigest()

    def _item_cache_content(self, item, cache_hash=None):
        text = item.serialize()
        if cache_hash is None:
            cache_hash = self._item_cache_hash(text.encode(self._encoding))
        return (cache_hash, item.uid, item.etag, text, item.name,
                item.component_name, *item.time_range)

    def _store_item_cache(self, href, item, cache_hash=None):
        cache_folder = os.path.join(self._filesystem_path, ".Radicale.cache",
                                    "item")
        content = self._item_cache_content(item, cache_hash)
        self._makedirs_synced(cache_folder)
        try:
            # Race: Other processes might have created and locked the
            # file.
            with self._atomic_write(os.path.join(cache_folder, href),
                                    "wb") as f:
                pickle.dump(content, f)
        except PermissionError:
            pass
        return content

    def _acquire_cache_lock(self, ns=""):
        if self._lock.locked == "w":
            return contextlib.ExitStack()
        cache_folder = os.path.join(self._filesystem_path, ".Radicale.cache")
        self._makedirs_synced(cache_folder)
        lock_path = os.path.join(cache_folder,
                                 ".Radicale.lock" + (".%s" % ns if ns else ""))
        lock = pathutils.RwLock(lock_path)
        return lock.acquire("w")

    def _load_item_cache(self, href, input_hash):
        cache_folder = os.path.join(self._filesystem_path, ".Radicale.cache",
                                    "item")
        cache_hash = uid = etag = text = name = tag = start = end = None
        try:
            with open(os.path.join(cache_folder, href), "rb") as f:
                cache_hash, *content = pickle.load(f)
                if cache_hash == input_hash:
                    uid, etag, text, name, tag, start, end = content
        except FileNotFoundError as e:
            pass
        except (pickle.UnpicklingError, ValueError) as e:
            logger.warning("Failed to load item cache entry %r in %r: %s",
                           href, self.path, e, exc_info=True)
        return cache_hash, uid, etag, text, name, tag, start, end

    def _clean_item_cache(self):
        cache_folder = os.path.join(self._filesystem_path, ".Radicale.cache",
                                    "item")
        self._clean_cache(cache_folder, (
            e.name for e in os.scandir(cache_folder) if not
            os.path.isfile(os.path.join(self._filesystem_path, e.name))))

    def _get(self, href, verify_href=True):
        if verify_href:
            try:
                if not pathutils.is_safe_filesystem_path_component(href):
                    raise pathutils.UnsafePathError(href)
                path = pathutils.path_to_filesystem(
                    self._filesystem_path, href)
            except ValueError as e:
                logger.debug(
                    "Can't translate name %r safely to filesystem in %r: %s",
                    href, self.path, e, exc_info=True)
                return None
        else:
            path = os.path.join(self._filesystem_path, href)
        try:
            with open(path, "rb") as f:
                raw_text = f.read()
        except (FileNotFoundError, IsADirectoryError):
            return None
        except PermissionError:
            # Windows raises ``PermissionError`` when ``path`` is a directory
            if (os.name == "nt" and
                    os.path.isdir(path) and os.access(path, os.R_OK)):
                return None
            raise
        # The hash of the component in the file system. This is used to check,
        # if the entry in the cache is still valid.
        input_hash = self._item_cache_hash(raw_text)
        cache_hash, uid, etag, text, name, tag, start, end = \
            self._load_item_cache(href, input_hash)
        if input_hash != cache_hash:
            with self._acquire_cache_lock("item"):
                # Lock the item cache to prevent multpile processes from
                # generating the same data in parallel.
                # This improves the performance for multiple requests.
                if self._lock.locked == "r":
                    # Check if another process created the file in the meantime
                    cache_hash, uid, etag, text, name, tag, start, end = \
                        self._load_item_cache(href, input_hash)
                if input_hash != cache_hash:
                    try:
                        vobject_items = tuple(vobject.readComponents(
                            raw_text.decode(self._encoding)))
                        radicale_item.check_and_sanitize_items(
                            vobject_items, tag=self.get_meta("tag"))
                        vobject_item, = vobject_items
                        temp_item = radicale_item.Item(
                            collection=self, vobject_item=vobject_item)
                        cache_hash, uid, etag, text, name, tag, start, end = \
                            self._store_item_cache(
                                href, temp_item, input_hash)
                    except Exception as e:
                        raise RuntimeError("Failed to load item %r in %r: %s" %
                                           (href, self.path, e)) from e
                    # Clean cache entries once after the data in the file
                    # system was edited externally.
                    if not self._item_cache_cleaned:
                        self._item_cache_cleaned = True
                        self._clean_item_cache()
        last_modified = time.strftime(
            "%a, %d %b %Y %H:%M:%S GMT",
            time.gmtime(os.path.getmtime(path)))
        # Don't keep reference to ``vobject_item``, because it requires a lot
        # of memory.
        return radicale_item.Item(
            collection=self, href=href, last_modified=last_modified, etag=etag,
            text=text, uid=uid, name=name, component_name=tag,
            time_range=(start, end))

    def get_multi(self, hrefs):
        # It's faster to check for file name collissions here, because
        # we only need to call os.listdir once.
        files = None
        for href in hrefs:
            if files is None:
                # List dir after hrefs returned one item, the iterator may be
                # empty and the for-loop is never executed.
                files = os.listdir(self._filesystem_path)
            path = os.path.join(self._filesystem_path, href)
            if (not pathutils.is_safe_filesystem_path_component(href) or
                    href not in files and os.path.lexists(path)):
                logger.debug(
                    "Can't translate name safely to filesystem: %r", href)
                yield (href, None)
            else:
                yield (href, self._get(href, verify_href=False))

    def get_all(self):
        # We don't need to check for collissions, because the the file names
        # are from os.listdir.
        return (self._get(href, verify_href=False) for href in self._list())

    def get_filtered(self, filters):
        tag, start, end, simple = radicale_filter.simplify_prefilters(
            filters, collection_tag=self.get_meta("tag"))
        if not tag:
            # no filter
            yield from ((item, simple) for item in self.get_all())
            return
        for item in (self._get(h, verify_href=False) for h in self._list()):
            istart, iend = item.time_range
            if tag == item.component_name and istart < end and iend > start:
                yield item, simple and (start <= istart or iend <= end)

    def upload(self, href, item):
        if not pathutils.is_safe_filesystem_path_component(href):
            raise pathutils.UnsafePathError(href)
        try:
            self._store_item_cache(href, item)
        except Exception as e:
            raise ValueError("Failed to store item %r in collection %r: %s" %
                             (href, self.path, e)) from e
        path = pathutils.path_to_filesystem(self._filesystem_path, href)
        with self._atomic_write(path, newline="") as fd:
            fd.write(item.serialize())
        # Clean the cache after the actual item is stored, or the cache entry
        # will be removed again.
        self._clean_item_cache()
        # Track the change
        self._update_history_etag(href, item)
        self._clean_history_cache()
        return self._get(href, verify_href=False)

    def delete(self, href=None):
        if href is None:
            # Delete the collection
            parent_dir = os.path.dirname(self._filesystem_path)
            try:
                os.rmdir(self._filesystem_path)
            except OSError:
                with TemporaryDirectory(
                        prefix=".Radicale.tmp-", dir=parent_dir) as tmp:
                    os.rename(self._filesystem_path, os.path.join(
                        tmp, os.path.basename(self._filesystem_path)))
                    self._sync_directory(parent_dir)
            else:
                self._sync_directory(parent_dir)
        else:
            # Delete an item
            if not pathutils.is_safe_filesystem_path_component(href):
                raise pathutils.UnsafePathError(href)
            path = pathutils.path_to_filesystem(self._filesystem_path, href)
            if not os.path.isfile(path):
                raise storage.ComponentNotFoundError(href)
            os.remove(path)
            self._sync_directory(os.path.dirname(path))
            # Track the change
            self._update_history_etag(href, None)
            self._clean_history_cache()

    def get_meta(self, key=None):
        # reuse cached value if the storage is read-only
        if self._lock.locked == "w" or self._meta_cache is None:
            try:
                try:
                    with open(self._props_path, encoding=self._encoding) as f:
                        self._meta_cache = json.load(f)
                except FileNotFoundError:
                    self._meta_cache = {}
                radicale_item.check_and_sanitize_props(self._meta_cache)
            except ValueError as e:
                raise RuntimeError("Failed to load properties of collection "
                                   "%r: %s" % (self.path, e)) from e
        return self._meta_cache.get(key) if key else self._meta_cache

    def set_meta(self, props):
        with self._atomic_write(self._props_path, "w") as f:
            json.dump(props, f, sort_keys=True)

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

    @classmethod
    @contextmanager
    def acquire_lock(cls, mode, user=None):
        with cls._lock.acquire(mode):
            yield
            # execute hook
            hook = cls.configuration.get("storage", "hook")
            if mode == "w" and hook:
                folder = os.path.expanduser(cls.configuration.get(
                    "storage", "filesystem_folder"))
                logger.debug("Running hook")
                debug = logger.isEnabledFor(logging.DEBUG)
                p = subprocess.Popen(
                    hook % {"user": shlex.quote(user or "Anonymous")},
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE if debug else subprocess.DEVNULL,
                    stderr=subprocess.PIPE if debug else subprocess.DEVNULL,
                    shell=True, universal_newlines=True, cwd=folder)
                stdout_data, stderr_data = p.communicate()
                if stdout_data:
                    logger.debug("Captured stdout hook:\n%s", stdout_data)
                if stderr_data:
                    logger.debug("Captured stderr hook:\n%s", stderr_data)
                if p.returncode != 0:
                    raise subprocess.CalledProcessError(p.returncode, p.args)
