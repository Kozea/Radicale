# This file is part of Radicale Server - Calendar Server
# Copyright © 2026-2026 Peter Bieringer <pb@bieringer.de>
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

from typing import Union

from radicale import sharing
from radicale.log import logger


class Sharing(sharing.BaseSharing):

    def init_database(self) -> bool:
        """ dummy initialization """
        return False

    def get_sharing_collection_by_token(self, token: str) -> Union[dict, None]:
        """ retrieve target and attributs by token """
        # default
        logger.debug("TRACE/sharing_by_token: 'none' cannot provide any map for token: %r", token)
        return None

    def get_sharing_collection_by_map(self, path) -> Union[dict, None]:
        """ retrieve target and attributs by map """
        logger.debug("TRACE/sharing_by_map: 'none' cannot provide any map for path: %r", path)
        return {"mapped": False}
