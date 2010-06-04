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
Radicale configuration module.

Give a configparser-like interface to read and write configuration.

"""

# TODO: Use abstract filenames for other platforms

import os
import sys
# Manage Python2/3 different modules
# pylint: disable=F0401
try:
    from configparser import RawConfigParser as ConfigParser
except ImportError:
    from ConfigParser import RawConfigParser as ConfigParser
# pylint: enable=F0401


# Default configuration
INITIAL_CONFIG = {
    "server": {
        "host": "",
        "port": "5232",
        "daemon": "False",
        "ssl": "False",
        "certificate": "/etc/apache2/ssl/server.crt",
        "key": "/etc/apache2/ssl/server.key"},
    "encoding": {
        "request": "utf-8",
        "stock": "utf-8"},
    "acl": {
        "type": "fake",
        "filename": "/etc/radicale/users",
        "encryption": "crypt"},
    "storage": {
        "folder": os.path.expanduser("~/.config/radicale/calendars")}}

# Create a ConfigParser and configure it
_CONFIG_PARSER = ConfigParser()

for section, values in INITIAL_CONFIG.items():
    _CONFIG_PARSER.add_section(section)
    for key, value in values.items():
        _CONFIG_PARSER.set(section, key, value)

_CONFIG_PARSER.read("/etc/radicale/config")
_CONFIG_PARSER.read(os.path.expanduser("~/.config/radicale/config"))

# Wrap config module into ConfigParser instance
sys.modules[__name__] = _CONFIG_PARSER
