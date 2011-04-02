#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of Radicale Server - Calendar Server
# Copyright © 2008-2011 Guillaume Ayoub
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

Launch the Radicale Server according to configuration and command-line
arguments.

"""

# TODO: Manage smart and configurable logs

import os
import sys
import optparse
import signal
import threading

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
    "-f", "--foreground", action="store_false", dest="daemon",
    help="launch in foreground (opposite of --daemon)")
parser.add_option(
    "-H", "--hosts",
    default=radicale.config.get("server", "hosts"),
    help="set server hostnames")
parser.add_option(
    "-s", "--ssl", action="store_true",
    default=radicale.config.getboolean("server", "ssl"),
    help="use SSL connection")
parser.add_option(
    "-S", "--no-ssl", action="store_false", dest="ssl",
    help="do not use SSL connection (opposite of --ssl)")
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

# Launch calendar servers
servers = []
server_class = radicale.HTTPSServer if options.ssl else radicale.HTTPServer

def exit():
    """Cleanly shutdown servers."""
    while servers:
        servers.pop().shutdown()

def serve_forever(server):
    """Serve a server forever with no traceback on keyboard interrupts."""
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        # No unwanted traceback
        pass
    finally:
        exit()

# Clean exit on SIGTERM
signal.signal(signal.SIGTERM, lambda *_: exit())

for host in options.hosts.split(','):
    address, port = host.strip().rsplit(':', 1)
    address, port = address.strip('[] '), int(port)
    servers.append(server_class((address, port), radicale.CalendarHTTPHandler))

for server in servers[:-1]:
    # More servers to come, launch a new thread
    threading.Thread(target=serve_forever, args=(server,)).start()

# Last server, no more thread
serve_forever(servers[-1])
