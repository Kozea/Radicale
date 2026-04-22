# This file is part of Radicale - CalDAV and CardDAV server
# Copyright © 2020 Unrud <unrud@outlook.com>
# Copyright © 2024-2026 Peter Bieringer <pb@bieringer.de>
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

import io
import logging
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET
from typing import Optional, Union

from radicale import (auth, config, hook, httputils, pathutils, rights,
                      sharing, storage, types, utils, web, xmlutils)
from radicale.log import logger
from radicale.rights import intersect

# HACK: https://github.com/tiran/defusedxml/issues/54
import defusedxml.ElementTree as DefusedET  # isort:skip
sys.modules["xml.etree"].ElementTree = ET  # type:ignore[attr-defined]

USER_PATTERN_STRICT: str = "a-zA-Z0-9@\\.\\-_"
PATH_PATTERN_STRICT: str = USER_PATTERN_STRICT + "\\/~"  # / as separator

USER_PATTERN_STRICT_RE: str = "^[" + USER_PATTERN_STRICT + "]+$"
PATH_PATTERN_STRICT_RE: str = "^[" + PATH_PATTERN_STRICT + "]+$"

USER_BLACKLIST_MINIMAL: list = [":", "'", '"', '*', '?']
PATH_BLACKLIST_MINIMAL: list = USER_BLACKLIST_MINIMAL

USER_WHITELIST_UNICODE: list = ["-", ".", "@", "_"]  # from USER_PATTERN_STRICT
PATH_WHITELIST_UNICODE: list = ["-", ".", "@", "_", "/", "~"]  # from PATH_PATTERN_STRICT


class ApplicationBase:

    configuration: config.Configuration
    _auth: auth.BaseAuth
    _storage: storage.BaseStorage
    _rights: rights.BaseRights
    _web: web.BaseWeb
    _sharing: sharing.BaseSharing
    _encoding: str
    _max_resource_size: int
    _permit_delete_collection: bool
    _permit_overwrite_collection: bool
    _strict_preconditions: bool
    _validate_user_value: str
    _validate_path_format: str
    _hook: hook.BaseHook

    def __init__(self, configuration: config.Configuration) -> None:
        self.configuration = configuration
        self._auth = auth.load(configuration)
        self._storage = storage.load(configuration)
        self._rights = rights.load(configuration)
        self._web = web.load(configuration)
        self._sharing = sharing.load(configuration)
        self._encoding = configuration.get("encoding", "request")
        self._log_bad_put_request_content = configuration.get("logging", "bad_put_request_content")
        self._response_content_on_debug = configuration.get("logging", "response_content_on_debug")
        self._request_content_on_debug = configuration.get("logging", "request_content_on_debug")
        self._limit_content = configuration.get("logging", "limit_content")
        self._validate_user_value = configuration.get("server", "validate_user_value")
        self._validate_path_value = configuration.get("server", "validate_path_value")
        self._hook = hook.load(configuration)

    def _read_xml_request_body(self, environ: types.WSGIEnviron
                               ) -> Optional[ET.Element]:
        content = httputils.decode_request(
            self.configuration, environ,
            httputils.read_raw_request_body(self.configuration, environ))
        if not content:
            return None
        try:
            xml_content = DefusedET.fromstring(content)
        except ET.ParseError as e:
            logger.debug("Request content (Invalid XML):\n%s", content)
            raise RuntimeError("Failed to parse XML: %s" % e) from e
        if logger.isEnabledFor(logging.DEBUG):
            if self._request_content_on_debug:
                logger.debug("Request content (XML):\n%s",
                             utils.textwrap_str(xmlutils.pretty_xml(xml_content)))
            else:
                logger.debug("Request content (XML): suppressed by config/option [logging] request_content_on_debug")
        return xml_content

    def _xml_response(self, xml_content: ET.Element) -> bytes:
        if logger.isEnabledFor(logging.DEBUG):
            if self._response_content_on_debug:
                logger.debug("Response content (XML):\n%s",
                             utils.textwrap_str(xmlutils.pretty_xml(xml_content), self._limit_content))
            else:
                logger.debug("Response content (XML): suppressed by config/option [logging] response_content_on_debug")
        f = io.BytesIO()
        ET.ElementTree(xml_content).write(f, encoding=self._encoding,
                                          xml_declaration=True)
        return f.getvalue()

    def _webdav_error_response(self, status: int, human_tag: str
                               ) -> types.WSGIResponse:
        """Generate XML error response."""
        headers = {"Content-Type": "text/xml; charset=%s" % self._encoding}
        content = self._xml_response(xmlutils.webdav_error(human_tag))
        return status, headers, content, None

    def _check_format(self,
                      string: str,
                      blacklist_minimal: list[str],
                      whitelist_unicode: list[str],
                      validation_type: str,
                      ) -> bool:
        check_minimal = (validation_type == "minimal")
        check_unicode_letter = (validation_type == "unicode-letter")
        check_no_unicode = (validation_type == "no-unicode")
        logger.trace("_check_format investigate %r (validation_type=%r check_minimal=%s check_unicode_letter=%s check_no_unicode=%s)", string, validation_type, check_minimal, check_unicode_letter, check_no_unicode)
        if not self._storage._supports_trailing_whitespace and string.endswith(' '):
            return False
        for c in string:
            if c <= chr(31) or (c >= chr(127) and c <= chr(159)):
                # ASCII: control char
                return False
            if unicodedata.category(c)[0] == "C":
                # https://unicodeplus.com/category
                # Unicode: control
                return False
            if check_minimal or not self._storage._supports_problematic_chars:
                if c in blacklist_minimal:
                    logger.trace("_check_format found %r", c)
                    return False
            if check_unicode_letter:
                if c not in whitelist_unicode:
                    if unicodedata.category(c)[0] != "L":
                        return False
            if check_no_unicode:
                if ord(c) > 255:
                    return False
        return True

    def _check_user_format(self, user: str) -> bool:
        if self._validate_user_value == "strict":
            return (re.search(USER_PATTERN_STRICT_RE, user) is not None)
        else:
            return self._check_format(user,
                                      USER_BLACKLIST_MINIMAL,
                                      USER_WHITELIST_UNICODE,
                                      self._validate_user_value,
                                      )

    def _check_path_format(self, path: str) -> bool:
        if self._validate_path_value == "strict":
            return (re.search(PATH_PATTERN_STRICT_RE, path) is not None)
        else:
            return self._check_format(path,
                                      PATH_BLACKLIST_MINIMAL,
                                      PATH_WHITELIST_UNICODE,
                                      self._validate_path_value,
                                      )


