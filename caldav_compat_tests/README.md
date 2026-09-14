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
