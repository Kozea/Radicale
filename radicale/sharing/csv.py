# This file is part of Radicale Server - Calendar Server
# Copyright © 2026-2026 Peter Bieringer <pb@bieringer.de>
# Copyright © 2026-2026 Max Berger <max@berger.name>
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
import json
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

    # *** Overloaded functions ***
    def database_init(self) -> bool:
        logger.debug("sharing database initialization for type 'csv'")
        sharing_db_file = self.configuration.get("sharing", "database_path")
        if sharing_db_file == "":
            folder = self.configuration.get("storage", "filesystem_folder")
            folder_db = os.path.join(folder, "collection-db")
            sharing_db_file = os.path.join(folder_db, "sharing.csv")
            logger.info("sharing database filename not provided, use default: %r", sharing_db_file)
        else:
            sharing_db_file = os.path.abspath(sharing_db_file)
            folder_db = os.path.dirname(sharing_db_file)
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

    def database_get_info(self) -> Union[dict, None]:
        database_info = {'type': "csv"}
        return database_info

    def database_verify(self) -> bool:
        logger.info("sharing database (csv) verification begin")
        logger.info("sharing database (csv) file: %r", self._sharing_db_file)
        logger.info("sharing database (csv) loaded entries: %d", self._lines)
        # nothing more todo for CSV
        logger.info("sharing database (csv) verification end")
        return True

    def database_get_sharing(self,
                             ShareType: str,
                             PathOrToken: str,
                             OnlyEnabled: bool = True,
                             User: Union[str, None] = None) -> Union[dict, None]:
        """ retrieve sharing target and attributes by map """
        # Lookup
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("TRACE/sharing: lookup ShareType=%r PathOrToken=%r User=%r OnlyEnabled=%s)", ShareType, PathOrToken, User, OnlyEnabled)

        index = 0
        found = False
        for row in self._sharing_cache:
            if index == 0:
                # skip fieldnames
                pass
            else:
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug("TRACE/sharing: check row: %r", row)
                if row['ShareType'] != ShareType:
                    pass
                elif row['PathOrToken'] != PathOrToken:
                    pass
                elif User is not None and row['User'] != User:
                    pass
                elif OnlyEnabled is True and row['EnabledByOwner'] is not True:
                    pass
                elif OnlyEnabled is True and row['EnabledByUser'] is not True:
                    pass
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
            Properties: Union[dict, None] = None
            if 'Properties' in row:
                Properties = row['Properties']
            return {
                    "mapped": True,
                    "ShareType": ShareType,
                    "PathOrToken": PathOrToken,
                    "PathMapped": PathMapped,
                    "Owner": Owner,
                    "User": UserShare,
                    "Hidden": Hidden,
                    "Permissions": Permissions,
                    "Properties": Properties}
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
                              HiddenByUser: Union[bool, None] = None) -> list[dict]:
        """ retrieve sharing """
        row: dict
        index = 0
        result = []

        with self._storage.acquire_lock("r", path=self._sharing_db_file):
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("TRACE/sharing/list/called: ShareType=%r OwnerOrUser=%r User=%r PathOrToken=%r PathMapped=%r EnabledByOwner=%s EnabledByUser=%s HiddenByOwner=%s HiddenByUser=%s", ShareType, OwnerOrUser, User, PathOrToken, PathMapped, EnabledByOwner, EnabledByUser, HiddenByOwner, HiddenByUser)

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
                            logger.debug("TRACE/sharing/list/row: add : %r", row)
                        result.append(row)
                index += 1
            return result

    def database_create_sharing(self,
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

        with self._storage.acquire_lock("w", path=self._sharing_db_file):
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
            elif ShareType == "bday":
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug("TRACE/sharing/bday/create: PathOrToken=%r Owner=%r PathMapped=%r User=%r Permissions=%r", PathOrToken, Owner, PathMapped, User, Permissions)
                # check for duplicate map entry
                for row in self._sharing_cache:
                    if row['ShareType'] != "bday":
                        continue
                    if row['PathMapped'] == PathMapped and row['User'] == User and row['PathOrToken'] == PathOrToken:
                        # must be unique systemwide
                        logger.error("sharing/bday/create: entry already exists: PathMapped=%r User=%r", PathMapped, User)
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
                   "TimestampUpdated": Timestamp,
                   "Properties": Properties}

            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("TRACE/sharing/*/create: add row: %r", row)
            self._sharing_cache.append(row)

            if self._write_csv(self._sharing_db_file):
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug("TRACE/sharing/%s/create: write CSV done", ShareType)
                return {"status": "success"}

        logger.error("sharing/%s/create: cannot update CSV database", ShareType)
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
                                Properties: Union[dict, None] = None) -> dict:
        """ update sharing """
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("TRACE/sharing/%s/update: PathOrToken=%r OwnerOrUser=%r PathMapped=%r Properties=%r EnabledByOwner=%s EnabledByUser=%s HiddenByOwner=%s HiddenByUser=%s", ShareType, PathOrToken, OwnerOrUser, PathMapped, Properties, EnabledByOwner, EnabledByUser, HiddenByOwner, HiddenByUser)

        with self._storage.acquire_lock("w", path=self._sharing_db_file):
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
                    logger.debug("TRACE/sharing/%s/update: orig row[%d]=%r", ShareType, index, row)

                # CSV: remove+adjust+readd
                if PathMapped is not None:
                    self._sharing_cache[index]["PathMapped"] = PathMapped
                if Permissions is not None:
                    self._sharing_cache[index]["Permissions"] = Permissions
                if User is not None:
                    self._sharing_cache[index]["User"] = User
                if EnabledByOwner is not None:
                    self._sharing_cache[index]["EnabledByOwner"] = EnabledByOwner
                if EnabledByUser is not None:
                    self._sharing_cache[index]["EnabledByUser"] = EnabledByUser
                if HiddenByOwner is not None:
                    self._sharing_cache[index]["HiddenByOwner"] = HiddenByOwner
                if HiddenByUser is not None:
                    self._sharing_cache[index]["HiddenByUser"] = HiddenByUser
                if Properties is not None:
                    self._sharing_cache[index]["Properties"] = Properties
                # update timestamp
                self._sharing_cache[index]["TimestampUpdated"] = Timestamp

                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug("TRACE/sharing/%s/update: adj  row[%d]=%r", ShareType, index, self._sharing_cache[index])

                if self._write_csv(self._sharing_db_file):
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug("TRACE/sharing/%s/update: write CSV done", ShareType)
                    return {"status": "success"}

                logger.error("sharing/%s/update: cannot update CSV database", ShareType)
                return {"status": "error"}
            else:
                return {"status": "not-found"}

    def database_delete_sharing(self,
                                ShareType: str,
                                PathOrToken: str) -> dict:
        """ delete sharing """
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("TRACE/sharing/%s/delete: PathOrToken=%r", ShareType, PathOrToken)

        with self._storage.acquire_lock("w", path=self._sharing_db_file):
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
                    found = True
                    break
                index += 1

            if found:
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug("TRACE/sharing/%s/delete: found index=%d", ShareType, index)
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug("TRACE/sharing/%s/delete: PathOrToken=%r Owner=%r index=%d", ShareType, PathOrToken, row['Owner'], index)
                self._sharing_cache.pop(index)

                if self._write_csv(self._sharing_db_file):
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug("TRACE/sharing_by_token: write CSV done")
                    return {"status": "success"}

                logger.error("sharing/%s/delete: cannot update CSV database", ShareType)
                return {"status": "error"}
            else:
                return {"status": "not-found"}

    # *** local functions ***
    def _create_empty_csv(self, file: str) -> bool:
        with self._storage.acquire_lock("w", None, path=file):
            with open(file, 'w', newline='') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=sharing.DB_FIELDS_V1, delimiter=';')
                writer.writeheader()
        return True

    def _load_csv(self, file: str) -> bool:
        logger.debug("sharing database load begin: %r", file)
        self._sharing_cache = []
        with self._storage.acquire_lock("r", None):
            with open(file, 'r', newline='') as csvfile:
                reader = csv.DictReader(csvfile, fieldnames=sharing.DB_FIELDS_V1, delimiter=';')
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
                    # convert txt to bool or int
                    if self._lines > 0:
                        for fieldname in row:
                            if logger.isEnabledFor(logging.DEBUG):
                                logger.debug("TRACE/sharing/_load: test fieldname=%r", fieldname)
                            if fieldname not in sharing.DB_TYPES_V1:
                                logger.error("sharing database row error, unsupported fieldname found: %r", fieldname)
                                return False
                            if sharing.DB_TYPES_V1[fieldname] is bool:
                                try:
                                    row[fieldname] = config._convert_to_bool(row[fieldname])
                                except Exception as e:
                                    logger.error("sharing database row error in type conversion fieldname=%r row=%r error: %r", fieldname, row, e)
                                    return False
                            elif sharing.DB_TYPES_V1[fieldname] is int:
                                try:
                                    row[fieldname] = int(row[fieldname])
                                except Exception as e:
                                    logger.error("sharing database row error in type conversion fieldname=%r row=%r error: %r", fieldname, row, e)
                                    return False
                            elif sharing.DB_TYPES_V1[fieldname] is dict:
                                if row[fieldname] is None or row[fieldname] == '':
                                    row[fieldname] = {}
                                else:
                                    field = row[fieldname].lstrip('"').rstrip('"').replace("'", '"')
                                    try:
                                        row[fieldname] = json.loads(field)
                                    except Exception as e:
                                        logger.error("sharing database row error in type conversion fieldname=%r field=%r row=%r error: %r", fieldname, field, row, e)
                                        return False
                    # check for duplicates
                    for row_cached in self._sharing_cache:
                        if row == row_cached:
                            logger.error("sharing database row duplicate row=%r", row)
                            return False
                    # logger.debug("sharing database load add: %r", row)
                    self._sharing_cache.append(row)
                    self._lines += 1
        logger.debug("sharing database load end: %r", file)
        return True

    def _write_csv(self, file: str) -> bool:
        with open(file, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=sharing.DB_FIELDS_V1, delimiter=';')
            writer.writerows(self._sharing_cache)
        return True
