# This file is part of Radicale Server - Calendar Server
# Copyright © 2019 Unrud <unrud@outlook.com>
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

import os
import shutil
import tempfile
from configparser import RawConfigParser

import pytest

from radicale import config
from radicale.tests.helpers import configuration_to_dict


class TestConfig:
    """Test the configuration."""

    def setup(self):
        self.colpath = tempfile.mkdtemp()

    def teardown(self):
        shutil.rmtree(self.colpath)

    def _write_config(self, config_dict, name):
        parser = RawConfigParser()
        parser.read_dict(config_dict)
        config_path = os.path.join(self.colpath, name)
        with open(config_path, "w") as f:
            parser.write(f)
        return config_path

    def test_parse_compound_paths(self):
        assert len(config.parse_compound_paths()) == 0
        assert len(config.parse_compound_paths("")) == 0
        assert len(config.parse_compound_paths(None, "")) == 0
        assert len(config.parse_compound_paths("config", "")) == 0
        assert len(config.parse_compound_paths("config", None)) == 1

        assert len(config.parse_compound_paths(os.pathsep.join(["", ""]))) == 0
        assert len(config.parse_compound_paths(os.pathsep.join([
            "", "config", ""]))) == 1

        paths = config.parse_compound_paths(os.pathsep.join([
            "config1", "?config2", "config3"]))
        assert len(paths) == 3
        for i, (name, ignore_if_missing) in enumerate([
                ("config1", False), ("config2", True), ("config3", False)]):
            assert os.path.isabs(paths[i][0])
            assert os.path.basename(paths[i][0]) == name
            assert paths[i][1] is ignore_if_missing

    def test_load_empty(self):
        config_path = self._write_config({}, "config")
        config.load([(config_path, False)])

    def test_load_full(self):
        config_path = self._write_config(
            configuration_to_dict(config.load()), "config")
        config.load([(config_path, False)])

    def test_load_missing(self):
        config_path = os.path.join(self.colpath, "does_not_exist")
        config.load([(config_path, True)])
        with pytest.raises(Exception) as exc_info:
            config.load([(config_path, False)])
        e = exc_info.value
        assert "Failed to load config file %r" % config_path in str(e)

    def test_load_multiple(self):
        config_path1 = self._write_config({
            "server": {"hosts": "192.0.2.1:1111"}}, "config1")
        config_path2 = self._write_config({
            "server": {"max_connections": 1111}}, "config2")
        configuration = config.load([(config_path1, False),
                                     (config_path2, False)])
        assert len(configuration.get("server", "hosts")) == 1
        assert configuration.get("server", "hosts")[0] == ("192.0.2.1", 1111)
        assert configuration.get("server", "max_connections") == 1111

    def test_copy(self):
        configuration1 = config.load()
        configuration1.update({"server": {"max_connections": "1111"}}, "test")
        configuration2 = configuration1.copy()
        configuration2.update({"server": {"max_connections": "1112"}}, "test")
        assert configuration1.get("server", "max_connections") == 1111
        assert configuration2.get("server", "max_connections") == 1112

    def test_invalid_section(self):
        configuration = config.load()
        with pytest.raises(Exception) as exc_info:
            configuration.update({"does_not_exist": {"x": "x"}}, "test")
        e = exc_info.value
        assert "Invalid section 'does_not_exist'" in str(e)

    def test_invalid_option(self):
        configuration = config.load()
        with pytest.raises(Exception) as exc_info:
            configuration.update({"server": {"x": "x"}}, "test")
        e = exc_info.value
        assert "Invalid option 'x'" in str(e)
        assert "section 'server'" in str(e)

    def test_invalid_option_plugin(self):
        configuration = config.load()
        with pytest.raises(Exception) as exc_info:
            configuration.update({"auth": {"x": "x"}}, "test")
        e = exc_info.value
        assert "Invalid option 'x'" in str(e)
        assert "section 'auth'" in str(e)

    def test_invalid_value(self):
        configuration = config.load()
        with pytest.raises(Exception) as exc_info:
            configuration.update({"server": {"max_connections": "x"}}, "test")
        e = exc_info.value
        assert "Invalid positive_int" in str(e)
        assert "option 'max_connections" in str(e)
        assert "section 'server" in str(e)
        assert "'x'" in str(e)

    def test_privileged(self):
        configuration = config.load()
        configuration.update({"server": {"_internal_server": "True"}},
                             "test", privileged=True)
        with pytest.raises(Exception) as exc_info:
            configuration.update(
                {"server": {"_internal_server": "True"}}, "test")
        e = exc_info.value
        assert "Invalid option '_internal_server'" in str(e)

    def test_plugin_schema(self):
        plugin_schema = {"auth": {"new_option": {"value": "False",
                                                 "type": bool}}}
        configuration = config.load()
        configuration.update({"auth": {"type": "new_plugin"}}, "test")
        plugin_configuration = configuration.copy(plugin_schema)
        assert plugin_configuration.get("auth", "new_option") is False
        configuration.update({"auth": {"new_option": "True"}}, "test")
        plugin_configuration = configuration.copy(plugin_schema)
        assert plugin_configuration.get("auth", "new_option") is True

    def test_plugin_schema_duplicate_option(self):
        plugin_schema = {"auth": {"type": {"value": "False",
                                           "type": bool}}}
        configuration = config.load()
        with pytest.raises(Exception) as exc_info:
            configuration.copy(plugin_schema)
        e = exc_info.value
        assert "option already exists in 'auth': 'type'" in str(e)

    def test_plugin_schema_invalid(self):
        plugin_schema = {"server": {"new_option": {"value": "False",
                                                   "type": bool}}}
        configuration = config.load()
        with pytest.raises(Exception) as exc_info:
            configuration.copy(plugin_schema)
        e = exc_info.value
        assert "not a plugin section: 'server" in str(e)

    def test_plugin_schema_option_invalid(self):
        plugin_schema = {"auth": {}}
        configuration = config.load()
        configuration.update({"auth": {"type": "new_plugin",
                                       "new_option": False}}, "test")
        with pytest.raises(Exception) as exc_info:
            configuration.copy(plugin_schema)
        e = exc_info.value
        assert "Invalid option 'new_option'" in str(e)
        assert "section 'auth'" in str(e)
