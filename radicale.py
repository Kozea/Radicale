#!/usr/bin/python
# -*- coding: utf-8; indent-tabs-mode: nil; -*-
#
# This file is part of Radicale Server - Calendar Server
# Copyright © 2008 The Radicale Team
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

# TODO: remove this hack
import sys
sys.path.append("/usr/local/lib/python2.5/site-packages")

from OpenSSL import SSL
from twisted.web import server
from twisted.internet import reactor
from twisted.python import log

import radicale

class ServerContextFactory(object):
    """
    SSL context factory
    """
    def getContext(self):
        """
        Get SSL context for the HTTP server
        """
        ctx = SSL.Context(SSL.SSLv23_METHOD)
        ctx.use_certificate_file(radicale.config.get("server", "certificate"))
        ctx.use_privatekey_file(radicale.config.get("server", "privatekey"))
        return ctx

log.startLogging(sys.stdout)
#log.startLogging(open(radicale.config.get("server", "log"), "w"))
factory = server.Site(radicale.HttpResource())
reactor.listenSSL(radicale.config.getint("server", "port"), factory, ServerContextFactory())
reactor.run()
