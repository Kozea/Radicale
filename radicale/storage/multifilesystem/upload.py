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

import errno
import os
import pickle
import sys
from typing import Iterable, Iterator, Optional, TextIO, cast

import radicale.item as radicale_item
from radicale import pathutils
from radicale.log import logger
from radicale.privacy.database import PrivacyDatabase
from radicale.storage.multifilesystem.base import CollectionBase
from radicale.storage.multifilesystem.cache import CollectionPartCache
from radicale.storage.multifilesystem.get import CollectionPartGet
from radicale.storage.multifilesystem.history import CollectionPartHistory


class CollectionPartUpload(CollectionPartGet, CollectionPartCache,
                           CollectionPartHistory, CollectionBase):

    _privacy_db: Optional[PrivacyDatabase] = None

    def upload(self, href: str, item: radicale_item.Item
               ) -> radicale_item.Item:
        if not pathutils.is_safe_filesystem_path_component(href):
            raise pathutils.UnsafePathError(href)
        path = pathutils.path_to_filesystem(self._filesystem_path, href)

        # Debug logging for item properties
        logger.debug("Item component name: %r", item.component_name)
        logger.debug("Item name: %r", item.name)
        logger.debug("Item type: %r", type(item))

        # Check for privacy settings if this is a VCF file
        if item.component_name == "VCARD" or item.name == "VCARD":
            logger.info("Intercepted vCard upload:")
            logger.info("vCard content:\n%s", item.serialize())

            # Lazy init privacy db
            if not hasattr(self, '_privacy_db') or self._privacy_db is None:
                self._privacy_db = PrivacyDatabase(self._storage.configuration)
                self._privacy_db.init_db()

            # Get email from vCard
            email = None
            vcard = item.vobject_item
            if hasattr(vcard, "email_list"):
                for email_prop in vcard.email_list:
                    email = email_prop.value
                    logger.info("Found email in vCard: %r", email)
                    break
            if email:
                # Get privacy settings for this email
                privacy_settings = self._privacy_db.get_user_settings(email)
                logger.info("Privacy settings for %r: %r", email, privacy_settings)
                if privacy_settings:
                    # Log all privacy settings
                    logger.info("Privacy settings details:")
                    logger.info("  Name disallowed: %r", privacy_settings.disallow_name)
                    logger.info("  Email disallowed: %r", privacy_settings.disallow_email)
                    logger.info("  Phone disallowed: %r", privacy_settings.disallow_phone)
                    logger.info("  Company disallowed: %r", privacy_settings.disallow_company)
                    logger.info("  Title disallowed: %r", privacy_settings.disallow_title)
                    logger.info("  Photo disallowed: %r", privacy_settings.disallow_photo)
                    logger.info("  Birthday disallowed: %r", privacy_settings.disallow_birthday)
                    logger.info("  Address disallowed: %r", privacy_settings.disallow_address)

                    # TODO: Apply privacy settings to vCard
                    # For each field in the vCard, check if it's allowed
                    # and modify/remove if not allowed
                else:
                    logger.info("No privacy settings found for %r", email)
            else:
                logger.info("No email found in vCard")
        else:
            logger.debug("Not a VCF file")

        try:
            with self._atomic_write(path, newline="") as fo:  # type: ignore
                f = cast(TextIO, fo)
                f.write(item.serialize())
        except Exception as e:
            raise ValueError("Failed to store item %r in collection %r: %s" %
                             (href, self.path, e)) from e
        # store cache file
        if self._storage._use_mtime_and_size_for_item_cache is True:
            cache_hash = self._item_cache_mtime_and_size(os.stat(path).st_size, os.stat(path).st_mtime_ns)
            if self._storage._debug_cache_actions is True:
                logger.debug("Item cache store  for: %r with mtime and size %r", path, cache_hash)
        else:
            cache_hash = self._item_cache_hash(item.serialize().encode(self._encoding))
            if self._storage._debug_cache_actions is True:
                logger.debug("Item cache store  for: %r with hash %r", path, cache_hash)
        try:
            self._store_item_cache(href, item, cache_hash)
        except Exception as e:
            raise ValueError("Failed to store item cache of %r in collection %r: %s" %
                             (href, self.path, e)) from e
        # Track the change
        self._update_history_etag(href, item)
        self._clean_history()
        uploaded_item = self._get(href, verify_href=False)
        if uploaded_item is None:
            raise RuntimeError("Storage modified externally")
        return uploaded_item

    def _upload_all_nonatomic(self, items: Iterable[radicale_item.Item],
                              suffix: str = "") -> None:
        """Upload a new set of items non-atomic"""
        def is_safe_free_href(href: str) -> bool:
            return (pathutils.is_safe_filesystem_path_component(href) and
                    not os.path.lexists(
                        os.path.join(self._filesystem_path, href)))

        def get_safe_free_hrefs(uid: str) -> Iterator[str]:
            for href in [uid if uid.lower().endswith(suffix.lower())
                         else uid + suffix,
                         radicale_item.get_etag(uid).strip('"') + suffix]:
                if is_safe_free_href(href):
                    yield href
            yield radicale_item.find_available_uid(
                lambda href: not is_safe_free_href(href), suffix)

        cache_folder = self._storage._get_collection_cache_subfolder(self._filesystem_path, ".Radicale.cache", "item")
        self._storage._makedirs_synced(cache_folder)
        for item in items:
            uid = item.uid
            logger.debug("Store item from list with uid: '%s'" % uid)
            cache_content = self._item_cache_content(item)
            for href in get_safe_free_hrefs(uid):
                path = os.path.join(self._filesystem_path, href)
                try:
                    f = open(path,
                             "w", newline="", encoding=self._encoding)
                except OSError as e:
                    if (sys.platform != "win32" and e.errno == errno.EINVAL or
                            sys.platform == "win32" and e.errno == 123):
                        # not a valid filename
                        continue
                    raise
                break
            else:
                raise RuntimeError("No href found for item %r in temporary "
                                   "collection %r" % (uid, self.path))

            try:
                with f:
                    f.write(item.serialize())
                    f.flush()
                    self._storage._fsync(f)
            except Exception as e:
                raise ValueError(
                    "Failed to store item %r in temporary collection %r: %s" %
                    (uid, self.path, e)) from e

            # store cache file
            if self._storage._use_mtime_and_size_for_item_cache is True:
                cache_hash = self._item_cache_mtime_and_size(os.stat(path).st_size, os.stat(path).st_mtime_ns)
                if self._storage._debug_cache_actions is True:
                    logger.debug("Item cache store  for: %r with mtime and size %r", path, cache_hash)
            else:
                cache_hash = self._item_cache_hash(item.serialize().encode(self._encoding))
                if self._storage._debug_cache_actions is True:
                    logger.debug("Item cache store  for: %r with hash %r", path, cache_hash)
            path_cache = os.path.join(cache_folder, href)
            if self._storage._debug_cache_actions is True:
                logger.debug("Item cache store into: %r", path_cache)
            with open(os.path.join(cache_folder, href), "wb") as fb:
                pickle.dump((cache_hash, *cache_content), fb)
                fb.flush()
                self._storage._fsync(fb)
        self._storage._sync_directory(cache_folder)
        self._storage._sync_directory(self._filesystem_path)

    def close_privacy_db(self):
        if hasattr(self, '_privacy_db') and self._privacy_db:
            self._privacy_db.close()
            self._privacy_db = None
