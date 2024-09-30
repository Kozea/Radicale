# This file is part of Radicale - CalDAV and CardDAV server
# Copyright © 2020 Unrud <unrud@outlook.com>
# Copyright © 2024-2024 Peter Bieringer <pb@bieringer.de>
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
import posixpath
import sys
import xml.etree.ElementTree as ET
from typing import Optional

from radicale import (auth, config, hook, httputils, pathutils, rights,
                      storage, types, web, xmlutils)
from radicale.log import logger

# HACK: https://github.com/tiran/defusedxml/issues/54
import defusedxml.ElementTree as DefusedET  # isort:skip
sys.modules["xml.etree"].ElementTree = ET  # type:ignore[attr-defined]


class ApplicationBase:

    configuration: config.Configuration
    _auth: auth.BaseAuth
    _storage: storage.BaseStorage
    _rights: rights.BaseRights
    _web: web.BaseWeb
    _encoding: str
    _permit_delete_collection: bool
    _permit_overwrite_collection: bool
    _hook: hook.BaseHook

    def __init__(self, configuration: config.Configuration) -> None:
        self.configuration = configuration
        self._auth = auth.load(configuration)
        self._storage = storage.load(configuration)
        self._rights = rights.load(configuration)
        self._web = web.load(configuration)
        self._encoding = configuration.get("encoding", "request")
        self._log_bad_put_request_content = configuration.get("logging", "bad_put_request_content")
        self._response_content_on_debug = configuration.get("logging", "response_content_on_debug")
        self._request_content_on_debug = configuration.get("logging", "request_content_on_debug")
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
                             xmlutils.pretty_xml(xml_content))
            else:
                logger.debug("Request content (XML): suppressed by config/option [logging] request_content_on_debug")
        return xml_content

    def _xml_response(self, xml_content: ET.Element) -> bytes:
        if logger.isEnabledFor(logging.DEBUG):
            if self._response_content_on_debug:
                logger.debug("Response content (XML):\n%s",
                             xmlutils.pretty_xml(xml_content))
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
        return status, headers, content


class Access:
    """Helper class to check access rights of an item"""

    user: str
    path: str
    parent_path: str
    permissions: str
    _rights: rights.BaseRights
    _parent_permissions: Optional[str]

    def __init__(self, rights: rights.BaseRights, user: str, path: str
                 ) -> None:
        self._rights = rights
        self.user = user
        self.path = path
        self.parent_path = pathutils.unstrip_path(
            posixpath.dirname(pathutils.strip_path(path)), True)
        self.permissions = self._rights.authorization(self.user, self.path)
        self._parent_permissions = None

    @property
    def parent_permissions(self) -> str:
        if self.path == self.parent_path:
            return self.permissions
        if self._parent_permissions is None:
            self._parent_permissions = self._rights.authorization(
                self.user, self.parent_path)
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
