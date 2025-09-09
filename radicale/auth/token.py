# This file is part of Radicale - CalDAV and CardDAV server
# Copyright © 2025 Radicale Contributors
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
Authentication backend that validates against a Bearer token from environment variables.

This module checks the Authorization header for a Bearer token and compares it 
against a token stored in an environment variable. This is intended for simple
password protection of routes without user-specific authentication.

Environment variables:
- RADICALE_TOKEN: The token to validate against (required)
"""

import os
import hmac
from typing import Tuple, Union

from radicale import auth, types
from radicale.log import logger


class Auth(auth.BaseAuth):
    
    def __init__(self, configuration):
        super().__init__(configuration)
        self._token = os.environ.get("RADICALE_TOKEN")
        
        if not self._token:
            logger.error("RADICALE_TOKEN environment variable not set")
            raise RuntimeError("Token authentication requires RADICALE_TOKEN environment variable")
        
        logger.info("auth token: (configured from environment)")

    def get_external_login(self, environ: types.WSGIEnviron) -> Union[
            Tuple[()], Tuple[str, str]]:
        """Extract and validate Bearer token from Authorization header."""
        
        # Get Authorization header
        auth_header = environ.get("HTTP_AUTHORIZATION", "")
        
        if not auth_header:
            logger.debug("No Authorization header found")
            return ()
        
        # Check if it's a Bearer token
        if not auth_header.startswith("Bearer "):
            logger.debug("Authorization header is not a Bearer token")
            return ()
        
        # Extract token
        provided_token = auth_header[7:]  # Remove "Bearer " prefix
        
        if not provided_token:
            logger.debug("Empty token in Authorization header")
            return ()
        
        # Validate token using constant-time comparison to prevent timing attacks
        if hmac.compare_digest(provided_token, self._token):
            logger.debug("Token authentication successful")
            return ("", "")
        else:
            logger.warning("Invalid token provided")
            return ()
