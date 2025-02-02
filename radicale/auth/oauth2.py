# This file is part of Radicale Server - Calendar Server
#
# Original from https://gitlab.mim-libre.fr/alphabet/radicale_oauth/
# Copyright © 2021-2022 Bruno Boiget
# Copyright © 2022-2022 Daniel Dehennin
#
# Since migration into upstream
# Copyright © 2025-2025 Peter Bieringer <pb@bieringer.de>
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
Authentication backend that checks credentials against an oauth2 server auth endpoint
"""

import requests

from radicale import auth
from radicale.log import logger


class Auth(auth.BaseAuth):
    def __init__(self, configuration):
        super().__init__(configuration)
        self._endpoint = configuration.get("auth", "oauth2_token_endpoint")
        if not self._endpoint:
            logger.error("auth.oauth2_token_endpoint URL missing")
            raise RuntimeError("OAuth2 token endpoint URL is required")
        logger.info("auth OAuth2 token endpoint: %s" % (self._endpoint))

    def _login(self, login, password):
        """Validate credentials.
        Sends login credentials to oauth token endpoint and checks that a token is returned
        """
        try:
            # authenticate to authentication endpoint and return login if ok, else ""
            req_params = {
                "username": login,
                "password": password,
                "grant_type": "password",
                "client_id": "radicale",
            }
            req_headers = {"Content-Type": "application/x-www-form-urlencoded"}
            response = requests.post(
                self._endpoint, data=req_params, headers=req_headers
            )
            if (
                response.status_code == requests.codes.ok
                and "access_token" in response.json()
            ):
                return login
        except OSError as e:
            logger.critical("Failed to authenticate against OAuth2 server %s: %s" % (self._endpoint, e))
        logger.warning("User failed to authenticate using OAuth2: %r" % login)
        return ""
