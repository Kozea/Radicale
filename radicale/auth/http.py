# -*- coding: utf-8 -*-
#
# This file is part of Radicale Server - Calendar Server
# Copyright © 2011 Corentin Le Bail
# Copyright © 2011-2012 Guillaume Ayoub
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

Make a request to an authentication server with the username/password.
Anything other than a 200/201 response is considered auth failure.

"""

import requests
from .. import config, log

AUTH_URL = config.get("auth", "auth_url")
USER_PARAM = config.get("auth", "user_param")
PASSWORD_PARAM = config.get("auth", "password_param")

def is_authenticated(user, password):
  payload = {USER_PARAM: user, PASSWORD_PARAM: password}
  r = requests.post(AUTH_URL, data=payload)
  return r.status_code in [200, 201]
