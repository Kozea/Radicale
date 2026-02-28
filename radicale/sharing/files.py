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

import logging
import os
import pickle
import urllib
from typing import Union

from radicale import sharing
from radicale.log import logger

""" File 'database' based sharing by token or map """

DB_VERSION: str = "1"


class Sharing(sharing.BaseSharing):
    _sharing_db_path_ShareType: dict = {}

    # Overloaded functions
    def init_database(self) -> bool:
        logger.debug("sharing database initialization for type 'files'")
        sharing_db_path = self.configuration.get("sharing", "database_path")
        if sharing_db_path == "":
            folder = self.configuration.get("storage", "filesystem_folder")
            folder_db = os.path.join(folder, "collection-db")
            sharing_db_path = os.path.join(folder_db, "files")
            logger.info("sharing database path not provided, use default: %r", sharing_db_path)
        else:
            logger.info("sharing database path: %r", sharing_db_path)

        if not os.path.exists(folder_db):
            logger.warning("sharing database folder is not existing: %r (create now)", folder_db)
            try:
                os.mkdir(folder_db)
            except Exception as e:
                logger.error("sharing database folder cannot be created (check permissions): %r (%r)", folder_db, e)
                return False
            logger.info("sharing database folder successfully created: %r", folder_db)

        if not os.path.exists(sharing_db_path):
            logger.warning("sharing database path is not existing: %r", sharing_db_path)
            try:
                os.mkdir(sharing_db_path)
            except Exception as e:
                logger.error("sharing database path cannot be created (check permissions): %r (%r)", sharing_db_path, e)
                return False
            logger.info("sharing database path successfully created: %r", sharing_db_path)

        for ShareType in sharing.SHARE_TYPES_V1:
            path = os.path.join(sharing_db_path, ShareType)
            self._sharing_db_path_ShareType[ShareType] = path
            if not os.path.exists(path):
                logger.warning("sharing database path for %r is not existing: %r", ShareType, path)
                try:
                    os.mkdir(path)
                except Exception as e:
                    logger.error("sharing database path for %r cannot be created (check permissions): %r (%r)", ShareType, path, e)
                    return False
                logger.info("sharing database path for %r successfully created: %r", ShareType, path)
        return True

    def get_database_info(self) -> Union[dict, None]:
        database_info = {'type': "files"}
        return database_info

    def verify_database(self) -> bool:
        logger.info("sharing database (files) verification begin")
        for ShareType in sharing.SHARE_TYPES_V1:
            logger.info("sharing database (files) path for %r: %r", ShareType, self._sharing_db_path_ShareType[ShareType])
        # TODO: count amount of files
        logger.info("sharing database (files) verification end")
        return True

    def get_sharing(self,
                    ShareType: str,
                    PathOrToken: str,
                    User: Union[str, None] = None) -> Union[dict, None]:
        """ retrieve sharing target and attributes by map """
        # Lookup
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("TRACE/sharing/%s/get: PathOrToken=%r User=%r)", ShareType, PathOrToken, User)

        sharing_config_file = os.path.join(self._sharing_db_path_ShareType[ShareType], self._encode_path(PathOrToken))

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
            elif row['EnabledByOwner'] is not True:
                return None
            elif row['ShareType'] == "map":
                if row['EnabledByUser'] is not True:
                    return None

            PathMapped = row['PathMapped']
            Owner = row['Owner']
            UserShare = row['User']
            Permissions = row['Permissions']
            Hidden: bool = (row['HiddenByOwner'] or row['HiddenByUser'])
            Properties: Union[dict, None] = None
            if 'Properties' in row:
                Properties = row['Properties']
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("TRACE/sharing: map %r to %r (Owner=%r User=%r Permissions=%r Hidden=%s Properties=%r)", PathOrToken, PathMapped, Owner, UserShare, Permissions, Hidden, Properties)
            return {
                    "mapped": True,
                    "PathOrToken": PathOrToken,
                    "PathMapped": PathMapped,
                    "Owner": Owner,
                    "User": UserShare,
                    "Hidden": Hidden,
                    "Permissions": Permissions,
                    "Properties": Properties}

        return None

    def list_sharing(self,
                     OwnerOrUser: Union[str, None] = None,
                     ShareType: Union[str, None] = None,
                     PathOrToken: Union[str, None] = None,
                     PathMapped: Union[str, None] = None,
                     User: Union[str, None] = None,
                     EnabledByOwner: Union[bool, None] = None,
                     EnabledByUser: Union[bool, None] = None,
                     HiddenByOwner: Union[bool, None] = None,
                     HiddenByUser: Union[bool, None] = None) -> list[dict]:
        """ retrieve sharing """
        result = []

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("TRACE/sharing/list/called: ShareType=%r OwnerOrUser=%r User=%r PathOrToken=%r PathMapped=%r HiddenByOwner=%s HiddenByUser=%s", ShareType, OwnerOrUser, User, PathOrToken, PathMapped, HiddenByOwner, HiddenByUser)

        for _ShareType in sharing.SHARE_TYPES_V1:
            if ShareType is not None and _ShareType != ShareType:
                # skip
                continue

            path = self._sharing_db_path_ShareType[_ShareType]
            with self._storage.acquire_lock("r", OwnerOrUser, path=path):
                for entry in os.scandir(path):
                    if not entry.is_file():
                        continue

                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug("TRACE/sharing/list: check file: %r", entry.name)
                    # read file
                    with open(entry, "rb") as fb:
                        (version, row) = pickle.load(fb)

                    if version != DB_VERSION:
                        # skip
                        continue

                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug("TRACE/sharing/list/row: test: %r", row)
                    if ShareType is not None and row['ShareType'] != ShareType:
                        if logger.isEnabledFor(logging.DEBUG):
                            logger.debug("TRACE/sharing/list/row: skip by ShareType")
                        pass
                    elif OwnerOrUser is not None and (row['Owner'] != OwnerOrUser and row['User'] != OwnerOrUser):
                        pass
                    elif User is not None and row['User'] != User:
                        if logger.isEnabledFor(logging.DEBUG):
                            logger.debug("TRACE/sharing/list/row: skip by User")
                        pass
                    elif PathOrToken is not None and row['PathOrToken'] != PathOrToken:
                        if logger.isEnabledFor(logging.DEBUG):
                            logger.debug("TRACE/sharing/list/row: skip by PathOrToken")
                        pass
                    elif PathMapped is not None and row['PathMapped'] != PathMapped:
                        if logger.isEnabledFor(logging.DEBUG):
                            logger.debug("TRACE/sharing/list/row: skip by PathMapped")
                        pass
                    elif EnabledByOwner is not None and row['EnabledByOwner'] != EnabledByOwner:
                        pass
                    elif EnabledByUser is not None and row['EnabledByUser'] != EnabledByUser:
                        pass
                    elif HiddenByOwner is not None and row['HiddenByOwner'] != HiddenByOwner:
                        pass
                    elif HiddenByUser is not None and row['HiddenByUser'] != HiddenByUser:
                        pass
                    else:
                        if logger.isEnabledFor(logging.DEBUG):
                            logger.debug("TRACE/sharing/list/row: add: %r", row)
                        result.append(row)

        return result

    def create_sharing(self,
                       ShareType: str,
                       PathOrToken: str, PathMapped: str,
                       Owner: str, User: str,
                       Permissions: str = "r",
                       EnabledByOwner: bool = False, EnabledByUser: bool = False,
                       HiddenByOwner:  bool = True, HiddenByUser:  bool = True,
                       Timestamp: int = 0,
                       Properties: Union[dict, None] = None) -> dict:
        """ create sharing """
        row: dict

        sharing_config_file = os.path.join(self._sharing_db_path_ShareType[ShareType], self._encode_path(PathOrToken))

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("TRACE/sharing/%s/create: sharing_config_file=%r", ShareType, sharing_config_file)
            logger.debug("TRACE/sharing/%s/create: PathOrToken=%r Owner=%r PathMapped=%r User=%r Permissions=%r", ShareType, PathOrToken, Owner, PathMapped, User, Permissions)
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
               "TimestampUpdated": Timestamp}

        version = DB_VERSION

        try:
            with self._storage.acquire_lock("w", Owner, path=sharing_config_file):
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug("TRACE/sharing/%s/create: store share-config: %r into file %r", ShareType, row, sharing_config_file)
                # write file
                with open(sharing_config_file, "wb") as fb:
                    pickle.dump((version, row), fb)
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug("TRACE/sharing/*/create: share-config file stored: %r", sharing_config_file)
                return {"status": "success"}
        except Exception as e:
            logger.error("sharing/%s/create: cannot store share-config: %r (%r)", ShareType, sharing_config_file, e)
            return {"status": "error"}

    def update_sharing(self,
                       ShareType: str,
                       PathOrToken: str,
                       OwnerOrUser: str,
                       User: Union[str, None] = None,
                       PathMapped: Union[str, None] = None,
                       Permissions: Union[str, None] = None,
                       EnabledByOwner: Union[bool, None] = None,
                       HiddenByOwner:  Union[bool, None] = None,
                       Timestamp: int = 0,
                       Properties: Union[dict, None] = None) -> dict:
        """ update sharing """
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("TRACE/sharing/%s/update: PathOrToken=%r OwnerOrUser=%r User=%r Properties=%r", ShareType, PathOrToken, OwnerOrUser, User, Properties)

        sharing_config_file = os.path.join(self._sharing_db_path_ShareType[ShareType], self._encode_path(PathOrToken))

        if not os.path.isfile(sharing_config_file):
            return {"status": "not-found"}

        # read content
        with self._storage.acquire_lock("w", OwnerOrUser, path=sharing_config_file):
            # read file
            with open(sharing_config_file, "rb") as fb:
                (version, row) = pickle.load(fb)

            if version != DB_VERSION:
                return {"status": "error"}

            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("TRACE/sharing/%s/update: check: %r", ShareType, row)

            if row['Owner'] != OwnerOrUser:
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug("TRACE/sharing/%s/update: OwnerOrUser=%r not matching Owner=%r -> check now for matching User=%r", ShareType, OwnerOrUser, row['Owner'], row['User'])
                if row['User'] == OwnerOrUser and PathMapped is None and Permissions is None and EnabledByOwner is None and HiddenByOwner is None and Properties is not None:
                    # user is only permitted to update Properties
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug("TRACE/sharing/%s/update: OwnerOrUser=%r PathOrToken=%r is permitted to update Properties", ShareType, OwnerOrUser, PathOrToken)
                    pass
                else:
                    return {"status": "permission-denied"}

            if User is not None and row['User'] != User:
                return {"status": "permission-denied"}

            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("TRACE/sharing/%s/update: orig row=%r", ShareType, row)

            if PathMapped is not None:
                row["PathMapped"] = PathMapped
            if Permissions is not None:
                row["Permissions"] = Permissions
            if User is not None:
                row["User"] = User
            if EnabledByOwner is not None:
                row["EnabledByOwner"] = EnabledByOwner
            if HiddenByOwner is not None:
                row["HiddenByOwner"] = HiddenByOwner
            if Properties is not None:
                row["Properties"] = Properties
            # update timestamp
            row["TimestampUpdated"] = Timestamp

            logger.debug("TRACE/sharing/%s/update: adj  row=%r", ShareType, row)

            try:
                # write file
                with open(sharing_config_file, "wb") as fb:
                    pickle.dump((version, row), fb)
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug("TRACE/sharing/%s/create: share-config file stored: %r", ShareType, sharing_config_file)
                return {"status": "success"}
            except Exception as e:
                logger.error("sharing/%s/create: cannot store share-config: %r (%r)", ShareType, sharing_config_file, e)
                return {"status": "error"}

    def delete_sharing(self,
                       ShareType: str,
                       PathOrToken: str, Owner: str,
                       PathMapped: Union[str, None] = None) -> dict:
        """ delete sharing """
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("TRACE/sharing/%s/delete: PathOrToken=%r Owner=%r", ShareType, PathOrToken, Owner)

        sharing_config_file = os.path.join(self._sharing_db_path_ShareType[ShareType], self._encode_path(PathOrToken))

        if not os.path.isfile(sharing_config_file):
            return {"status": "not-found"}

        # read content
        with self._storage.acquire_lock("r", Owner, path=sharing_config_file):
            # read file
            with open(sharing_config_file, "rb") as fb:
                (version, row) = pickle.load(fb)

            if version != DB_VERSION:
                return {"status": "error"}

            # verify owner
            if row['Owner'] != Owner:
                return {"status": "permission-denied"}

            try:
                os.remove(sharing_config_file)
            except Exception as e:
                logger.error("sharing/%s/delete: cannot remove share-config: %r (%r)", ShareType, sharing_config_file, e)
                return {"status": "error"}

        logger.debug("sharing/%s/delete: successful removed share-config: %r", ShareType, sharing_config_file)
        return {"status": "success"}

    def toggle_sharing(self,
                       ShareType: str,
                       PathOrToken: str,
                       OwnerOrUser: str,
                       Action: str,
                       PathMapped: Union[str, None] = None,
                       User: Union[str, None] = None,
                       Timestamp: int = 0) -> dict:
        """ toggle sharing """
        row: dict

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("TRACE/sharing/%s/%s: OwnerOrUser=%r User=%r PathOrToken=%r PathMapped=%r", ShareType, Action, OwnerOrUser, User, PathOrToken, PathMapped)

        if Action not in sharing.API_SHARE_TOGGLES_V1:
            # should not happen
            raise

        sharing_config_file = os.path.join(self._sharing_db_path_ShareType[ShareType], self._encode_path(PathOrToken))

        if not os.path.isfile(sharing_config_file):
            return {"status": "not-found"}

        # read content
        with self._storage.acquire_lock("w", OwnerOrUser, path=sharing_config_file):
            # read file
            with open(sharing_config_file, "rb") as fb:
                (version, row) = pickle.load(fb)

            if version != DB_VERSION:
                return {"status": "error"}

            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("TRACE/sharing/%s/%s: check: %r", ShareType, Action, row)

            # verify ownership or user
            if User is not None and row['User'] != User:
                return {"status": "permission-denied"}
            elif row['Owner'] == OwnerOrUser:
                pass
            elif row['User'] == OwnerOrUser:
                pass
            else:
                return {"status": "permission-denied"}

            if row['Owner'] == OwnerOrUser:
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug("TRACE/sharing/%s/%s: Owner=%r User=%r PathOrToken=%r", ShareType, Action, OwnerOrUser, User, PathOrToken)
                if Action == "disable":
                    row['EnabledByOwner'] = False
                elif Action == "enable":
                    row['EnabledByOwner'] = True
                elif Action == "hide":
                    row['HiddenByOwner'] = True
                elif Action == "unhide":
                    row['HiddenByOwner'] = False
                row['TimestampUpdated'] = Timestamp
            if row['User'] == OwnerOrUser:
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug("TRACE/sharing/%s/%s: User=%r PathOrToken=%r", ShareType, Action, OwnerOrUser, PathOrToken)
                if Action == "disable":
                    row['EnabledByUser'] = False
                elif Action == "enable":
                    row['EnabledByUser'] = True
                elif Action == "hide":
                    row['HiddenByUser'] = True
                elif Action == "unhide":
                    row['HiddenByUser'] = False

            row['TimestampUpdated'] = Timestamp

            try:
                # write file
                with open(sharing_config_file, "wb") as fb:
                    pickle.dump((version, row), fb)
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug("TRACE/sharing/%s/create: share-config file stored: %r", ShareType, sharing_config_file)
                return {"status": "success"}
            except Exception as e:
                logger.error("sharing/%s/create: cannot store share-config: %r (%r)", ShareType, sharing_config_file, e)
                return {"status": "error"}

    # local functions
    def _encode_path(self, path: str) -> str:
        return urllib.parse.quote(path, safe="")

    def _decode_path(self, path: str) -> str:
        return urllib.parse.unquote(path)
