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

import json
import os

import radicale.item as radicale_item


class CollectionMetaMixin:
    def __init__(self):
        super().__init__()
        self._meta_cache = None
        self._props_path = os.path.join(
            self._filesystem_path, ".Radicale.props")

    def get_meta(self, key=None):
        # reuse cached value if the storage is read-only
        if self._storage._lock.locked == "w" or self._meta_cache is None:
            try:
                try:
                    with open(self._props_path, encoding=self._encoding) as f:
                        temp_meta = json.load(f)
                except FileNotFoundError:
                    temp_meta = {}
                self._meta_cache = radicale_item.check_and_sanitize_props(
                    temp_meta)
            except ValueError as e:
                raise RuntimeError("Failed to load properties of collection "
                                   "%r: %s" % (self.path, e)) from e
        return self._meta_cache if key is None else self._meta_cache.get(key)

    def set_meta(self, props):
        with self._atomic_write(self._props_path, "w") as f:
            json.dump(props, f, sort_keys=True)
