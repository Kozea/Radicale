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

"""
Radicale Server entry point.

Launch the Radicale Serve according to configuration and command-line
arguments.
"""

# TODO: Manage depth and calendars/collections (see xmlutils)
# TODO: Manage smart and configurable logs
# TODO: Manage authentication

import os
import sys
import optparse

import radicale

parser = optparse.OptionParser()
parser.add_option(
    "-d", "--daemon", action="store_true",
    default=radicale.config.getboolean("server", "daemon"),
    help="launch as daemon")
parser.add_option(
    "-n", "--name",
    default=radicale.config.get("server", "name"),
    help="set server name")
parser.add_option(
    "-p", "--port",
    default=radicale.config.getint("server", "port"),
    help="set server port")
parser.add_option(
    "-P", "--protocol",
    default=radicale.config.get("server", "protocol"),
    help="set server protocol")
options, args = parser.parse_args()

if options.daemon:
    if os.fork():
        sys.exit()
    sys.stdout = sys.stderr = open(os.devnull, "w")
if options.protocol == "http":
    server = radicale.server.HTTPServer(
        (options.name, options.port), radicale.CalendarHandler)
    server.serve_forever()
else:
    raise StandardError("%s: unsupported protocol" % options.protocol)
