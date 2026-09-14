# This file is part of Radicale - CalDAV and CardDAV server
# Copyright © 2026-2026 Arnav S <172543153+theofficialtruck@users.noreply.github.com>
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
CalDAV compatibility test, using the caldav-server-tester project
(https://github.com/python-caldav/caldav-server-tester) to run a battery of
CalDAV client/server interoperability checks against a real Radicale
server and compare the observed feature-support levels against a known
baseline.

This is meant to catch compatibility *regressions*: if Radicale starts
failing a check that used to pass (or vice versa), this test will fail and
EXPECTED_DEVIATIONS will need to be reviewed and, if the change is
intentional/acceptable, updated.

See README.md in this directory for how to run this locally and how to
update the baseline.

See also: https://github.com/Kozea/Radicale/issues/1911
"""

import pathlib
from typing import Any, Generator

import pytest
from caldav.davclient import DAVClient
from caldav_server_tester import ServerQuirkChecker

from caldav_compat_tests.common import start_radicale_server

# Features where Radicale's observed support level differs from the
# caldav-server-tester default (RFC-compliant) expectation, using an
# out-of-the-box htpasswd-authenticated, filesystem-backed configuration.
#
# Radicale does not implement CalDAV Scheduling (RFC 6638) or principal
# search, hence the "scheduling.*" and "principal-search" entries below.
# The rest are narrower gaps; see each feature's description (printed by
# ServerQuirkChecker.report()) for details.
EXPECTED_DEVIATIONS = {
    "get-current-user-principal.has-calendar": {"support": "unsupported"},
    "principal-search": {"support": "unsupported"},
    "scheduling": {"support": "unsupported"},
    "scheduling.auto-schedule": {"support": "unsupported"},
    "scheduling.calendar-user-address-set": {"support": "unsupported"},
    "scheduling.freebusy-query": {"support": "unsupported"},
    "scheduling.mailbox": {"support": "unsupported"},
    "scheduling.mailbox.inbox-delivery": {"support": "unsupported"},
    "scheduling.schedule-tag": {"support": "unsupported"},
    "scheduling.schedule-tag.stable-partstat": {"support": "unsupported"},
    "search.recurrences.expanded.todo": {"support": "unsupported"},
    "search.text.case-sensitive": {"support": "unsupported"},
}


@pytest.fixture
def radicale_server(tmp_path: pathlib.Path) -> Generator[str, Any, None]:
    yield from start_radicale_server(tmp_path)


def test_compatibility(radicale_server: str) -> None:
    with DAVClient(
        url=radicale_server, username="tester", password="testpassword"
    ) as client:
        checker = ServerQuirkChecker(client)
        checker.check_all()
        try:
            observed_deviations = checker.features_checked.dotted_feature_set_list(
                compact=True
            )
            assert observed_deviations == EXPECTED_DEVIATIONS, (
                "Observed CalDAV compatibility deviates from the known baseline "
                "(see caldav_compat_tests/test_compatibility.py). This can mean "
                "either a compatibility regression, or an improvement/change "
                "that requires updating EXPECTED_DEVIATIONS. Full report:\n"
                + checker.report(verbose=False, show_diff=True)
            )
        finally:
            checker.cleanup(force=True)
