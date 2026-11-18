# CI and CD

Workflows live in `.github/workflows/`. Versions of actions and runners below are the ones in those files. The Test workflow is the one that must pass before a maintainer merges a code change.

## What does not run the tests

`test.yml` ignores pushes and pull requests that only touch:

* `docs/**`
* `**.md` (including `DOCUMENTATION.md`, `CHANGELOG.md`, `AGENTS.md`)
* `radicale/web/README.md` and `radicale/web/internal_data/css/icons/credits.md`
* `Dockerfile`, `Dockerfile.dev`, `config`, `rights`, `contrib/**`, `compose.yaml`
* `setup.py.legacy`
* the Docker, documentation, PyPI, CodeQL, and dependency-audit workflow files

A change to Python under `radicale/` runs the workflow. A documentation-only change does not.

## Test workflow

File: `.github/workflows/test.yml`. It runs on `push` and `pull_request`, minus the paths above.

Lint runs first, on `ubuntu-26.04` with Python 3.15:

```
tox -c pyproject.toml -e flake8,isort,mypy
```

The pins are flake8 7.1.0, isort 5.13.2, and mypy 1.11.0. See [AGENTS.md](../AGENTS.md).

`test-ubuntu-python-newest` lists `lint` in `needs`. Several later jobs do not name `lint` themselves. `coveralls-dryrun`, `js-test`, `htmlvalidator`, `integ-test`, and `caldav-compat-test` need `test-ubuntu-python-newest`, so they still wait for lint. `coveralls-test` needs `coveralls-dryrun`, and `coveralls-finish` needs `coveralls-test`. Commands:

| Job | Where | Command |
| --- | --- | --- |
| Newest CPython | Ubuntu 26.04, Python 3.15 | `tox -c pyproject.toml -e py` |
| passlib instead of libpass | same, after `sed` replaces `libpass` with `passlib` in `pyproject.toml` | `tox -c pyproject.toml -e py` |
| VFAT, VFAT+UTF-8, NTFS | Ubuntu 26.04, Python 3.15 | `tox -c pyproject.toml -e py_filesystem_vfat`, and the same with `py_filesystem_vfat_utf8` and `py_filesystem_ntfs` |
| 32-bit | `i386/python:3.11` | `tox -c /__w/Radicale/Radicale/pyproject.toml -e py` |
| macOS and Windows, newest | `macos-latest`, `windows-latest`, Python 3.15 | `tox -c pyproject.toml -e py` |
| Older CPython and PyPy | Ubuntu 26.04: 3.14, 3.13, 3.12, 3.11, 3.10, PyPy 3.11, PyPy 3.10 | `tox -c pyproject.toml -e py` |
| Oldest | Ubuntu 24.04: Python 3.9 and PyPy 3.9 | `tox -c pyproject.toml -e py` |
| Older on macOS and Windows | 3.14 down to 3.9, and PyPy 3.11, 3.10, 3.9 on macOS only | `tox -c pyproject.toml -e py` |
| JavaScript | Ubuntu 26.04, Node 24 | `tsc -p radicale/web/jsconfig.json` with TypeScript 7.0.2 |
| HTML | `radicale/web/internal_data/`, CSS included | `html5validator-action` |
| Web UI | Ubuntu 26.04, Python 3.15 | `uv run --extra dev pytest integ_tests/ -v` |
| CalDAV compatibility | same | `uv run --extra caldav_test pytest caldav_compat_tests/ -v` |
| Coverage dry run | Ubuntu 26.04, Python 3.15, after `libldap-dev` and `libsasl2-dev` | `tox -c pyproject.toml -e py_coverage` |

`py` runs `pytest -r s .` with the `test` extra. That extra installs pytest, waitress, bcrypt, argon2-cffi, pam, ldap3, hypercorn, cheroot, pika, and requests. `integ_tests` and `caldav_compat_tests` are excluded by `[tool.pytest.ini_options] norecursedirs`, so `tox -c pyproject.toml -e py` does not collect them.

Coveralls upload (`coveralls-test` and `coveralls-finish`) runs only when `github.event_name == 'push'`. A pull request runs the dry-run coverage job and skips the upload. A skipped Coveralls check on a pull request is expected.

