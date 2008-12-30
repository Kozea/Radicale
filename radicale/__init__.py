# -*- coding: utf-8; indent-tabs-mode: nil; -*-
#
# This file is part of Radicale Server - Calendar Server
# Copyright © 2008 The Radicale Team
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

from twisted.web.resource import Resource
from twisted.web import http
import posixpath

import config

import support
import acl

import xmlutils
import calendar

_users = acl.users()
_calendars = support.calendars()

class CalendarResource(Resource):
    """
    Twisted resource for requests at calendar depth (/user/calendar)
    """
    isLeaf = True

    def __init__(self, user, cal):
        """
        Initialize resource creating a calendar object corresponding
        to the stocked calendar named user/cal
        """
        Resource.__init__(self)
        self.calendar = calendar.Calendar(user, cal)

    def render_DELETE(self, request):
        """
        Manage DELETE requests
        """
        obj = request.getHeader("if-match")
        answer = xmlutils.delete(obj, self.calendar, str(request.URLPath()))
        request.setResponseCode(http.NO_CONTENT)
        return answer

    def render_OPTIONS(self, request):
        """
        Manage OPTIONS requests
        """
        request.setHeader("Allow", "DELETE, OPTIONS, PROPFIND, PUT, REPORT")
        request.setHeader("DAV", "1, calendar-access")
        request.setResponseCode(http.OK)
        return ""

    def render_PROPFIND(self, request):
        """
        Manage PROPFIND requests
        """
        xmlRequest = request.content.read()
        answer = xmlutils.propfind(xmlRequest, self.calendar, str(request.URLPath()))
        request.setResponseCode(http.MULTI_STATUS)
        return answer

    def render_PUT(self, request):
        """
        Manage PUT requests
        """
        # TODO: Improve charset detection
        contentType = request.getHeader("content-type")
        if contentType and "charset=" in contentType:
            charset = contentType.split("charset=")[1].strip()
        else:
            charset = config.get("encoding", "request")
        icalRequest = unicode(request.content.read(), charset)
        obj = request.getHeader("if-match")
        xmlutils.put(icalRequest, self.calendar, str(request.URLPath()), obj)
        request.setResponseCode(http.CREATED)
        return ""

    def render_REPORT(self, request):
        """
        Manage REPORT requests
        """
        xmlRequest = request.content.read()
        answer = xmlutils.report(xmlRequest, self.calendar, str(request.URLPath()))
        request.setResponseCode(http.MULTI_STATUS)
        return answer

class UserResource(Resource):
    """
    Twisted resource for requests at user depth (/user)
    """
    def __init__(self, user):
        """
        Initialize resource by connecting children requests to
        the user calendars resources
        """
        Resource.__init__(self)
        for cal in _calendars:
            if cal.startswith("%s%s"%(user, posixpath.sep)):
                calName = cal.split(posixpath.sep)[1]
                self.putChild(calName, CalendarResource(user, cal))
    
    def getChild(self, cal, request):
        """
        Get calendar resource if user exists
        """
        if cal in _calendars:
            return Resource.getChild(self, cal, request)
        else:
            return self

class HttpResource(Resource):
    """
    Twisted resource for requests at root depth (/)
    """
    def __init__(self):
        """
        Initialize resource by connecting children requests to
        the users resources
        """
        Resource.__init__(self)
        for user in _users:
            self.putChild(user, UserResource(user))

    def getChild(self, user, request):
        """
        Get user resource if user exists
        """
        if user in _users:
            return Resource.getChild(self, user, request)
        else:
            return self
