#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# This file is part of Radicale Server - Calendar Server
# Copyright © 2009-2010 Guillaume Ayoub
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
Radicale CalDAV server
======================

The Radicale Project is a CalDAV calendar server.  It aims to be a light
solution, easy to use, easy to install, easy to configure.  As a consequence,
it requires few software dependances and is pre-configured to work
out-of-the-box.

The Radicale Project runs on most of the UNIX-like platforms (Linux, *BSD,
MacOS X) and Windows.  It is known to work with Lightning and Sunbird 0.9+. It
is free and open-source software, released under GPL version 3.

For further information, please visit the `Radicale Website
<http://www.radicale.org/>`_.

"""

import os
import shutil

from distutils.core import setup, Command
from distutils.command.build_scripts import build_scripts

class BuildScripts(build_scripts):
    """Build the package."""
    def run(self):
        """Run building."""
        self.mkpath(self.build_dir)
        for script in self.scripts:
            root, _ = os.path.splitext(script)
            self.copy_file(script, os.path.join(self.build_dir, root))

class Clean(Command):
    """Clean up package temporary files."""
    description = "clean up package temporary files"
    user_options = []

    def initialize_options(self):
        """Pre-processing."""
        pass

    def finalize_options(self):
        """Post-processing."""
        pass

    def run(self):
        """Run clean up."""
        path = os.path.abspath(os.path.dirname(__file__))
        for pathname, _, files in os.walk(path):
            for filename in filter(self._should_remove, files):
                os.unlink(os.path.join(pathname, filename))

        for folder in ("build", "dist"):
            if os.path.isdir(os.path.join(path, folder)):
                shutil.rmtree(os.path.join(path, folder))

        if os.path.isfile(os.path.join(path, "MANIFEST")):
            os.unlink(os.path.join(path, "MANIFEST"))

    @staticmethod
    def _should_remove(filename):
        """Return if ``filename`` should be considered as temporary."""
        return (os.path.splitext(filename)[1] == ".pyc" or
                os.path.splitext(filename)[1] == ".pyo" or
                filename.endswith("~") or
                (filename.startswith("#") and filename.endswith("#")))
        

setup(
    name="Radicale",
    version="0.2",
    description="CalDAV Server",
    long_description=__doc__,
    author="Guillaume Ayoub",
    author_email="guillaume.ayoub@kozea.fr",
    url="http://www.radicale.org/",
    download_url = "http://radicale.org/src/radicale/Radicale-0.2.tar.gz",
    license="GNU GPL v3",
    platforms="Any",
    packages=["radicale", "radicale.acl"],
    provides=["radicale"],
    scripts=["radicale.py"],
    cmdclass={"clean": Clean,
              "build_scripts": BuildScripts},
    keywords=["calendar", "CalDAV"],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Environment :: Web Environment",
        "Intended Audience :: End Users/Desktop",
        "Intended Audience :: Information Technology",
        "License :: OSI Approved :: GNU General Public License (GPL)",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 2.5",
        "Programming Language :: Python :: 2.6",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.0",
        "Programming Language :: Python :: 3.1",
        "Topic :: Office/Business :: Groupware"])
