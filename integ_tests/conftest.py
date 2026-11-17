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

"""Playwright launch options shared by the web UI integration tests."""

from typing import Any

import pytest

# A name that is not a loopback host, so http:// is not a secure context.
# Chromium maps it to 127.0.0.1, where the test server is bound.
INSECURE_HOST = "radicale.insecure"


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args: dict[str, Any]) -> dict[str, Any]:
    """Resolve the insecure test host without changing other origins."""
    args = list(browser_type_launch_args.get("args") or [])
    args.append("--host-resolver-rules=MAP %s 127.0.0.1" % INSECURE_HOST)
    return {**browser_type_launch_args, "args": args}
