# -*- coding: utf-8 -*-
#
# This file is part of Radicale Server - Calendar Server
# Copyright © 2008-2013 Guillaume Ayoub
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
        "hosts": "0.0.0.0:5232",
        "daemon": "False",
        "pid": "",
        "ssl": "False",
        "certificate": "/etc/apache2/ssl/server.crt",
        "key": "/etc/apache2/ssl/server.key",
        "protocol": "PROTOCOL_SSLv23",
        "ciphers": "",
        "dns_lookup": "True",
        "base_prefix": "/",
        "realm": "Radicale - Password Required"},
    "encoding": {
        "request": "utf-8",
        "stock": "utf-8"},
    "auth": {
        "type": "None",
        "custom_handler": "",
        "htpasswd_filename": "/etc/radicale/users",
        "htpasswd_encryption": "crypt",
        "imap_hostname": "localhost",
        "imap_port": "143",
        "imap_ssl": "False",
        "ldap_url": "ldap://localhost:389/",
        "ldap_base": "ou=users,dc=example,dc=com",
        "ldap_attribute": "uid",
        "ldap_filter": "",
        "ldap_binddn": "",
        "ldap_password": "",
        "ldap_scope": "OneLevel",
        "pam_group_membership": "",
        "courier_socket": "",
        "http_url": "",
        "http_user_parameter": "",
        "http_password_parameter": ""},
    "git": {
        "committer": "Radicale <radicale@example.com>"},
    "rights": {
        "type": "None",
        "custom_handler": "",
        "file": "~/.config/radicale/rights"},
    "storage": {
        "type": "filesystem",
        "custom_handler": "",
        "filesystem_folder": os.path.expanduser(
            "~/.config/radicale/collections"),
        "database_url": ""},
    "logging": {
        "config": "/etc/radicale/logging",
        "debug": "False",
        "full_environment": "False"}}

# Create a ConfigParser and configure it
_CONFIG_PARSER = ConfigParser()

for section, values in INITIAL_CONFIG.items():
    _CONFIG_PARSER.add_section(section)
    for key, value in values.items():
        _CONFIG_PARSER.set(section, key, value)

_CONFIG_PARSER.read("/etc/radicale/config")
_CONFIG_PARSER.read(os.path.expanduser("~/.config/radicale/config"))
if "RADICALE_CONFIG" in os.environ:
    _CONFIG_PARSER.read(os.environ["RADICALE_CONFIG"])

# Wrap config module into ConfigParser instance
sys.modules[__name__] = _CONFIG_PARSER
