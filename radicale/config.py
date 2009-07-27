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
Radicale configuration module.

Give a configparser-like interface to read and write configuration.
"""

from ConfigParser import RawConfigParser as ConfigParser

_config = ConfigParser()
get = _config.get
set = _config.set
getboolean = _config.getboolean
getint = _config.getint
getfloat = _config.getfloat
options = _config.options
items = _config.items

_initial = {
    "server": {
        "type": "http",
        "certificate": "/etc/apache2/ssl/server.crt",
        "privatekey": "/etc/apache2/ssl/server.key",
        "log": "/var/www/radicale/server.log",
        "port": "5232",
        },
    "encoding": {
        "request": "utf-8",
        "stock": "utf-8",
        },
    "namespace": {
        "C": "urn:ietf:params:xml:ns:caldav",
        "D": "DAV:",
        "CS": "http://calendarserver.org/ns/",
        },
    "status": {
        "200": "HTTP/1.1 200 OK",
        "204": "HTTP/1.1 204 No Content",
        },
    "acl": {
        "type": "fake",
        "filename": "/etc/radicale/users",
        "user": "radicale",
        },
    "support": {
        "type": "plain",
        "folder": "~/.config/radicale",
        "calendar": "radicale/calendar",
        },
    }

for section, values in _initial.iteritems():
    _config.add_section(section)
    for key, value in values.iteritems():
        _config.set(section, key, value)

# TODO: Use abstract filename for other platforms
_config.read("/etc/radicale/config")
