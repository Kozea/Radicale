# This file is part of Radicale Server - Calendar Server
# Copyright © 2008-2017 Guillaume Ayoub
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
from collections import OrderedDict
from configparser import RawConfigParser as ConfigParser

# Default configuration
INITIAL_CONFIG = OrderedDict([
    ("server", OrderedDict([
        ("hosts", {
            "value": "127.0.0.1:5232",
            "help": "set server hostnames including ports",
            "aliases": ["-H", "--hosts"]}),
        ("daemon", {
            "value": "False",
            "help": "launch as daemon",
            "aliases": ["-d", "--daemon"],
            "opposite": ["-f", "--foreground"]}),
        ("pid", {
            "value": "",
            "help": "set PID filename for daemon mode",
            "aliases": ["-p", "--pid"]}),
        ("max_connections", {
            "value": "20",
            "help": "maximum number of parallel connections"}),
        ("max_content_length", {
            "value": "10000000",
            "help": "maximum size of request body in bytes"}),
        ("timeout", {
            "value": "10",
            "help": "socket timeout"}),
        ("ssl", {
            "value": "False",
            "help": "use SSL connection",
            "aliases": ["-s", "--ssl"],
            "opposite": ["-S", "--no-ssl"]}),
        ("certificate", {
            "value": "/etc/ssl/radicale.cert.pem",
            "help": "set certificate file",
            "aliases": ["-c", "--certificate"]}),
        ("key", {
            "value": "/etc/ssl/radicale.key.pem",
            "help": "set private key file",
            "aliases": ["-k", "--key"]}),
        ("protocol", {
            "value": "PROTOCOL_TLSv1_2",
            "help": "SSL protocol used"}),
        ("ciphers", {
            "value": "",
            "help": "available ciphers"}),
        ("dns_lookup", {
            "value": "True",
            "help": "use reverse DNS to resolve client address in logs"}),
        ("realm", {
            "value": "Radicale - Password Required",
            "help": "message displayed when a password is needed"})])),
    ("encoding", OrderedDict([
        ("request", {
            "value": "utf-8",
            "help": "encoding for responding requests"}),
        ("stock", {
            "value": "utf-8",
            "help": "encoding for storing local collections"})])),
    ("auth", OrderedDict([
        ("type", {
            "value": "None",
            "help": "authentication method"}),
        ("htpasswd_filename", {
            "value": "/etc/radicale/users",
            "help": "htpasswd filename"}),
        ("htpasswd_encryption", {
            "value": "bcrypt",
            "help": "htpasswd encryption method"}),
        ("delay", {
            "value": "1",
            "help": "incorrect authentication delay"})])),
    ("rights", OrderedDict([
        ("type", {
            "value": "owner_only",
            "help": "rights backend"}),
        ("file", {
            "value": "/etc/radicale/rights",
            "help": "file for rights management from_file"})])),
    ("storage", OrderedDict([
        ("type", {
            "value": "multifilesystem",
            "help": "storage backend"}),
        ("filesystem_folder", {
            "value": os.path.expanduser(
                "/var/lib/radicale/collections"),
            "help": "path where collections are stored"}),
        ("filesystem_fsync", {
            "value": "True",
            "help": "sync all changes to filesystem during requests"}),
        ("filesystem_close_lock_file", {
            "value": "False",
            "help": "close the lock file when no more clients are waiting"}),
        ("hook", {
            "value": "",
            "help": "command that is run after changes to storage"})])),
    ("logging", OrderedDict([
        ("config", {
            "value": "",
            "help": "logging configuration file"}),
        ("debug", {
            "value": "False",
            "help": "print debug information",
            "aliases": ["-D", "--debug"]}),
        ("full_environment", {
            "value": "False",
            "help": "store all environment variables"}),
        ("mask_passwords", {
            "value": "True",
            "help": "mask passwords in logs"})]))])


def load(paths=(), extra_config=None):
    config = ConfigParser()
    for section, values in INITIAL_CONFIG.items():
        config.add_section(section)
        for key, data in values.items():
            config.set(section, key, data["value"])
    if extra_config:
        for section, values in extra_config.items():
            for key, value in values.items():
                config.set(section, key, value)
    for path in paths:
        if path:
            config.read(path)
    return config
