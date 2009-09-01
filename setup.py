#!/usr/bin/python
# -*- coding: utf-8; indent-tabs-mode: nil; -*-
#
# This file is part of Radicale Server - Calendar Server
# Copyright © 2009 Guillaume Ayoub
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

import os
import shutil

from distutils.core import setup, Command
from distutils.command.build_scripts import build_scripts

class BuildScripts(build_scripts):
    def run(self):
        self.mkpath(self.build_dir)
        for script in self.scripts:
            root, _ = os.path.splitext(script)
            self.copy_file(script, os.path.join(self.build_dir, root))

class Clean(Command):
    description = "clean up package temporary files"
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
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
        return (os.path.splitext(filename)[1] == ".pyc" or
                os.path.splitext(filename)[1] == ".pyo" or
                filename.endswith("~") or
                (filename.startswith("#") and filename.endswith("#")))
        

setup(
    name="Radicale",
    version="0.0",
    description="Radicale CalDAV Server",
    author="Guillaume Ayoub",
    author_email="guillaume.ayoub@kozea.fr",
    url="http://www.radicale.org/",
    license="GNU GPL v3",
    requires=["twisted.web"],
    packages=["radicale", "radicale.acl", "radicale.support"],
    scripts=["radicale.py"],
    cmdclass={'clean': Clean,
              "build_scripts": BuildScripts})
