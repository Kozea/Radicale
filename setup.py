#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# This file is part of Radicale Server - Calendar Server
# Copyright © 2009-2013 Guillaume Ayoub
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

from distutils.core import setup
import radicale


# When the version is updated, ``radicale.VERSION`` must be modified.
# A new section in the ``NEWS`` file must be added too.
setup(
    name="Radicale",
    version=radicale.VERSION,
    description="CalDAV and CardDAV Server",
    long_description=__doc__,
    author="Guillaume Ayoub",
    author_email="guillaume.ayoub@kozea.fr",
    url="http://www.radicale.org/",
    download_url=("http://pypi.python.org/packages/source/R/Radicale/"
                  "Radicale-%s.tar.gz" % radicale.VERSION),
    license="GNU GPL v3",
    platforms="Any",
    packages=["radicale", "radicale.auth", "radicale.storage", "radicale.rights"],
    provides=["radicale"],
    scripts=["bin/radicale"],
    keywords=["calendar", "addressbook", "CalDAV", "CardDAV"],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Environment :: Web Environment",
        "Intended Audience :: End Users/Desktop",
        "Intended Audience :: Information Technology",
        "License :: OSI Approved :: GNU General Public License (GPL)",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 2.6",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.1",
        "Programming Language :: Python :: 3.2",
        "Programming Language :: Python :: 3.3",
        "Programming Language :: Python :: 3.4",
        "Topic :: Office/Business :: Groupware"])
