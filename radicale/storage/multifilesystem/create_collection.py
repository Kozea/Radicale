# This file is part of Radicale Server - Calendar Server
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

import os
from tempfile import TemporaryDirectory

from radicale import pathutils


class CollectionCreateCollectionMixin:
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
