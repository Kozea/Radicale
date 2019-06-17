# This file is part of Radicale Server - Calendar Server
# Copyright © 2008-2017 Guillaume Ayoub
# Copyright © 2008 Nicolas Kandel
# Copyright © 2008 Pascal Halter
# Copyright © 2017-2019 Unrud <unrud@outlook.com>
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
from configparser import RawConfigParser

from radicale import auth, rights, storage, web
from radicale.log import logger

DEFAULT_CONFIG_PATH = os.pathsep.join([
    "?/etc/radicale/config",
    "?~/.config/radicale/config"])


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


def logging_level(value):
    if value not in ("debug", "info", "warning", "error", "critical"):
        raise ValueError("unsupported level: %r" % value)
    return value


def filepath(value):
    if not value:
        return ""
    value = os.path.expanduser(value)
    if os.name == "nt":
        value = os.path.expandvars(value)
    return os.path.abspath(value)


def list_of_ip_address(value):
    def ip_address(value):
        try:
            address, port = value.strip().rsplit(":", 1)
            return address.strip("[] "), int(port)
        except ValueError:
            raise ValueError("malformed IP address: %r" % value)
    return [ip_address(s.strip()) for s in value.split(",")]


def _convert_to_bool(value):
    if value.lower() not in RawConfigParser.BOOLEAN_STATES:
        raise ValueError("Not a boolean: %r" % value)
    return RawConfigParser.BOOLEAN_STATES[value.lower()]


# Default configuration
DEFAULT_CONFIG_SCHEMA = OrderedDict([
    ("server", OrderedDict([
        ("hosts", {
            "value": "127.0.0.1:5232",
            "help": "set server hostnames including ports",
            "aliases": ["-H", "--hosts"],
            "type": list_of_ip_address}),
        ("max_connections", {
            "value": "8",
            "help": "maximum number of parallel connections",
            "type": positive_int}),
        ("max_content_length", {
            "value": "100000000",
            "help": "maximum size of request body in bytes",
            "type": positive_int}),
        ("timeout", {
            "value": "30",
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
            "type": filepath}),
        ("key", {
            "value": "/etc/ssl/radicale.key.pem",
            "help": "set private key file",
            "aliases": ["-k", "--key"],
            "type": filepath}),
        ("certificate_authority", {
            "value": "",
            "help": "set CA certificate for validating clients",
            "aliases": ["--certificate-authority"],
            "type": filepath}),
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
            "type": bool})])),
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
            "type": filepath}),
        ("htpasswd_encryption", {
            "value": "bcrypt",
            "help": "htpasswd encryption method",
            "type": str}),
        ("realm", {
            "value": "Radicale - Password Required",
            "help": "message displayed when a password is needed",
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
            "type": filepath})])),
    ("storage", OrderedDict([
        ("type", {
            "value": "multifilesystem",
            "help": "storage backend",
            "type": str,
            "internal": storage.INTERNAL_TYPES}),
        ("filesystem_folder", {
            "value": "/var/lib/radicale/collections",
            "help": "path where collections are stored",
            "type": filepath}),
        ("max_sync_token_age", {
            "value": "2592000",  # 30 days
            "help": "delete sync token that are older",
            "type": positive_int}),
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
        ("level", {
            "value": "warning",
            "help": "threshold for the logger",
            "type": logging_level}),
        ("mask_passwords", {
            "value": "True",
            "help": "mask passwords in logs",
            "type": bool})])),
    ("headers", OrderedDict([
        ("_allow_extra", True)])),
    ("internal", OrderedDict([
        ("_internal", True),
        ("filesystem_fsync", {
            "value": "True",
            "help": "sync all changes to filesystem during requests",
            "type": bool}),
        ("internal_server", {
            "value": "False",
            "help": "the internal server is used",
            "type": bool})]))])


def parse_compound_paths(*compound_paths):
    """Parse a compound path and return the individual paths.
    Paths in a compound path are joined by ``os.pathsep``. If a path starts
    with ``?`` the return value ``IGNORE_IF_MISSING`` is set.

    When multiple ``compound_paths`` are passed, the last argument that is
    not ``None`` is used.

    Returns a dict of the format ``[(PATH, IGNORE_IF_MISSING), ...]``

    """
    compound_path = ""
    for p in compound_paths:
        if p is not None:
            compound_path = p
    paths = []
    for path in compound_path.split(os.pathsep):
        ignore_if_missing = path.startswith("?")
        if ignore_if_missing:
            path = path[1:]
        path = filepath(path)
        if path:
            paths.append((path, ignore_if_missing))
    return paths


