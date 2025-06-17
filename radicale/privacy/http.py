"""
HTTP API endpoints for privacy management in Radicale.

This module provides HTTP API endpoints for managing user privacy settings and card processing.
"""

import base64
import json
import logging
from http import client
from typing import Any, Dict, List, Optional, Union

from radicale import config, httputils, types
from radicale.app.base import ApplicationBase
from radicale.auth.otp_twilio import Auth as OTPAuth
from radicale.privacy.core import PrivacyCore

logger = logging.getLogger(__name__)

# Define the possible result types
SettingsResult = Union[Dict[str, bool], Dict[str, str]]
CardsResult = Dict[str, List[Dict[str, Any]]]
StatusResult = Dict[str, Union[str, int, List[str]]]
APIResult = Union[SettingsResult, CardsResult, StatusResult, str]


class PrivacyHTTP(ApplicationBase):
    """HTTP endpoints for privacy management."""

    # Universal CORS headers
    CORS_HEADERS = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
        "Access-Control-Allow-Headers": "*",
        "Access-Control-Expose-Headers": "Authorization",
        "Access-Control-Max-Age": "86400",
    }

    def __init__(self, configuration: "config.Configuration") -> None:
        """Initialize the privacy HTTP endpoints.

        Args:
            configuration: The Radicale configuration object
        """
        super().__init__(configuration)
        self._privacy_core = PrivacyCore(configuration)
        self._otp_auth = OTPAuth(configuration)

    def _get_authenticated_user(self, environ) -> tuple[Optional[str], Optional[str]]:
        """Get authenticated user and JWT token if applicable.

        Returns:
            Tuple of (user, jwt_token) where jwt_token is only set on successful OTP verification
        """
        auth_header = environ.get("HTTP_AUTHORIZATION", "")

        # Check for Bearer JWT token first
        if auth_header.startswith("Bearer "):
            jwt_token = auth_header.split(" ", 1)[1]
            user = self._otp_auth._validate_jwt(jwt_token)
            return user, None  # No new JWT needed

        # Check for Basic Auth (OTP verification)
        elif auth_header.startswith("Basic "):
            try:
                credentials = base64.b64decode(auth_header.split(" ", 1)[1]).decode()
                login, password = credentials.split(":", 1)

                # Use login_with_session to get both user and JWT
                user, jwt_token = self._otp_auth.login_with_session(login, password)
                return user, jwt_token
            except Exception as e:
                logger.error("Authentication error: %s", e)
                return None, None

        return None, None

    def _add_cors_headers(self, headers: dict) -> dict:
        """Merge CORS headers into the response headers."""
        merged = dict(headers)
        merged.update(self.CORS_HEADERS)
        return merged

    def _to_wsgi_response(self, success: bool, result: APIResult, jwt_token: Optional[str] = None) -> types.WSGIResponse:
        """Convert API response to WSGI response, always adding CORS headers.

        Args:
            success: Whether the API call was successful
            result: The API response data
            jwt_token: JWT token to include in Authorization header if provided

        Returns:
            WSGI response tuple (status, headers, body)
        """
        headers = {"Content-Type": "application/json"}
        headers = self._add_cors_headers(headers)

        # Add JWT token to Authorization header if provided
        if jwt_token:
            headers["Authorization"] = f"Bearer {jwt_token}"
            logger.info("Adding JWT token to response headers: %s", jwt_token[:20] + "..." if len(jwt_token) > 20 else jwt_token)
        else:
            logger.info("No JWT token to add to response headers")

        if isinstance(result, str):
            # Error message
            return client.BAD_REQUEST, headers, json.dumps({"error": result})
        return client.OK, headers, json.dumps(result)

    def do_GET(self, environ: types.WSGIEnviron, base_prefix: str, path: str,
               user: str) -> types.WSGIResponse:
        """Handle GET requests for privacy endpoints.

        Args:
            environ: The WSGI environment
            base_prefix: The base URL prefix
            path: The request path
            user: The authenticated user (from main app, may be empty for JWT auth)

        Returns:
            WSGI response
        """
        # Check authentication and get JWT token if this is OTP verification
        authenticated_user, jwt_token = self._get_authenticated_user(environ)
        logger.info("do_GET: authenticated_user=%s, jwt_token=%s", authenticated_user, jwt_token is not None)

        if not authenticated_user:
            # No authentication - return 401 (main app will handle OTP sending)
            return httputils.FORBIDDEN[0], self._add_cors_headers(dict(httputils.FORBIDDEN[1])), httputils.FORBIDDEN[2]

        # For JWT authentication, the main app user parameter may be empty, so we skip this check
        # For Basic auth, we still want to verify consistency
        if user and authenticated_user != user:
            logger.warning("User mismatch: authenticated_user=%s, main_app_user=%s", authenticated_user, user)
            return httputils.FORBIDDEN[0], self._add_cors_headers(dict(httputils.FORBIDDEN[1])), httputils.FORBIDDEN[2]

        # Extract user identifier from path
        # Path format: /privacy/settings/{user} or /privacy/cards/{user}
        parts = path.strip("/").split("/")
        if len(parts) < 3:
            return httputils.BAD_REQUEST[0], self._add_cors_headers(dict(httputils.BAD_REQUEST[1])), httputils.BAD_REQUEST[2]

        resource_type = parts[1]  # 'settings' or 'cards'
        user_identifier = parts[2]

        success: bool
        result: APIResult

        if resource_type == "settings":
            success, result = self._privacy_core.get_settings(user_identifier)
        elif resource_type == "cards":
            success, result = self._privacy_core.get_matching_cards(user_identifier)
        else:
            return httputils.BAD_REQUEST[0], self._add_cors_headers(dict(httputils.BAD_REQUEST[1])), httputils.BAD_REQUEST[2]

        # Pass JWT token to response if this was OTP verification
        return self._to_wsgi_response(success, result, jwt_token)

    def do_POST(self, environ: types.WSGIEnviron, base_prefix: str, path: str,
                user: str) -> types.WSGIResponse:
        """Handle POST requests for privacy endpoints.

        Args:
            environ: The WSGI environment
            base_prefix: The base URL prefix
            path: The request path
            user: The authenticated user (from main app, may be empty for JWT auth)

        Returns:
            WSGI response
        """
        # Check if authenticated user matches the requested user
        authenticated_user, _ = self._get_authenticated_user(environ)
        if user and authenticated_user != user:
            return httputils.FORBIDDEN[0], self._add_cors_headers(dict(httputils.FORBIDDEN[1])), httputils.FORBIDDEN[2]

        # Extract user identifier and action from path
        parts = path.strip("/").split("/")
        if len(parts) < 3:
            return httputils.BAD_REQUEST[0], self._add_cors_headers(dict(httputils.BAD_REQUEST[1])), httputils.BAD_REQUEST[2]

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
            return httputils.BAD_REQUEST[0], self._add_cors_headers(dict(httputils.BAD_REQUEST[1])), httputils.BAD_REQUEST[2]

        success: bool
        result: APIResult

        if resource_type == "settings":
            success, result = self._privacy_core.create_settings(user_identifier, data)
            if success:
                return client.CREATED, self._add_cors_headers({"Content-Type": "application/json"}), json.dumps(result)
        elif resource_type == "cards" and len(parts) > 3 and parts[3] == "reprocess":
            success, result = self._privacy_core.reprocess_cards(user_identifier)
        else:
            return httputils.BAD_REQUEST[0], self._add_cors_headers(dict(httputils.BAD_REQUEST[1])), httputils.BAD_REQUEST[2]

        return self._to_wsgi_response(success, result)

    def do_PUT(self, environ: types.WSGIEnviron, base_prefix: str, path: str,
               user: str) -> types.WSGIResponse:
        """Handle PUT requests for privacy endpoints.

        Args:
            environ: The WSGI environment
            base_prefix: The base URL prefix
            path: The request path
            user: The authenticated user (from main app, may be empty for JWT auth)

        Returns:
            WSGI response
        """
        # Check if authenticated user matches the requested user
        authenticated_user, _ = self._get_authenticated_user(environ)
        if user and authenticated_user != user:
            return httputils.FORBIDDEN[0], self._add_cors_headers(dict(httputils.FORBIDDEN[1])), httputils.FORBIDDEN[2]

        # Extract user identifier from path
        parts = path.strip("/").split("/")
        if len(parts) != 3 or parts[1] != "settings":
            return httputils.BAD_REQUEST[0], self._add_cors_headers(dict(httputils.BAD_REQUEST[1])), httputils.BAD_REQUEST[2]

        user_identifier = parts[2]

        # Read request body
        try:
            content_length = int(environ.get("CONTENT_LENGTH", 0))
            if content_length > 0:
                body = environ["wsgi.input"].read(content_length)
                data = json.loads(body)
            else:
                return httputils.BAD_REQUEST[0], self._add_cors_headers(dict(httputils.BAD_REQUEST[1])), httputils.BAD_REQUEST[2]
        except (ValueError, json.JSONDecodeError):
            return httputils.BAD_REQUEST[0], self._add_cors_headers(dict(httputils.BAD_REQUEST[1])), httputils.BAD_REQUEST[2]

        success: bool
        result: APIResult
        success, result = self._privacy_core.update_settings(user_identifier, data)
        return self._to_wsgi_response(success, result)

    def do_DELETE(self, environ: types.WSGIEnviron, base_prefix: str, path: str,
                  user: str) -> types.WSGIResponse:
        """Handle DELETE requests for privacy endpoints.

        Args:
            environ: The WSGI environment
            base_prefix: The base URL prefix
            path: The request path
            user: The authenticated user (from main app, may be empty for JWT auth)

        Returns:
            WSGI response
        """
        # Check if authenticated user matches the requested user
        authenticated_user, _ = self._get_authenticated_user(environ)
        if user and authenticated_user != user:
            return httputils.FORBIDDEN[0], self._add_cors_headers(dict(httputils.FORBIDDEN[1])), httputils.FORBIDDEN[2]

        # Extract user identifier from path
        parts = path.strip("/").split("/")
        if len(parts) != 3 or parts[1] != "settings":
            return httputils.BAD_REQUEST[0], self._add_cors_headers(dict(httputils.BAD_REQUEST[1])), httputils.BAD_REQUEST[2]

        user_identifier = parts[2]

        success: bool
        result: APIResult
        success, result = self._privacy_core.delete_settings(user_identifier)
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
        headers = self._add_cors_headers({})
        return client.OK, headers, b""
