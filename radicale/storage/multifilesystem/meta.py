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

import json
import os

from radicale import item as radicale_item


class CollectionMetaMixin:
    def __init__(self):
        super().__init__()
        self._meta_cache = None
        self._props_path = os.path.join(
            self._filesystem_path, ".Radicale.props")

    def get_meta(self, key=None):
        # reuse cached value if the storage is read-only
        if self._lock.locked == "w" or self._meta_cache is None:
            try:
                try:
                    with open(self._props_path, encoding=self._encoding) as f:
                        self._meta_cache = json.load(f)
                except FileNotFoundError:
                    self._meta_cache = {}
                if self._share:
                    self._meta_cache = self._share.get_meta(
                        self._meta_cache, self._base_collection.get_meta())
                radicale_item.check_and_sanitize_props(self._meta_cache)
            except ValueError as e:
                raise RuntimeError("Failed to load properties of collection "
                                   "%r: %s" % (self.path, e)) from e
        return self._meta_cache.get(key) if key else self._meta_cache

    def set_meta(self, props):
        if self._share:
            props, base_props = self._share.set_meta(
                props, self.get_meta(), self._base_collection.get_meta())
            with self._atomic_write(self._props_path, "w") as f1,\
                    self._atomic_write(
                        self._base_collection._props_path, "w") as f2:
                json.dump(props, f1, sort_keys=True)
                json.dump(base_props, f2, sort_keys=True)
        else:
            with self._atomic_write(self._props_path, "w") as f:
                json.dump(props, f, sort_keys=True)
