"""
HTTP API endpoints for privacy management in Radicale.

This module provides HTTP API endpoints for managing user privacy settings and card processing.
Uses Werkzeug's routing system for sophisticated URL handling.
"""

import os
import json
import logging
from http import client
from typing import Any, Dict, List, Union

from werkzeug.routing import Map, Rule
from werkzeug.exceptions import NotFound, MethodNotAllowed
from werkzeug.wrappers import Request

from radicale import httputils, types
from radicale.privacy.core import PrivacyCore

logger = logging.getLogger(__name__)

# Define the possible result types
SettingsResult = Union[Dict[str, bool], Dict[str, str]]
CardsResult = Dict[str, List[Dict[str, Any]]]
StatusResult = Dict[str, Union[str, int, List[str]]]
APIResult = Union[SettingsResult, CardsResult, StatusResult, str]


class PrivacyHTTP:
    """HTTP endpoints for privacy management using Werkzeug routing."""

    def __init__(self, configuration) -> None:
        """Initialize the privacy HTTP endpoints.

        Args:
            configuration: The Radicale configuration object
        """
        self.configuration = configuration
        self._privacy_core = PrivacyCore(configuration)
        
        # Define URL rules for all supported routes
        self.url_map = Map([
            Rule('/privacy/settings/<user>', endpoint='get_settings', methods=['GET']),
            Rule('/privacy/cards/<user>', endpoint='get_cards', methods=['GET']),
            Rule('/privacy/settings/<user>', endpoint='create_settings', methods=['POST']),
            Rule('/privacy/cards/<user>/reprocess', endpoint='reprocess_cards', methods=['POST']),
            Rule('/privacy/settings/<user>', endpoint='update_settings', methods=['PUT']),
            Rule('/privacy/settings/<user>', endpoint='delete_settings', methods=['DELETE']),
        ])

        # Map endpoints to handler methods
        self.endpoints = {
            "get_settings": self._handle_get_settings,
            "get_cards": self._handle_get_cards,
            "create_settings": self._handle_create_settings,
            "update_settings": self._handle_update_settings,
            "delete_settings": self._handle_delete_settings,
            "reprocess_cards": self._handle_reprocess_cards,
        }

    def _check_authentication(self, environ: types.WSGIEnviron) -> bool:
        """Check if the request is authenticated using token auth.

        Args:
            environ: WSGI environment

        Returns:
            True if authenticated, False otherwise
        """
        auth_header = environ.get("HTTP_AUTHORIZATION")
        if not auth_header or not auth_header.startswith("Bearer "):
            logger.info("Authentication failed: No Bearer token in Authorization header")
            return False

        token = auth_header[len("Bearer "):].strip()
        expected_token = os.environ.get("RADICALE_TOKEN")
        if not expected_token:
            logger.warning("RADICALE_TOKEN environment variable not set")
            return False

        if token == expected_token:
            logger.info("Authentication successful")
            return True
        else:
            logger.info("Authentication failed: Invalid token")
            return False

    def _dispatch_request(
        self, method: str, path: str, environ: types.WSGIEnviron
    ) -> types.WSGIResponse:
        """Dispatch request using Werkzeug router.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            path: Request path
            environ: WSGI environment

        Returns:
            WSGI response tuple
        """
        # Check authentication first
        if not self._check_authentication(environ):
            logger.warning("Unauthorized access attempt to privacy endpoint: %s %s", method, path)
            return (
                client.UNAUTHORIZED,
                {"Content-Type": "application/json", "WWW-Authenticate": "Bearer"},
                json.dumps({"error": "Unauthorized. Bearer token required."}).encode(),
            )

        adapter = self.url_map.bind("")
        try:
            endpoint, url_params = adapter.match(path, method)
            handler = self.endpoints[endpoint]
            logger.debug(
                "Routing %s %s to endpoint %s with params %s",
                method,
                path,
                endpoint,
                url_params,
            )
            return handler(environ, url_params)
        except NotFound:
            logger.warning("Route not found: %s %s", method, path)
            return (
                httputils.NOT_FOUND[0],
                {"Content-Type": "application/json"},
                json.dumps({"error": "Route not found"}).encode(),
            )
        except MethodNotAllowed:
            logger.warning("Method not allowed: %s %s", method, path)
            return (
                httputils.METHOD_NOT_ALLOWED[0],
                {"Content-Type": "application/json"},
                json.dumps({"error": "Method not allowed"}).encode(),
            )

    def _get_request_json(
        self, environ: types.WSGIEnviron
    ) -> Union[Dict[str, Any], types.WSGIResponse]:
        """Get JSON data from request body using Werkzeug.

        Args:
            environ: WSGI environment

        Returns:
            Either the parsed JSON data or an error response tuple
        """
        request = Request(environ)
        try:
            json_data = request.get_json()
            if json_data is None:
                return (
                    httputils.BAD_REQUEST[0],
                    {"Content-Type": "application/json"},
                    json.dumps({"error": "Missing or invalid JSON body"}).encode(),
                )
            return json_data
        except Exception as e:
            logger.error("Error parsing JSON request body: %s", e)
            return (
                httputils.BAD_REQUEST[0],
                {"Content-Type": "application/json"},
                json.dumps({"error": "Invalid JSON"}).encode(),
            )

    def _to_wsgi_response(self, success: bool, result: APIResult) -> types.WSGIResponse:
        """Convert API response to WSGI response.

        Args:
            success: Whether the API call was successful
            result: The API response data

        Returns:
            WSGI response tuple (status, headers, body)
        """
        headers = {"Content-Type": "application/json"}

        if not success or isinstance(result, str):
            # Error message - either explicit failure or string result indicates error
            return client.BAD_REQUEST, headers, json.dumps({"error": result}).encode()
        return client.OK, headers, json.dumps(result).encode()

    # Route handler methods
    def _handle_get_settings(
        self, environ: types.WSGIEnviron, url_params: Dict[str, str]
    ) -> types.WSGIResponse:
        """Handle GET /privacy/settings/<user>"""
        user_identifier = url_params["user"]
        logger.info("GET settings for user: %s", user_identifier)

        success, result = self._privacy_core.get_settings(user_identifier)
        return self._to_wsgi_response(success, result)

    def _handle_get_cards(
        self, environ: types.WSGIEnviron, url_params: Dict[str, str]
    ) -> types.WSGIResponse:
        """Handle GET /privacy/cards/<user>"""
        user_identifier = url_params["user"]
        logger.info("GET cards for user: %s", user_identifier)

        success, result = self._privacy_core.get_matching_cards(user_identifier)
        return self._to_wsgi_response(success, result)

    def _handle_create_settings(
        self, environ: types.WSGIEnviron, url_params: Dict[str, str]
    ) -> types.WSGIResponse:
        """Handle POST /privacy/settings/<user>"""
        user_identifier = url_params["user"]
        logger.info("CREATE settings for user: %s", user_identifier)

        # Get JSON data using Werkzeug
        data = self._get_request_json(environ)
        if isinstance(data, tuple):  # Error response
            return data

        success, result = self._privacy_core.create_settings(user_identifier, data)
        if success:
            return (
                client.CREATED,
                {"Content-Type": "application/json"},
                json.dumps(result).encode(),
            )

        return self._to_wsgi_response(success, result)

    def _handle_update_settings(
        self, environ: types.WSGIEnviron, url_params: Dict[str, str]
    ) -> types.WSGIResponse:
        """Handle PUT /privacy/settings/<user>"""
        user_identifier = url_params["user"]
        logger.info("UPDATE settings for user: %s", user_identifier)

        # Get JSON data using Werkzeug
        data = self._get_request_json(environ)
        if isinstance(data, tuple):  # Error response
            return data

        success, result = self._privacy_core.update_settings(user_identifier, data)
        return self._to_wsgi_response(success, result)

    def _handle_delete_settings(
        self, environ: types.WSGIEnviron, url_params: Dict[str, str]
    ) -> types.WSGIResponse:
        """Handle DELETE /privacy/settings/<user>"""
        user_identifier = url_params["user"]
        logger.info("DELETE settings for user: %s", user_identifier)

        success, result = self._privacy_core.delete_settings(user_identifier)
        return self._to_wsgi_response(success, result)

    def _handle_reprocess_cards(
        self, environ: types.WSGIEnviron, url_params: Dict[str, str]
    ) -> types.WSGIResponse:
        """Handle POST /privacy/cards/<user>/reprocess"""
        user_identifier = url_params["user"]
        logger.info("REPROCESS cards for user: %s", user_identifier)

        # No body required for reprocess
        success, result = self._privacy_core.reprocess_cards(user_identifier)
        return self._to_wsgi_response(success, result)

    # HTTP method handlers that integrate with the existing structure
    def do_GET(self, environ: types.WSGIEnviron, path: str) -> types.WSGIResponse:
        """Handle GET requests for privacy endpoints."""
        return self._dispatch_request("GET", path, environ)

    def do_POST(self, environ: types.WSGIEnviron, path: str) -> types.WSGIResponse:
        """Handle POST requests for privacy endpoints."""
        return self._dispatch_request("POST", path, environ)

    def do_PUT(self, environ: types.WSGIEnviron, path: str) -> types.WSGIResponse:
        """Handle PUT requests for privacy endpoints."""
        return self._dispatch_request("PUT", path, environ)

    def do_DELETE(self, environ: types.WSGIEnviron, path: str) -> types.WSGIResponse:
        """Handle DELETE requests for privacy endpoints."""
        return self._dispatch_request("DELETE", path, environ)
