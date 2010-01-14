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

"""
iCal parsing functions.
"""

# TODO: Manage filters (see xmlutils)

import calendar

def write_calendar(headers=[
        calendar.Header("PRODID:-//Radicale//NONSGML Radicale Server//EN"),
        calendar.Header("VERSION:2.0")],
                  timezones=[], todos=[], events=[]):
    """Create calendar from ``headers``, ``timezones``, ``todos``, ``events``."""
    # TODO: Manage encoding and EOL
    cal = u"\n".join((
        u"BEGIN:VCALENDAR",
        u"\n".join([header.text for header in headers]),
        u"\n".join([timezone.text for timezone in timezones]),
        u"\n".join([todo.text for todo in todos]),
        u"\n".join([event.text for event in events]),
        u"END:VCALENDAR"))
    return u"\n".join([line for line in cal.splitlines() if line])

def headers(vcalendar):
    """Find Headers items in ``vcalendar``."""
    headers = []

    lines = vcalendar.splitlines()
    for line in lines:
        if line.startswith("PRODID:"):
            headers.append(calendar.Header(line))
    for line in lines:
        if line.startswith("VERSION:"):
            headers.append(calendar.Header(line))

    return headers

def _parse(vcalendar, tag, obj):
    """Find ``tag`` items in ``vcalendar``.
    
    Return a list of items of type ``obj``.
    """
    items = []

    lines = vcalendar.splitlines()
    inItem = False
    itemLines = []

    for line in lines:
        if line.startswith("BEGIN:%s" % tag):
            inItem = True
            itemLines = []

        if inItem:
            # TODO: Manage encoding
            itemLines.append(line)
            if line.startswith("END:%s" % tag):
                items.append(obj("\n".join(itemLines)))

    return items

events = lambda vcalendar: _parse(vcalendar, "VEVENT", calendar.Event)
todos = lambda vcalendar: _parse(vcalendar, "VTODO", calendar.Todo)
timezones = lambda vcalendar: _parse(vcalendar, "VTIMEZONE", calendar.Timezone)
