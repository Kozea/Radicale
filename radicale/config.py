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

from ConfigParser import RawConfigParser as ConfigParser

# Default functions
_config = ConfigParser()
get = _config.get
set = _config.set
getboolean = _config.getboolean
getint = _config.getint
getfloat = _config.getfloat
options = _config.options
items = _config.items

# Default config
_initial = {
    "server": {
        "certificate": "/etc/apache2/ssl/server.crt",
        "privatekey": "/etc/apache2/ssl/server.key",
        "log": "/var/www/radicale/server.log",
        "port": "1001",
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
        },
    "acl": {
        "type": "htpasswd",
        "filename": "/etc/radicale/users",
        },
    "support": {
        "type": "plain",
        "folder": "/var/local/radicale",
        },
    }

# Set the default config
for section, values in _initial.iteritems():
    _config.add_section(section)
    for key, value in values.iteritems():
        _config.set(section, key, value)

# Set the user config
_config.read("/etc/radicale/config")
