# This file is part of Radicale Server - Calendar Server
# Copyright © 2008-2016 Guillaume Ayoub
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

import os
from configparser import RawConfigParser as ConfigParser

# Default configuration
INITIAL_CONFIG = {
    "server": {
        "hosts": "0.0.0.0:5232",
        "daemon": "False",
        "pid": "",
        "max_connections": "20",
        "max_content_length": "10000000",
        "timeout": "10",
        "ssl": "False",
        "certificate": "/etc/apache2/ssl/server.crt",
        "key": "/etc/apache2/ssl/server.key",
        "protocol": "PROTOCOL_SSLv23",
        "ciphers": "",
        "dns_lookup": "True",
        "base_prefix": "/",
        "can_skip_base_prefix": "False",
        "realm": "Radicale - Password Required"},
    "encoding": {
        "request": "utf-8",
        "stock": "utf-8"},
    "auth": {
        "type": "None",
        "htpasswd_filename": "/etc/radicale/users",
        "htpasswd_encryption": "crypt"},
    "rights": {
        "type": "None",
        "file": "~/.config/radicale/rights"},
    "storage": {
        "type": "multifilesystem",
        "filesystem_folder": os.path.expanduser(
            "~/.config/radicale/collections"),
        "fsync": "True",
        "cache": "True",
        "hook": "",
        "close_lock_file": "False"},
    "logging": {
        "config": "/etc/radicale/logging",
        "debug": "False",
        "full_environment": "False",
        "performance": "False",
        "cache_statistics_interval": "300",
        "mask_passwords": "True"}}


def load(paths=(), extra_config=None):
    config = ConfigParser()
    for section, values in INITIAL_CONFIG.items():
        config.add_section(section)
        for key, value in values.items():
            config.set(section, key, value)
    if extra_config:
        for section, values in extra_config.items():
            for key, value in values.items():
                config.set(section, key, value)
    for path in paths:
        if path:
            config.read(path)
    return config
