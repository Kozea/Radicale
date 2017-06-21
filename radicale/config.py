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

import math
import os
from collections import OrderedDict
from configparser import RawConfigParser as ConfigParser

from . import auth, rights, storage, web


def positive_int(value):
    value = int(value)
    if value < 0:
        raise ValueError("value is negative: %d" % value)
    return value


def positive_float(value):
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("value is infinite")
    if math.isnan(value):
        raise ValueError("value is not a number")
    if value < 0:
        raise ValueError("value is negative: %f" % value)
    return value


# Default configuration
INITIAL_CONFIG = OrderedDict([
    ("server", OrderedDict([
        ("hosts", {
            "value": "127.0.0.1:5232",
            "help": "set server hostnames including ports",
            "aliases": ["-H", "--hosts"],
            "type": str}),
        ("daemon", {
            "value": "False",
            "help": "launch as daemon",
            "aliases": ["-d", "--daemon"],
            "opposite": ["-f", "--foreground"],
            "type": bool}),
        ("pid", {
            "value": "",
            "help": "set PID filename for daemon mode",
            "aliases": ["-p", "--pid"],
            "type": str}),
        ("max_connections", {
            "value": "20",
            "help": "maximum number of parallel connections",
            "type": positive_int}),
        ("max_content_length", {
            "value": "10000000",
            "help": "maximum size of request body in bytes",
            "type": positive_int}),
        ("timeout", {
            "value": "10",
            "help": "socket timeout",
            "type": positive_int}),
        ("ssl", {
            "value": "False",
            "help": "use SSL connection",
            "aliases": ["-s", "--ssl"],
            "opposite": ["-S", "--no-ssl"],
            "type": bool}),
        ("certificate", {
            "value": "/etc/ssl/radicale.cert.pem",
            "help": "set certificate file",
            "aliases": ["-c", "--certificate"],
            "type": str}),
        ("key", {
            "value": "/etc/ssl/radicale.key.pem",
            "help": "set private key file",
            "aliases": ["-k", "--key"],
            "type": str}),
        ("certificate_authority", {
            "value": "",
            "help": "set CA certificate for validating clients",
            "aliases": ["--certificate-authority"],
            "type": str}),
        ("protocol", {
            "value": "PROTOCOL_TLSv1_2",
            "help": "SSL protocol used",
            "type": str}),
        ("ciphers", {
            "value": "",
            "help": "available ciphers",
            "type": str}),
        ("dns_lookup", {
            "value": "True",
            "help": "use reverse DNS to resolve client address in logs",
            "type": bool}),
        ("realm", {
            "value": "Radicale - Password Required",
            "help": "message displayed when a password is needed",
            "type": str})])),
    ("encoding", OrderedDict([
        ("request", {
            "value": "utf-8",
            "help": "encoding for responding requests",
            "type": str}),
        ("stock", {
            "value": "utf-8",
            "help": "encoding for storing local collections",
            "type": str})])),
    ("auth", OrderedDict([
        ("type", {
            "value": "none",
            "help": "authentication method",
            "type": str,
            "internal": auth.INTERNAL_TYPES}),
        ("htpasswd_filename", {
            "value": "/etc/radicale/users",
            "help": "htpasswd filename",
            "type": str}),
        ("htpasswd_encryption", {
            "value": "bcrypt",
            "help": "htpasswd encryption method",
            "type": str}),
        ("delay", {
            "value": "1",
            "help": "incorrect authentication delay",
            "type": positive_float})])),
    ("rights", OrderedDict([
        ("type", {
            "value": "owner_only",
            "help": "rights backend",
            "type": str,
            "internal": rights.INTERNAL_TYPES}),
        ("file", {
            "value": "/etc/radicale/rights",
            "help": "file for rights management from_file",
            "type": str})])),
    ("storage", OrderedDict([
        ("type", {
            "value": "multifilesystem",
            "help": "storage backend",
            "type": str,
            "internal": storage.INTERNAL_TYPES}),
        ("filesystem_folder", {
            "value": os.path.expanduser(
                "/var/lib/radicale/collections"),
            "help": "path where collections are stored",
            "type": str}),
        ("max_sync_token_age", {
            "value": 2592000,  # 30 days
            "help": "delete sync token that are older",
            "type": int}),
        ("filesystem_fsync", {
            "value": "True",
            "help": "sync all changes to filesystem during requests",
            "type": bool}),
        ("filesystem_locking", {
            "value": "True",
            "help": "lock the storage while accessing it",
            "type": bool}),
        ("filesystem_close_lock_file", {
            "value": "False",
            "help": "close the lock file when no more clients are waiting",
            "type": bool}),
        ("hook", {
            "value": "",
            "help": "command that is run after changes to storage",
            "type": str})])),
    ("web", OrderedDict([
        ("type", {
            "value": "internal",
            "help": "web interface backend",
            "type": str,
            "internal": web.INTERNAL_TYPES})])),
    ("logging", OrderedDict([
        ("config", {
            "value": "",
            "help": "logging configuration file",
            "type": str}),
        ("debug", {
            "value": "False",
            "help": "print debug information",
            "aliases": ["-D", "--debug"],
            "type": bool}),
        ("full_environment", {
            "value": "False",
            "help": "store all environment variables",
            "type": bool}),
        ("mask_passwords", {
            "value": "True",
            "help": "mask passwords in logs",
            "type": bool})]))])


def load(paths=(), extra_config=None, ignore_missing_paths=True):
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
        if path or not ignore_missing_paths:
            try:
                if not config.read(path) and not ignore_missing_paths:
                    raise RuntimeError("No such file: %r" % path)
            except Exception as e:
                raise RuntimeError(
                    "Failed to load config file %r: %s" % (path, e)) from e
    # Check the configuration
    for section in config.sections():
        if section == "headers":
            continue
        if section not in INITIAL_CONFIG:
            raise RuntimeError("Invalid section %r in config" % section)
        allow_extra_options = ("type" in INITIAL_CONFIG[section] and
                               config.get(section, "type") not in
                               INITIAL_CONFIG[section]["type"].get("internal",
                                                                   ()))
        for option in config[section]:
            if option not in INITIAL_CONFIG[section]:
                if allow_extra_options:
                    continue
                raise RuntimeError("Invalid option %r in section %r in "
                                   "config" % (option, section))
            type_ = INITIAL_CONFIG[section][option]["type"]
            try:
                if type_ == bool:
                    config.getboolean(section, option)
                else:
                    type_(config.get(section, option))
            except Exception as e:
                raise RuntimeError(
                    "Invalid %s value for option %r in section %r in config: "
                    "%r" % (type_.__name__, option, section,
                            config.get(section, option))) from e
    return config
