# This file is part of Radicale - CalDAV and CardDAV server
# Copyright © 2026-2026 Peter Bieringer <pb@bieringer.de>
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
Tests for utils module.

"""

import logging
import os
import ssl
import sys
from types import SimpleNamespace

import pytest

from radicale import auth, config, utils
from radicale.auth import none as none_auth


class TestUtils:
    """Tests generic utils function."""

    def test_format_unit_dec(self) -> None:
        """Verify format unit decimal"""
        test_matrix = {
                1: "1",
                1100: "1.1 k",
                1100000: "1.1 m",
                1100000000: "1.1 g",
                }

        for value in test_matrix:
            string = utils.format_unit(value)
            assert string == test_matrix[value]

    def test_format_unit_bin(self) -> None:
        """Verify format unit binary"""
        test_matrix = {
                1: "1",
                1000: "1000",
                2000: "2.0 K",
                10000000: "9.5 M",
                10000000000: "9.3 G",
                }
        for value in test_matrix:
            string = utils.format_unit(value, binary=True)
            assert string == test_matrix[value]

    def test_ssl_context_options(self) -> None:
        """Test SSL context options"""
        test_matrix = {
                "SSLv3": [ssl.OP_NO_TLSv1, ssl.OP_NO_TLSv1_1, ssl.OP_NO_TLSv1_2, ssl.OP_NO_TLSv1_3],
                "TLSv1": [ssl.OP_NO_SSLv3, ssl.OP_NO_TLSv1_1, ssl.OP_NO_TLSv1_2, ssl.OP_NO_TLSv1_3],
                "TLSv1.2": [ssl.OP_NO_SSLv3, ssl.OP_NO_TLSv1, ssl.OP_NO_TLSv1_1, ssl.OP_NO_TLSv1_3],
                "TLSv1.3": [ssl.OP_NO_SSLv3, ssl.OP_NO_TLSv1, ssl.OP_NO_TLSv1_1, ssl.OP_NO_TLSv1_2],
                "-ALL": [ssl.OP_NO_SSLv3, ssl.OP_NO_TLSv1, ssl.OP_NO_TLSv1_1, ssl.OP_NO_TLSv1_2, ssl.OP_NO_TLSv1_3],
                "ALL -SSLv3": [ssl.OP_NO_SSLv3],
                "ALL -TLSv1": [ssl.OP_NO_TLSv1],
                "ALL -TLSv1.1": [ssl.OP_NO_TLSv1_1],
                "ALL -TLSv1.2": [ssl.OP_NO_TLSv1_2],
                "ALL -TLSv1.3": [ssl.OP_NO_TLSv1_3],
                }
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        for proto in test_matrix:
            ssl_context_options = utils.ssl_context_options_by_protocol(proto, context.options)
            logging.debug("ssl_context_options=%r", ssl_context_options)
            for opt in test_matrix[proto]:
                assert opt in ssl_context_options

    def test_ssl_context_minium(self) -> None:
        """Test SSL context minimum"""
        test_matrix = {
                ssl.TLSVersion.SSLv3: [ssl.OP_NO_TLSv1, ssl.OP_NO_TLSv1_1, ssl.OP_NO_TLSv1_2, ssl.OP_NO_TLSv1_3],
                ssl.TLSVersion.TLSv1: [ssl.OP_NO_SSLv3, ssl.OP_NO_TLSv1_1, ssl.OP_NO_TLSv1_2, ssl.OP_NO_TLSv1_3],
                ssl.TLSVersion.TLSv1_1: [ssl.OP_NO_SSLv3, ssl.OP_NO_TLSv1, ssl.OP_NO_TLSv1_2, ssl.OP_NO_TLSv1_3],
                ssl.TLSVersion.TLSv1_2: [ssl.OP_NO_SSLv3, ssl.OP_NO_TLSv1, ssl.OP_NO_TLSv1_1, ssl.OP_NO_TLSv1_3],
                ssl.TLSVersion.TLSv1_3: [ssl.OP_NO_SSLv3, ssl.OP_NO_TLSv1, ssl.OP_NO_TLSv1_1, ssl.OP_NO_TLSv1_2],
                }
        for version in test_matrix:
            logging.debug("test version=%r", version)
            ssl_context_options = 0
            for opt in test_matrix[version]:
                ssl_context_options |= opt
            ssl_context_minimum_version = utils.ssl_context_minimum_version_by_options(ssl_context_options)
            logging.debug("ssl_context_options=%r", ssl_context_options)
            assert ssl_context_minimum_version == version

    def test_ssl_context_maximum(self) -> None:
        """Test SSL context maximum"""
        test_matrix = {
                ssl.TLSVersion.SSLv3: [ssl.OP_NO_TLSv1, ssl.OP_NO_TLSv1_1, ssl.OP_NO_TLSv1_2, ssl.OP_NO_TLSv1_3],
                ssl.TLSVersion.TLSv1: [ssl.OP_NO_SSLv3, ssl.OP_NO_TLSv1_1, ssl.OP_NO_TLSv1_2, ssl.OP_NO_TLSv1_3],
                ssl.TLSVersion.TLSv1_1: [ssl.OP_NO_SSLv3, ssl.OP_NO_TLSv1, ssl.OP_NO_TLSv1_2, ssl.OP_NO_TLSv1_3],
                ssl.TLSVersion.TLSv1_2: [ssl.OP_NO_SSLv3, ssl.OP_NO_TLSv1, ssl.OP_NO_TLSv1_1, ssl.OP_NO_TLSv1_3],
                ssl.TLSVersion.TLSv1_3: [ssl.OP_NO_SSLv3, ssl.OP_NO_TLSv1, ssl.OP_NO_TLSv1_1, ssl.OP_NO_TLSv1_2],
                }
        for version in test_matrix:
            logging.debug("test version=%r", version)
            ssl_context_options = 0
            for opt in test_matrix[version]:
                ssl_context_options |= opt
            ssl_context_minimum_version = utils.ssl_context_minimum_version_by_options(ssl_context_options)
            logging.debug("ssl_context_options=%r", ssl_context_options)
            assert ssl_context_minimum_version == version


def _enabled_protocols(options):
    return {
        "SSLv3": not bool(options & ssl.OP_NO_SSLv3),
        "TLSv1": not bool(options & ssl.OP_NO_TLSv1),
        "TLSv1.1": not bool(options & ssl.OP_NO_TLSv1_1),
        "TLSv1.2": not bool(options & ssl.OP_NO_TLSv1_2),
        "TLSv1.3": not bool(options & ssl.OP_NO_TLSv1_3),
    }


_ALL_OFF = {"SSLv3": False, "TLSv1": False, "TLSv1.1": False, "TLSv1.2": False, "TLSv1.3": False}
_ALL_ON = {"SSLv3": True, "TLSv1": True, "TLSv1.1": True, "TLSv1.2": True, "TLSv1.3": True}


class TestUtilsOutcomes:
    def test_format_address(self):
        assert utils.format_address(("127.0.0.1", 5232)) == "127.0.0.1:5232"
        assert utils.format_address(("::1", 5232, 0, 0)) == "[::1]:5232"
        with pytest.raises(NotImplementedError, match="Unsupported address format"):
            utils.format_address((b"\x7f\x00\x00\x01", 5232))

    def test_format_unit_decimal_and_binary_boundaries(self):
        assert utils.format_unit(0) == "0"
        assert utils.format_unit(1000) == "1000"
        assert utils.format_unit(1001) == "1.0 k"
        assert utils.format_unit(2_500_000) == "2.5 m"
        assert utils.format_unit(2_500_000_000) == "2.5 g"
        assert utils.format_unit(-5) == "-5"
        assert utils.format_unit(1024, binary=True) == "1024"
        assert utils.format_unit(1025, binary=True) == "1.0 K"
        assert utils.format_unit(5 * 1024 * 1024, binary=True) == "5.0 M"
        assert utils.format_unit(3 * 1024 * 1024 * 1024, binary=True) == "3.0 G"

    def test_format_ut_boundaries(self):
        if sys.platform == "win32":
            assert utils.format_ut(0) == "0"
            assert utils.format_ut(utils.DATETIME_MIN_UNIXTIME) == str(utils.DATETIME_MIN_UNIXTIME)
            return
        assert utils.format_ut(0) == "0(1970-01-01T00:00:00Z)"
        minimum = utils.format_ut(utils.DATETIME_MIN_UNIXTIME)
        maximum = utils.format_ut(utils.DATETIME_MAX_UNIXTIME)
        assert minimum.startswith(str(utils.DATETIME_MIN_UNIXTIME) + "(<=MIN:")
        assert maximum.startswith(str(utils.DATETIME_MAX_UNIXTIME) + "(>=MAX:")

    def test_limit_and_textwrap(self):
        assert utils.limit_str("abcd", 0) == "abcd"
        assert utils.limit_str("ab", 4) == "ab"
        shortened = utils.limit_str("abcd", 4)
        assert shortened.startswith("abcd...")
        assert "original length 4" in shortened
        assert "limit 4" in shortened
        wrapped = utils.textwrap_str("hi", limit=10)
        assert wrapped.endswith("hi")
        assert wrapped.startswith(" ")
        alien = utils.textwrap_str(5, limit=10)  # type: ignore[arg-type]
        assert alien == "content is not of type 'str' but '<class 'int'>'"

    def test_hexdump_marks_bytes_and_controls(self):
        dumped = utils.hexdump_str("A\r\nü")
        assert dumped.startswith("Hexdump of string:")
        assert "41 " in dumped
        assert "C" in dumped
        assert "L" in dumped
        lines = utils.hexdump_lines("A\r\nB")
        assert lines.startswith("Hexdump of lines:")
        assert "0  " in lines or "   0" in lines
        assert "C" in lines

    def test_sha256_known_digests(self):
        empty = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        abc = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
        assert utils.sha256_str("") == empty
        assert utils.sha256_bytes(b"") == empty
        assert utils.sha256_str("abc") == abc
        assert utils.sha256_bytes(b"abc") == abc

    def test_get_server_netloc(self):
        base = {"SERVER_NAME": "ignored", "SERVER_PORT": "5232", "wsgi.url_scheme": "http"}
        assert utils.get_server_netloc(dict(base, HTTP_HOST="cal.example")) == "cal.example:5232"
        https = dict(base, HTTP_HOST="cal.example", wsgi_url_scheme="https")
        https["wsgi.url_scheme"] = "https"
        https["SERVER_PORT"] = "443"
        assert utils.get_server_netloc(https) == "cal.example"
        assert utils.get_server_netloc(https, force_port=True) == "cal.example:443"
        forwarded = {
            "HTTP_X_FORWARDED_HOST": "cal.example",
            "HTTP_X_FORWARDED_PROTO": "https",
            "SERVER_NAME": "x",
            "SERVER_PORT": "1",
            "wsgi.url_scheme": "http",
        }
        assert utils.get_server_netloc(forwarded) == "cal.example"
        forwarded["HTTP_X_FORWARDED_PORT"] = "8443"
        assert utils.get_server_netloc(forwarded) == "cal.example:8443"
        forwarded["HTTP_X_FORWARDED_HOST"] = "cal.example:8443"
        assert utils.get_server_netloc(forwarded) == "cal.example:8443"
        assert utils.get_server_netloc(dict(base, HTTP_HOST="")) == "ignored:5232"

    def test_user_groups_as_string_names_this_process(self):
        text = utils.user_groups_as_string()
        if sys.platform == "win32":
            assert text.startswith("user=")
            assert "groups=" not in text
            return
        assert text.startswith("user=")
        assert "(%d)" % os.geteuid() in text
        assert "groups=" in text
        assert "(%d)" % os.getegid() in text

    def test_packages_version_lists_runtime_and_libraries(self):
        text = utils.packages_version()
        assert text.startswith("python=%d.%d.%d" % sys.version_info[:3])
        assert "vobject=" in text
        assert "ldap3=" in text
        assert " " in text

    def test_package_version_passlib_and_missing(self):
        assert utils.package_version("passlib")
        with pytest.raises(Exception):
            utils.package_version("radicale-no-such-distribution")

    def test_vobject_feature_flags_follow_the_probes(self, monkeypatch):
        monkeypatch.setattr(utils, "package_version", lambda name: "1.2.3")
        assert utils.vobject_supports_vcard4() is True
        monkeypatch.setattr(utils, "package_version", lambda name: "0.9.9")
        assert utils.vobject_supports_vcard4() is False

        def boom(name):
            raise RuntimeError("missing")

        monkeypatch.setattr(utils, "package_version", boom)
        assert utils.vobject_supports_vcard4() is False

        class Boom:
            def serialize(self):
                raise RuntimeError("no period")

        class Ok:
            def serialize(self):
                return "ok"

        utils.vobject_supports_period_cache = None
        utils.vobject_has_no_AttributeError_cache = None
        try:
            monkeypatch.setattr(utils.vobject, "readOne", lambda content: Boom())
            assert utils.vobject_supports_period() is False
            assert utils.vobject_supports_period() is False
            utils.vobject_supports_period_cache = None
            monkeypatch.setattr(utils.vobject, "readOne", lambda content: Ok())
            assert utils.vobject_supports_period() is True
            utils.vobject_has_no_AttributeError_cache = None
            monkeypatch.setattr(utils.vobject, "readOne", lambda content: Boom())
            assert utils.vobject_has_no_AttributeError() is False
            utils.vobject_has_no_AttributeError_cache = None
            monkeypatch.setattr(utils.vobject, "readOne", lambda content: Ok())
            assert utils.vobject_has_no_AttributeError() is True
        finally:
            utils.vobject_supports_period_cache = None
            utils.vobject_has_no_AttributeError_cache = None
            utils.vobject_supports_period()
            utils.vobject_has_no_AttributeError()

    def test_unknown_if_empty(self):
        assert utils.unknown_if_empty("") == "UNKNOWN"
        assert utils.unknown_if_empty("alice") == "alice"

    def test_load_plugin_internal_external_and_callable(self):
        configuration = config.load()
        configuration.update({"auth": {"type": "none", "delay": "0"}}, "test")
        loaded = utils.load_plugin(auth.INTERNAL_TYPES, "auth", "Auth", auth.BaseAuth, configuration)
        user, _groups, auth_type = loaded.login("alice", "secret", auth.AuthContext())
        assert user == "alice"
        assert auth_type == "none"

        def factory(loaded_config):
            plugin = none_auth.Auth(loaded_config)
            plugin.marker = "factory-used"
            return plugin

        configuration.update({"auth": {"type": factory}}, "test")
        created = utils.load_plugin(auth.INTERNAL_TYPES, "auth", "Auth", auth.BaseAuth, configuration)
        assert created.marker == "factory-used"
        assert created.login("bob", "pw", auth.AuthContext())[0] == "bob"

        configuration.update({"auth": {"type": "radicale.tests.does_not_exist"}}, "test")
        with pytest.raises(RuntimeError, match="Failed to load auth module"):
            utils.load_plugin(auth.INTERNAL_TYPES, "auth", "Auth", auth.BaseAuth, configuration)

    @pytest.mark.parametrize(("protocol", "enabled"), [
        ("", _ALL_OFF),
        ("SSLv2", _ALL_OFF),
        ("SSLv3", {"SSLv3": True, "TLSv1": False, "TLSv1.1": False, "TLSv1.2": False, "TLSv1.3": False}),
        ("TLSv1", {"SSLv3": False, "TLSv1": True, "TLSv1.1": False, "TLSv1.2": False, "TLSv1.3": False}),
        ("TLSv1.1", {"SSLv3": False, "TLSv1": False, "TLSv1.1": True, "TLSv1.2": False, "TLSv1.3": False}),
        ("+TLSv1.2", {"SSLv3": False, "TLSv1": False, "TLSv1.1": False, "TLSv1.2": True, "TLSv1.3": False}),
        ("TLSv1.3", {"SSLv3": False, "TLSv1": False, "TLSv1.1": False, "TLSv1.2": False, "TLSv1.3": True}),
        ("ALL", _ALL_ON),
        ("-ALL", _ALL_OFF),
        ("ALL -TLSv1.1 -SSLv3", {"SSLv3": False, "TLSv1": True, "TLSv1.1": False, "TLSv1.2": True, "TLSv1.3": True}),
        ("-SSLv2", _ALL_OFF),
        ("-SSLv3", _ALL_OFF),
        ("-TLSv1", _ALL_OFF),
        ("-TLSv1.1", _ALL_OFF),
        ("-TLSv1.2", _ALL_OFF),
        ("-TLSv1.3", _ALL_OFF),
    ])
    def test_ssl_protocol_bits(self, protocol, enabled, caplog):
        caplog.set_level(logging.WARNING)
        options = utils.ssl_context_options_by_protocol(protocol, 0)
        assert _enabled_protocols(options) == enabled
        if protocol == "SSLv2":
            assert "ignore SSLv2" in caplog.text

    def test_ssl_protocol_rejects_unknown_entry(self):
        with pytest.raises(RuntimeError, match="unsupported entry 'TLS1.4'"):
            utils.ssl_context_options_by_protocol("TLS1.4", 0)

    def test_ssl_version_bounds_and_protocol_list(self):
        only_12 = utils.ssl_context_options_by_protocol("TLSv1.2", 0)
        assert utils.ssl_context_minimum_version_by_options(only_12) == ssl.TLSVersion.TLSv1_2
        assert utils.ssl_context_maximum_version_by_options(only_12) == ssl.TLSVersion.TLSv1_2
        everything = utils.ssl_context_options_by_protocol("ALL", 0)
        assert utils.ssl_context_minimum_version_by_options(everything) == ssl.TLSVersion.SSLv3
        assert utils.ssl_context_maximum_version_by_options(everything) == ssl.TLSVersion.TLSv1_3
        disabled = utils.ssl_context_options_by_protocol("-ALL", 0)
        assert utils.ssl_context_minimum_version_by_options(disabled) == 0
        assert utils.ssl_context_maximum_version_by_options(disabled) == 0
        listed = utils.ssl_get_protocols(SimpleNamespace(
            options=everything,
            minimum_version=ssl.TLSVersion.SSLv3,
            maximum_version=ssl.TLSVersion.TLSv1_3,
        ))
        assert listed == ["SSLv3", "TLSv1", "TLSv1.1", "TLSv1.2", "TLSv1.3"]
        assert utils.ssl_get_protocols(SimpleNamespace(
            options=disabled, minimum_version=0, maximum_version=0)) == []
        only_listed = utils.ssl_get_protocols(SimpleNamespace(
            options=only_12,
            minimum_version=ssl.TLSVersion.TLSv1_2,
            maximum_version=ssl.TLSVersion.TLSv1_2,
        ))
        assert only_listed == ["TLSv1.2"]
