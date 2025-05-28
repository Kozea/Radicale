"""
Privacy HTTP endpoints for Radicale.

This module provides HTTP endpoints for managing user privacy settings.
"""

import json
import logging
from http import client
from typing import Any, Dict, List, Union

from radicale import config, httputils, types
from radicale.app.base import ApplicationBase
from radicale.privacy.api import PrivacyAPI

logger = logging.getLogger(__name__)

# Define the possible result types
SettingsResult = Union[Dict[str, bool], Dict[str, str]]
CardsResult = Dict[str, List[Dict[str, Any]]]
StatusResult = Dict[str, Union[str, int, List[str]]]
APIResult = Union[SettingsResult, CardsResult, StatusResult, str]


class ApplicationPartPrivacy(ApplicationBase):
    """Privacy HTTP endpoints."""

    def __init__(self, configuration: "config.Configuration") -> None:
        """Initialize the privacy HTTP endpoints.

        Args:
            configuration: The Radicale configuration object
        """
        super().__init__(configuration)
        self._privacy_api = PrivacyAPI(configuration)

    def _to_wsgi_response(self, success: bool, result: APIResult) -> types.WSGIResponse:
        """Convert API response to WSGI response.

        Args:
            success: Whether the API call was successful
            result: The API response data. Can be:
                - A string (error message)
                - A dictionary with boolean values (settings)
                - A dictionary with list of dictionaries (matching cards)
                - A dictionary with mixed values (status messages)

        Returns:
            WSGI response tuple (status, headers, body)
        """
        headers: Dict[str, str] = {"Content-Type": "application/json"}
        if isinstance(result, str):
            # Error message
            return client.BAD_REQUEST, headers, json.dumps({"error": result}).encode()
        return client.OK, headers, json.dumps(result).encode()

    def do_GET(self, environ: types.WSGIEnviron, base_prefix: str, path: str,
               user: str) -> types.WSGIResponse:
        """Handle GET requests for privacy endpoints.

        Args:
            environ: The WSGI environment
            base_prefix: The base URL prefix
            path: The request path
            user: The authenticated user

        Returns:
            WSGI response
        """
        if not path.startswith("/.privacy/"):
            return httputils.METHOD_NOT_ALLOWED

        # Extract user identifier from path
        # Path format: /.privacy/settings/{user} or /.privacy/cards/{user}
        parts = path.strip("/").split("/")
        if len(parts) < 3:
            return httputils.BAD_REQUEST

        resource_type = parts[1]  # 'settings' or 'cards'
        user_identifier = parts[2]

        success: bool
        result: APIResult

        if resource_type == "settings":
            success, result = self._privacy_api.get_settings(user_identifier)
        elif resource_type == "cards":
            success, result = self._privacy_api.get_matching_cards(user_identifier)
        else:
            return httputils.BAD_REQUEST

        return self._to_wsgi_response(success, result)

    def do_POST(self, environ: types.WSGIEnviron, base_prefix: str, path: str,
                user: str) -> types.WSGIResponse:
        """Handle POST requests for privacy endpoints.

        Args:
            environ: The WSGI environment
            base_prefix: The base URL prefix
            path: The request path
            user: The authenticated user

        Returns:
            WSGI response
        """
        if not path.startswith("/.privacy/"):
            return httputils.METHOD_NOT_ALLOWED

        # Extract user identifier and action from path
        parts = path.strip("/").split("/")
        if len(parts) < 3:
            return httputils.BAD_REQUEST

        resource_type = parts[1]  # 'settings' or 'cards'
        user_identifier = parts[2]

        # Read request body
        try:
            content_length = int(environ.get("CONTENT_LENGTH", 0))
            if content_length > 0:
                body = environ["wsgi.input"].read(content_length)
                data = json.loads(body)
            else:
                data = {}
        except (ValueError, json.JSONDecodeError):
            return httputils.BAD_REQUEST

        success: bool
        result: APIResult

        if resource_type == "settings":
            success, result = self._privacy_api.create_settings(user_identifier, data)
            if success:
                return client.CREATED, {"Content-Type": "application/json"}, json.dumps(result).encode()
        elif resource_type == "cards" and len(parts) > 3 and parts[3] == "reprocess":
            success, result = self._privacy_api.reprocess_cards(user_identifier)
        else:
            return httputils.BAD_REQUEST

        return self._to_wsgi_response(success, result)

    def do_PUT(self, environ: types.WSGIEnviron, base_prefix: str, path: str,
               user: str) -> types.WSGIResponse:
        """Handle PUT requests for privacy endpoints.

        Args:
            environ: The WSGI environment
            base_prefix: The base URL prefix
            path: The request path
            user: The authenticated user

        Returns:
            WSGI response
        """
        if not path.startswith("/.privacy/"):
            return httputils.METHOD_NOT_ALLOWED

        # Extract user identifier from path
        parts = path.strip("/").split("/")
        if len(parts) != 3 or parts[1] != "settings":
            return httputils.BAD_REQUEST

        user_identifier = parts[2]

        # Read request body
        try:
            content_length = int(environ.get("CONTENT_LENGTH", 0))
            if content_length > 0:
                body = environ["wsgi.input"].read(content_length)
                data = json.loads(body)
            else:
                return httputils.BAD_REQUEST
        except (ValueError, json.JSONDecodeError):
            return httputils.BAD_REQUEST

        success: bool
        result: APIResult
        success, result = self._privacy_api.update_settings(user_identifier, data)
        return self._to_wsgi_response(success, result)

    def do_DELETE(self, environ: types.WSGIEnviron, base_prefix: str, path: str,
                  user: str) -> types.WSGIResponse:
        """Handle DELETE requests for privacy endpoints.

        Args:
            environ: The WSGI environment
            base_prefix: The base URL prefix
            path: The request path
            user: The authenticated user

        Returns:
            WSGI response
        """
        if not path.startswith("/.privacy/"):
            return httputils.METHOD_NOT_ALLOWED

        # Extract user identifier from path
        parts = path.strip("/").split("/")
        if len(parts) != 3 or parts[1] != "settings":
            return httputils.BAD_REQUEST

        user_identifier = parts[2]
        success: bool
        result: APIResult
        success, result = self._privacy_api.delete_settings(user_identifier)
        return self._to_wsgi_response(success, result)

    def do_OPTIONS(self, environ: types.WSGIEnviron, base_prefix: str, path: str,
                   user: str) -> types.WSGIResponse:
        """Handle OPTIONS requests for CORS preflight.

        Args:
            environ: The WSGI environment
            base_prefix: The base URL prefix
            path: The request path
            user: The authenticated user

        Returns:
            WSGI response with CORS headers
        """
        if not path.startswith("/.privacy/"):
            return httputils.METHOD_NOT_ALLOWED

        headers: Dict[str, str] = {
            "Allow": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
            "Access-Control-Max-Age": "86400",  # 24 hours
        }
        return client.OK, headers, b""
