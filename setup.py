#!/usr/bin/env python3
#
# This file is part of Radicale Server - Calendar Server
# Copyright © 2009-2017 Guillaume Ayoub
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

import sys

from setuptools import setup

# When the version is updated, a new section in the NEWS.md file must be
# added too.
VERSION = "2.1.12"
WEB_FILES = ["web/css/icon.png", "web/css/main.css", "web/fn.js",
             "web/index.html"]


needs_pytest = {"pytest", "test", "ptr"}.intersection(sys.argv)
pytest_runner = ["pytest-runner"] if needs_pytest else []
tests_require = ["pytest-runner", "pytest", "pytest-cov", "pytest-flake8",
                 "pytest-isort"]

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
    packages=["radicale"],
    package_data={"radicale": WEB_FILES},
    entry_points={"console_scripts": ["radicale = radicale.__main__:run"]},
    install_requires=["vobject>=0.9.6", "python-dateutil>=2.7.3"],
    setup_requires=pytest_runner,
    tests_require=tests_require,
    extras_require={
        "test": tests_require,
        "md5": "passlib",
        "bcrypt": "passlib[bcrypt]"},
    keywords=["calendar", "addressbook", "CalDAV", "CardDAV"],
    python_requires=">=3.3",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Console",
        "Environment :: Web Environment",
        "Intended Audience :: End Users/Desktop",
        "Intended Audience :: Information Technology",
        "License :: OSI Approved :: GNU General Public License (GPL)",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.3",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Topic :: Office/Business :: Groupware"])
