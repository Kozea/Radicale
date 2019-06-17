# This file is part of Radicale Server - Calendar Server
# Copyright © 2012-2017 Guillaume Ayoub
# Copyright © 2017-2018 Unrud <unrud@outlook.com>
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
Tests for Radicale.

"""

import logging
import os
import sys
from io import BytesIO

from pytest_cov import embed

import radicale
from radicale import server

# Measure coverage of forked processes
finish_request = server.ParallelHTTPServer.finish_request
pid = os.getpid()


def finish_request_cov(self, request, client_address):
    cov = None
    if pid != os.getpid():
        cov = embed.init()
    try:
        return finish_request(self, request, client_address)
    finally:
        if cov:
            embed.cleanup(cov)


server.ParallelHTTPServer.finish_request = finish_request_cov

# Allow importing of tests.custom....
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
# Enable debug output
radicale.log.logger.setLevel(logging.DEBUG)


class BaseTest:
    """Base class for tests."""

    def request(self, method, path, data=None, **args):
        """Send a request."""
        self.application._status = None
        self.application._headers = None
        self.application._answer = None

        for key in args:
            args[key.upper()] = args[key]
        args["REQUEST_METHOD"] = method.upper()
        args["PATH_INFO"] = path
        if data:
            data = data.encode("utf-8")
            args["wsgi.input"] = BytesIO(data)
            args["CONTENT_LENGTH"] = str(len(data))
        args["wsgi.errors"] = sys.stderr
        status = headers = None

        def start_response(status_, headers_):
            nonlocal status, headers
            status = status_
            headers = headers_
        answer = self.application(args, start_response)

        return (int(status.split()[0]), dict(headers),
                answer[0].decode("utf-8") if answer else None)
