# -*- coding: utf-8 -*-
#
# This file is part of Radicale Server - Calendar Server
# Copyright © 2012 Ehsanul Hoque
# Copyright © 2013 Guillaume Ayoub
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
HTTP authentication.

Authentication based on the ``requests`` module.

Post a request to an authentication server with the username/password.
Anything other than a 200/201 response is considered auth failure.

"""

import requests

from .. import config, log

AUTH_URL = config.get("auth", "http_url")
USER_PARAM = config.get("auth", "http_user_parameter")
PASSWORD_PARAM = config.get("auth", "http_password_parameter")


def is_authenticated(user, password):
    """Check if ``user``/``password`` couple is valid."""
    log.LOGGER.debug("HTTP-based auth on %s." % AUTH_URL)
    payload = {USER_PARAM: user, PASSWORD_PARAM: password}
    return requests.post(AUTH_URL, data=payload).status_code in (200, 201)
