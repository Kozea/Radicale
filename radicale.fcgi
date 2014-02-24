#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of Radicale Server - Calendar Server
# Copyright © 2011-2013 Guillaume Ayoub
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
Radicale FastCGI Example.

Launch a Radicale FastCGI server according to configuration.

"""

try:
    from flup.server.fcgi import WSGIServer
except ImportError:
    from flipflop import WSGIServer
import radicale


radicale.log.start()
radicale.log.LOGGER.info("Starting Radicale FastCGI server")
WSGIServer(radicale.Application()).run()
radicale.log.LOGGER.info("Stopping Radicale FastCGI server")
