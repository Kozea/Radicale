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

import contextlib
import json
import os

from radicale import pathutils
from radicale.log import logger

import posixpath  # isort:skip


class CollectionDiscoverMixin:
    @classmethod
    def discover(cls, path, depth="0", child_context_manager=(
                 lambda path, href=None: contextlib.ExitStack())):
        # Path should already be sanitized
        sane_path = pathutils.strip_path(path)
        attributes = sane_path.split("/") if sane_path else []

        folder = cls._get_collection_root_folder()
        # Create the root collection
        cls._makedirs_synced(folder)

        if (len(attributes) >= 1 and
                attributes[-1].startswith(".share_") or
                len(attributes) >= 2 and
                attributes[-1].startswith(".share_")):
            if attributes[-1].startswith(".share_"):
                href = None
            else:
                href = attributes.pop()
            parent_sane_path = "/".join(attributes[:-1])
            share_path = pathutils.unescape_shared_path(
                attributes[-1][len(".share"):])
            base_path, *share_group = share_path.rsplit("//", 1)
            if share_group:
                base_path += "/"
                share_group = share_group[0]
            else:
                share_group = ""
            if (base_path != pathutils.sanitize_path(base_path) or
                    not base_path.endswith("/")):
                return
            base_sane_path = pathutils.strip_path(base_path)
            for share in cls.shares:
                if share.group == share_group:
                    break
            else:
                return
            try:
                base_filesystem_path = pathutils.path_to_filesystem(
                    folder, base_sane_path)
                filesystem_path = os.path.join(pathutils.path_to_filesystem(
                    os.path.join(
                        pathutils.path_to_filesystem(folder, parent_sane_path),
                        ".Radicale.shares"),
                    base_sane_path), ".Radicale.share_group_%s" % share_group
                    if share_group else ".Radicale.share_group")
            except ValueError as e:
                # Path is unsafe
                logger.debug("Unsafe path %r requested from storage: %s",
                             sane_path, e, exc_info=True)
                return
            share_uuid_path = os.path.join(filesystem_path, ".Radicale.share")
            try:
                with open(share_uuid_path,  encoding=cls._encoding) as f:
                    share_uuid = json.load(f)
            except FileNotFoundError:
                return
            except ValueError as e:
                raise RuntimeError(
                    "Invalid share of collection %r to %r: %s" %
                    (base_sane_path, parent_sane_path, e)) from e
            if not os.path.isdir(base_filesystem_path):
                return
            for share in cls.shares:
                if share.uuid == share_uuid and share.group == share_group:
                    break
            else:
                return
            base_collection = cls(base_sane_path)
            if base_collection.get_meta("tag") not in share.tags:
                return
            collection = cls(
                sane_path, filesystem_path=filesystem_path,
                share=share, base_collection=base_collection)
            if href:
                yield collection._get(href)
                return
            yield collection
            if depth == "0":
                return
            for href in collection._list():
                with child_context_manager(sane_path, href):
                    child_item = collection._get(href)
                    if child_item:
                        yield child_item
            return

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
        collection = cls(sane_path)

        if href:
            yield collection._get(href)
            return

        yield collection

        if depth == "0":
            return

        for href in collection._list():
            with child_context_manager(sane_path, href):
                child_item = collection._get(href)
                if child_item:
                    yield child_item

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
            with child_context_manager(sane_child_path):
                yield cls(sane_child_path)

        def scan_shares(shares_folder, parent_sane_path=""):
            for entry in os.scandir(
                    os.path.join(shares_folder, parent_sane_path)):
                if not entry.is_dir():
                    continue
                if pathutils.is_safe_filesystem_path_component(entry.name):
                    base_sane_path = os.path.join(parent_sane_path, entry.name)
                    yield from scan_shares(shares_folder, base_sane_path)
                    continue
                if (entry.name != ".Radicale.share_group" and
                        not entry.name.startswith(".Radicale.share_group_") or
                        entry.name == ".Radicale.share_group_"):
                    continue
                share_group = entry.name[len(".Radicale.share_group_"):]
                base_sane_path = parent_sane_path
                child_filesystem_path = os.path.join(
                    shares_folder, base_sane_path, entry.name)
                share_uuid_path = os.path.join(
                    child_filesystem_path, ".Radicale.share")
                try:
                    with open(share_uuid_path, encoding=cls._encoding) as f:
                        share_uuid = json.load(f)
                except FileNotFoundError:
                    continue
                except ValueError as e:
                    raise RuntimeError(
                        "Invalid share of collection %r to %r: %s" %
                        (base_sane_path, sane_path, e)) from e
                for share in cls.shares:
                    if (share.uuid == share_uuid and
                            share.group == share_group):
                        break
                else:
                    continue
                try:
                    base_filesystem_path = pathutils.path_to_filesystem(
                        folder, base_sane_path)
                except ValueError:
                    continue
                if not os.path.isdir(base_filesystem_path):
                    continue
                base_collection = cls(base_sane_path)
                if base_collection.get_meta("tag") not in share.tags:
                    continue
                child_sane_path = os.path.join(
                    sane_path,
                    ".share%s" % pathutils.escape_shared_path(
                        pathutils.unstrip_path(base_sane_path, True) +
                        ("/%s" % share.group if share.group else "")))
                child_collection = cls(
                    child_sane_path, filesystem_path=child_filesystem_path,
                    share=share, base_collection=base_collection)
                yield child_collection

        shares_folder = os.path.join(filesystem_path, ".Radicale.shares")
        if os.path.isdir(shares_folder):
            yield from scan_shares(shares_folder)
