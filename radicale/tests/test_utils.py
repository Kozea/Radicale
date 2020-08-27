from pytest import deprecated_call, fixture, mark, raises

import radicale.utils as utils
from radicale.utils import load_plugin


class Configuration:
    def __init__(self, data):
        self.data = data

    def get(self, a, b):
        return self.data.get(a, {}).get(b)


class Module:
    class Plugin:
        @classmethod
        def from_config(cls, config):
            return cls()

    class LegacyPlugin:
        def __init__(self, config):
            self.config = config


class TestLoadPlugin:
    @fixture(autouse=True)
    def import_module(self, monkeypatch):
        def import_module(module):
            if module == "test.plugin" or "radicale.test.plugin":
                return Module
            raise ImportError(module)

        monkeypatch.setattr(utils, "import_module", import_module)

        return import_module

    @fixture
    def config(self):
        return Configuration({"test": {"type": "test.plugin"}})

    @mark.parametrize(["internal_types"], [
        (["test.plugin"],),
        ([],),
    ])
    def test_ok(self, internal_types, config):
        plugin = load_plugin(internal_types, "test", "Plugin", config)

        assert isinstance(plugin, Module.Plugin)

    def test_warning(self, config):
        with deprecated_call():
            plugin = load_plugin([], "test", "LegacyPlugin", config)

        assert isinstance(plugin, Module.LegacyPlugin)
        assert plugin.config is config

    def test_not_found(self, config):
        with raises(RuntimeError):
            load_plugin([], "any", "CustomPlugin", config)
