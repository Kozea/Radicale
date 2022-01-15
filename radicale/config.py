# This file is part of Radicale - CalDAV and CardDAV server
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
Configuration module

Use ``load()`` to obtain an instance of ``Configuration`` for use with
``radicale.app.Application``.

"""

import contextlib
import math
import os
import string
import sys
from collections import OrderedDict
from configparser import RawConfigParser
from typing import (Any, Callable, ClassVar, Iterable, List, Optional,
                    Sequence, Tuple, TypeVar, Union)

from radicale import auth, rights, storage, types, web

DEFAULT_CONFIG_PATH: str = os.pathsep.join([
    "?/etc/radicale/config",
    "?~/.config/radicale/config"])


def positive_int(value: Any) -> int:
    value = int(value)
    if value < 0:
        raise ValueError("value is negative: %d" % value)
    return value


def positive_float(value: Any) -> float:
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("value is infinite")
    if math.isnan(value):
        raise ValueError("value is not a number")
    if value < 0:
        raise ValueError("value is negative: %f" % value)
    return value


def logging_level(value: Any) -> str:
    if value not in ("debug", "info", "warning", "error", "critical"):
        raise ValueError("unsupported level: %r" % value)
    return value


def filepath(value: Any) -> str:
    if not value:
        return ""
    value = os.path.expanduser(value)
    if sys.platform == "win32":
        value = os.path.expandvars(value)
    return os.path.abspath(value)


def list_of_ip_address(value: Any) -> List[Tuple[str, int]]:
    def ip_address(value):
        try:
            address, port = value.rsplit(":", 1)
            return address.strip(string.whitespace + "[]"), int(port)
        except ValueError:
            raise ValueError("malformed IP address: %r" % value)
    return [ip_address(s) for s in value.split(",")]


def str_or_callable(value: Any) -> Union[str, Callable]:
    if callable(value):
        return value
    return str(value)


def unspecified_type(value: Any) -> Any:
    return value


def _convert_to_bool(value: Any) -> bool:
    if value.lower() not in RawConfigParser.BOOLEAN_STATES:
        raise ValueError("not a boolean: %r" % value)
    return RawConfigParser.BOOLEAN_STATES[value.lower()]


INTERNAL_OPTIONS: Sequence[str] = ("_allow_extra",)
# Default configuration
DEFAULT_CONFIG_SCHEMA: types.CONFIG_SCHEMA = OrderedDict([
    ("server", OrderedDict([
        ("hosts", {
            "value": "localhost:5232",
            "help": "set server hostnames including ports",
            "aliases": ("-H", "--hosts",),
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
            "type": positive_float}),
        ("ssl", {
            "value": "False",
            "help": "use SSL connection",
            "aliases": ("-s", "--ssl",),
            "opposite_aliases": ("-S", "--no-ssl",),
            "type": bool}),
        ("certificate", {
            "value": "/etc/ssl/radicale.cert.pem",
            "help": "set certificate file",
            "aliases": ("-c", "--certificate",),
            "type": filepath}),
        ("key", {
            "value": "/etc/ssl/radicale.key.pem",
            "help": "set private key file",
            "aliases": ("-k", "--key",),
            "type": filepath}),
        ("certificate_authority", {
            "value": "",
            "help": "set CA certificate for validating clients",
            "aliases": ("--certificate-authority",),
            "type": filepath}),
        ("_internal_server", {
            "value": "False",
            "help": "the internal server is used",
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
            "type": str_or_callable,
            "internal": auth.INTERNAL_TYPES}),
        ("htpasswd_filename", {
            "value": "/etc/radicale/users",
            "help": "htpasswd filename",
            "type": filepath}),
        ("htpasswd_encryption", {
            "value": "md5",
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
            "type": str_or_callable,
            "internal": rights.INTERNAL_TYPES}),
        ("file", {
            "value": "/etc/radicale/rights",
            "help": "file for rights management from_file",
            "type": filepath})])),
    ("storage", OrderedDict([
        ("type", {
            "value": "multifilesystem",
            "help": "storage backend",
            "type": str_or_callable,
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
            "type": str}),
        ("_filesystem_fsync", {
            "value": "True",
            "help": "sync all changes to filesystem during requests",
            "type": bool})])),
    ("web", OrderedDict([
        ("type", {
            "value": "internal",
            "help": "web interface backend",
            "type": str_or_callable,
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
        ("_allow_extra", str)]))])


def parse_compound_paths(*compound_paths: Optional[str]
                         ) -> List[Tuple[str, bool]]:
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


def load(paths: Optional[Iterable[Tuple[str, bool]]] = None
         ) -> "Configuration":
    """
    Create instance of ``Configuration`` for use with
    ``radicale.app.Application``.

    ``paths`` a list of configuration files with the format
    ``[(PATH, IGNORE_IF_MISSING), ...]``.
    If a configuration file is missing and IGNORE_IF_MISSING is set, the
    config is set to ``Configuration.SOURCE_MISSING``.

    The configuration can later be changed with ``Configuration.update()``.

    """
    if paths is None:
        paths = []
    configuration = Configuration(DEFAULT_CONFIG_SCHEMA)
    for path, ignore_if_missing in paths:
        parser = RawConfigParser()
        config_source = "config file %r" % path
        config: types.CONFIG
        try:
            with open(path, "r") as f:
                parser.read_file(f)
                config = {s: {o: parser[s][o] for o in parser.options(s)}
                          for s in parser.sections()}
        except Exception as e:
            if not ignore_if_missing or not isinstance(e, FileNotFoundError):
                raise RuntimeError("Failed to load %s: %s" % (config_source, e)
                                   ) from e
            config = Configuration.SOURCE_MISSING
        configuration.update(config, config_source)
    return configuration


_Self = TypeVar("_Self", bound="Configuration")


class Configuration:

    SOURCE_MISSING: ClassVar[types.CONFIG] = {}

    _schema: types.CONFIG_SCHEMA
    _values: types.MUTABLE_CONFIG
    _configs: List[Tuple[types.CONFIG, str, bool]]

    def __init__(self, schema: types.CONFIG_SCHEMA) -> None:
        """Initialize configuration.

        ``schema`` a dict that describes the configuration format.
        See ``DEFAULT_CONFIG_SCHEMA``.
        The content of ``schema`` must not change afterwards, it is kept
        as an internal reference.

        Use ``load()`` to create an instance for use with
        ``radicale.app.Application``.

        """
        self._schema = schema
        self._values = {}
        self._configs = []
        default = {section: {option: self._schema[section][option]["value"]
                             for option in self._schema[section]
                             if option not in INTERNAL_OPTIONS}
                   for section in self._schema}
        self.update(default, "default config", privileged=True)

    def update(self, config: types.CONFIG, source: Optional[str] = None,
               privileged: bool = False) -> None:
        """Update the configuration.

        ``config`` a dict of the format {SECTION: {OPTION: VALUE, ...}, ...}.
        The configuration is checked for errors according to the config schema.
        The content of ``config`` must not change afterwards, it is kept
        as an internal reference.

        ``source`` a description of the configuration source (used in error
        messages).

        ``privileged`` allows updating sections and options starting with "_".

        """
        if source is None:
            source = "unspecified config"
        new_values: types.MUTABLE_CONFIG = {}
        for section in config:
            if (section not in self._schema or
                    section.startswith("_") and not privileged):
                raise ValueError(
                    "Invalid section %r in %s" % (section, source))
            new_values[section] = {}
            extra_type = None
            extra_type = self._schema[section].get("_allow_extra")
            if "type" in self._schema[section]:
                if "type" in config[section]:
                    plugin = config[section]["type"]
                else:
                    plugin = self.get(section, "type")
                if plugin not in self._schema[section]["type"]["internal"]:
                    extra_type = unspecified_type
            for option in config[section]:
                type_ = extra_type
                if option in self._schema[section]:
                    type_ = self._schema[section][option]["type"]
                if (not type_ or option in INTERNAL_OPTIONS or
                        option.startswith("_") and not privileged):
                    raise RuntimeError("Invalid option %r in section %r in "
                                       "%s" % (option, section, source))
                raw_value = config[section][option]
                try:
                    if type_ == bool and not isinstance(raw_value, bool):
                        raw_value = _convert_to_bool(raw_value)
                    new_values[section][option] = type_(raw_value)
                except Exception as e:
                    raise RuntimeError(
                        "Invalid %s value for option %r in section %r in %s: "
                        "%r" % (type_.__name__, option, section, source,
                                raw_value)) from e
        self._configs.append((config, source, bool(privileged)))
        for section in new_values:
            self._values[section] = self._values.get(section, {})
            self._values[section].update(new_values[section])

    def get(self, section: str, option: str) -> Any:
        """Get the value of ``option`` in ``section``."""
        with contextlib.suppress(KeyError):
            return self._values[section][option]
        raise KeyError(section, option)

    def get_raw(self, section: str, option: str) -> Any:
        """Get the raw value of ``option`` in ``section``."""
        for config, _, _ in reversed(self._configs):
            if option in config.get(section, {}):
                return config[section][option]
        raise KeyError(section, option)

    def get_source(self, section: str, option: str) -> str:
        """Get the source that provides ``option`` in ``section``."""
        for config, source, _ in reversed(self._configs):
            if option in config.get(section, {}):
                return source
        raise KeyError(section, option)

    def sections(self) -> List[str]:
        """List all sections."""
        return list(self._values.keys())

    def options(self, section: str) -> List[str]:
        """List all options in ``section``"""
        return list(self._values[section].keys())

    def sources(self) -> List[Tuple[str, bool]]:
        """List all config sources."""
        return [(source, config is self.SOURCE_MISSING) for
                config, source, _ in self._configs]

    def copy(self: _Self, plugin_schema: Optional[types.CONFIG_SCHEMA] = None
             ) -> _Self:
        """Create a copy of the configuration

        ``plugin_schema`` is a optional dict that contains additional options
        for usage with a plugin. See ``DEFAULT_CONFIG_SCHEMA``.

        """
        if plugin_schema is None:
            schema = self._schema
        else:
            new_schema = dict(self._schema)
            for section, options in plugin_schema.items():
                if (section not in new_schema or
                        "type" not in new_schema[section] or
                        "internal" not in new_schema[section]["type"]):
                    raise ValueError("not a plugin section: %r" % section)
                new_section = dict(new_schema[section])
                new_type = dict(new_section["type"])
                new_type["internal"] = (self.get(section, "type"),)
                new_section["type"] = new_type
                for option, value in options.items():
                    if option in new_section:
                        raise ValueError("option already exists in %r: %r" %
                                         (section, option))
                    new_section[option] = value
                new_schema[section] = new_section
            schema = new_schema
        copy = type(self)(schema)
        for config, source, privileged in self._configs:
            copy.update(config, source, privileged)
        return copy
