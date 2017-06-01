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
<http://www.radicale.org/>`_.

"""

import re
import sys
from os import path

from setuptools import setup

WEB_FILES = ["web/css/icon.png", "web/css/main.css", "web/fn.js",
             "web/index.html"]

init_path = path.join(path.dirname(__file__), "radicale", "__init__.py")
with open(init_path, "r", encoding="utf-8") as fd:
    version = re.search('VERSION = "([^"]+)"', fd.read().strip()).group(1)


needs_pytest = {'pytest', 'test', 'ptr'}.intersection(sys.argv)
pytest_runner = ['pytest-runner'] if needs_pytest else []

# When the version is updated, ``radicale.VERSION`` must be modified.
# A new section in the ``NEWS`` file must be added too.
setup(
    name="Radicale",
    version=version,
    description="CalDAV and CardDAV Server",
    long_description=__doc__,
    author="Guillaume Ayoub",
    author_email="guillaume.ayoub@kozea.fr",
    url="http://www.radicale.org/",
    download_url=("http://pypi.python.org/packages/source/R/Radicale/"
                  "Radicale-%s.tar.gz" % version),
    license="GNU GPL v3",
    platforms="Any",
    packages=["radicale"],
    package_data={"radicale": WEB_FILES},
    provides=["radicale"],
    scripts=["bin/radicale"],
    install_requires=["vobject"],
    setup_requires=pytest_runner,
    tests_require=[
        "pytest-runner", "pytest-cov", "pytest-flake8", "pytest-isort"],
    extras_require={"test": [
        "pytest-runner", "pytest-cov", "pytest-flake8", "pytest-isort"]},
    keywords=["calendar", "addressbook", "CalDAV", "CardDAV"],
    python_requires='>=3.3',
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
