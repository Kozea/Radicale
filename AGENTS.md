# Agent instructions

These rules apply to every change in this repository.

## One change per commit

Put each logical change in its own commit. Do not bundle unrelated edits. Leave unrelated files untouched.

A review comment, a bugfix, and a test addition are separate commits when they are separate changes. The test that shows a bugfix belongs in that bugfix commit.

## Adversarial review of every commit

Review every commit before the next change starts. The wording fixes at the end of that review stay in the same commit and are not reviewed again.

1. Send the commit to several independent adversarial review agents. Three is the minimum. They try to break the change: wrong behavior, lost coverage, a test that does not exercise the code it names, a fix that hides an error, and anything that would fail the project's lint or type checks.
2. Apply every finding that is more than a nit to that same commit. Amend the commit when it has not been published.
3. Review the updated commit again. Report what it still gets wrong, including leftover nits. Do not repeat a finding the update already fixed.
4. Repeat until every remaining finding is a nit.
5. Apply those nits to that same commit, then move on to the next change. Do not open another review round for the nits.

A nit is wording, naming, or formatting that does not change behavior and would not fail CI. Anything that can mislead a later reader about what the test guarantees is not a nit.

Reviewers report findings. They do not edit the tree. The implementing agent applies the fixes.

## Python in this repository

Match the file you are editing. Leave neighboring lines as they are. These notes describe this repository. They are not a substitute for its tests and config.

### Versions

`requires-python` is `>=3.9.0`. Classifiers list CPython 3.9 through 3.14 and PyPy. Do not use syntax or standard-library behavior that 3.9 does not have. A change also has to keep working on the Enterprise Linux versions named on the project wiki. `CONTRIBUTING.md` says not to break that compatibility.

### Checks

The pinned lint and type checks are:

```
tox -c pyproject.toml -e flake8,isort,mypy
```

`pyproject.toml` pins flake8 7.1.0, isort 5.13.2, and mypy 1.11.0 for those environments. `.flake8` ignores E501, so flake8 does not fail on a long line. isort's line length is 79, and `isort --check` fails when an import is not wrapped at that length. isort treats `defusedxml`, `libpass`, `pkg_resources`, `pytest`, and `vobject` as third party. mypy sets `ignore_missing_imports` and `show_error_codes`.

The server suite is:

```
tox -c pyproject.toml -e py
```

That runs `pytest -r s .` with the `test` extra. `[tool.pytest.ini_options]` sets `norecursedirs` to `integ_tests` and `caldav_compat_tests`, so those suites stay out of that run. Run them with `tox -c pyproject.toml -e integ_test` and `tox -c pyproject.toml -e caldav_compat_test`. `PYTEST_RADICALE_LOGLEVEL` selects the Radicale log level inside the suite. The default in `BaseTest` is `debug`.

### Tests

Put a test next to the case it extends. Server tests are usually a `BaseTest` subclass in `radicale/tests/`. `setup_method` creates a temporary storage folder and sets a short auth delay. Change behavior through `configure()`. Assert the outcome a caller sees: a status, a log line, stored data, or a return value.

An assertion that stays green when the branch it names is removed does not cover that branch. A bugfix commit includes the test that failed before the fix.

Optional dependencies are extras, and the import name is not always the extra name. `ldap` provides `ldap3` (the backend then tries `ldap` from the `python_ldap` extra), `pam` provides `pam`, `bcrypt` provides `bcrypt`, `argon2` provides `argon2`, `h2` provides `hypercorn`, `cheroot` provides `cheroot`, `rabbitmq` provides `pika`, and `oauth2` provides `requests`. Skip a test when that imported module is missing. Do not skip on the extra name. Do not import `radicale.auth.pam` at module level. That module imports `pwd` and `grp` at import time. Those modules are missing on Windows, so a test module that imports it there fails during collection. Import it inside the test that needs it, and mark that test with `skipif(sys.platform == "win32", reason="Not supported on Windows")`. pytest errors on `skipif` when `reason` is omitted. `radicale/auth/pam.py` imports the `pam` package inside `Auth.__init__`.

### Errors and logging

Log through `radicale.log.logger`. Keep an error message specific to the failure it reports. A broad `except` that already exists in a file is part of that file's behavior. Do not turn an unrelated exception into success, and do not report it as a different failure.

`# pragma: no cover` is excluded by `[tool.coverage.report]`. Do not add it to hide a branch a test can reach. Leave `[tool.coverage.*]` unchanged unless the change is about how coverage is measured.

### Changelog, docs, config, and copyright

A user-visible change gets a bullet under the current `## x.y.z.dev` section in `CHANGELOG.md`. The `version` in `pyproject.toml` and that section stay together. When the version changes, add the new changelog section in the same change.

A new or changed option is updated in the reference `config` file. When it changes what an operator does, update `DOCUMENTATION.md` as well.

A new Python file copies the GPL header from an existing file in the same area and adds the author's copyright line. On a file that already has copyright lines, add a line when the contribution is large enough. Do not replace another author's line.

### Pull requests

Review the diff and run the local test suite before marking the pull request ready. `CONTRIBUTING.md` requires that local run. When an assistant wrote part of the change, a person reviews it and the pull request says so. The style of the new code matches the file around it. Maintainers merge a pull request after the whole test suite passes.
