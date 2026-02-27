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

import csv
import logging
import os
from typing import Union

from radicale import config, sharing
from radicale.log import logger

""" CVS based sharing by token or map """


class Sharing(sharing.BaseSharing):
    _lines: int = 0
    _sharing_cache: list[dict] = []
    _sharing_db_file: str

    # Overloaded functions
    def init_database(self) -> bool:
        logger.debug("sharing database initialization for type 'csv'")
        sharing_db_file = self.configuration.get("sharing", "database_path")
        if sharing_db_file == "":
            folder = self.configuration.get("storage", "filesystem_folder")
            folder_db = os.path.join(folder, "collection-db")
            sharing_db_file = os.path.join(folder_db, "sharing.csv")
            logger.info("sharing database filename not provided, use default: %r", sharing_db_file)
        else:
            logger.info("sharing database filename: %r", sharing_db_file)

        if not os.path.exists(folder_db):
            logger.warning("sharing database folder is not existing: %r (create now)", folder_db)
            try:
                os.mkdir(folder_db)
            except Exception as e:
                logger.error("sharing database folder cannot be created (check permissions): %r (%r)", folder_db, e)
                return False
            logger.info("sharing database folder successfully created: %r", folder_db)

        if not os.path.exists(sharing_db_file):
            logger.warning("sharing database is not existing: %r", sharing_db_file)
            try:
                if self._create_empty_csv(sharing_db_file) is not True:
                    raise
            except Exception as e:
                logger.error("sharing database (empty) cannot be created (check permissions): %r (%r)", sharing_db_file, e)
                return False
            logger.info("sharing database (empty) successfully created: %r", sharing_db_file)
        else:
            logger.info("sharing database exists: %r", sharing_db_file)

        # read database
        try:
            if self._load_csv(sharing_db_file) is not True:
                return False
        except Exception as e:
            logger.error("sharing database load failed: %r (%r)", sharing_db_file, e)
            return False
        logger.info("sharing database load successful: %r (lines=%d)", sharing_db_file, self._lines)
        self._sharing_db_file = sharing_db_file
        return True

    def get_database_info(self) -> Union[dict, None]:
        database_info = {'type': "csv"}
        return database_info

    def verify_database(self) -> bool:
        logger.info("sharing database (csv) verification begin")
        logger.info("sharing database (csv) file: %r", self._sharing_db_file)
        logger.info("sharing database (csv) loaded entries: %d", self._lines)
        # nothing more todo for CSV
        logger.info("sharing database (csv) verification end")
        return True

    def get_sharing(self,
                    ShareType: str,
                    PathOrToken: str,
                    User: Union[str, None] = None) -> Union[dict, None]:
        """ retrieve sharing target and attributes by map """
        # Lookup
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("TRACE/sharing: lookup ShareType=%r PathOrToken=%r User=%r)", ShareType, PathOrToken, User)

        index = 0
        found = False
        for row in self._sharing_cache:
            if index == 0:
                # skip fieldnames
                pass
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("TRACE/sharing: check row: %r", row)
            if row['ShareType'] != ShareType:
                pass
            elif row['PathOrToken'] != PathOrToken:
                pass
            elif User is not None and row['User'] != User:
                pass
            elif row['EnabledByOwner'] is not True:
                pass
            elif row['ShareType'] == "map":
                if row['EnabledByUser'] is not True:
                    pass
                else:
                    found = True
                    break
            else:
                found = True
                break
            index += 1

        if found:
            PathMapped = row['PathMapped']
            Owner = row['Owner']
            UserShare = row['User']
            Permissions = row['Permissions']
            Hidden: bool = (row['HiddenByOwner'] or row['HiddenByUser'])
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
        row: dict
        index = 0
        result = []

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("TRACE/sharing/list/called: ShareType=%r OwnerOrUser=%r User=%r PathOrToken=%r PathMapped=%r HiddenByOwner=%s HiddenByUser=%s", ShareType, OwnerOrUser, User, PathOrToken, PathMapped, HiddenByOwner, HiddenByUser)

        for row in self._sharing_cache:
            if index == 0:
                # skip fieldnames
                pass
            else:
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
            index += 1
        return result

    def create_sharing(self,
                       ShareType: str,
                       PathOrToken: str, PathMapped: str,
                       Owner: str, User: str,
                       Permissions: str = "r",
                       EnabledByOwner: bool = False, EnabledByUser: bool = False,
                       HiddenByOwner:  bool = True, HiddenByUser:  bool = True,
                       Timestamp: int = 0,
                       Properties: Union[str, None] = None) -> dict:
        """ create sharing """
        row: dict

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("TRACE/sharing: ShareType=%r", ShareType)
        if ShareType == "token":
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("TRACE/sharing/token/create: PathOrToken=%r Owner=%r PathMapped=%r User=%r Permissions=%r", PathOrToken, Owner, PathMapped, User, Permissions)
            # check for duplicate token entry
            for row in self._sharing_cache:
                if row['ShareType'] != "token":
                    continue
                if row['PathOrToken'] == PathOrToken:
                    # must be unique systemwide
                    logger.error("sharing/token/create: PathOrToken already exists: PathOrToken=%r", PathOrToken)
                    return {"status": "conflict"}
        elif ShareType == "map":
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("TRACE/sharing/map/create: PathOrToken=%r Owner=%r PathMapped=%r User=%r Permissions=%r", PathOrToken, Owner, PathMapped, User, Permissions)
            # check for duplicate map entry
            for row in self._sharing_cache:
                if row['ShareType'] != "map":
                    continue
                if row['PathMapped'] == PathMapped and row['User'] == User and row['PathOrToken'] == PathOrToken:
                    # must be unique systemwide
                    logger.error("sharing/map/create: entry already exists: PathMapped=%r User=%r", PathMapped, User)
                    return {"status": "conflict"}
        else:
            return {"status": "error"}

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
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("TRACE/sharing/*/create: add row: %r", row)
        self._sharing_cache.append(row)

        with self._storage.acquire_lock("w", Owner, path=self._sharing_db_file):
            if self._write_csv(self._sharing_db_file):
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug("TRACE/sharing/%s/create: write CSV done", ShareType)
                return {"status": "success"}
        logger.error("sharing/%s/create: cannot update CSV database", ShareType)
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
                       Properties: Union[str, None] = None) -> dict:
        """ update sharing """
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("TRACE/sharing/%s/update: PathOrToken=%r OwnerOrUser=%r PathMapped=%r Properties=%r", ShareType, PathOrToken, OwnerOrUser, PathMapped, Properties)

        # lookup token
        found = False
        index = 0
        for row in self._sharing_cache:
            if index == 0:
                # skip fieldnames
                pass
            if row['ShareType'] != ShareType:
                pass
            elif row['PathOrToken'] != PathOrToken:
                pass
            else:
                found = True
                break
            index += 1

        if found:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("TRACE/sharing/%s/update: found index=%d", ShareType, index)

            if row['Owner'] != OwnerOrUser:
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug("TRACE/sharing/%s/update: OwnerOrUser=%r not matching Owner=%r -> check now for matching User=%r", ShareType, OwnerOrUser, row['Owner'], row['User'])
                if row['User'] == OwnerOrUser and PathMapped is None and Permissions is None and EnabledByOwner is None and HiddenByOwner is None and Properties is not None:
                    # user is only permitted to update Properties
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug("TRACE/sharing/%s/update: OwnerOrUser=%r PathOrToken=%r index=%d is permitted to update Properties", ShareType, OwnerOrUser, PathOrToken, index)
                    pass
                else:
                    return {"status": "permission-denied"}

            if User is not None and row['User'] != User:
                return {"status": "permission-denied"}

            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("TRACE/sharing/%s/update: OwnerOrUser=%r PathOrToken=%r index=%d", ShareType, OwnerOrUser, PathOrToken, index)
                logger.debug("TRACE/sharing/%s/update: orig row=%r", ShareType, row)

            # CSV: remove+adjust+readd
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

            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("TRACE/sharing/%s/update: adj  row=%r", ShareType, row)

            # replace row
            self._sharing_cache.pop(index)
            self._sharing_cache.append(row)

            with self._storage.acquire_lock("w", OwnerOrUser, path=self._sharing_db_file):
                if self._write_csv(self._sharing_db_file):
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug("TRACE/sharing/%s/update: write CSV done", ShareType)
                    return {"status": "success"}
            logger.error("sharing/%s/update: cannot update CSV database", ShareType)
            return {"status": "error"}
        else:
            return {"status": "not-found"}

    def delete_sharing(self,
                       ShareType: str,
                       PathOrToken: str, Owner: str,
                       PathMapped: Union[str, None] = None) -> dict:
        """ delete sharing """
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("TRACE/sharing/%s/delete: PathOrToken=%r Owner=%r PathMapped=%r", ShareType, PathOrToken, Owner, PathMapped)

        # lookup token
        found = False
        index = 0
        for row in self._sharing_cache:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("TRACE/sharing/%s/delete: check: %r", ShareType, row)
            if index == 0:
                # skip fieldnames
                pass
            if row['ShareType'] != ShareType:
                pass
            elif row['PathOrToken'] != PathOrToken:
                pass
            else:
                if ShareType == "map":
                    # extra filter
                    if row['PathMapped'] != PathMapped:
                        pass
                    else:
                        found = True
                        break
                else:
                    found = True
                    break
            index += 1

        if found:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("TRACE/sharing/%s/delete: found index=%d", ShareType, index)
            if row['Owner'] != Owner:
                return {"status": "permission-denied"}
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("TRACE/sharing/%s/delete: Owner=%r PathOrToken=%r index=%d", ShareType, Owner, PathOrToken, index)
            self._sharing_cache.pop(index)

            with self._storage.acquire_lock("w", Owner, path=self._sharing_db_file):
                if self._write_csv(self._sharing_db_file):
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug("TRACE/sharing_by_token: write CSV done")
                    return {"status": "success"}
            logger.error("sharing/%s/delete: cannot update CSV database", ShareType)
            return {"status": "error"}
        else:
            return {"status": "not-found"}

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

        if Action not in sharing.API_SHARE_TOGGLES_V1:
            # should not happen
            raise

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("TRACE/sharing/%s/%s: OwnerOrUser=%r User=%r PathOrToken=%r PathMapped=%r", ShareType, Action, OwnerOrUser, User, PathOrToken, PathMapped)

        # lookup entry
        found = False
        index = 0
        for row in self._sharing_cache:
            if index == 0:
                # skip fieldnames
                pass
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("TRACE/sharing/*/" + Action + ": check: %r", row)
            if row['ShareType'] != ShareType:
                pass
            elif row['PathOrToken'] != PathOrToken:
                pass
            elif PathMapped is not None and row['PathMapped'] != PathMapped:
                pass
            elif row['Owner'] == OwnerOrUser:
                found = True
                break
            else:
                found = True
                break
            index += 1

        if found:
            # if logger.isEnabledFor(logging.DEBUG):
            #   logger.debug("TRACE/sharing/*/" + Action + ": found: %r", row)
            if User is not None and row['User'] != User:
                return {"status": "permission-denied"}
            elif row['Owner'] == OwnerOrUser:
                pass
            elif row['User'] == OwnerOrUser:
                pass
            else:
                return {"status": "permission-denied"}

            # TODO: locking
            if row['Owner'] == OwnerOrUser:
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug("TRACE/sharing/%s/%s: Owner=%r User=%r PathOrToken=%r index=%d", ShareType, Action, OwnerOrUser, User, PathOrToken, index)
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
                    logger.debug("TRACE/sharing/%s/%s: User=%r PathOrToken=%r index=%d", ShareType, Action, OwnerOrUser, PathOrToken, index)
                if Action == "disable":
                    row['EnabledByUser'] = False
                elif Action == "enable":
                    row['EnabledByUser'] = True
                elif Action == "hide":
                    row['HiddenByUser'] = True
                elif Action == "unhide":
                    row['HiddenByUser'] = False

            row['TimestampUpdated'] = Timestamp

            # remove
            self._sharing_cache.pop(index)
            # readd
            self._sharing_cache.append(row)

            with self._storage.acquire_lock("w", OwnerOrUser, path=self._sharing_db_file):
                if self._write_csv(self._sharing_db_file):
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug("TRACE: write CSV done")
                    return {"status": "success"}
            logger.error("sharing: cannot update CSV database")
            return {"status": "error"}
        else:
            return {"status": "not-found"}

    # local functions
    def _create_empty_csv(self, file: str) -> bool:
        with self._storage.acquire_lock("w", None, path=file):
            with open(file, 'w', newline='') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=sharing.DB_FIELDS_V1)
                writer.writeheader()
        return True

    def _load_csv(self, file: str) -> bool:
        logger.debug("sharing database load begin: %r", file)
        with self._storage.acquire_lock("r", None):
            with open(file, 'r', newline='') as csvfile:
                reader = csv.DictReader(csvfile, fieldnames=sharing.DB_FIELDS_V1)
                self._lines = 0
                for row in reader:
                    # logger.debug("sharing database load read: %r", row)
                    if self._lines == 0:
                        # header line, check
                        for fieldname in sharing.DB_FIELDS_V1:
                            logger.debug("sharing database load check fieldname: %r", fieldname)
                            if fieldname not in row:
                                logger.debug("sharing database is incompatible: %r", file)
                                return False
                    # convert txt to bool
                    if self._lines > 0:
                        for fieldname in sharing.DB_FIELDS_V1_BOOL:
                            row[fieldname] = config._convert_to_bool(row[fieldname])
                        for fieldname in sharing.DB_FIELDS_V1_INT:
                            row[fieldname] = int(row[fieldname])
                    # check for duplicates
                    dup = False
                    for row_cached in self._sharing_cache:
                        if row == row_cached:
                            dup = True
                            break
                    if dup:
                        continue
                    # logger.debug("sharing database load add: %r", row)
                    self._sharing_cache.append(row)
                    self._lines += 1
        logger.debug("sharing database load end: %r", file)
        return True

    def _write_csv(self, file: str) -> bool:
        with open(file, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=sharing.DB_FIELDS_V1)
            writer.writerows(self._sharing_cache)
        return True
