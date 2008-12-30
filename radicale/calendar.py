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

# TODO: Manage inheritance for classes

from time import time

import support

class Calendar(object):
    """
    Internal Calendar Class
    """
    def __init__(self, user, cal):
        # TODO: Use properties from the calendar
        self.encoding = "utf-8"
        self.owner = "lize"
        self.user = user
        self.cal = cal
        self.version = "2.0"
        self.ctag = str(hash(self.vcalendar()))

    def append(self, vcalendar):
        """
        Append vcalendar
        """
        self.ctag = str(hash(self.vcalendar()))
        support.append(self.cal, vcalendar)

    def remove(self, uid):
        """
        Remove Object Named uid
        """
        self.ctag = str(hash(self.vcalendar()))
        support.remove(self.cal, uid)

    def replace(self, uid, vcalendar):
        """
        Replace Objet Named uid by vcalendar
        """
        self.ctag = str(hash(self.vcalendar()))
        support.remove(self.cal, uid)
        support.append(self.cal, vcalendar)

    def vcalendar(self):
        return unicode(support.read(self.cal), self.encoding)

class Event(object):
    """
    Internal Event Class
    """
    # TODO: Fix the behaviour if no UID is given
    def __init__(self, vcalendar):
        self.text = vcalendar

    def etag(self):
        return str(hash(self.text))

class Header(object):
    """
    Internal Headers Class
    """
    def __init__(self, vcalendar):
        self.text = vcalendar

class Timezone(object):
    """
    Internal Timezone Class
    """
    def __init__(self, vcalendar):
        lines = vcalendar.splitlines()
        for line in lines:
            if line.startswith("TZID:"):
                self.tzid = line.lstrip("TZID:")
                break

        self.text = vcalendar

class Todo(object):
    """
    Internal Todo Class
    """
    # TODO: Fix the behaviour if no UID is given
    def __init__(self, vcalendar):
        self.text = vcalendar

    def etag(self):
        return str(hash(self.text))
