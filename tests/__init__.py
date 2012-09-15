# -*- coding: utf-8 -*-
#
# This file is part of Radicale Server - Calendar Server
# Copyright © 2012 Guillaume Ayoub
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

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import radicale


class BaseTest(object):
    """Base class for tests."""

    def setup(self):
        """Setup function for each test."""
        self.application = radicale.Application()

    def teardown(self):
        """Teardown function for each test."""

    def request(self, method, path, **args):
        """Send a request."""
        self.application._status = None
        self.application._headers = None
        self.application._answer = None

        for key in args:
            args[key.upper()] = args[key]
        args["REQUEST_METHOD"] = method.upper()
        args["PATH_INFO"] = path
        self.application._answer = self.application(args, self.start_response)

        return (
            int(self.application._status.split()[0]),
            dict(self.application._headers),
            self.application._answer[0].decode("utf-8"))

    def start_response(self, status, headers):
        """Put the response values into the current application."""
        self.application._status = status
        self.application._headers = headers
