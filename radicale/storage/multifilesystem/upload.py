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

import os
import pickle

from Crypto.Cipher import AES
from Crypto import Random
import hashlib
import binascii


from radicale import item as radicale_item
from radicale import pathutils


class CollectionUploadMixin:
    def upload(self, href, item):
        if not pathutils.is_safe_filesystem_path_component(href):
            raise pathutils.UnsafePathError(href)
        try:
            self._store_item_cache(href, item)
        except Exception as e:
            raise ValueError("Failed to store item %r in collection %r: %s" %
                             (href, self.path, e)) from e
        path = pathutils.path_to_filesystem(self._filesystem_path, href)

        if self.configuration.getboolean("storage", "encrypt"):
            self.auth_file = self.configuration.get("auth", "htpasswd_filename")
            try:
                with open(self.auth_file) as f:
                    for line in f:
                        line = line.rstrip("\n")
                        if line.lstrip() and not line.lstrip().startswith("#"):
                            try:
                                hash_login, hash_value = line.split(
                                    ":", maxsplit=1)
                            except ValueError as e:
                                raise RuntimeError("Invalid htpasswd file %r: %s" %
                                                   (self.filename, e)) from e
            except OSError as e:
                raise RuntimeError("Failed to load htpasswd file %r: %s" %
                                   (self.filename, e)) from e
            key = hashlib.sha256(hash_value.encode()).digest()
            iv = Random.new().read(AES.block_size)
            enc_obj = AES.new(key, AES.MODE_CFB, iv)
            cipher_text = enc_obj.encrypt(item.serialize())
            cipher_text = iv + cipher_text
            cipher_text =  binascii.b2a_hex(cipher_text)
            cipher_text = cipher_text.decode()
            to_write = cipher_text
        else:
            to_write = item.serialize()

        with self._atomic_write(path, newline="") as fd:
            fd.write(to_write)

        # Clean the cache after the actual item is stored, or the cache entry
        # will be removed again.
        self._clean_item_cache()
        # Track the change
        self._update_history_etag(href, item)
        self._clean_history()
        return self._get(href, verify_href=False)

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
