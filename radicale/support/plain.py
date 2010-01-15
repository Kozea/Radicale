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
Plain text storage.
"""

import os
import posixpath
import codecs

from radicale import config, ical

_folder = os.path.expanduser(config.get("support", "folder"))

def _open(path, mode="r"):
    return codecs.open(path, mode, config.get("encoding", "stock"))

def calendars():
    """List available calendars paths."""
    calendars = []

    for folder in os.listdir(_folder):
        for cal in os.listdir(os.path.join(_folder, folder)):
            calendars.append(posixpath.join(folder, cal))

    return calendars

def mkcalendar(name):
    """Write a new calendar called ``name``."""
    user, cal = name.split(posixpath.sep)
    if not os.path.exists(os.path.join(_folder, user)):
        os.makedirs(os.path.join(_folder, user))
    fd = _open(os.path.join(_folder, user, cal), "w")
    fd.write(ical.write_calendar())

def read(cal):
    """Read calendar ``cal``."""
    path = os.path.join(_folder, cal.replace(posixpath.sep, os.path.sep))
    return _open(path).read()

def append(cal, vcalendar):
    """Append ``vcalendar`` to ``cal``."""
    old_calendar = read(cal)
    old_tzs = [tz.tzid for tz in ical.timezones(old_calendar)]
    path = os.path.join(_folder, cal.replace(posixpath.sep, os.path.sep))

    old_objects = []
    old_objects.extend([event.etag() for event in ical.events(old_calendar)])
    old_objects.extend([todo.etag() for todo in ical.todos(old_calendar)])

    objects = []
    objects.extend(ical.events(vcalendar))
    objects.extend(ical.todos(vcalendar))

    for tz in ical.timezones(vcalendar):
        if tz.tzid not in old_tzs:
            # TODO: Manage position and EOL
            fd = _open(path)
            lines = [line for line in fd.readlines() if line]
            fd.close()

            for i,line in enumerate(tz.text.splitlines()):
                lines.insert(2 + i, line + "\n")

            fd = _open(path, "w")
            fd.writelines(lines)
            fd.close()

    for obj in objects:
        if obj.etag() not in old_objects:
            # TODO: Manage position and EOL
            fd = _open(path)
            lines = [line for line in fd.readlines() if line]
            fd.close()

            for line in obj.text.splitlines():
                lines.insert(-1, line + "\n")

            fd = _open(path, "w")
            fd.writelines(lines)
            fd.close()

def remove(cal, etag):
    """Remove object named ``etag`` from ``cal``."""
    path = os.path.join(_folder, cal.replace(posixpath.sep, os.path.sep))

    cal = read(cal)

    headers = ical.headers(cal)
    timezones = ical.timezones(cal)
    todos = [todo for todo in ical.todos(cal) if todo.etag() != etag]
    events = [event for event in ical.events(cal) if event.etag() != etag]

    fd = _open(path, "w")
    fd.write(ical.write_calendar(headers, timezones, todos, events))
    fd.close()

if config.get("support", "calendar"):
    user, cal = config.get("support", "calendar").split(posixpath.sep)
    if not os.path.exists(os.path.join(_folder, user, cal)):
        mkcalendar(config.get("support", "calendar"))
