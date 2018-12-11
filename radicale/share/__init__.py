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

from importlib import import_module

from radicale.log import logger

INTERNAL_TYPES = ("read", "write", "birthday")


def load(configuration):
    """Load the share plugins chosen in configuration."""
    share_types = tuple([
        s.strip() for s in configuration.get("share", "type").split(",")])
    classes = []
    for share_type in share_types:
        if share_type in INTERNAL_TYPES:
            module = "radicale.share.%s" % share_type
        else:
            module = share_type
        try:
            classes.append(import_module(module).Share)
        except Exception as e:
            raise RuntimeError("Failed to load share module %r: %s" %
                               (module, e)) from e
    logger.info("Share types are %r", share_types)
    return tuple([class_(configuration) for class_ in classes])


class BaseShare:

    name = ""
    uuid = ""
    group = ""

    tags = ()
    item_writethrough = False

    def __init__(self, configuration):
        self.configuration = configuration

    def get(self, item):
        raise NotImplementedError

    def get_meta(self, props, base_props):
        raise NotImplementedError

    def set_meta(self, props, old_props, old_base_props):
        raise NotImplementedError
