# Integration tests

These tests use Playwright to run the tests agains a full Radicale instance.

## First time install

You need to install playwright. The easiest way to do this is to create a .venv with playwright inside. You can do this by trying to run the integ tests and then entering the .venv

Assuming you use uv to run/create your .venvs, note that the invocation will fail:

``` lang=shell
uv run --extra integ_test pytest integ_tests
source .venv/bin/activate
```

then run

``` lang=shell
playwright install --with-deps
```

## Running the tests

if you use uv, you can run

``` lang=shell
uv run --extra integ_test pytest integ_tests
```
