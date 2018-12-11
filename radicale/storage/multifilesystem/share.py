# This file is part of Radicale Server - Calendar Server
# Copyright © 2018 Unrud<unrud@outlook.com>
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

import json
import os

from radicale import pathutils


class CollectionShareMixin:

    def list_shares(self):
        if self._share:
            yield from self._base_collection.list_shares()
            return
        folder = self._get_collection_root_folder()
        for entry in os.scandir(folder):
            if (not entry.is_dir() or
                    not pathutils.is_safe_filesystem_path_component(
                        entry.name)):
                continue
            user = entry.name
            shares_path = os.path.join(folder, user, ".Radicale.shares")
            try:
                share_path = pathutils.path_to_filesystem(
                    shares_path, self.path)
            except ValueError:
                continue
            try:
                group_scanner = os.scandir(share_path)
            except FileNotFoundError:
                continue
            for group_entry in group_scanner:
                if (group_entry.name != ".Radicale.share_group" and
                        not group_entry.name.startswith(
                            ".Radicale.share_group_") or
                        entry.name == ".Radicale.share_group_"):
                    continue
                share_group = group_entry.name[len(".Radicale.share_group_"):]
                child_filesystem_path = os.path.join(
                    share_path, group_entry.name)
                share_uuid_path = os.path.join(
                    child_filesystem_path, ".Radicale.share")
                try:
                    with open(share_uuid_path, encoding=self._encoding) as f:
                        share_uuid = json.load(f)
                except FileNotFoundError:
                    continue
                except ValueError as e:
                    raise RuntimeError(
                        "Invalid share of collection %r to %r: %s" %
                        (self.path, user, e)) from e
                for share in self.shares:
                    if (share.uuid == share_uuid and
                            share.group == share_group):
                        break
                else:
                    continue
                if self.get_meta("tag") not in share.tags:
                    continue
                yield (user, share)
