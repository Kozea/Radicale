# CalDAV compatibility tests

These tests use the [caldav](https://pypi.org/project/caldav/) client
library together with
[caldav-server-tester](https://pypi.org/project/caldav-server-tester/) to
run a battery of CalDAV client/server interoperability checks against a
real Radicale server (started as a subprocess, listening on a free
localhost port).

The observed feature-support levels are compared against a known baseline
(`EXPECTED_DEVIATIONS` in `test_compatibility.py`). The goal is to catch
compatibility *regressions*: if Radicale starts failing (or passing) a
check differently than before, this test fails.

See also: [Kozea/Radicale#1911](https://github.com/Kozea/Radicale/issues/1911).

## Running the tests

### UV

```lang=shell
uv run --extra caldav_test pytest caldav_compat_tests
```

### Tox

```lang=shell
tox -c pyproject.toml -e caldav_compat_test
```

### Pip

```lang=shell
pip install -e ".[caldav_test]"
pytest caldav_compat_tests
```

## Pinned client library versions

The observed feature report depends not only on `caldav-server-tester`, but
also on the `caldav` client library (which defines the feature model and
how results are reported) and on the libraries it uses to evaluate search
and recurrence results (`icalendar`, `icalendar-searcher`,
`recurring-ical-events`). A new release of any of them can change the
report without any change to Radicale.

They are therefore all pinned to exact, known-good versions in the
`caldav_test` extra in `pyproject.toml`. That is the only place they are
pinned: CI, tox, uv and pip all install them via that extra. Bump them
deliberately in their own PR, updating `EXPECTED_DEVIATIONS` in the same
PR if the new versions change observed behaviour.

## Updating the baseline

If a change to Radicale (or a new release of `caldav-server-tester`)
intentionally changes the observed compatibility, run the tests, inspect
the failure output (it includes the full compatibility report and diff),
and update `EXPECTED_DEVIATIONS` in `test_compatibility.py` accordingly.
Please explain the change in the pull request description.

To print a full compatibility report by hand, point `caldav-server-tester`
(installed as part of the `caldav_test` extra) directly at a running
Radicale instance:

```lang=shell
caldav-server-tester --caldav-url http://127.0.0.1:5232/ \
    --caldav-username tester --caldav-password testpassword \
    --diff
```
