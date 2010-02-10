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

from radicale import calendar


def write_calendar(headers=(
        calendar.Header("PRODID:-//Radicale//NONSGML Radicale Server//EN"),
        calendar.Header("VERSION:2.0")),
                   timezones=(), todos=(), events=()):
    """Create calendar from given parameters."""
    cal = "\n".join((
        "BEGIN:VCALENDAR",
        "\n".join([header.text for header in headers]),
        "\n".join([timezone.text for timezone in timezones]),
        "\n".join([todo.text for todo in todos]),
        "\n".join([event.text for event in events]),
        "END:VCALENDAR"))
    return "\n".join([line for line in cal.splitlines() if line])


def _parse(vcalendar, tag, obj):
    """Find ``tag`` items in ``vcalendar``.
    
    Return a list of items of type ``obj``.

    """
    items = []

    lines = vcalendar.splitlines()
    in_item = False
    item_lines = []

    for line in lines:
        if line.startswith("BEGIN:%s" % tag):
            in_item = True
            item_lines = []

        if in_item:
            item_lines.append(line)
            if line.startswith("END:%s" % tag):
                items.append(obj("\n".join(item_lines)))

    return items


def headers(vcalendar):
    """Find Headers items in ``vcalendar``."""
    header_lines = []

    lines = vcalendar.splitlines()
    for line in lines:
        if line.startswith("PRODID:"):
            header_lines.append(calendar.Header(line))
    for line in lines:
        if line.startswith("VERSION:"):
            header_lines.append(calendar.Header(line))

    return header_lines


def events(vcalendar):
    """Get list of ``Event`` from VEVENTS items in ``vcalendar``."""
    return _parse(vcalendar, "VEVENT", calendar.Event)


def todos(vcalendar):
    """Get list of ``Todo`` from VTODO items in ``vcalendar``."""
    return _parse(vcalendar, "VTODO", calendar.Todo)


def timezones(vcalendar):
    """Get list of ``Timezome`` from VTIMEZONE items in ``vcalendar``."""
    return _parse(vcalendar, "VTIMEZONE", calendar.Timezone)
