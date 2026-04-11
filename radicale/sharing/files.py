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

import os
import pickle
import urllib
from typing import Union

from radicale import sharing
from radicale.log import logger

""" File 'database' based sharing by token or map """

DB_VERSION: str = "1"


class Sharing(sharing.BaseSharing):
    _sharing_database_path_ShareType: dict = {}

    # Overloaded functions
    def database_init(self) -> bool:
        logger.debug("sharing database initialization for type 'files'")
        sharing_database_path = self.configuration.get("sharing", "database_path")
        if sharing_database_path == "":
            folder = self.configuration.get("storage", "filesystem_folder")
            folder_db = os.path.join(folder, "collection-db")
            sharing_database_path = os.path.join(folder_db, "files")
            logger.info("sharing database path not provided, use default: %r", sharing_database_path)
        else:
            logger.info("sharing database path: %r", sharing_database_path)

        if not os.path.exists(folder_db):
            logger.notice("sharing database folder is not existing: %r (create now)", folder_db)
            try:
                os.mkdir(folder_db)
            except Exception as e:
                logger.error("sharing database folder cannot be created (check permissions): %r (%r)", folder_db, e)
                return False
            logger.notice("sharing database folder successfully created: %r", folder_db)

        if not os.path.exists(sharing_database_path):
            logger.notice("sharing database path is not existing: %r", sharing_database_path)
            try:
                os.mkdir(sharing_database_path)
            except Exception as e:
                logger.error("sharing database path cannot be created (check permissions): %r (%r)", sharing_database_path, e)
                return False
            logger.notice("sharing database path successfully created: %r", sharing_database_path)

        for ShareType in sharing.SHARE_TYPES_V1:
            path = os.path.join(sharing_database_path, ShareType)
            self._sharing_database_path_ShareType[ShareType] = path
            if not os.path.exists(path):
                logger.notice("sharing database path for %r is not existing: %r", ShareType, path)
                try:
                    os.mkdir(path)
                except Exception as e:
                    logger.error("sharing database path for %r cannot be created (check permissions): %r (%r)", ShareType, path, e)
                    return False
                logger.notice("sharing database path for %r successfully created: %r", ShareType, path)
        return True

    def database_get_info(self) -> Union[dict, None]:
        database_info = {'type': "files"}
        return database_info

    def database_verify(self) -> bool:
        logger.info("sharing database (files) verification begin")
        for ShareType in sharing.SHARE_TYPES_V1:
            logger.info("sharing database (files) path for %r: %r", ShareType, self._sharing_database_path_ShareType[ShareType])
        # TODO: count amount of files
        logger.info("sharing database (files) verification end")
        return True

    def database_get_sharing(self,
                             ShareType: str,
                             PathOrToken: str,
                             OnlyEnabled: bool = True,
                             User: Union[str, None] = None) -> Union[dict, None]:
        """ retrieve sharing target and attributes by map """
        # Lookup
        logger.trace("sharing/%s/get: PathOrToken=%r User=%r)", ShareType, PathOrToken, User)

        sharing_config_file = os.path.join(self._sharing_database_path_ShareType[ShareType], self._encode_path(PathOrToken))

        if not os.path.isfile(sharing_config_file):
            return None

        # read content
        with self._storage.acquire_lock("r", User):
            # read file
            with open(sharing_config_file, "rb") as fb:
                (version, row) = pickle.load(fb)

            if version != DB_VERSION:
                return {"status": "error"}

            if User is not None and row['User'] != User:
                return None
            elif OnlyEnabled is True and row['EnabledByOwner'] is not True:
                return None
            elif OnlyEnabled is True and row['ShareType'] == "map":
                if row['EnabledByUser'] is not True:
                    return None

            PathMapped = row['PathMapped']
            Owner = row['Owner']
            UserShare = row['User']
            Permissions = row['Permissions']
            Hidden: bool = (row['HiddenByOwner'] or row['HiddenByUser'])
            Properties: Union[dict, None] = None
            Conversion: Union[str, None] = None
            Actions: Union[dict, None] = None
            if 'Properties' in row:
                Properties = row['Properties']
            if 'Conversion' in row:
                Conversion = row['Conversion']
            if 'Actions' in row:
                Actions = row['Actions']
            logger.trace("sharing: map %r to %r (Owner=%r User=%r Permissions=%r Hidden=%s Properties=%r)", PathOrToken, PathMapped, Owner, UserShare, Permissions, Hidden, Properties)
            return {
                    "mapped": True,
                    "ShareType": ShareType,
                    "PathOrToken": PathOrToken,
                    "PathMapped": PathMapped,
                    "Owner": Owner,
                    "User": UserShare,
                    "Hidden": Hidden,
                    "EnabledByOwner": row['EnabledByOwner'],
                    "EnabledByUser": row['EnabledByUser'],
                    "Permissions": Permissions,
                    "Properties": Properties,
                    "Conversion": Conversion,
                    "Actions": Actions,
                    }

        return None

    def database_list_sharing(self,
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
                              ) -> list[dict]:
        """ retrieve sharing """
        result = []

        logger.trace("sharing/list/called: ShareType=%r OwnerOrUser=%r User=%r PathOrToken=%r PathMapped=%r EnabledByOwner=%s EnabledByUser=%s HiddenByOwner=%s HiddenByUser=%s Conversion=%r", ShareType, OwnerOrUser, User, PathOrToken, PathMapped, EnabledByOwner, EnabledByUser, HiddenByOwner, HiddenByUser, Conversion)

        for _ShareType in sharing.SHARE_TYPES_V1:
            if ShareType is not None and _ShareType != ShareType:
                # skip
                continue

            path = self._sharing_database_path_ShareType[_ShareType]
            with self._storage.acquire_lock("r", OwnerOrUser, path=path):
                for entry in os.scandir(path):
                    if not entry.is_file():
                        continue

                    logger.trace("sharing/list: check file: %r", entry.name)
                    # read file
                    with open(entry, "rb") as fb:
                        (version, row) = pickle.load(fb)

                    if version != DB_VERSION:
                        # skip
                        continue

                    logger.trace("sharing/list/row: test: %r", row)
                    if ShareType is not None and row['ShareType'] != ShareType:
                        logger.trace("sharing/list/row: skip by ShareType")
                        pass
                    elif OwnerOrUser is not None and (row['Owner'] != OwnerOrUser and row['User'] != OwnerOrUser):
                        pass
                    elif User is not None and row['User'] != User:
                        logger.trace("sharing/list/row: skip by User")
                        pass
                    elif PathOrToken is not None and row['PathOrToken'] != PathOrToken:
                        logger.trace("sharing/list/row: skip by PathOrToken")
                        pass
                    elif PathMapped is not None and row['PathMapped'] != PathMapped:
                        logger.trace("sharing/list/row: skip by PathMapped")
                        pass
                    elif EnabledByOwner is not None and row['EnabledByOwner'] != EnabledByOwner:
                        pass
                    elif EnabledByUser is not None and row['EnabledByUser'] != EnabledByUser:
                        pass
                    elif HiddenByOwner is not None and row['HiddenByOwner'] != HiddenByOwner:
                        pass
                    elif HiddenByUser is not None and row['HiddenByUser'] != HiddenByUser:
                        pass
                    elif Conversion is not None and row['Conversion'] != Conversion:
                        pass
                    else:
                        logger.trace("sharing/list/row: add: %r", row)
                        result.append(row)

        return result

    def database_create_sharing(self,
                                ShareType: str,
                                PathOrToken: str, PathMapped: str,
                                Conversion: str,
                                Owner: str, User: str,
                                Permissions: str = "r",
                                EnabledByOwner: bool = False, EnabledByUser: bool = False,
                                HiddenByOwner:  bool = True, HiddenByUser:  bool = True,
                                Timestamp: int = 0,
                                Properties: Union[dict, None] = None,
                                Actions: Union[dict, None] = None,
                                ) -> dict:
        """ create sharing """
        row: dict

        sharing_config_file = os.path.join(self._sharing_database_path_ShareType[ShareType], self._encode_path(PathOrToken))

        logger.trace("sharing/%s/create: sharing_config_file=%r", ShareType, sharing_config_file)
        logger.trace("sharing/%s/create: PathOrToken=%r Owner=%r PathMapped=%r User=%r Permissions=%r", ShareType, PathOrToken, Owner, PathMapped, User, Permissions)
        if os.path.isfile(sharing_config_file):
            return {"status": "conflict"}

        row = {"ShareType": ShareType,
               "PathOrToken": PathOrToken,
               "PathMapped": PathMapped,
               "Owner": Owner,
               "User": User,
               "Permissions": Permissions,
               "EnabledByOwner": EnabledByOwner,
               "EnabledByUser": EnabledByUser,
               "HiddenByOwner": HiddenByOwner,
               "HiddenByUser": HiddenByUser,
               "TimestampCreated": Timestamp,
               "TimestampUpdated": Timestamp,
               "Properties": Properties,
               "Conversion": Conversion,
               "Actions": Actions,
               }

        version = DB_VERSION

        try:
            with self._storage.acquire_lock("w", Owner, path=sharing_config_file):
                logger.trace("sharing/%s/create: store share-config: %r into file %r", ShareType, row, sharing_config_file)
                # write file
                with open(sharing_config_file, "wb") as fb:
                    pickle.dump((version, row), fb)
                logger.trace("sharing/*/create: share-config file stored: %r", sharing_config_file)
                return {"status": "success"}
        except Exception as e:
            logger.error("sharing/%s/create: cannot store share-config: %r (%r)", ShareType, sharing_config_file, e)
            return {"status": "error"}

    def database_update_sharing(self,
                                ShareType: str,
                                PathOrToken: str,
                                OwnerOrUser: Union[str, None] = None,
                                User: Union[str, None] = None,
                                PathMapped: Union[str, None] = None,
                                Permissions: Union[str, None] = None,
                                EnabledByOwner: Union[bool, None] = None,
                                EnabledByUser:  Union[bool, None] = None,
                                HiddenByOwner:  Union[bool, None] = None,
                                HiddenByUser:   Union[bool, None] = None,
                                Timestamp: int = 0,
                                Properties: Union[dict, None] = None,
                                Conversion: Union[str, None] = None,
                                Actions: Union[dict, None] = None,
                                ) -> dict:
        """ update sharing """
        logger.trace("sharing/%s/update: PathOrToken=%r OwnerOrUser=%r User=%r Properties=%r", ShareType, PathOrToken, OwnerOrUser, User, Properties)

        sharing_config_file = os.path.join(self._sharing_database_path_ShareType[ShareType], self._encode_path(PathOrToken))

        if not os.path.isfile(sharing_config_file):
            return {"status": "not-found"}

        # read content
        with self._storage.acquire_lock("w", OwnerOrUser, path=sharing_config_file):
            # read file
            with open(sharing_config_file, "rb") as fb:
                (version, row) = pickle.load(fb)

            if version != DB_VERSION:
                return {"status": "error"}

            logger.trace("sharing/%s/update: orig row=%r", ShareType, row)

            if PathMapped is not None:
                row["PathMapped"] = PathMapped
            if Permissions is not None:
                row["Permissions"] = Permissions
            if User is not None:
                row["User"] = User
            if EnabledByOwner is not None:
                row["EnabledByOwner"] = EnabledByOwner
            if EnabledByUser is not None:
                row["EnabledByUser"] = EnabledByUser
            if HiddenByOwner is not None:
                row["HiddenByOwner"] = HiddenByOwner
            if HiddenByUser is not None:
                row["HiddenByUser"] = HiddenByUser
            if Properties is not None:
                row["Properties"] = Properties
            if Conversion is not None:
                row["Conversion"] = Conversion
            if Actions is not None:
                row["Actions"] = Actions
            # update timestamp
            row["TimestampUpdated"] = Timestamp

            logger.trace("sharing/%s/update: adj  row=%r", ShareType, row)

            try:
                # write file
                with open(sharing_config_file, "wb") as fb:
                    pickle.dump((version, row), fb)
                logger.trace("sharing/%s/create: share-config file stored: %r", ShareType, sharing_config_file)
                return {"status": "success"}
            except Exception as e:
                logger.error("sharing/%s/create: cannot store share-config: %r (%r)", ShareType, sharing_config_file, e)
                return {"status": "error"}

    def database_delete_sharing(self,
                                ShareType: str,
                                PathOrToken: str,
                                User: str) -> dict:
        """ delete sharing """
        logger.trace("sharing/%s/delete: PathOrToken=%r", ShareType, PathOrToken)

        sharing_config_file = os.path.join(self._sharing_database_path_ShareType[ShareType], self._encode_path(PathOrToken))

        if not os.path.isfile(sharing_config_file):
            return {"status": "not-found"}

        # open writable so storage hook triggers
        with self._storage.acquire_lock("w", User, path=sharing_config_file):
            # read file
            with open(sharing_config_file, "rb") as fb:
                (version, row) = pickle.load(fb)

            if version != DB_VERSION:
                return {"status": "error"}

            try:
                os.remove(sharing_config_file)
            except Exception as e:
                logger.error("sharing/%s/delete: cannot remove share-config: %r (%r)", ShareType, sharing_config_file, e)
                return {"status": "error"}

        logger.debug("sharing/%s/delete: successful removed share-config: %r", ShareType, sharing_config_file)
        return {"status": "success"}

    # local functions
    def _encode_path(self, path: str) -> str:
        return urllib.parse.quote(path, safe="")

    def _decode_path(self, path: str) -> str:
        return urllib.parse.unquote(path)
