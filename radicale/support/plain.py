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

import os
import posixpath

from .. import ical
from .. import config

_folder = os.path.expanduser(config.get("support", "folder"))

def calendars():
    """
    List Available Calendars Paths
    """
    calendars = []

    for folder in os.listdir(_folder):
        for cal in os.listdir(os.path.join(_folder, folder)):
            calendars.append(posixpath.join(folder, cal))

    return calendars

def mkcalendar(name):
    """
    Write new calendar
    """
    user, cal = name.split(posixpath.sep)
    if not os.path.exists(os.path.join(_folder, user)):
        os.makedirs(os.path.join(_folder, user))
    fd = open(os.path.join(_folder, user, cal), "w")
    fd.write(ical.writeCalendar())

def read(cal):
    """
    Read cal
    """
    path = os.path.join(_folder, cal.replace(posixpath.sep, os.path.sep))
    return open(path).read()

def append(cal, vcalendar):
    """
    Append vcalendar to cal
    """
    oldCalendar = unicode(read(cal), config.get("encoding", "stock"))
    oldTzs = [tz.tzid for tz in ical.timezones(oldCalendar)]
    path = os.path.join(_folder, cal.replace(posixpath.sep, os.path.sep))

    oldObjects = []
    oldObjects.extend([event.etag() for event in ical.events(oldCalendar)])
    oldObjects.extend([todo.etag() for todo in ical.todos(oldCalendar)])

    objects = []
    objects.extend(ical.events(vcalendar))
    objects.extend(ical.todos(vcalendar))

    for tz in ical.timezones(vcalendar):
        if tz.tzid not in oldTzs:
            # TODO: Manage position, encoding and EOL
            fd = open(path)
            lines = [line for line in fd.readlines() if line]
            fd.close()

            for i,line in enumerate(tz.text.splitlines()):
                lines.insert(2+i, line.encode("utf-8")+"\n")

            fd = open(path, "w")
            fd.writelines(lines)
            fd.close()

    for obj in objects:
        if obj.etag() not in oldObjects:
            # TODO: Manage position, encoding and EOL
            fd = open(path)
            lines = [line for line in fd.readlines() if line]
            fd.close()

            for line in obj.text.splitlines():
                lines.insert(-1, line.encode("utf-8")+"\n")

            fd = open(path, "w")
            fd.writelines(lines)
            fd.close()

def remove(cal, etag):
    """
    Remove object named uid from cal
    """
    path = os.path.join(_folder, cal.replace(posixpath.sep, os.path.sep))

    cal = unicode(read(cal), config.get("encoding", "stock"))

    headers = ical.headers(cal)
    timezones = ical.timezones(cal)
    todos = [todo for todo in ical.todos(cal) if todo.etag() != etag]
    events = [event for event in ical.events(cal) if event.etag() != etag]

    fd = open(path, "w")
    fd.write(ical.writeCalendar(headers, timezones, todos, events))
    fd.close()

if config.get("support", "defaultCalendar"):
    user, cal = config.get("support", "defaultCalendar").split(posixpath.sep)
    if not os.path.exists(os.path.join(_folder, user, cal)):
        mkcalendar(config.get("support", "defaultCalendar"))

