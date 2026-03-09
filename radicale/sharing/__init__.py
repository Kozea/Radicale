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

import base64
import io
import json
import logging
import re
import socket
import uuid
from csv import DictWriter
from datetime import datetime
from http import client
from typing import Sequence, Union
from urllib.parse import parse_qs

from radicale import (config, httputils, pathutils, rights, storage, types,
                      utils)
from radicale.log import logger

INTERNAL_TYPES: Sequence[str] = ("csv", "files", "none")

DB_FIELDS_V1: Sequence[str] = ('ShareType', 'PathOrToken', 'PathMapped', 'Owner', 'User', 'Permissions', 'EnabledByOwner', 'EnabledByUser', 'HiddenByOwner', 'HiddenByUser', 'TimestampCreated', 'TimestampUpdated', 'Properties')
# ShareType:        <token|map>
# PathOrToken:      <path|token> [PrimaryKey]
# PathMapped:       <path>
# Owner:            <owner> (creator of database entry)
# User:             <user> (user of database entry)
# Permissions:      <radicale permission string>
# EnabledByOwner:   True|False (share status "invite/grant")
# EnabledByUser:    True|False (share status "accept") - check skipped of Owner==User
# HiddenByOwner:    True|False (share exposure controlled by owner)
# HiddenByUser:     True|False (share exposure controlled by user) - check skipped if Owner==User
# TimestampCreated: <unixtime> (when created)
# TimestampUpdated: <unixtime> (last update)
# Properties:       Overlay of collection properties in JSON

DB_TYPES_V1: dict[str, type] = {
        "ShareType": str,
        "PathOrToken": str,
        "PathMapped": str,
        "Owner": str,
        "User": str,
        "Permissions": str,
        "EnabledByOwner": bool,
        "HiddenByOwner": bool,
        "EnabledByUser": bool,
        "HiddenByUser": bool,
        "TimestampCreated": int,
        "TimestampUpdated": int,
        "Properties": dict
}

DB_FIELDS_V1_USER_PERMITTED: Sequence[str] = ('EnabledByUser', 'HiddenByUser', 'Properties')

SHARE_TYPES: Sequence[str] = ('token', 'map', 'all')

SHARE_TYPES_V1: Sequence[str] = ('token', 'map')
# token: share by secret token (does not require authentication)
# map  : share by mapping collection of one user to another as virtual
# all  : only supported for "list" and "info"

API_HOOKS_V1: Sequence[str] = ('list', 'create', 'delete', 'update', 'hide', 'unhide', 'enable', 'disable', 'info')
# list  : list sharings (optional filtered)
# create : create share by token or map
# delete : delete share
# update : update share
# hide   : hide share (by user or owner)
# unhide : unhide share (by user or owner)
# enable : hide share (by user or owner)
# disable: unhide share (by user or owner)
# info   : display support status and permissions

API_SHARE_TOGGLES_V1: Sequence[str] = ('hide', 'unhide', 'enable', 'disable')

API_TYPES_V1: dict[str, type] = {
        "ApiVersion": int,
        "Status": str,
        "Lines": int,
        "FeatureEnabledCollectionByMap": bool,
        "FeatureEnabledCollectionByToken": bool,
        "PermittedCreateCollectionByMap": bool,
        "PermittedCreateCollectionByToken": bool,
        "ShareType": str,
        "PathOrToken": str,
        "PathMapped": str,
        "Owner": str,
        "User": str,
        "Permissions": str,
        "Enabled": bool,
        "Hidden": bool,
        "Properties": dict}

TOKEN_PATTERN_V1: str = "(v1/[a-zA-Z0-9_=\\-]{44})"

PATH_PATTERN: str = "([a-zA-Z0-9/.\\-]+)"  # TODO: extend or find better source

USER_PATTERN: str = "([a-zA-Z0-9@]+)"  # TODO: extend or find better source

OVERLAY_PROPERTIES_WHITELIST: Sequence[str] = ("C:calendar-description", "ICAL:calendar-color", "CR:addressbook-description", "INF:addressbook-color")


def load(configuration: "config.Configuration") -> "BaseSharing":
    """Load the sharing database module chosen in configuration."""
    return utils.load_plugin(INTERNAL_TYPES, "sharing", "Sharing", BaseSharing, configuration)


