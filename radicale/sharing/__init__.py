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
DB_FIELDS_V1_BOOL: Sequence[str] = ('EnabledByOwner', 'EnabledByUser', 'HiddenByOwner', 'HiddenByUser')
DB_FIELDS_V1_INT: Sequence[str] = ('TimestampCreated', 'TimestampUpdated')
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

SHARE_TYPES: Sequence[str] = ('token', 'map', 'all')
SHARE_TYPES_V1: Sequence[str] = ('token', 'map')
# token: share by secret token (does not require authentication)
# map  : share by mapping collection of one user to another as virtual
# all  : only supported for "list" and "info"

OUTPUT_TYPES: Sequence[str] = ('csv', 'json', 'txt')

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
        logger.info("sharing.collection_by_map  : %s", self.sharing_collection_by_map)
        logger.info("sharing.collection_by_token: %s", self.sharing_collection_by_token)
        logger.info("sharing.permit_create_token: %s", self.permit_create_token)
        logger.info("sharing.permit_create_map  : %s", self.permit_create_map)
        logger.info("sharing.default_permissions_create_token: %r", self.default_permissions_create_token)
        logger.info("sharing.default_permissions_create_map  : %r", self.default_permissions_create_map)

        if ((self.sharing_collection_by_map is False) and (self.sharing_collection_by_token is False)):
            logger.info("sharing disabled as no feature is enabled")
            self._enabled = False
            return
        else:
            self._enabled = True

        # database tasks
        self.sharing_db_type = configuration.get("sharing", "type")
        logger.info("sharing.db_type: %s", self.sharing_db_type)

        try:
            if self.init_database() is False:
                logger.info("sharing disabled as no database is active")
                self._enabled = False
                return
        except Exception as e:
            logger.error("sharing database cannot be initialized: %r", e)
            exit(1)
        database_info = self.get_database_info()
        if database_info:
            logger.info("sharing database info: %r", database_info)
        else:
            logger.info("sharing database info: (not provided)")

    # overloadable functions
    def init_database(self) -> bool:
        """ initialize database """
        return False

    def get_database_info(self) -> Union[dict, None]:
        """ retrieve database information """
        return None

    def verify_database(self) -> bool:
        """ verify database information """
        return False

    def list_sharing(self,
                     OwnerOrUser: Union[str, None] = None,
                     ShareType: Union[str, None] = None,
                     PathOrToken: Union[str, None] = None,
                     PathMapped: Union[str, None] = None,
                     User: Union[str, None] = None,
                     EnabledByOwner: Union[bool, None] = None,
                     EnabledByUser: Union[bool, None] = None,
                     HiddenByOwner: Union[bool, None] = None,
                     HiddenByUser:  Union[bool, None] = None) -> list[dict]:
        """ retrieve sharing """
        return []

    def get_sharing(self,
                    ShareType: str,
                    PathOrToken: str,
                    User: Union[str, None] = None) -> Union[dict, None]:
        """ retrieve sharing target and attributes by map """
        return {"status": "not-implemented"}

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
        return {"status": "not-implemented"}

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
        return {"status": "not-implemented"}

    def delete_sharing(self,
                       ShareType: str,
                       PathOrToken: str,
                       Owner: str,
                       PathMapped: Union[str, None] = None) -> dict:
        """ delete sharing """
        return {"status": "not-implemented"}

    def toggle_sharing(self,
                       ShareType: str,
                       PathOrToken: str,
                       OwnerOrUser: str,
                       Action: str,
                       PathMapped: Union[str, None] = None,
                       User: Union[str, None] = None,
                       Timestamp: int = 0) -> dict:
        """ toggle sharing """
        return {"status": "not-implemented"}

    # sharing functions called by request methods
    def verify(self) -> bool:
        """ verify database """
        logger.info("sharing database verification begin")
        logger.info("sharing database verification call: %s", self.sharing_db_type)
        result = self.verify_database()
        if result is not True:
            logger.error("sharing database verification call -> PROBLEM: %s", self.sharing_db_type)
            return False
        else:
            pass
        logger.info("sharing database verification call -> OK: %s", self.sharing_db_type)
        # check all entries
        logger.info("sharing database verification content start")
        with self._storage.acquire_lock("r"):
            for entry in self.list_sharing():
                logger.debug("analyze: %r", entry)
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
                # TODO: check PathMapped exists
        logger.info("sharing database verification content successful")
        return True

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
            return None

        if self.sharing_collection_by_map:
            result = self.sharing_collection_by_map_resolver(path, user)
            if result is not None:
                return result
        else:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("TRACE/sharing/map: not active")
            return None

        # final
        return None

    # list sharings of type "map"
    def sharing_collection_map_list(self, user: str, active: bool = True) -> list[dict]:
        """ returning dict with shared collections (active==True: enabled and unhidden) or None if not found"""
        if not self.sharing_collection_by_map:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("TRACE/sharing/map: not active")
            return [{}]

        # retrieve collections which are enabled and not hidden by owner+user
        if active:
            shared_collection_list = self.list_sharing(
                    ShareType="map",
                    OwnerOrUser=user,
                    User=user,
                    EnabledByOwner=True,
                    EnabledByUser=True,
                    HiddenByOwner=False,
                    HiddenByUser=False)
        else:
            # unconditional
            shared_collection_list = self.list_sharing(
                    ShareType="map",
                    OwnerOrUser=user,
                    User=user)

        # final
        return shared_collection_list

    # internal sharing functions
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
                    return self.get_sharing(
                            ShareType="token",
                            PathOrToken=match[1])
            else:
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug("TRACE/sharing/token: no supported prefix found in path: %r", path)
                return None
        else:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("TRACE/sharing/token: not active")
            return None

    def sharing_collection_by_map_resolver(self, path: str, user: str) -> Union[dict, None]:
        """ returning dict with PathMapped, Owner, Permissions or None if invalid"""
        if self.sharing_collection_by_map:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("TRACE/sharing/map/resolver: check path: %r", path)
            result = self.get_sharing(
                    ShareType="map",
                    PathOrToken=path,
                    User=user)
            if result:
                return result
            else:
                # fallback to parent path
                parent_path = pathutils.parent_path(path)
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug("TRACE/sharing/map/resolver: check parent path: %r", parent_path)
                result = self.get_sharing(
                        ShareType="map",
                        PathOrToken=parent_path,
                        User=user)
                if result:
                    result['PathMapped'] = path.replace(parent_path, result['PathMapped'])
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug("TRACE/sharing/map/resolver: PathMapped=%r Permissions=%r by parent_path=%r", result['PathMapped'], result['Permissions'], parent_path)
                    return result
                else:
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug("TRACE/sharing/map: not found")
                    return None
        else:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("TRACE/sharing/map: not active")
            return None

    # POST API
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
        if not self._enabled:
            # API is not enabled
            return httputils.NOT_FOUND

        if user == "":
            # anonymous users are not allowed
            return httputils.NOT_ALLOWED

        # supported API version check
        if not path.startswith("/.sharing/v1/"):
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

        api_info = "sharing/API/POST/" + ShareType + "/" + action

        # parse body according to content-type
        content_type = environ.get("CONTENT_TYPE", "")
        if 'application/json' in content_type:
            try:
                request_data = json.loads(request_body)
            except json.JSONDecodeError:
                return httputils.bad_request("Invalid JSON")
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("TRACE/" + api_info + " (json): %r", f"{request_data}")
        elif 'application/x-www-form-urlencoded' in content_type:
            request_parsed = parse_qs(request_body)
            # convert arrays into single value
            request_data = {}
            for key in request_parsed:
                if key == "Properties":
                    # Properties key value parser
                    properties_dict: dict = {}
                    for entry in request_parsed[key]:
                        m = re.search('^([^=]+)=([^=]+)$', entry)
                        if not m:
                            return httputils.bad_request("Invalid properties format in form")
                        token = m.group(1).lstrip('"\'').rstrip('"\'')
                        value = m.group(2).lstrip('"\'').rstrip('"\'')
                        properties_dict[token] = value
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug("TRACE/sharing/API: converted Properties from form into dict: %r", properties_dict)
                    request_data[key] = properties_dict
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
        else:
            output_format = "txt"

        if output_format == "csv":
            if not action == "list":
                return httputils.bad_request("CSV output format is only allowed for list action")
        elif output_format == "json":
            pass
        elif output_format == "txt":
            pass
        else:
            return httputils.bad_request("Output format not supported")

        # parameters default
        PathOrToken: Union[str, None] = None
        PathMapped: Union[str, None] = None
        Owner: str = user
        User: Union[str, None] = None
        Permissions: Union[str, None] = None  # no permissions by default
        EnabledByOwner: Union[bool, None] = None
        HiddenByOwner:  Union[bool, None] = None
        EnabledByUser:  Union[bool, None] = None
        HiddenByUser:   Union[bool, None] = None
        Properties:     Union[dict, None] = None

        # parameters sanity check
        for key in request_data:
            if key == "Permissions":
                if not re.search('^[a-zA-Z]+$', request_data[key]):
                    return httputils.bad_request("Invalid value for Permissions")
            elif key == "PathOrToken":
                if ShareType == "token":
                    if not re.search('^' + TOKEN_PATTERN_V1 + '$', request_data[key]):
                        logger.error(api_info + ": unsupported " + key)
                        return httputils.bad_request("Invalid value for PathOrToken")
                elif ShareType == "map":
                    if not re.search('^' + PATH_PATTERN + '$', request_data[key]):
                        logger.error(api_info + ": unsupported " + key)
                        return httputils.bad_request("Invalid value for PathOrToken")
                elif not request_data[key].endswith("/"):
                    return httputils.bad_request("PathOrToken not ending with /")
            elif key == "PathMapped":
                if not re.search('^' + PATH_PATTERN + '$', request_data[key]):
                    logger.error(api_info + ": unsupported " + key)
                    return httputils.bad_request("Invalid value for PathMapped")
                elif not request_data[key].endswith("/"):
                    return httputils.bad_request("PathMapped not ending with /")
            elif key == "Enabled" or key == "Hidden":
                if not re.search('^(False|True)$', request_data[key]):
                    logger.error(api_info + ": unsupported " + key)
                    return httputils.bad_request("Invalid value for " + key)
            elif key == "User":
                if not re.search('^' + USER_PATTERN + '$', request_data[key]):
                    logger.error(api_info + ": unsupported " + key)
                    return httputils.bad_request("Invalid value for User")

        # check for mandatory parameters
        if 'PathMapped' not in request_data:
            if action in ['info', 'list', 'update']:
                # ignored
                pass
            else:
                if ShareType == "token" and action != 'create':
                    # optional
                    pass
                else:
                    logger.error(api_info + ": missing PathMapped")
                    return httputils.bad_request("Missing PathMapped")
        else:
            PathMapped = request_data['PathMapped']

        if 'PathOrToken' not in request_data:
            if action == 'info':
                # ignored
                pass
            elif action not in ['list', 'create']:
                logger.error(api_info + ": missing PathOrToken")
                return httputils.bad_request("Missing PathOrToken")
            else:
                # PathOrToken is optional
                pass
        else:
            if action == "create" and ShareType == "token":
                # not supported
                logger.error(api_info + ": PathOrToken found but not supported")
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

        if ShareType == "map":
            if action == 'info':
                # ignored
                pass
            else:
                if 'User' not in request_data:
                    if action not in ['list', 'delete', 'update']:
                        logger.warning(api_info + ": missing User")
                        return httputils.bad_request("Missing User")
                    else:
                        # optional
                        pass
                else:
                    User = request_data['User']

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
            if 'PathOrToken' in request_data:
                PathOrToken = request_data['PathOrToken']
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug("TRACE/" + api_info + ": filter: %r", PathOrToken)

            if ShareType != "all":
                result_array = self.list_sharing(
                        ShareType=ShareType,
                        OwnerOrUser=Owner,
                        PathMapped=PathMapped,
                        PathOrToken=PathOrToken)
            else:
                result_array = self.list_sharing(
                        OwnerOrUser=Owner,
                        PathMapped=PathMapped,
                        PathOrToken=PathOrToken)

            answer['Lines'] = len(result_array)
            if len(result_array) == 0:
                answer['Status'] = "not-found"
            else:
                answer['Status'] = "success"
            answer['Content'] = result_array

        # action: create
        elif action == "create":
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("TRACE/" + api_info + ": start")
            if 'Permissions' not in request_data:
                if ShareType == "token":
                    Permissions = self.default_permissions_create_token
                elif ShareType == "map":
                    Permissions = self.default_permissions_create_map
                else:
                    # default
                    Permissions = "r"

            if 'Enabled' in request_data:
                EnabledByOwner = config._convert_to_bool(request_data['Enabled'])
            else:
                EnabledByOwner = False # security by default

            if 'Hidden' in request_data:
                HiddenByOwner = config._convert_to_bool(request_data['Hidden'])
            else:
                HiddenByOwner = True # security by default

            EnabledByUser = False # security by default
            HiddenByUser = True # security by default

            if ShareType == "token":
                # check access Permissions
                access = Access(self._rights, user, str(PathMapped))  # PathMapped is mandatory
                if not access.check("r"):
                    logger.info("Add sharing-by-token: access to %r not allowed for user %r", PathMapped, user)
                    return httputils.NOT_ALLOWED

                if self.permit_create_token is False:
                    if "t" not in access.permissions:
                        logger.info("Add sharing-by-token: access to %r not allowed for user %r (permit=False but explict grant misses 't')", PathMapped, user)
                        return httputils.NOT_ALLOWED
                else:
                    if "T" in access.permissions:
                        logger.info("Add sharing-by-token: access to %r not allowed for user %r (permit=True but denied by 'T')", PathMapped, user)
                        return httputils.NOT_ALLOWED

                # v1: create uuid token with 2x 32 bytes = 256 bit
                token = "v1/" + str(base64.urlsafe_b64encode(uuid.uuid4().bytes + uuid.uuid4().bytes), 'utf-8')

                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug("TRACE/" + api_info + ": %r (Permissions=%r token=%r)", PathMapped, Permissions, token)
                result = self.create_sharing(
                        ShareType=ShareType,
                        PathOrToken=token,
                        PathMapped=str(PathMapped), # mandatory
                        Owner=Owner, User=Owner,
                        Permissions=str(Permissions), # mandantory
                        EnabledByOwner=EnabledByOwner, HiddenByOwner=HiddenByOwner,
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

                if User is None:
                    return httputils.bad_request("Missing User")
                else:
                    User = str(User)

                # check access Permissions
                access = Access(self._rights, Owner, str(PathMapped), None)  # PathMapped is mandatory
                if not access.check("r") and "i" not in access.permissions:
                    logger.info("Add sharing-by-map: access to path(mapped) %r not allowed for owner %r", PathMapped, Owner)
                    return httputils.NOT_ALLOWED

                if self.permit_create_map is False:
                    if "m" not in access.permissions:
                        logger.info("Add sharing-by-map: access to %r not allowed for user %r (permit=False but explicit grant misses 'm')", PathMapped, user)
                        return httputils.NOT_ALLOWED
                else:
                    if "M" in access.permissions:
                        logger.info("Add sharing-by-map: access to %r not allowed for user %r (permit=True but denied by 'M')", PathMapped, user)
                        return httputils.NOT_ALLOWED

                access = Access(self._rights, str(User), PathOrToken)
                if not access.check("r"):
                    logger.info("Add sharing-by-map: access to path %r not allowed for user %r", PathOrToken, User)
                    return httputils.NOT_ALLOWED

                # check whether share is already existing as real collection
                with self._storage.acquire_lock("r", user, path=PathOrToken):
                    item = next(iter(self._storage.discover(PathOrToken)), None)
                    if not item:
                        pass
                    else:
                        logger.info("Add sharing-by-map: path %r already exists as real collection for user %r", PathOrToken, user)
                        return httputils.CONFLICT

                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug("TRACE/" + api_info + ": %r (Permissions=%r PathOrToken=%r user=%r)", PathMapped, Permissions, PathOrToken, User)
                result = self.create_sharing(
                        ShareType=ShareType,
                        PathOrToken=PathOrToken,  # verification above that it is not None
                        PathMapped=str(PathMapped),  # mandatory
                        Owner=Owner,
                        User=User,  # verification above that it is not None
                        Permissions=str(Permissions),  # mandatory
                        EnabledByOwner=EnabledByOwner, HiddenByOwner=HiddenByOwner,
                        EnabledByUser=EnabledByUser, HiddenByUser=HiddenByUser,
                        Timestamp=Timestamp,
                        Properties=Properties)

            else:
                logger.error(api_info + ": unsupported for ShareType=%r", ShareType)
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
                return httputils.bad_request("Internal failure")

            if ShareType == "token":
                logger.info(api_info + "(success): %r (Permissions=%r token=%r)", PathMapped, Permissions, token)
                answer['PathOrToken'] = token

        # action: update
        elif action == "update":
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("TRACE/" + api_info + ": start")

            if PathOrToken is None:
                return httputils.bad_request("Missing PathOrToken")

            if ShareType == "token":
                result = self.update_sharing(
                       ShareType=ShareType,
                       PathMapped=PathMapped,
                       Permissions=Permissions,
                       EnabledByOwner=EnabledByOwner,
                       HiddenByOwner=HiddenByOwner,
                       PathOrToken=str(PathOrToken),  # verification above that it is not None
                       OwnerOrUser=Owner,
                       User=User,
                       Timestamp=Timestamp,
                       Properties=Properties)

            elif ShareType == "map":
                result = self.update_sharing(
                       ShareType=ShareType,
                       PathMapped=PathMapped,
                       Permissions=Permissions,
                       EnabledByOwner=EnabledByOwner,
                       HiddenByOwner=HiddenByOwner,
                       PathOrToken=str(PathOrToken),  # verification above that it is not None
                       OwnerOrUser=Owner,
                       User=User,
                       Timestamp=Timestamp,
                       Properties=Properties)

            else:
                logger.error(api_info + ": unsupported for ShareType=%r", ShareType)
                return httputils.bad_request("Invalid share type")

            # result handling
            if result['status'] == "not-found":
                return httputils.NOT_FOUND
            elif result['status'] == "permission-denied":
                return httputils.NOT_ALLOWED
            elif result['status'] == "success":
                answer['Status'] = "success"
                pass
            else:
                if ShareType == "token":
                    logger.info("Update of sharing-by-token: %r not successful", request_data['PathOrToken'])
                elif ShareType == "map":
                    logger.info("Update of sharing-by-map: %r not successful", request_data['PathOrToken'])
                return httputils.bad_request("Invalid share type")

        # action: delete
        elif action == "delete":
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("TRACE/" + api_info + ": start")

            if PathOrToken is None:
                return httputils.bad_request("Missing PathOrToken")

            if ShareType == "token":
                result = self.delete_sharing(
                       ShareType=ShareType,
                       PathOrToken=str(PathOrToken),  # verification above that it is not None
                       Owner=Owner)

            elif ShareType == "map":
                result = self.delete_sharing(
                       ShareType=ShareType,
                       PathOrToken=str(PathOrToken),  # verification above that it is not None
                       PathMapped=PathMapped,
                       Owner=Owner)

            else:
                logger.error(api_info + ": unsupported for ShareType=%r", ShareType)
                return httputils.bad_request("Invalid share type")

            # result handling
            if result['status'] == "not-found":
                return httputils.NOT_FOUND
            elif result['status'] == "permission-denied":
                return httputils.NOT_ALLOWED
            elif result['status'] == "success":
                answer['Status'] = "success"
                pass
            else:
                if ShareType == "token":
                    logger.info("Delete sharing-by-token: %r of user %r not successful", request_data['PathOrToken'], request_data['User'])
                elif ShareType == "map":
                    logger.info("Delete sharing-by-map: %r of user %r not successful", request_data['PathOrToken'], request_data['User'])
                return httputils.bad_request("Invalid share type")

        # action: info
        elif action == "info":
            answer['Status'] = "success"
            if ShareType in ["all", "map"]:
                answer['FeatureEnabledCollectionByMap'] = self.sharing_collection_by_map
                answer['PermittedCreateCollectionByMap'] = True # TODO toggle per permission, default?
            if ShareType in ["all", "token"]:
                answer['FeatureEnabledCollectionByToken'] = self.sharing_collection_by_token
                answer['PermittedCreateCollectionByToken'] = True # TODO toggle per permission, default?

        # action: TOGGLE
        elif action in API_SHARE_TOGGLES_V1:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("TRACE/sharing/API/POST/" + action)

            if ShareType in ["token", "map"]:
                if PathOrToken is None:
                    return httputils.bad_request("Missing PathOrToken")

                result = self.toggle_sharing(
                       ShareType=ShareType,
                       PathOrToken=str(PathOrToken),  # verification above that it is not None
                       OwnerOrUser=user,        # authenticated user
                       User=User,               # optional for selection
                       PathMapped=PathMapped,  # optional for selection
                       Action=action,
                       Timestamp=Timestamp)

                if result:
                    if result['status'] == "not-found":
                        return httputils.NOT_FOUND
                    if result['status'] == "permission-denied":
                        return httputils.NOT_ALLOWED
                    elif result['status'] == "success":
                        answer['Status'] = "success"
                        pass
                else:
                    logger.error("Toggle sharing: %r of user %s not successful", request_data['PathOrToken'], user)
                    return httputils.bad_request("Internal Error")

            else:
                logger.error(api_info + ": unsupported for ShareType=%r", ShareType)
                return httputils.bad_request("Invalid share type")

        else:
            # default
            logger.error(api_info + ": unsupported action=%r", action)
            return httputils.bad_request("Invalid action")

        # output handler
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("TRACE/sharing/API/POST output format: %r", output_format)
            logger.debug("TRACE/sharing/API/POST answer: %r", answer)
        if output_format == "csv" or output_format == "txt":
            answer_array = []
            if output_format == "txt":
                for key in answer:
                    if key != 'Content':
                        answer_array.append(key + '=' + str(answer[key]))
            if 'Content' in answer and answer['Content'] is not None:
                csv = io.StringIO()
                writer = DictWriter(csv, fieldnames=DB_FIELDS_V1, delimiter=';')
                if output_format == "csv":
                    writer.writeheader()
                for entry in answer['Content']:
                    writer.writerow(entry)
                if output_format == "csv":
                    answer_array.append(csv.getvalue())
                else:
                    index = 0
                    for line in csv.getvalue().splitlines():
                        # create a shell array with content lines
                        answer_array.append('Content[' + str(index) + ']="' + line.replace('"', '\\"') + '"')
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
