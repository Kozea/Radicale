# -*- coding: utf-8 -*-
#
# This file is part of Radicale Server - Calendar Server
# Copyright © 2008-2010 Guillaume Ayoub
# Copyright © 2008 Nicolas Kandel
# Copyright © 2008 Pascal Halter
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

# TODO: Manage errors (see xmlutils)

import posixpath
import httplib
import BaseHTTPServer

import config
import support
import acl
import xmlutils
import calendar

_users = acl.users()
_calendars = support.calendars()

class CalendarHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    """HTTP requests handler for calendars."""
    def _parse_path(self):
        path = self.path.strip("/").split("/")
        if len(path) >= 2:
            cal = "%s/%s" % (path[0], path[1])
            self.calendar = calendar.Calendar(_users[0], cal)

    def do_DELETE(self):
        """Manage DELETE ``request``."""
        self._parse_path()
        obj = self.headers.get("if-match", None)
        answer = xmlutils.delete(obj, self.calendar, self.path)

        self.send_response(httplib.NO_CONTENT)
        self.send_header("Content-Length", len(answer))
        self.end_headers()
        self.wfile.write(answer)

    def do_OPTIONS(self):
        """Manage OPTIONS ``request``."""
        self.send_response(httplib.OK)
        self.send_header("Allow", "DELETE, OPTIONS, PROPFIND, PUT, REPORT")
        self.send_header("DAV", "1, calendar-access")
        self.end_headers()

    def do_PROPFIND(self):
        """Manage PROPFIND ``request``."""
        self._parse_path()
        xml_request = self.rfile.read(int(self.headers["Content-Length"]))
        answer = xmlutils.propfind(xml_request, self.calendar, self.path)

        self.send_response(httplib.MULTI_STATUS)
        self.send_header("DAV", "1, calendar-access")
        self.send_header("Content-Length", len(answer))
        self.end_headers()
        self.wfile.write(answer)

    def do_PUT(self):
        """Manage PUT ``request``."""
        # TODO: Improve charset detection
        self._parse_path()
        contentType = self.headers["content-type"]
        if contentType and "charset=" in contentType:
            charset = contentType.split("charset=")[1].strip()
        else:
            charset = config.get("encoding", "request")
        ical_request = self.rfile.read(int(self.headers["Content-Length"])).decode(charset)
        obj = self.headers.get("if-match", None)
        xmlutils.put(ical_request, self.calendar, self.path, obj)

        self.send_response(httplib.CREATED)

    def do_REPORT(self):
        """Manage REPORT ``request``."""
        self._parse_path()
        xml_request = self.rfile.read(int(self.headers["Content-Length"]))
        answer = xmlutils.report(xml_request, self.calendar, self.path)

        self.send_response(httplib.MULTI_STATUS)
        self.send_header("Content-Length", len(answer))
        self.end_headers()
        self.wfile.write(answer)
