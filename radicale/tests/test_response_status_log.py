# This file is part of Radicale - CalDAV and CardDAV server
# Copyright © 2026-2026 oliviasculley <olivia@sculley.dev>
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

"""HTTP status logging: 4xx is error, and the notice statuses stay quieter."""

import logging

from radicale.tests import BaseTest


class TestResponseStatusLog(BaseTest):

    def setup_method(self) -> None:
        super().setup_method()
        self.configure({
            "auth": {"type": "none", "delay": "0"},
            "server": {"delay_on_error": "0"},
        })

    def test_client_error_is_logged_at_error(self, caplog) -> None:
        caplog.set_level(logging.ERROR, logger="radicale")
        status, _, _ = self.request(
            "PROPFIND", "/", "<not-xml",
            HTTP_DEPTH="0", login="alice:secret", check=None)
        assert status == 400
        assert any(
            record.levelno == logging.ERROR and "400 Bad Request" in record.message
            for record in caplog.records)

    def test_not_found_stays_below_error(self, caplog) -> None:
        caplog.set_level(logging.DEBUG, logger="radicale")
        status, _, _ = self.request(
            "GET", "/alice/missing.ics", login="alice:secret", check=None)
        assert status == 404
        assert any(
            "404 Not Found" in record.message for record in caplog.records)
        assert not any(
            record.levelno >= logging.ERROR and "404 Not Found" in record.message
            for record in caplog.records)
