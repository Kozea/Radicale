# -*- coding: utf-8; indent-tabs-mode: nil; -*-
#
# This file is part of Radicale Server - Calendar Server
# Copyright © 2008-2009 Guillaume Ayoub
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

"""
Radicale calendar classes.

Define the main classes of a calendar as seen from the server.
"""

import support

hash_tag = lambda vcalendar: str(hash(vcalendar))

class Calendar(object):
    """Internal calendar class."""
    def __init__(self, user, cal):
        """Initialize the calendar with ``cal`` and ``user`` parameters."""
        # TODO: Use properties from the calendar configuration
        self.encoding = "utf-8"
        self.owner = "lize"
        self.user = user
        self.cal = cal
        self.version = "2.0"
        self.ctag = hash_tag(self.vcalendar())

    def append(self, vcalendar):
        """Append vcalendar to the calendar."""
        self.ctag = hash_tag(self.vcalendar())
        support.append(self.cal, vcalendar)

    def remove(self, uid):
        """Remove object named ``uid`` from the calendar."""
        self.ctag = hash_tag(self.vcalendar())
        support.remove(self.cal, uid)

    def replace(self, uid, vcalendar):
        """Replace objet named ``uid`` by ``vcalendar`` in the calendar."""
        self.ctag = hash_tag(self.vcalendar())
        support.remove(self.cal, uid)
        support.append(self.cal, vcalendar)

    def vcalendar(self):
        """Return unicode calendar from the calendar."""
        return unicode(support.read(self.cal), self.encoding)

    def etag(self):
        """Return etag from calendar."""
        return '"%s"' % hash_tag(self.vcalendar())

class Event(object):
    """Internal event class."""
    def __init__(self, vcalendar):
        """Initialize event from ``vcalendar``."""
        self.text = vcalendar

    def etag(self):
        """Return etag from event."""
        return '"%s"' % hash_tag(self.text)

class Header(object):
    """Internal header class."""
    def __init__(self, vcalendar):
        """Initialize header from ``vcalendar``."""
        self.text = vcalendar

class Timezone(object):
    """Internal timezone class."""
    def __init__(self, vcalendar):
        """Initialize timezone from ``vcalendar``."""
        lines = vcalendar.splitlines()
        for line in lines:
            if line.startswith("TZID:"):
                self.tzid = line.lstrip("TZID:")
                break

        self.text = vcalendar

class Todo(object):
    """Internal todo class."""
    def __init__(self, vcalendar):
        """Initialize todo from ``vcalendar``."""
        self.text = vcalendar

    def etag(self):
        """Return etag from todo."""
        return hash_tag(self.text)
