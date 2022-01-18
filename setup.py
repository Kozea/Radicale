#!/usr/bin/env python3

# This file is part of Radicale - CalDAV and CardDAV server
# Copyright © 2009-2017 Guillaume Ayoub
# Copyright © 2017-2018 Unrud <unrud@outlook.com>
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
Radicale CalDAV and CardDAV server
==================================

The Radicale Project is a CalDAV (calendar) and CardDAV (contact) server.  It
aims to be a light solution, easy to use, easy to install, easy to configure.
As a consequence, it requires few software dependances and is pre-configured to
work out-of-the-box.

The Radicale Project runs on most of the UNIX-like platforms (Linux, BSD,
MacOS X) and Windows.  It is known to work with Evolution, Lightning, iPhone
and Android clients. It is free and open-source software, released under GPL
version 3.

For further information, please visit the `Radicale Website
<https://radicale.org/>`_.

"""

import os
import sys

from setuptools import find_packages, setup

# When the version is updated, a new section in the CHANGELOG.md file must be
# added too.
VERSION = "3.1.1"
WEB_FILES = ["web/internal_data/css/icon.png",
             "web/internal_data/css/main.css",
             "web/internal_data/fn.js",
             "web/internal_data/index.html"]

setup_requires = []
if {"pytest", "test", "ptr"}.intersection(sys.argv):
    setup_requires.append("pytest-runner")
tests_require = ["pytest-runner", "pytest", "pytest-cov", "pytest-flake8",
                 "pytest-isort", "typeguard", "waitress"]
os.environ["PYTEST_ADDOPTS"] = os.environ.get("PYTEST_ADDOPTS", "")
# Mypy only supports CPython
if sys.implementation.name == "cpython":
    tests_require.extend(["pytest-mypy", "types-setuptools"])
    os.environ["PYTEST_ADDOPTS"] += " --mypy"

setup(
    name="Radicale",
    version=VERSION,
    description="CalDAV and CardDAV Server",
    long_description=__doc__,
    author="Guillaume Ayoub",
    author_email="guillaume.ayoub@kozea.fr",
    url="https://radicale.org/",
    download_url=("https://pypi.python.org/packages/source/R/Radicale/"
                  "Radicale-%s.tar.gz" % VERSION),
    license="GNU GPL v3",
    platforms="Any",
    packages=find_packages(
        exclude=["*.tests", "*.tests.*", "tests.*", "tests"]),
    package_data={"radicale": [*WEB_FILES, "py.typed"]},
    entry_points={"console_scripts": ["radicale = radicale.__main__:run"]},
    install_requires=["defusedxml", "passlib", "vobject>=0.9.6",
                      "python-dateutil>=2.7.3", "setuptools"],
    setup_requires=setup_requires,
    tests_require=tests_require,
    extras_require={"test": tests_require,
                    "bcrypt": ["passlib[bcrypt]", "bcrypt"]},
    keywords=["calendar", "addressbook", "CalDAV", "CardDAV"],
    python_requires=">=3.6.0",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Console",
        "Environment :: Web Environment",
        "Intended Audience :: End Users/Desktop",
        "Intended Audience :: Information Technology",
        "License :: OSI Approved :: GNU General Public License (GPL)",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: Implementation :: CPython",
        "Programming Language :: Python :: Implementation :: PyPy",
        "Topic :: Office/Business :: Groupware"])