class Access:
    """Helper class to check access rights of an item"""

    user: str
    path: str
    parent_path: str
    permissions: str
    _rights: rights.BaseRights
    _parent_permissions: Optional[str]
    _permissions_filter: Union[str, None] = None

    def __init__(self, rights: rights.BaseRights, user: str, path: str, permissions_filter: Union[str, None] = None
                 ) -> None:
        self._rights = rights
        self.user = user
        self.path = path
        self.parent_path = pathutils.parent_path(path)
        self.permissions = self._rights.authorization(self.user, self.path)
        if permissions_filter is not None:
            self._permissions_filter = permissions_filter
            permissions_filtered = intersect(self.permissions, permissions_filter)
            self.permissions = permissions_filtered
        self._parent_permissions = None

    @property
    def parent_permissions(self) -> str:
        if self.path == self.parent_path:
            return self.permissions
        if self._parent_permissions is None:
            self._parent_permissions = self._rights.authorization(
                self.user, self.parent_path)
        if self._permissions_filter is not None:
            parent_permissions_filtered = intersect(self._parent_permissions, self._permissions_filter)
            self._parent_permissions = parent_permissions_filtered
        return self._parent_permissions

    def check(self, permission: str,
              item: Optional[types.CollectionOrItem] = None) -> bool:
        if permission not in "rwdDoO":
            raise ValueError("Invalid permission argument: %r" % permission)
        if not item:
            permissions = permission + permission.upper()
            parent_permissions = permission
        elif isinstance(item, storage.BaseCollection):
            if item.tag:
                permissions = permission
            else:
                permissions = permission.upper()
            parent_permissions = ""
        else:
            permissions = ""
            parent_permissions = permission
        return bool(rights.intersect(self.permissions, permissions) or (
            self.path != self.parent_path and
            rights.intersect(self.parent_permissions, parent_permissions)))
