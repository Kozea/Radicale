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

# TODO: Manage filters (see xmlutils)
# TODO: Factorize code

import calendar

def writeCalendar(headers=[], timezones=[], todos=[], events=[]):
    """
    Create calendar from headers, timezones, todos, events
    """
    # TODO: Manage encoding and EOL
    return "\n".join((
        "BEGIN:VCALENDAR",
        "\n".join([header.text for header in headers]),
        "\n".join([timezone.text for timezone in timezones]),
        "\n".join([todo.text for todo in todos]),
        "\n".join([event.text for event in events]),
        "END:VCALENDAR"))

def events(vcalendar):
    """
    Find VEVENT Items in vcalendar
    """
    events = []

    lines = vcalendar.splitlines()
    inEvent = False
    eventLines = []

    for line in lines:
        if line.startswith("BEGIN:VEVENT"):
            inEvent = True
            eventLines = []

        if inEvent:
            # TODO: Manage encoding
            eventLines.append(line)
            if line.startswith("END:VEVENT"):
                events.append(calendar.Event("\n".join(eventLines)))

    return events

def headers(vcalendar):
    """
    Find Headers Items in vcalendar
    """
    headers = []

    lines = vcalendar.splitlines()
    for line in lines:
        if line.startswith("PRODID:"):
            headers.append(calendar.Header(line))
    for line in lines:
        if line.startswith("VERSION:"):
            headers.append(calendar.Header(line))

    return headers
    
def timezones(vcalendar):
    """
    Find VTIMEZONE Items in vcalendar
    """
    timezones = []

    lines = vcalendar.splitlines()
    inTz = False
    tzLines = []

    for line in lines:
        if line.startswith("BEGIN:VTIMEZONE"):
            inTz = True
            tzLines = []

        if inTz:
            tzLines.append(line)
            if line.startswith("END:VTIMEZONE"):
                timezones.append(calendar.Timezone("\n".join(tzLines)))

    return timezones

def todos(vcalendar):
    """
    Find VTODO Items in vcalendar
    """
    todos = []

    lines = vcalendar.splitlines()
    inTodo = False
    todoLines = []

    for line in lines:
        if line.startswith("BEGIN:VTODO"):
            inTodo = True
            todoLines = []

        if inTodo:
            # TODO: Manage encoding
            todoLines.append(line)
            if line.startswith("END:VTODO"):
                todos.append(calendar.Todo("\n".join(todoLines)))

    return todos
