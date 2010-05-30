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

# This file is just a script, allow [a-z0-9]* variable names
# pylint: disable-msg=C0103

# ``import radicale`` refers to the ``radicale`` module, not ``radicale.py`` 
# pylint: disable-msg=W0406

"""
Radicale Server entry point.

Launch the Radicale Serve according to configuration and command-line
arguments.

"""

# TODO: Manage smart and configurable logs

import os
import sys
import optparse

import radicale

# Get command-line options
parser = optparse.OptionParser()
parser.add_option(
    "-v", "--version", action="store_true",
    default=False,
    help="show version and exit")
parser.add_option(
    "-d", "--daemon", action="store_true",
    default=radicale.config.getboolean("server", "daemon"),
    help="launch as daemon")
parser.add_option(
    "-H", "--host",
    default=radicale.config.get("server", "host"),
    help="set server hostname")
parser.add_option(
    "-p", "--port", type="int",
    default=radicale.config.getint("server", "port"),
    help="set server port")
parser.add_option(
    "-s", "--ssl", action="store_true",
    default=radicale.config.getboolean("server", "ssl"),
    help="use SSL connection")
parser.add_option(
    "-k", "--key",
    default=radicale.config.get("server", "key"),
    help="private key file ")
parser.add_option(
    "-c", "--certificate",
    default=radicale.config.get("server", "certificate"),
    help="certificate file ")
options = parser.parse_args()[0]

# Update Radicale configuration according to options
for option in parser.option_list:
    key = option.dest
    if key:
        value = getattr(options, key)
        radicale.config.set("server", key, value)

# Print version and exit if the option is given
if options.version:
    print(radicale.VERSION)
    sys.exit()

# Fork if Radicale is launched as daemon
if options.daemon:
    if os.fork():
        sys.exit()
    sys.stdout = sys.stderr = open(os.devnull, "w")

# Launch calendar server
server_class = radicale.HTTPSServer if options.ssl else radicale.HTTPServer
server = server_class(
    (options.host, options.port), radicale.CalendarHTTPHandler)
server.serve_forever()
