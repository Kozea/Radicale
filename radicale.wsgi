#!/usr/bin/env python3
#
# This file is part of Radicale Server - Calendar Server
# Copyright © 2011-2017 Guillaume Ayoub
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
Radicale WSGI file (mod_wsgi and uWSGI compliant).

"""

import os
from radicale import Application, config, log


config_paths = []
if os.environ.get("RADICALE_CONFIG"):
    config_paths.append(os.environ["RADICALE_CONFIG"])
configuration = config.load(config_paths, ignore_missing_paths=False)
filename = os.path.expanduser(configuration.get("logging", "config"))
debug = configuration.getboolean("logging", "debug")
logger = log.start("radicale", filename, debug)
application = Application(configuration, logger)
