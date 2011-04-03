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
Radicale CalDAV Server.

Launch the server according to configuration and command-line options.

"""

# TODO: Manage smart and configurable logs

import os
import sys
import optparse
import signal
import threading

import radicale

# Get command-line options
parser = optparse.OptionParser(version=radicale.VERSION)
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
    help="set server hostnames and ports")
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
    help="set private key file")
parser.add_option(
    "-c", "--certificate",
    default=radicale.config.get("server", "certificate"),
    help="set certificate file")
options = parser.parse_args()[0]

# Update Radicale configuration according to options
for option in parser.option_list:
    key = option.dest
    if key:
        value = getattr(options, key)
        radicale.config.set("server", key, value)

# Fork if Radicale is launched as daemon
if options.daemon:
    if os.fork():
        sys.exit()
    sys.stdout = sys.stderr = open(os.devnull, "w")

# Create calendar servers
servers = []
server_class = radicale.HTTPSServer if options.ssl else radicale.HTTPServer

for host in options.hosts.split(','):
    address, port = host.strip().rsplit(':', 1)
    address, port = address.strip('[] '), int(port)

    servers.append(server_class((address, port), radicale.CalendarHTTPHandler))

# this event marks that the program should be shut down
server_exited = threading.Event()

# SIGTERM and SIGINT (aka KeyboardInterrupt) should just mark this for shutdown
signal.signal(signal.SIGTERM, lambda *_: server_exited.set())
signal.signal(signal.SIGINT, lambda *_: server_exited.set())

def serve_forever(server):
    """Serve a server forever, and mark the process for shut down if things go wrong."""
    try:
        server.serve_forever()
    finally:
        server_exited.set()

# start the servers in a different loop to avoid possible race-conditions,
# when a server exists but another server is added to the list at the same time
for server in servers:
    threading.Thread(target=serve_forever, args=(server,)).start()

# mainloop: wait until all servers are exited
# we must do the busy-waiting here, as all ".join()"-calls
# completly block the thread, such that signals are not received
try:
    while True:
        # the number is irrelevant -- the only thing that matters, is that it is
        # larger than 0.05
        # this is due to python implementing its own busy-waiting logic
        server_exited.wait(10.0)
        if server_exited.is_set():
            break
finally:
    #
    # Cleanly shutdown server
    #

    # ignore signals, s.t. they cannot interfere
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    signal.signal(signal.SIGTERM, signal.SIG_IGN)

    for server in servers:             
        server.shutdown()
