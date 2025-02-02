"""
Authentication backend that checks credentials against an oauth2 server auth endpoint
"""

from radicale import auth
from radicale.log import logger
import requests
from requests.utils import quote


class Auth(auth.BaseAuth):
    def __init__(self, configuration):
        super().__init__(configuration)
        self._endpoint = configuration.get("auth", "oauth2_token_endpoint")
        logger.warning("Using oauth2 token endpoint: %s" % (self._endpoint))

    def login(self, login, password):
        """Validate credentials.
        Sends login credentials to oauth auth endpoint and checks that a token is returned
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
            raise RuntimeError(
                "Failed to authenticate against oauth server %r: %s"
                % (self._endpoint, e)
            ) from e
        logger.warning("User %s failed to authenticate" % (str(login)))
        return ""
