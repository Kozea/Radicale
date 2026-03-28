# Integration tests

These tests use Playwright to run the tests agains a full Radicale instance.

## First time install

You need to install playwright. The easiest way to do this is to create a .venv with playwright inside. You can do this by trying to run the integ tests and then entering the .venv

### UV

Assuming you use uv to run/create your .venvs, note that the invocation will fail:

```lang=shell
uv run --extra integ_test pytest integ_tests
source .venv/bin/activate
```

then run

```lang=shell
playwright install --with-deps
```

### Tox

Tox will install the needed browser automatically. However, it will not automatically install the needed system depedencies, since those would need root permissions. To install all playwright with all needed libraries, run:

```lang=shell
tox -c pyproject.toml -e integ_test exec -- playwright install --with-deps
```

## Running the tests

### UV

if you use uv, you can run

```lang=shell
uv run --extra dev pytest integ_tests
```

### Tox

if you use tox, you can run

```lang=shell
tox -c pyproject.toml -e integ_test
```
