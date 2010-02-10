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

FOLDER = os.path.expanduser(config.get("support", "folder"))
DEFAULT_CALENDAR = config.get("support", "calendar")


def _open(path, mode="r"):
    """Open file at ``path`` with ``mode``, automagically managing encoding."""
    return codecs.open(path, mode, config.get("encoding", "stock"))


def calendars():
    """List available calendars paths."""
    available_calendars = []

    for filename in os.listdir(FOLDER):
        if os.path.isdir(os.path.join(FOLDER, filename)):
            for cal in os.listdir(os.path.join(FOLDER, filename)):
                available_calendars.append(posixpath.join(filename, cal))

    return available_calendars


def mkcalendar(name):
    """Write a new calendar called ``name``."""
    user, cal = name.split(posixpath.sep)
    if not os.path.exists(os.path.join(FOLDER, user)):
        os.makedirs(os.path.join(FOLDER, user))
    descriptor = _open(os.path.join(FOLDER, user, cal), "w")
    descriptor.write(ical.write_calendar())


def read(cal):
    """Read calendar ``cal``."""
    path = os.path.join(FOLDER, cal.replace(posixpath.sep, os.path.sep))
    return _open(path).read()


def append(cal, vcalendar):
    """Append ``vcalendar`` to ``cal``."""
    old_calendar = read(cal)
    old_timezones = [timezone.id for timezone in ical.timezones(old_calendar)]
    path = os.path.join(FOLDER, cal.replace(posixpath.sep, os.path.sep))

    old_objects = []
    old_objects.extend([event.etag for event in ical.events(old_calendar)])
    old_objects.extend([todo.etag for todo in ical.todos(old_calendar)])

    objects = []
    objects.extend(ical.events(vcalendar))
    objects.extend(ical.todos(vcalendar))

    for timezone in ical.timezones(vcalendar):
        if timezone.id not in old_timezones:
            descriptor = _open(path)
            lines = [line for line in descriptor.readlines() if line]
            descriptor.close()

            for i, line in enumerate(timezone.text.splitlines()):
                lines.insert(2 + i, line + "\n")

            descriptor = _open(path, "w")
            descriptor.writelines(lines)
            descriptor.close()

    for obj in objects:
        if obj.etag not in old_objects:
            descriptor = _open(path)
            lines = [line for line in descriptor.readlines() if line]
            descriptor.close()

            for line in obj.text.splitlines():
                lines.insert(-1, line + "\n")

            descriptor = _open(path, "w")
            descriptor.writelines(lines)
            descriptor.close()


def remove(cal, etag):
    """Remove object named ``etag`` from ``cal``."""
    path = os.path.join(FOLDER, cal.replace(posixpath.sep, os.path.sep))

    cal = read(cal)

    headers = ical.headers(cal)
    timezones = ical.timezones(cal)
    todos = [todo for todo in ical.todos(cal) if todo.etag != etag]
    events = [event for event in ical.events(cal) if event.etag != etag]

    descriptor = _open(path, "w")
    descriptor.write(ical.write_calendar(headers, timezones, todos, events))
    descriptor.close()


# Create default calendar if not present
if DEFAULT_CALENDAR:
    if DEFAULT_CALENDAR not in calendars():
        mkcalendar(DEFAULT_CALENDAR)
