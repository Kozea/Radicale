# -*- coding: utf-8 -*-
#
# This file is part of Radicale Server - Calendar Server
# Copyright © 2012-2013 Guillaume Ayoub
# Copyright © 2012-2013 Jean-Marc Martins
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
Radicale tests with simple requests and authentication.

"""

from nose import with_setup
from . import HtpasswdAuthSystem


class TestBaseAuthRequests(HtpasswdAuthSystem):
    """
    Tests basic requests with auth.

    ..note Only htpasswd works at the moment since
    it requires to spawn processes running servers for
    others auth methods (ldap).
    """

    @with_setup(HtpasswdAuthSystem.setup, HtpasswdAuthSystem.teardown)
    def test_root(self):
        """Tests a GET request at "/"."""
        status, headers, answer = self.request(
            "GET", "/", HTTP_AUTHORIZATION=self.userpass)
        assert status == 200
        assert "Radicale works!" in answer
