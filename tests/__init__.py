# -*- coding: utf-8 -*-
#
# This file is part of Radicale Server - Calendar Server
# Copyright © 2012-2013 Guillaume Ayoub
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
from io import BytesIO

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

os.environ["RADICALE_CONFIG"] = os.path.join(os.path.dirname(
    os.path.dirname(__file__)), "config")

from .helpers import get_file_content


class BaseTest(object):
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
            if sys.version_info[0] >= 3:
                data = data.encode("utf-8")
            args["wsgi.input"] = BytesIO(data)
            args["CONTENT_LENGTH"] = str(len(data))
        self.application._answer = self.application(args, self.start_response)

        return (
            int(self.application._status.split()[0]),
            dict(self.application._headers),
            self.application._answer[0].decode("utf-8")
            if self.application._answer else None)

    def start_response(self, status, headers):
        """Put the response values into the current application."""
        self.application._status = status
        self.application._headers = headers
