import sys
from importlib.util import find_spec


def pytest_addoption(parser, pluginmanager):
    # Ignore the "--mypy" argument if pytest-mypy is not installed and
    # the implementation is not cpython
    if sys.implementation.name != 'cpython' and not find_spec("pytest_mypy"):
        parser.addoption("--mypy", action="store_true")