def load(paths=()):
    """Load configuration from files.

    ``paths`` a list of the format ``[(PATH, IGNORE_IF_MISSING), ...]``.

    """
    configuration = Configuration(DEFAULT_CONFIG_SCHEMA)
    for path, ignore_if_missing in paths:
        parser = RawConfigParser()
        config_source = "config file %r" % path
        try:
            if not parser.read(path):
                config = Configuration.SOURCE_MISSING
                if not ignore_if_missing:
                    raise RuntimeError("No such file: %r" % path)
            else:
                config = {s: {o: parser[s][o] for o in parser.options(s)}
                          for s in parser.sections()}
        except Exception as e:
            raise RuntimeError(
                "Failed to load %s: %s" % (config_source, e)) from e
        configuration.update(config, config_source, internal=False)
    return configuration


class Configuration:
    SOURCE_MISSING = {}

    def __init__(self, schema):
        """Initialize configuration.

        ``schema`` a dict that describes the configuration format.
        See ``DEFAULT_CONFIG_SCHEMA``.

        """
        self._schema = schema
        self._values = {}
        self._configs = []
        values = {}
        for section in schema:
            values[section] = {}
            for option in schema[section]:
                if option.startswith("_"):
                    continue
                values[section][option] = schema[section][option]["value"]
        self.update(values, "default config")

    def update(self, config, source, internal=True):
        """Update the configuration.

        ``config`` a dict of the format {SECTION: {OPTION: VALUE, ...}, ...}.
        Set to ``Configuration.SOURCE_MISSING`` to indicate a missing
        configuration source for inspection.

        ``source`` a description of the configuration source

        ``internal`` allows updating "_internal" sections and skips the source
        during inspection.

        """
        new_values = {}
        for section in config:
            if (section not in self._schema or not internal and
                    self._schema[section].get("_internal", False)):
                raise RuntimeError(
                    "Invalid section %r in %s" % (section, source))
            new_values[section] = {}
            if "_allow_extra" in self._schema[section]:
                allow_extra_options = self._schema[section]["_allow_extra"]
            elif "type" in self._schema[section]:
                if "type" in config[section]:
                    plugin_type = config[section]["type"]
                else:
                    plugin_type = self.get(section, "type")
                allow_extra_options = plugin_type not in self._schema[section][
                    "type"].get("internal", [])
            else:
                allow_extra_options = False
            for option in config[section]:
                if option in self._schema[section]:
                    type_ = self._schema[section][option]["type"]
                elif allow_extra_options:
                    type_ = str
                else:
                    raise RuntimeError("Invalid option %r in section %r in "
                                       "%s" % (option, section, source))
                raw_value = config[section][option]
                try:
                    if type_ == bool:
                        raw_value = _convert_to_bool(raw_value)
                    new_values[section][option] = type_(raw_value)
                except Exception as e:
                    raise RuntimeError(
                        "Invalid %s value for option %r in section %r in %s: "
                        "%r" % (type_.__name__, option, section, source,
                                raw_value)) from e
        self._configs.append((config, source, internal))
        for section in new_values:
            if section not in self._values:
                self._values[section] = {}
            for option in new_values[section]:
                self._values[section][option] = new_values[section][option]

    def get(self, section, option):
        """Get the value of ``option`` in ``section``."""
        return self._values[section][option]

    def get_raw(self, section, option):
        """Get the raw value of ``option`` in ``section``."""
        fconfig = self._configs[0]
        for config, _, _ in reversed(self._configs):
            if section in config and option in config[section]:
                fconfig = config
                break
        return fconfig[section][option]

    def sections(self):
        """List all sections."""
        return self._values.keys()

    def options(self, section):
        """List all options in ``section``"""
        return self._values[section].keys()

    def copy(self, plugin_schema=None):
        """Create a copy of the configuration

        ``plugin_schema`` is a optional dict that contains additional options
        for usage with a plugin. See ``DEFAULT_CONFIG_SCHEMA``.

        """
        if plugin_schema is None:
            schema = self._schema
            skip = 1  # skip default config
        else:
            skip = 0
            schema = self._schema.copy()
            for section, options in plugin_schema.items():
                if (section not in schema or "type" not in schema[section] or
                        "internal" not in schema[section]["type"]):
                    raise ValueError("not a plugin section: %r" % section)
                schema[section] = schema[section].copy()
                schema[section]["type"] = schema[section]["type"].copy()
                schema[section]["type"]["internal"] = [
                    self.get(section, "type")]
                for option, value in options.items():
                    if option in schema[section]:
                        raise ValueError("option already exists in %r: %r" % (
                            section, option))
                    schema[section][option] = value
        copy = self.__class__(schema)
        for config, source, allow_internal in self._configs[skip:]:
            copy.update(config, source, allow_internal)
        return copy

    def inspect(self):
        """Inspect all external config sources and write problems to logger."""
        for config, source, internal in self._configs:
            if internal:
                continue
            if config is self.SOURCE_MISSING:
                logger.info("Skipped missing %s", source)
            else:
                logger.info("Parsed %s", source)