class BaseSharing:

    _storage: storage.BaseStorage
    _rights: rights.BaseRights
    _enabled: bool = False
    default_permissions_create_token: str
    default_permissions_create_map: str
    sharing_db_type: str

    def __init__(self, configuration: "config.Configuration") -> None:
        """Initialize Sharing.

        ``configuration`` see ``radicale.config`` module.
        The ``configuration`` must not change during the lifetime of
        this object, it is kept as an internal reference.

        """
        self.configuration = configuration
        self._rights = rights.load(configuration)
        self._storage = storage.load(configuration)
        # Sharing
        self.sharing_collection_by_map = configuration.get("sharing", "collection_by_map")
        self.sharing_collection_by_token = configuration.get("sharing", "collection_by_token")
        self.permit_create_token = configuration.get("sharing", "permit_create_token")
        self.permit_create_map = configuration.get("sharing", "permit_create_map")
        self.default_permissions_create_token = configuration.get("sharing", "default_permissions_create_token")
        self.default_permissions_create_map = configuration.get("sharing", "default_permissions_create_map")
        self.permit_properties_overlay = configuration.get("sharing", "permit_properties_overlay")
        self.enforce_properties_overlay = configuration.get("sharing", "enforce_properties_overlay")
        logger.info("sharing.collection_by_map  : %s", self.sharing_collection_by_map)
        logger.info("sharing.collection_by_token: %s", self.sharing_collection_by_token)
        logger.info("sharing.permit_create_token: %s", self.permit_create_token)
        logger.info("sharing.permit_create_map  : %s", self.permit_create_map)
        logger.info("sharing.default_permissions_create_token: %r", self.default_permissions_create_token)
        logger.info("sharing.default_permissions_create_map  : %r", self.default_permissions_create_map)
        logger.info("sharing.permit_properties_overlay: %s", self.permit_properties_overlay)
        logger.info("sharing.enforce_properties_overlay: %s", self.enforce_properties_overlay)

        # database tasks
        self.sharing_db_type = configuration.get("sharing", "type")
        logger.info("sharing.database_type: %s", self.sharing_db_type)

        if ((self.sharing_collection_by_map is False) and (self.sharing_collection_by_token is False)):
            logger.info("sharing disabled as no feature is enabled")
            self._enabled = False
            return
        else:
            self._enabled = True

        if not self._init_db():
            return

    def _init_db(self) -> bool:
        """Initialize Sharing Database
        """
        try:
            if self.database_init() is False:
                logger.info("sharing disabled as no database is active")
                self._enabled = False
                return False
        except Exception as e:
            logger.error("sharing database cannot be initialized: %r", e)
            exit(1)
        database_info = self.database_get_info()
        if database_info:
            logger.info("sharing database info: %r", database_info)
        else:
            logger.info("sharing database info: (not provided)")
        return True

    # *** overloadable database functions ***
    def database_init(self) -> bool:
        """ initialize db """
        return False

    def database_get_info(self) -> Union[dict, None]:
        """ retrieve db information """
        return None

    def database_verify(self) -> bool:
        """ verify db information """
        return False

    def database_list_sharing(self,
                              OwnerOrUser: Union[str, None] = None,
                              ShareType: Union[str, None] = None,
                              PathOrToken: Union[str, None] = None,
                              PathMapped: Union[str, None] = None,
                              User: Union[str, None] = None,
                              EnabledByOwner: Union[bool, None] = None,
                              EnabledByUser:  Union[bool, None] = None,
                              HiddenByOwner:  Union[bool, None] = None,
                              HiddenByUser:   Union[bool, None] = None) -> list[dict]:
        """ retrieve sharing """
        return []

    def database_get_sharing(self,
                             ShareType: str,
                             PathOrToken: str,
                             OnlyEnabled: bool = True,
                             User: Union[str, None] = None) -> Union[dict, None]:
        """ retrieve sharing target and attributes by map """
        return {"status": "not-implemented"}

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
        return {"status": "not-implemented"}

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
        return {"status": "not-implemented"}

    def database_delete_sharing(self,
                                ShareType: str,
                                PathOrToken: str) -> dict:
        """ delete sharing """
        return {"status": "not-implemented"}

    # *** functions called by cli ***
    def verify(self) -> bool:
        """ verify database """
        logger.info("sharing database verification begin")

        if not self._init_db():
            return False

        logger.info("sharing database verification call: %s", self.sharing_db_type)
        result = self.database_verify()
        if result is not True:
            logger.error("sharing database verification call -> PROBLEM: %s", self.sharing_db_type)
            return False
        else:
            pass
        logger.info("sharing database verification call -> OK: %s", self.sharing_db_type)
        # check all entries
        logger.info("sharing database verification content start")
        with self._storage.acquire_lock("r"):
            for entry in self.database_list_sharing():
                logger.debug("analyze: %r", entry)

                # check type
                for fieldname in entry:
                    if fieldname not in DB_TYPES_V1:
                        logger.error("sharing database row error, unsupported fieldname found: %r", fieldname)
                        return False
                    if type(entry[fieldname]) is not DB_TYPES_V1[fieldname]:
                        logger.error("sharing database entry type error fieldname=%r is %r should %r entry=%r", fieldname, type(fieldname), DB_TYPES_V1[fieldname], entry)
                        return False

                if entry['ShareType'] not in SHARE_TYPES_V1:
                    logger.error("ShareType not supported: %r", entry['ShareType'])
                    return False
                elif not entry['PathMapped'].endswith("/"):
                    logger.error("PathMapped not ending with '/': %r", entry['PathMapped'])
                    return False
                elif entry['ShareType'] == "map":
                    if not entry['PathOrToken'].endswith("/"):
                        logger.error("PathOrToken not ending with '/': %r", entry['PathOrToken'])
                        return False
                else:
                    pass

                # permissions
                try:
                    # test
                    config.rights_permission(entry['Permissions'])
                except ValueError:
                    logger.error("Permissions contain invalid entry: %r", entry['Permissions'])
                    return False

                # check PathMapped exists
                with self._storage.acquire_lock("r", path=entry['PathMapped']):
                    item = next(iter(self._storage.discover(entry['PathMapped'])), None)
                    if not item:
                        logger.error("PathMapped is not existing: %r", entry['PathMapped'])
                        return False
                    else:
                        logger.debug("PathMapped exists(ok): %r", entry['PathMapped'])

        logger.info("sharing database verification content successful")
        return True

    # *** sharing functions called by request methods ***
    # list sharings of type "map"
    def sharing_collection_map_list(self, User: Union[str, None] = None, Enabled: Union[bool, None] = None, Hidden: Union[bool, None] = None) -> list[dict]:
        """ returning dict with shared collections by filter(User/Enabled/Hidden) or None if not found"""
        if not self.sharing_collection_by_map:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("TRACE/sharing/map: not active")
            return []

        # retrieve collections depending on filter
        shared_collection_list = self.database_list_sharing(
                ShareType="map",
                OwnerOrUser=User,
                User=User,
                EnabledByOwner=Enabled,
                EnabledByUser=Enabled,
                HiddenByOwner=Hidden,
                HiddenByUser=Hidden)

        # final
        return shared_collection_list

    # resolves a path to a share
    def sharing_collection_resolver(self, path: str, user: str) -> Union[dict, None]:
        """ returning dict with PathMapped, Owner, Permissions or None if not found"""
        if self.sharing_collection_by_token:
            result = self.sharing_collection_by_token_resolver(path)
            if result is not None:
                return result
            else:
                # check for map
                pass
        else:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("TRACE/sharing/token: not active")
            pass

        if self.sharing_collection_by_map:
            result = self.sharing_collection_by_map_resolver(path, user)
            if result is not None:
                return result
        else:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("TRACE/sharing/map: not active")
            return None

        return None

    # adjust a share
    def sharing_collection_update(self, ShareType: str, PathOrToken: str, OwnerOrUser: str, Properties: dict) -> None:
        """ returning dict with PathMapped, Owner, Permissions or None if not found"""
        logger.info("Sharing/collection/update: ShareType=%r PathOrToken=%r OwnerOrUser=%r", ShareType, PathOrToken, OwnerOrUser)
        self.database_update_sharing(ShareType=ShareType,
                                     PathOrToken=PathOrToken,
                                     OwnerOrUser=OwnerOrUser,
                                     Properties=Properties)

    # *** internal sharing functions ***
    # resolves a token "path" to a share
    def sharing_collection_by_token_resolver(self, path) -> Union[dict, None]:
        """ returning dict with PathMapped, Owner, Permissions or None if invalid"""
        if self.sharing_collection_by_token:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("TRACE/sharing/token: check path: %r", path)
            if path.startswith("/.token/"):
                pattern = re.compile('^/\\.token/' + TOKEN_PATTERN_V1 + '$')
                match = pattern.match(path)
                if not match:
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug("TRACE/sharing/token: unsupported token: %r", path)
                    return None
                else:
                    # TODO add token validity checks
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug("TRACE/sharing/token: supported token found in path: %r (token=%r)", path, match[1])
                    result = self.database_get_sharing(
                            ShareType="token",
                            PathOrToken=match[1])
                    if result is not None:
                        logger.info("Sharing/%s: resolved %r->%r, user ->%r, permissions %r", "token", path, result['PathMapped'], result['Owner'], result['Permissions'])
                    return result
            else:
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug("TRACE/sharing/token: no supported prefix found in path: %r", path)
                return None
        else:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("TRACE/sharing/token: not active")
            return None

    # resolves a map "path" to a share
    def sharing_collection_by_map_resolver(self, path: str, user: str) -> Union[dict, None]:
        """ returning dict with PathMapped, Owner, Permissions or None if invalid"""
        if self.sharing_collection_by_map:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("TRACE/sharing/map/resolver: check path: %r", path)
            result = self.database_get_sharing(
                    ShareType="map",
                    PathOrToken=path,
                    User=user)
            if result:
                pass
            else:
                # fallback to parent path
                parent_path = pathutils.parent_path(path)
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug("TRACE/sharing/map/resolver: check parent path: %r", parent_path)
                result = self.database_get_sharing(
                        ShareType="map",
                        PathOrToken=parent_path,
                        User=user)
                if result:
                    result['PathMapped'] = path.replace(parent_path, result['PathMapped'])
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug("TRACE/sharing/map/resolver: PathMapped=%r Permissions=%r by parent_path=%r", result['PathMapped'], result['Permissions'], parent_path)
                else:
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug("TRACE/sharing/map: not found")
                    return None

            logger.info("Sharing/%s: resolved path %r->%r, user %r->%r, permissions %r", "map", path, result['PathMapped'], user, result['Owner'], result['Permissions'])
            return result
        else:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("TRACE/sharing/map: not active")
            return None

    # *** POST API ***
    def post(self, environ: types.WSGIEnviron, base_prefix: str, path: str, user: str) -> types.WSGIResponse:
        # Late import to avoid circular dependency in config
        from radicale.app.base import Access

        """POST request.

        ``base_prefix`` is sanitized and never ends with "/".

        ``path`` is sanitized and always starts with "/.sharing"

        ``user`` is empty for anonymous users.

        Request:
            action: (token|map/list
                PathOrToken: <path|token> (optional for filter)

            action: (token|map)/create
                PathMapped: <path> (mandatory)
                Permissions: <Permissions> (default: r)

                token -> returns <token>

                map
                    PathOrToken: <path> (mandatory)
                    User: <target_user> (mandatory)

            action: (token|map)/update

            action: (token|map)/(delete|disable|enable|hide|unhide)
                PathOrToken: <path|token> (mandatory)

                token

                map
                    PathMapped: <path> (mandator)
                    User: <target_user>

        Response: output format depending on ACCEPT header
            action: list
                by user-owned filtered sharing list in CSV/JSON/TEXT

            actions: (other)
                Status in JSON/TEXT (TEXT can be parsed by shell)

        """
        # initial log prefix
        api_info = "Sharing/API/POST"

        if not self._enabled:
            # API is not enabled
            logger.warning(api_info + ": API is not enabled")
            return httputils.NOT_FOUND

        if user == "":
            # anonymous users are not allowed
            return httputils.NOT_ALLOWED

        # supported API version check
        if not path.startswith("/.sharing/v1/"):
            logger.warning(api_info + ": leading part of path not matching supported API version")
            return httputils.NOT_FOUND

        # split into ShareType and action
        ShareType_action = path.removeprefix("/.sharing/v1/")
        match = re.search('([a-z]+)/([a-z]+)$', ShareType_action)
        if not match:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("TRACE/sharing/API: ShareType/action not extractable: %r", ShareType_action)
            return httputils.NOT_FOUND
        else:
            ShareType = match.group(1)
            action = match.group(2)

        # append ShareType
        api_info = api_info + "/" + ShareType

        # check for valid ShareTypes
        if ShareType:
            if ShareType not in SHARE_TYPES:
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug("TRACE/sharing/API: ShareType not whitelisted: %r", ShareType)
                return httputils.NOT_FOUND

        # check for enabled ShareTypes
        if not self.sharing_collection_by_map and ShareType == "map":
            # API "map" is not enabled
            return httputils.NOT_FOUND

        if not self.sharing_collection_by_token and ShareType == "token":
            # API "token" is not enabled
            return httputils.NOT_FOUND

        # check for valid API hooks
        if action not in API_HOOKS_V1:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("TRACE/sharing/API: action not whitelisted: %r", action)
            return httputils.NOT_FOUND

        # append action
        api_info = api_info + "/" + action

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("TRACE/sharing/API: called by authenticated user: %r", user)
        # read POST data
        try:
            request_body = httputils.read_request_body(self.configuration, environ)
        except RuntimeError as e:
            logger.warning("Bad POST request on %r (read_request_body): %s", path, e, exc_info=True)
            return httputils.bad_request("Failed read POST request body")
        except socket.timeout:
            logger.debug("Client timed out", exc_info=True)
            return httputils.REQUEST_TIMEOUT

        # parse body according to content-type
        content_type = environ.get("CONTENT_TYPE", "")
        if 'application/json' in content_type:
            input_format = "json"
            output_format = "json" # default
            try:
                request_data = json.loads(request_body)
            except json.JSONDecodeError:
                return httputils.bad_request("Invalid JSON")
            for key in ["Enabled", "Hidden"]:
                # convert JSON boolean
                if key in request_data:
                    if type(request_data[key]) is not bool:
                        logger.warning(api_info + ": unsupported (non-boolean) " + key + ": " + request_data[key])
                        return httputils.bad_request("Invalid non-boolean value for " + key + ": " + request_data[key])
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("TRACE/" + api_info + " (json): %r", f"{request_data}")
        elif 'application/x-www-form-urlencoded' in content_type:
            input_format = "form"
            output_format = "plain"  # default
            request_parsed = parse_qs(request_body, keep_blank_values=True)
            # convert arrays into single value
            request_data = {}
            for key in request_parsed:
                if key == "Properties":
                    # Properties key value parser
                    properties_dict: dict = {}
                    for entry in request_parsed[key]:
                        if logger.isEnabledFor(logging.DEBUG):
                            logger.debug("TRACE/sharing/API: parse property %r", entry)
                        if entry == "":
                            continue
                        m = re.search('^([^=]+)=([^=]+)$', entry)
                        if not m:
                            return httputils.bad_request("Invalid properties format in form")
                        token = m.group(1).lstrip('"\'').rstrip('"\'')
                        value = m.group(2).lstrip('"\'').rstrip('"\'')
                        properties_dict[token] = value
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug("TRACE/sharing/API: converted Properties from form into dict: %r", properties_dict)
                    request_data[key] = properties_dict
                    if len(request_data[key]) == 0:
                        # empty
                        request_data[key] = {}
                elif key in ["Enabled", "Hidden"]:
                    try:
                        request_data[key] = config._convert_to_bool(request_parsed[key][0])
                    except ValueError:
                        logger.warning(api_info + ": unsupported (non-boolean) " + key + ": " + request_parsed[key][0])
                        return httputils.bad_request("Invalid non-boolean value for " + key + ": " + request_parsed[key][0])
                else:
                    request_data[key] = request_parsed[key][0]
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("TRACE/" + api_info + " (form): %r", f"{request_data}")
        else:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("TRACE/" + api_info + ": no supported content data")
            return httputils.bad_request("Content-type not supported")

        # check for requested output type
        accept = environ.get("HTTP_ACCEPT", "")
        if 'application/json' in accept:
            output_format = "json"
        elif 'text/csv' in accept:
            output_format = "csv"
        elif 'text/plain' in accept:
            output_format = "plain"
        else:
            # default from input type
            pass

        if output_format == "csv":
            if not action == "list":
                return httputils.bad_request("CSV output format is only allowed for list action")
        elif output_format == "json":
            pass
        elif output_format == "plain":
            pass
        else:
            return httputils.bad_request("Output format not supported")

        # extend log prefix
        api_info = api_info + "(" + input_format + "->" + output_format + ")"

        # parameters default
        PathOrToken: Union[str, None] = None
        PathMapped: Union[str, None] = None
        User: Union[str, None] = None
        Permissions: Union[str, None] = None  # no permissions by default
        Enabled: Union[bool, None] = None
        Hidden:  Union[bool, None] = None
        Properties:     Union[dict, None] = None

        # parameters sanity check
        for key in request_data:
            if key == "Permissions":
                for permission in request_data[key]:
                    if permission not in rights.INTERNAL_PERMISSIONS:
                        return httputils.bad_request("Invalid value for Permissions")
            elif key == "PathOrToken":
                if ShareType == "token":
                    if not re.search('^' + TOKEN_PATTERN_V1 + '$', request_data[key]):
                        logger.warning(api_info + ": unsupported " + key)
                        return httputils.bad_request("Invalid value for PathOrToken")
                elif ShareType == "map":
                    if not re.search('^' + PATH_PATTERN + '$', request_data[key]):
                        logger.warning(api_info + ": unsupported " + key)
                        return httputils.bad_request("Invalid value for PathOrToken")
                elif not request_data[key].endswith("/"):
                    return httputils.bad_request("PathOrToken not ending with /")
            elif key == "PathMapped":
                if not re.search('^' + PATH_PATTERN + '$', request_data[key]):
                    logger.warning(api_info + ": unsupported " + key)
                    return httputils.bad_request("Invalid value for PathMapped")
                elif not request_data[key].endswith("/"):
                    return httputils.bad_request("PathMapped not ending with /")
            elif key == "User":
                if not re.search('^' + USER_PATTERN + '$', request_data[key]):
                    logger.warning(api_info + ": unsupported " + key)
                    return httputils.bad_request("Invalid value for User")

        # check for optional parameters
        if 'PathMapped' in request_data:
            # used by create or list(filter)
            PathMapped = request_data['PathMapped']

        if 'PathOrToken' not in request_data:
            if action == 'info':
                # ignored
                pass
            elif action not in ['list', 'create']:
                logger.warning(api_info + ": missing PathOrToken")
                return httputils.bad_request("Missing PathOrToken")
            else:
                # PathOrToken is optional
                pass
        else:
            if action == "create" and ShareType == "token":
                # not supported
                logger.warning(api_info + ": PathOrToken found but not supported")
                return httputils.bad_request("PathOrToken not supported")
            PathOrToken = request_data['PathOrToken']

        if 'Permissions' in request_data:
            Permissions = request_data['Permissions']

        if 'Properties' in request_data:
            # verify against whitelist
            for entry in request_data['Properties']:
                if entry not in OVERLAY_PROPERTIES_WHITELIST:
                    return httputils.bad_request("Property not supported to overlay: %r" % entry)
            Properties = request_data['Properties']

        if 'Enabled' in request_data:
            Enabled = request_data['Enabled']
        else:
            Enabled = None

        if 'Hidden' in request_data:
            Hidden = request_data['Hidden']
        else:
            Hidden = None

        if 'User' in request_data:
            User = request_data['User']
        else:
            User = None

        answer: dict = {}
        result: dict = {}
        result_array: list[dict]
        answer['ApiVersion'] = 1
        Timestamp = int((datetime.now() - datetime(1970, 1, 1)).total_seconds())

        if not self.sharing_collection_by_map and not self.sharing_collection_by_token:
            if not action == 'info':
                # API is not enabled
                return httputils.NOT_FOUND

        # action: list
        if action == "list":
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("TRACE/" + api_info + ": start")

            if PathOrToken is not None:
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug("TRACE/" + api_info + ": filter: %r", PathOrToken)

            if ShareType != "all":
                result_array = self.database_list_sharing(
                        ShareType=ShareType,
                        OwnerOrUser=user,
                        PathMapped=PathMapped,
                        PathOrToken=PathOrToken)
            else:
                result_array = self.database_list_sharing(
                        OwnerOrUser=user,
                        PathMapped=PathMapped,
                        PathOrToken=PathOrToken)

            answer['Lines'] = len(result_array)
            if len(result_array) == 0:
                answer['Status'] = "not-found"
            else:
                answer['Status'] = "success"
            answer['Content'] = result_array

            logger.info(api_info + ": " + answer['Status'])

        # action: create
        elif action == "create":
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("TRACE/" + api_info + ": start")

            if PathMapped is None:
                logger.warning(api_info + ": missing PathMapped")
                return httputils.bad_request("Missing PathMapped")

            # check whether collection exists
            with self._storage.acquire_lock("r", user, path=PathMapped):
                item = next(iter(self._storage.discover(PathMapped)), None)
                if not item:
                    logger.warning(api_info + ": cannot find PathMapped=%r", PathMapped)
                    return httputils.NOT_FOUND
                if not isinstance(item, storage.BaseCollection):
                    return httputils.METHOD_NOT_ALLOWED

            if Permissions is None:
                if ShareType == "token":
                    Permissions = self.default_permissions_create_token
                elif ShareType == "map":
                    Permissions = self.default_permissions_create_map
                else:
                    # default
                    Permissions = "r"
            else:
                Permissions = str(Permissions)

            if Enabled is None:
                Enabled = False # security by default

            if Hidden is None:
                Hidden = True # security by default

            # create token share with security-by-default for User
            EnabledByUser: bool = False
            HiddenByUser: bool = True

            if user == User:
                # create token share with same flags
                EnabledByUser = Enabled
                HiddenByUser = Hidden

            if ShareType == "token":
                # check access Permissions
                access = Access(self._rights, user, PathMapped)
                if not access.check("r"):
                    logger.warning(api_info + ": access to PathMapped=%r not allowed for owner %r", PathMapped, user)
                    return httputils.NOT_ALLOWED

                if self.permit_create_token is False:
                    if "t" not in access.permissions:
                        logger.warning(api_info + ": access to PathMapped=%r not allowed for owner %r (permit=False but explict grant misses 't')", PathMapped, user)
                        return httputils.NOT_ALLOWED
                else:
                    if "T" in access.permissions:
                        logger.warning(api_info + ": access to PathMapped=%r not allowed for owner %r (permit=True but denied by 'T')", PathMapped, user)
                        return httputils.NOT_ALLOWED

                if User is not None:
                    # user is optional on tokens, otherwise it's the owner itself
                    User = str(User)
                else:
                    User = user

                # v1: create uuid token with 2x 32 bytes = 256 bit
                token = "v1/" + str(base64.urlsafe_b64encode(uuid.uuid4().bytes + uuid.uuid4().bytes), 'utf-8')

                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug("TRACE/" + api_info + ": %r (Permissions=%r token=%r)", PathMapped, Permissions, token)

                result = self.database_create_sharing(
                        ShareType=ShareType,
                        PathOrToken=token,
                        PathMapped=PathMapped,
                        Owner=user,
                        User=User,
                        Permissions=Permissions,
                        EnabledByOwner=Enabled,
                        EnabledByUser=EnabledByUser,
                        HiddenByOwner=Hidden,
                        HiddenByUser=HiddenByUser,
                        Timestamp=Timestamp,
                        Properties=Properties)

                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug("TRACE/" + api_info + ": result=%r", result)

            elif ShareType == "map":
                # check preconditions
                if PathOrToken is None:
                    return httputils.bad_request("Missing PathOrToken")
                else:
                    PathOrToken = str(PathOrToken)

                # retrieve existing share
                share = self.database_get_sharing(ShareType=ShareType, PathOrToken=PathOrToken, OnlyEnabled=False)
                if share is not None:
                    logger.warning(api_info + ": share already exists PathOrToken=%r", PathOrToken)
                    return httputils.CONFLICT

                if User is None:
                    return httputils.bad_request("Missing User")
                else:
                    User = str(User)

                # check access Permissions
                access = Access(self._rights, user, PathMapped, None)  # PathMapped is mandatory
                if not access.check("r") and "i" not in access.permissions:
                    logger.warning(api_info + ": access to PathMapped=%r not allowed for owner %r", PathMapped, user)
                    return httputils.NOT_ALLOWED

                if self.permit_create_map is False:
                    if "m" not in access.permissions:
                        logger.warning(api_info + ": access to PathMapped=%r not allowed for owner %r (permit=False but explicit grant misses 'm')", PathMapped, user)
                        return httputils.NOT_ALLOWED
                else:
                    if "M" in access.permissions:
                        logger.warning(api_info + ": access to PathMapped=%r not allowed for owner %r (permit=True but denied by 'M')", PathMapped, user)
                        return httputils.NOT_ALLOWED

                access = Access(self._rights, User, PathOrToken)
                if not access.check("r"):
                    logger.warning(api_info + ": access to PathOrToken=%r not allowed for User=%r", PathOrToken, User)
                    return httputils.NOT_ALLOWED

                # check whether share is already existing as real collection
                with self._storage.acquire_lock("r", User, path=PathOrToken):
                    item = next(iter(self._storage.discover(PathOrToken)), None)
                    if not item:
                        pass
                    else:
                        logger.warning(api_info + ": PathOrToken=%r already exists as real collection for User=%r", PathOrToken, User)
                        return httputils.CONFLICT

                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug("TRACE/" + api_info + ": %r (Permissions=%r PathOrToken=%r Owner=%r User=%r)", PathMapped, Permissions, PathOrToken, user, User)

                result = self.database_create_sharing(
                        ShareType=ShareType,
                        PathOrToken=PathOrToken,
                        PathMapped=PathMapped,
                        Owner=user,
                        User=User,
                        Permissions=Permissions,
                        EnabledByOwner=Enabled,
                        EnabledByUser=EnabledByUser,
                        HiddenByOwner=Hidden,
                        HiddenByUser=HiddenByUser,
                        Timestamp=Timestamp,
                        Properties=Properties)

            else:
                logger.warning(api_info + ": unsupported for ShareType=%r", ShareType)
                return httputils.bad_request("Invalid share type")
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("TRACE/" + api_info + ": result=%r", result)
            # result handling
            if result['status'] == "conflict":
                return httputils.CONFLICT
            elif result['status'] == "error":
                return httputils.INTERNAL_SERVER_ERROR
            elif result['status'] == "success":
                answer['Status'] = "success"
            else:
                logger.warning(api_info + ": %r by user %r not successful", PathMapped, request_data['User'])
                return httputils.bad_request("Internal Error")

            if ShareType == "token":
                PathOrToken = token
                answer['PathOrToken'] = token

            logger.info(api_info + " success: PathMapped=%r Permissions=%r PathOrToken=%r", PathMapped, Permissions, PathOrToken)

        # action: update
        elif action == "update":
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("TRACE/" + api_info + ": start")

            if ShareType not in ["token", "map"]:
                logger.warning(api_info + ": unsupported for ShareType=%r", ShareType)
                return httputils.bad_request("Invalid share type")

            if PathOrToken is None:
                return httputils.bad_request("Missing PathOrToken")
            else:
                PathOrToken = str(PathOrToken)

            # retrieve existing share
            share = self.database_get_sharing(ShareType=ShareType, PathOrToken=PathOrToken, OnlyEnabled=False)
            if share is None:
                return httputils.NOT_FOUND

            if 'Properties' in request_data:
                if Properties is None:
                    # clear properties
                    Properties = {}
                elif Properties == {}:
                    # empty, nothing to do
                    pass
                elif share['Properties'] is not None:
                    # replace properties
                    for prop in share['Properties']:
                        if logger.isEnabledFor(logging.DEBUG):
                            logger.debug("TRACE/" + api_info + ": check for existing property %r", prop)
                        if prop not in Properties:
                            # overtake
                            if logger.isEnabledFor(logging.DEBUG):
                                logger.debug("TRACE/" + api_info + ": overtake property %r", prop)
                            Properties[prop] = share['Properties'][prop]
                        elif Properties[prop] == '':
                            # unset, do nothing
                            if logger.isEnabledFor(logging.DEBUG):
                                logger.debug("TRACE/" + api_info + ": clear property %r", prop)
                            del Properties[prop]

            if user == share['Owner']:
                if PathMapped is not None:
                    # check access Permissions
                    access = Access(self._rights, user, str(PathMapped), None)
                    if not access.check("r") and "i" not in access.permissions:
                        logger.warning(api_info + ": access to %r not allowed for user %r", PathMapped, user)
                        return httputils.NOT_ALLOWED

                result = self.database_update_sharing(
                       ShareType=ShareType,
                       PathMapped=PathMapped,
                       Permissions=Permissions,
                       EnabledByOwner=Enabled,
                       HiddenByOwner=Hidden,
                       PathOrToken=PathOrToken,
                       OwnerOrUser=user,
                       User=User,
                       Timestamp=Timestamp,
                       Properties=Properties)

            elif user == share['User']:
                # User is only allowed to update Properties
                if PathMapped is not None or Permissions is not None or User is not None:
                    logger.warning(api_info + ": access to %r not allowed for user %r to adjust anything beside: %s", PathOrToken, user, " ".join(DB_FIELDS_V1_USER_PERMITTED))
                    return httputils.NOT_ALLOWED
                if 'Properties' in request_data:
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug("TRACE/sharing/API/update: permit_properties_overlay=%s Permissions=%r", self.permit_properties_overlay, share['Permissions'])
                    if self.permit_properties_overlay:
                        if share['Permissions'] is not None and "p" in str(share['Permissions']):
                            logger.warning(api_info + ": %r properties overlay permitted by option, but denied by permission 'p'", PathOrToken)
                            return httputils.NOT_ALLOWED
                        else:
                            logger.info(api_info + ": %r properties overlay permitted by option", PathOrToken)
                    else:
                        if share['Permissions'] is not None and "P" in str(share['Permissions']):
                            logger.info(api_info + ": %r properties overlay denied by option, but granted by permission 'P'", PathOrToken)
                        else:
                            logger.warning(api_info + ": %r properties overlay denied by option", PathOrToken)
                            return httputils.NOT_ALLOWED
                        return httputils.NOT_ALLOWED

                # limited update as user
                result = self.database_update_sharing(
                       ShareType=ShareType,
                       PathOrToken=str(PathOrToken),  # verification above that it is not None
                       EnabledByUser=Enabled,
                       HiddenByUser=Hidden,
                       Timestamp=Timestamp,
                       Properties=Properties)

            else:
                # neither owner nor user matches
                logger.warning(api_info + ": sharing of %r not permitted for user %r", PathOrToken, user)
                return httputils.NOT_ALLOWED

            # result handling
            if result['status'] == "not-found":
                return httputils.NOT_FOUND
            elif result['status'] == "permission-denied":
                return httputils.NOT_ALLOWED
            elif result['status'] == "success":
                answer['Status'] = "success"
                pass
            else:
                logger.warning(api_info + ": %r not successful", request_data['PathOrToken'])
                return httputils.bad_request("Internal Error")

        # action: delete
        elif action == "delete":
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("TRACE/" + api_info + ": start")

            if ShareType not in ["token", "map"]:
                logger.warning(api_info + ": unsupported for ShareType=%r", ShareType)
                return httputils.bad_request("Invalid share type")

            if PathOrToken is None:
                return httputils.bad_request("Missing PathOrToken")
            else:
                PathOrToken = str(PathOrToken)

            # check whether share exists
            share = self.database_get_sharing(ShareType=ShareType, PathOrToken=PathOrToken, OnlyEnabled=False)
            if share is None:
                return httputils.NOT_FOUND

            if user == share['Owner']:
                result = self.database_delete_sharing(
                       ShareType=ShareType,
                       PathOrToken=PathOrToken) # verification above that it is not None
            else:
                # only owner is permitted to delete a share
                logger.warning(api_info + ": %r not permitted for user %r", PathOrToken, user)
                return httputils.NOT_ALLOWED

            # result handling
            if result['status'] == "not-found":
                return httputils.NOT_FOUND
            elif result['status'] == "permission-denied":
                return httputils.NOT_ALLOWED
            elif result['status'] == "success":
                answer['Status'] = "success"
                pass
            else:
                logger.warning(api_info + ": %r by user %r not successful", request_data['PathOrToken'], request_data['User'])
                return httputils.bad_request("Internal Error")

        # action: info
        elif action == "info":
            logger.info(api_info + ": success")
            answer['Status'] = "success"
            if ShareType in ["all", "map"]:
                answer['FeatureEnabledCollectionByMap'] = self.sharing_collection_by_map
                answer['PermittedCreateCollectionByMap'] = self.permit_create_map
            if ShareType in ["all", "token"]:
                answer['FeatureEnabledCollectionByToken'] = self.sharing_collection_by_token
                answer['PermittedCreateCollectionByToken'] = self.permit_create_token

        # action: TOGGLE
        elif action in API_SHARE_TOGGLES_V1:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("TRACE/sharing/API/POST/" + action)

            if ShareType not in ["token", "map"]:
                logger.warning(api_info + ": unsupported for ShareType=%r", ShareType)
                return httputils.bad_request("Invalid share type")

            if PathOrToken is None:
                return httputils.bad_request("Missing PathOrToken")
            else:
                PathOrToken = str(PathOrToken)

            share = self.database_get_sharing(ShareType=ShareType, PathOrToken=PathOrToken, OnlyEnabled=False)
            if share is None:
                return httputils.NOT_FOUND

            Enabled = None
            Hidden = None

            if action == "disable":
                Enabled = False
            elif action == "enable":
                Enabled = True
            elif action == "hide":
                Hidden = True
            elif action == "unhide":
                Hidden = False

            if user == share['Owner']:
                if user == share['User']:
                    # user is Owner and User
                    result = self.database_update_sharing(
                           ShareType=ShareType,
                           PathOrToken=PathOrToken,
                           EnabledByOwner=Enabled,
                           EnabledByUser=Enabled,
                           HiddenByOwner=Hidden,
                           HiddenByUser=Hidden,
                           Timestamp=Timestamp)
                else:
                    result = self.database_update_sharing(
                           ShareType=ShareType,
                           PathOrToken=PathOrToken,
                           EnabledByOwner=Enabled,
                           HiddenByOwner=Hidden,
                           Timestamp=Timestamp)

            elif user == share['User']:
                result = self.database_update_sharing(
                       ShareType=ShareType,
                       PathOrToken=str(PathOrToken),  # verification above that it is not None
                       EnabledByUser=Enabled,
                       HiddenByUser=Hidden,
                       Timestamp=Timestamp)

            else:
                # neither owner nor user matches
                logger.warning(api_info + ": %r by user %r not permitted", PathOrToken, user)
                return httputils.NOT_ALLOWED

            if result:
                if result['status'] == "not-found":
                    return httputils.NOT_FOUND
                if result['status'] == "permission-denied":
                    return httputils.NOT_ALLOWED
                elif result['status'] == "success":
                    answer['Status'] = "success"
                    pass
            else:
                logger.warning(api_info + ": %r by user %s not successful", request_data['PathOrToken'], user)
                return httputils.bad_request("Internal Error")

        else:
            # default
            logger.warning(api_info + ": unsupported action=%r", action)
            return httputils.bad_request("Invalid action")

        # output handler
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("TRACE/sharing/API/POST output format: %r", output_format)
            logger.debug("TRACE/sharing/API/POST answer: %r", answer)
        if output_format == "csv" or output_format == "plain":
            answer_array = []
            if output_format == "plain":
                for key in answer:
                    if key != 'Content':
                        if API_TYPES_V1[key] is bool or API_TYPES_V1[key] is int:
                            answer_array.append(key + '=' + str(answer[key]))
                        else:
                            answer_array.append(key + "='" + str(answer[key]) + "'")
            if 'Content' in answer and answer['Content'] is not None:
                csv = io.StringIO()
                writer = DictWriter(csv, fieldnames=DB_FIELDS_V1, delimiter=';')
                if output_format == "csv":
                    writer.writeheader()
                elif output_format == "plain":
                    writer.writeheader()
                for entry in answer['Content']:
                    # TODO: Argument 1 to "writerow" of "DictWriter" has incompatible type "str"; expected "Mapping[str, Any]"  [arg-type]
                    writer.writerow(entry)  # type: ignore[arg-type]
                if output_format == "csv":
                    answer_array.append(csv.getvalue())
                else:
                    index = 0
                    for line in csv.getvalue().splitlines():
                        # create a shell array with content lines
                        if index == 0:
                            answer_array.append('Fields="' + line + '"')
                        else:
                            answer_array.append('Content[' + str(index - 1) + ']="' + line.replace('"', '\\"') + '"')
                        index += 1
            headers = {
                "Content-Type": "text/csv"
            }
            return client.OK, headers, "\n".join(answer_array), None
        elif output_format == "json":
            answer_raw = json.dumps(answer)
            headers = {
                "Content-Type": "text/json"
            }
            return client.OK, headers, answer_raw, None
        else:
            # should not be reached
            return httputils.bad_request("Invalid output format")

        return httputils.METHOD_NOT_ALLOWED
