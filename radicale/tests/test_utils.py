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
import ssl

from radicale import utils


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
