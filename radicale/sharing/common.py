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

from radicale import rights, sharing
from radicale.log import logger


def database_common_check_row_match(
                                      row: dict,
                                      OwnerOrUser: Union[str, None] = None,
                                      ShareType: Union[str, None] = None,
                                      PathOrToken: Union[str, None] = None,
                                      PathMapped: Union[str, None] = None,
                                      User: Union[str, None] = None,
                                      EnabledByOwner: Union[bool, None] = None,
                                      EnabledByUser: Union[bool, None] = None,
                                      HiddenByOwner: Union[bool, None] = None,
                                      HiddenByUser: Union[bool, None] = None,
                                      Conversion: Union[str, None] = None,
                                      ) -> Union[dict, None]:
    """Returns given row if matching conditions."""

    if OwnerOrUser is not None:
        owner_or_user_without_group = OwnerOrUser.split(sharing.SHARING_SEPARATOR_GROUP)[0]

    user = None

    if ShareType is not None and row['ShareType'] != ShareType:
        return None
    if Conversion is not None and row['Conversion'] != Conversion:
        return None
    if EnabledByOwner is not None and row['EnabledByOwner'] != EnabledByOwner:
        return None
    if EnabledByUser is not None and row['EnabledByUser'] != EnabledByUser:
        return None
    if HiddenByOwner is not None and row['HiddenByOwner'] != HiddenByOwner:
        return None
    if HiddenByUser is not None and row['HiddenByUser'] != HiddenByUser:
        return None
    if PathMapped is not None and row['PathMapped'] != PathMapped:
        return None
    if OwnerOrUser is not None:
        if User is not None and OwnerOrUser == User:
            pass  # will be checked below
        elif row['Owner'] == owner_or_user_without_group:
            if PathOrToken is not None and row['PathOrToken'] != PathOrToken:
                return None
            return row
        elif User is None:
            user = OwnerOrUser
            pass  # will be checked below

    group_check = False
    if row['User'].startswith(sharing.SHARING_SEPARATOR_GROUP) or row['User'].startswith(sharing.SHARING_SEPARATOR_REALM):
        group_check = True

    if User is not None:
        user = User

    if user is not None:
        user_without_group = user.split(sharing.SHARING_SEPARATOR_GROUP)[0]
        if row['User'].startswith(sharing.SHARING_SEPARATOR_REALM):
            if not user.split(':')[0].endswith(row['User']):
                return None
        elif row['User'].startswith(sharing.SHARING_SEPARATOR_GROUP):
            if sharing.SHARING_SEPARATOR_GROUP not in user:
                return None  # user has no group
            groups_of_user = user.split(sharing.SHARING_SEPARATOR_GROUP)[1].split(',')
            Groups = row['User'].removeprefix(sharing.SHARING_SEPARATOR_GROUP).split(',')
            logger.trace("sharing/common/check_row_match/groups: groups_of_user=%r Groups=%r", groups_of_user, Groups)
            found = False
            for group in groups_of_user:
                if group in Groups:
                    found = True
                    break
            if found:
                pass
            else:
                return None
        elif row['User'] == user_without_group:
            pass
        else:
            return None

    row_copy = row.copy()

    if group_check and user is not None:
        if row['User'].startswith(sharing.SHARING_SEPARATOR_REALM):
            user_without_group = user.split(sharing.SHARING_SEPARATOR_GROUP)[0]
        elif row['User'].startswith(sharing.SHARING_SEPARATOR_GROUP):
            user_without_group = user.split(sharing.SHARING_SEPARATOR_GROUP)[0]
        else:
            user_without_group = user
        row_copy['PathOrToken'] = row['PathOrToken'].replace("{user}", user_without_group)  # replace placeholder
        row_copy['User'] = user_without_group  # replace with real user
        row_copy['Permissions'] = rights.add(rights.remove(row_copy['Permissions'], "u"), "U")  # replace flag for resolved group

    if PathOrToken is not None and row_copy['PathOrToken'] != PathOrToken:
        return None

    return row_copy