`requires-python` is `>=3.9.0`. Classifiers list CPython 3.9 through 3.14 and PyPy. CI also runs CPython 3.15. The wiki table of tested versions is the support statement. This file only lists what the workflow runs.

## CodeQL

`.github/workflows/codeql.yml` runs on push and pull request to `master`, and on a weekly schedule (`19 5 * * 5`). Languages are `actions`, `javascript-typescript`, and `python`, all with `build-mode: none`.

## Dependency audit

`.github/workflows/dependency-audit.yml` runs `pip-audit` on push and pull request, and every day at 06:30 UTC. It installs Radicale with the `bcrypt`, `argon2`, `ldap`, `oauth2`, `rabbitmq`, `cheroot`, and `h2` extras, then audits that environment. A known vulnerability fails the job, so a new advisory shows up without a code change. The Test workflow does not run for this file alone.

## Documentation site

`.github/workflows/generate-documentation.yml` runs on a push that changes `DOCUMENTATION.md`. It checks out the `gh-pages` branch and runs `documentation-generator/run.py` from that branch. The generator is not in the `master` tree. Editing `docs/` does not publish the operator site.

## Containers

`.github/workflows/docker-publish.yml` runs when a GitHub Release is published (`release: types: [released]`), every day at 00:00 UTC, and on `workflow_dispatch`.

The scheduled run is skipped when the repository variable `DOCKERHUB_ORGNAME` is empty. A release or a manual run is not skipped for that reason.

The image is built from `Dockerfile` for `linux/amd64`, `linux/arm64`, and `linux/arm/v7`. Build arguments are `DEPENDENCIES=bcrypt,argon2,ldap,pam` and `VERSION` set to the release tag, or the ref name when there is no tag. The Dockerfile installs `Radicale[DEPENDENCIES]` from `https://github.com/Kozea/Radicale/archive/${VERSION}.tar.gz`. It does not copy the working tree into the image. `flavor: latest=true` has no event condition, so `latest` is requested on a release, a scheduled run, and a manual run. `stable` is added only when `github.event_name == 'release'`. Semver tags (`version`, `major`, `major.minor`) come from a semver git tag. A scheduled build is also tagged `nightly-YYYYMMDD`. A manual run enables the raw tag `workflow_dispatch-{{branch}}-{{sha}}`. The workflow uses `docker/metadata-action@v5`. In the current source of that tag, `{{branch}}` is empty unless the ref starts with `refs/heads/`, and `{{sha}}` is the first 7 characters of the commit unless `DOCKER_METADATA_SHORT_SHA_LENGTH` is set. `sanitizeTag` then replaces each run of characters outside `[A-Za-z0-9._-]` with one `-`. A branch `feature/foo` renders `workflow_dispatch-feature-foo-` plus that short sha. A ref that is not `refs/heads/…` renders `workflow_dispatch--` plus that short sha.

Images are pushed to GHCR and Docker Hub.

`.github/workflows/docker-nightly-cleanup.yml` runs at 00:10 UTC and on `workflow_dispatch`. It deletes GHCR versions of package `Radicale` in org `Kozea` whose tags contain `nightly` and whose `created_at` string is less than the ISO date of 30 days ago. That cutoff is a date with no time, so a version created on the cutoff day is kept. The inspect name is `ghcr.io/kozea/radicale`.

## PyPI

`.github/workflows/pypi-publish.yml` runs on `release: types: [released]`. The workflow file has no repository guard. It builds an sdist and a wheel with `python -m build --sdist --wheel` and publishes both with `pypa/gh-action-pypi-publish` using GitHub OIDC (`id-token: write`). A tag by itself does not publish. A draft does not publish. Publishing a pre-release directly emits `prereleased`. Publishing a draft as a pre-release emits `published`, not `prereleased`. Neither emits `released`, so this workflow does not run for a pre-release. GitHub documents that `prereleased` does not fire for a pre-release published from a draft.

## Local equivalents

The wiki page [Development Testing Release](https://github.com/Kozea/Radicale/wiki/05-%E2%80%90-Development-Testing-Release) lists the tox environments, including filesystem environments that need root and a loop mount (`py_filesystem_vfat`, `py_filesystem_ntfs`, and others). Those are optional local runs. CI runs the three named in the table above.
