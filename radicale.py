#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# This file is part of Radicale Server - Calendar Server
# Copyright © 2008-2010 Guillaume Ayoub
# Copyright © 2008 Nicolas Kandel
# Copyright © 2008 Pascal Halter
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

# TODO: Manage depth and calendars/collections (see xmlutils)
# TODO: Manage smart and configurable logs
# TODO: Manage authentication
# TODO: Magage command-line options

"""
Radicale Server entry point.

Launch the Radicale Serve according to the configuration.
"""

import sys
import BaseHTTPServer

import radicale

if radicale.config.get("server", "type") == "http":
    server = BaseHTTPServer.HTTPServer(
        ("", radicale.config.getint("server", "port")),
        radicale.CalendarHandler)
    server.serve_forever()
