"""
HTTP API endpoints for privacy management in Radicale.

This module provides HTTP API endpoints for managing user privacy settings and card processing.
"""

import base64
import json
import logging
from http import client
from typing import Any, Dict, List, Optional, Union

from radicale import httputils, types
from radicale.auth.token import Auth as TokenAuth
from radicale.privacy.core import PrivacyCore

logger = logging.getLogger(__name__)

# Define the possible result types
SettingsResult = Union[Dict[str, bool], Dict[str, str]]
CardsResult = Dict[str, List[Dict[str, Any]]]
StatusResult = Dict[str, Union[str, int, List[str]]]
APIResult = Union[SettingsResult, CardsResult, StatusResult, str]


class PrivacyHTTP:
    """HTTP endpoints for privacy management."""

    def __init__(self, configuration) -> None:
        """Initialize the privacy HTTP endpoints.

        Args:
            configuration: The Radicale configuration object
        """
        self.configuration = configuration
        self._privacy_core = PrivacyCore(configuration)
        self._token_auth = TokenAuth(configuration)

    def _get_authenticated_user(self, environ) -> tuple[Optional[str], Optional[str]]:
        """Get authenticated user and JWT token if applicable.

        Returns:
            Tuple of (user, jwt_token) where jwt_token is only set on successful OTP verification
        """
        auth_header = environ.get("HTTP_AUTHORIZATION", "")

        # Check for Bearer JWT token first
        if auth_header.startswith("Bearer "):
            jwt_token = auth_header.split(" ", 1)[1]
            user = self._token_auth._validate_jwt(jwt_token)
            return user, None  # No new JWT needed

        # Check for Basic Auth (OTP verification)
        elif auth_header.startswith("Basic "):
            try:
                credentials = base64.b64decode(auth_header.split(" ", 1)[1]).decode()
                login, password = credentials.split(":", 1)

                # Use login_with_jwt to get both user and JWT
                user, jwt_token = self._token_auth.login_with_jwt(login, password)
                return user, jwt_token
            except Exception as e:
                logger.error("AUTH: Authentication error: %s", e)
                return None, None

        return None, None

    def _to_wsgi_response(self, success: bool, result: APIResult, jwt_token: Optional[str] = None) -> types.WSGIResponse:
        """Convert API response to WSGI response.

        Args:
            success: Whether the API call was successful
            result: The API response data
            jwt_token: JWT token to include in Authorization header if provided

        Returns:
            WSGI response tuple (status, headers, body)
        """
        headers = {"Content-Type": "application/json"}

        # Add JWT token to Authorization header if provided
        if jwt_token:
            headers["Authorization"] = f"Bearer {jwt_token}"
            logger.info("AUTH: Added JWT token to response headers")

        if isinstance(result, str):
            # Error message
            return client.BAD_REQUEST, headers, json.dumps({"error": result}).encode()
        return client.OK, headers, json.dumps(result).encode()

    def do_GET(self, environ: types.WSGIEnviron, base_prefix: str, path: str,
               user: str, jwt_token: Optional[str] = None) -> types.WSGIResponse:
        """Handle GET requests for privacy endpoints.

        Args:
            environ: The WSGI environment
            base_prefix: The base URL prefix
            path: The request path
            user: The authenticated user (from main app, may be empty for JWT auth)
            jwt_token: JWT token from main authentication (optional)

        Returns:
            WSGI response
        """
        # If main authentication already succeeded, trust that result
        if user:
            authenticated_user: Optional[str] = user
            logger.info("AUTH: Using main auth result - user=%s", authenticated_user)
        else:
            # Check if this is an OTP request (empty password) that was already handled by main app
            auth_header = environ.get("HTTP_AUTHORIZATION", "")
            if auth_header.startswith("Basic "):
                try:
                    credentials = base64.b64decode(auth_header.split(" ", 1)[1]).decode()
                    login, password = credentials.split(":", 1)

                    # If password is empty, this is an OTP request that was already handled by main app
                    # Don't try to authenticate again to avoid double OTP sending
                    if not password:
                        logger.info("AUTH: OTP request already handled by main app for %s", login)
                        return client.UNAUTHORIZED, {"Content-Type": "application/json"}, json.dumps({"error": "Authentication required"}).encode()
                except Exception as e:
                    logger.error("AUTH: Error parsing Basic auth: %s", e)

            # Check authentication and get JWT token if this is OTP verification
            # Only do this if we don't already have a user from main app
            auth_result = self._get_authenticated_user(environ)
            authenticated_user, jwt_token = auth_result
            logger.info("AUTH: Auth result - user=%s, token=%s", authenticated_user, jwt_token is not None)
            if not authenticated_user:
                # No authentication - return 401 (main app will handle OTP sending)
                return client.UNAUTHORIZED, {"Content-Type": "application/json"}, json.dumps({"error": "Authentication required"}).encode()

        # Extract user identifier from path
        # Path format: /privacy/settings/{user} or /privacy/cards/{user}
        parts = path.strip("/").split("/")
        if len(parts) < 3:
            return httputils.BAD_REQUEST[0], {"Content-Type": "application/json"}, json.dumps({"error": "Invalid request format"}).encode()

        resource_type = parts[1]  # 'settings' or 'cards'
        user_identifier = parts[2]

        # Only restrict access for 'settings' resource
        if resource_type == "settings" and authenticated_user != user_identifier:
            logger.warning("AUTH: Access denied - user %s attempted to access %s", authenticated_user, user_identifier)
            return httputils.FORBIDDEN[0], {"Content-Type": "application/json"}, json.dumps({"error": "Action on the requested resource refused."}).encode()

        success: bool
        result: APIResult

        if resource_type == "settings":
            success, result = self._privacy_core.get_settings(user_identifier)
        elif resource_type == "cards":
            success, result = self._privacy_core.get_matching_cards(user_identifier)
        else:
            return httputils.BAD_REQUEST[0], {"Content-Type": "application/json"}, json.dumps({"error": "Invalid resource type"}).encode()

        if not success:
            return httputils.BAD_REQUEST[0], {"Content-Type": "application/json"}, json.dumps({"error": result}).encode()

        # Pass JWT token to response if this was OTP verification
        return self._to_wsgi_response(success, result, jwt_token)

    def do_POST(self, environ: types.WSGIEnviron, base_prefix: str, path: str,
                user: str) -> types.WSGIResponse:
        """Handle POST requests for privacy endpoints.

        Args:
            environ: The WSGI environment
            base_prefix: The base URL prefix
            path: The request path
            user: The authenticated user (from main app)

        Returns:
            WSGI response
        """
        # POST requests should only use JWT Bearer token authentication
        # OTP authentication only happens with GET requests
        if not user:
            return client.UNAUTHORIZED, {"Content-Type": "application/json"}, json.dumps({"error": "Authentication required"}).encode()

        authenticated_user = user
        logger.info("AUTH: POST request - user=%s", authenticated_user)

        # Extract user identifier and action from path
        parts = path.strip("/").split("/")
        if len(parts) < 3:
            return httputils.BAD_REQUEST[0], {"Content-Type": "application/json"}, json.dumps({"error": "Invalid request format"}).encode()

        resource_type = parts[1]  # 'settings' or 'cards'
        user_identifier = parts[2]

        # Only restrict access for 'settings' resource
        if resource_type == "settings" and authenticated_user != user_identifier:
            logger.warning("AUTH: Access denied - user %s attempted to access %s", authenticated_user, user_identifier)
            return httputils.FORBIDDEN[0], {"Content-Type": "application/json"}, json.dumps({"error": "Action on the requested resource refused."}).encode()

        success: bool
        result: APIResult

        if resource_type == "settings":
            # Read request body
            try:
                content_length = int(environ.get("CONTENT_LENGTH", 0))
                if content_length > 0:
                    body = environ["wsgi.input"].read(content_length)
                    data = json.loads(body)
                else:
                    return httputils.BAD_REQUEST[0], {"Content-Type": "application/json"}, json.dumps({"error": "Missing content length"}).encode()
            except (ValueError, json.JSONDecodeError):
                return httputils.BAD_REQUEST[0], {"Content-Type": "application/json"}, json.dumps({"error": "Invalid JSON"}).encode()

            success, result = self._privacy_core.create_settings(user_identifier, data)
            if success:
                return client.CREATED, {"Content-Type": "application/json"}, json.dumps(result).encode()
        elif resource_type == "cards" and len(parts) > 3 and parts[3] == "reprocess":
            # No body required for reprocess
            success, result = self._privacy_core.reprocess_cards(user_identifier)
        else:
            return httputils.BAD_REQUEST[0], {"Content-Type": "application/json"}, json.dumps({"error": "Invalid request format"}).encode()

        return self._to_wsgi_response(success, result, None)  # No JWT token for POST requests

    def do_PUT(self, environ: types.WSGIEnviron, base_prefix: str, path: str,
               user: str) -> types.WSGIResponse:
        """Handle PUT requests for privacy endpoints.

        Args:
            environ: The WSGI environment
            base_prefix: The base URL prefix
            path: The request path
            user: The authenticated user (from main app)

        Returns:
            WSGI response
        """
        # PUT requests should only use JWT Bearer token authentication
        # OTP authentication only happens with GET requests
        if not user:
            return client.UNAUTHORIZED, {"Content-Type": "application/json"}, json.dumps({"error": "Authentication required"}).encode()

        authenticated_user = user
        logger.info("AUTH: PUT request - user=%s", authenticated_user)

        # Extract user identifier from path
        parts = path.strip("/").split("/")
        if len(parts) != 3 or parts[1] != "settings":
            return httputils.BAD_REQUEST[0], dict(httputils.BAD_REQUEST[1]), httputils.BAD_REQUEST[2]

        resource_type = parts[1]  # 'settings' or 'cards'
        user_identifier = parts[2]

        # Only restrict access for 'settings' resource
        if resource_type == "settings" and authenticated_user != user_identifier:
            logger.warning("AUTH: Access denied - user %s attempted to access %s", authenticated_user, user_identifier)
            return httputils.FORBIDDEN[0], {"Content-Type": "application/json"}, json.dumps({"error": "Action on the requested resource refused."}).encode()

        # Read request body
        try:
            content_length = int(environ.get("CONTENT_LENGTH", 0))
            if content_length > 0:
                body = environ["wsgi.input"].read(content_length)
                data = json.loads(body)
            else:
                return httputils.BAD_REQUEST[0], dict(httputils.BAD_REQUEST[1]), httputils.BAD_REQUEST[2]
        except (ValueError, json.JSONDecodeError):
            return httputils.BAD_REQUEST[0], dict(httputils.BAD_REQUEST[1]), httputils.BAD_REQUEST[2]

        success: bool
        result: APIResult
        success, result = self._privacy_core.update_settings(user_identifier, data)
        return self._to_wsgi_response(success, result, None)  # No JWT token for PUT requests

    def do_DELETE(self, environ: types.WSGIEnviron, base_prefix: str, path: str,
                  user: str) -> types.WSGIResponse:
        """Handle DELETE requests for privacy endpoints.

        Args:
            environ: The WSGI environment
            base_prefix: The base URL prefix
            path: The request path
            user: The authenticated user (from main app)

        Returns:
            WSGI response
        """
        # DELETE requests should only use JWT Bearer token authentication
        # OTP authentication only happens with GET requests
        if not user:
            return client.UNAUTHORIZED, {"Content-Type": "application/json"}, json.dumps({"error": "Authentication required"}).encode()

        authenticated_user = user
        logger.info("AUTH: DELETE request - user=%s", authenticated_user)

        # Extract user identifier from path
        parts = path.strip("/").split("/")
        if len(parts) != 3 or parts[1] != "settings":
            return httputils.BAD_REQUEST[0], dict(httputils.BAD_REQUEST[1]), httputils.BAD_REQUEST[2]

        resource_type = parts[1]  # 'settings' or 'cards'
        user_identifier = parts[2]

        # Only restrict access for 'settings' resource
        if resource_type == "settings" and authenticated_user != user_identifier:
            logger.warning("AUTH: Access denied - user %s attempted to access %s", authenticated_user, user_identifier)
            return httputils.FORBIDDEN[0], {"Content-Type": "application/json"}, json.dumps({"error": "Action on the requested resource refused."}).encode()

        success: bool
        result: APIResult
        success, result = self._privacy_core.delete_settings(user_identifier)
        return self._to_wsgi_response(success, result, None)  # No JWT token for DELETE requests
