"""
Privacy API endpoints for Radicale.

This module provides RESTful endpoints for managing user privacy settings.
"""

import json
from http import client
from typing import Dict

from radicale import config, httputils, types
from radicale.privacy.database import PrivacyDatabase


class PrivacyAPI:
    """Privacy API endpoints."""

    def __init__(self, configuration: "config.Configuration") -> None:
        """Initialize the privacy API.

        Args:
            configuration: The Radicale configuration object
        """
        self.configuration = configuration
        self._privacy_db = PrivacyDatabase(configuration)

    def get_settings(self, user: str) -> types.WSGIResponse:
        """Get privacy settings for a user.

        Args:
            user: The user identifier (email or phone)

        Returns:
            WSGI response with the user's privacy settings
        """
        if not user:
            return httputils.UNAUTHORIZED

        settings = self._privacy_db.get_user_settings(user)
        if not settings:
            return httputils.NOT_FOUND

        # Convert settings to dict
        settings_dict = {
            "allow_name": settings.allow_name,
            "allow_email": settings.allow_email,
            "allow_phone": settings.allow_phone,
            "allow_company": settings.allow_company,
            "allow_title": settings.allow_title,
            "allow_photo": settings.allow_photo,
            "allow_birthday": settings.allow_birthday,
            "allow_address": settings.allow_address
        }

        return client.OK, {"Content-Type": "application/json"}, json.dumps(settings_dict)

    def create_settings(self, user: str, settings: Dict[str, bool]) -> types.WSGIResponse:
        """Create privacy settings for a user.

        Args:
            user: The user identifier (email or phone)
            settings: Dictionary of privacy settings

        Returns:
            WSGI response indicating success or failure
        """
        if not user:
            return httputils.NOT_ALLOWED

        # Validate settings
        required_fields = {
            "allow_name", "allow_email", "allow_phone", "allow_company",
            "allow_title", "allow_photo", "allow_birthday", "allow_address"
        }
        if not all(field in settings for field in required_fields):
            return client.BAD_REQUEST, {"Content-Type": "application/json"}, json.dumps({
                "error": "Missing required fields",
                "required_fields": list(required_fields)
            })

        if not all(isinstance(settings[field], bool) for field in required_fields):
            return client.BAD_REQUEST, {"Content-Type": "application/json"}, json.dumps({
                "error": "All settings must be boolean values"
            })

        try:
            self._privacy_db.create_user_settings(user, settings)
            return client.CREATED, {"Content-Type": "application/json"}, json.dumps({"status": "created"})
        except Exception as e:
            return client.BAD_REQUEST, {"Content-Type": "application/json"}, json.dumps({"error": str(e)})

    def update_settings(self, user: str, settings: Dict[str, bool]) -> types.WSGIResponse:
        """Update privacy settings for a user.

        Args:
            user: The user identifier (email or phone)
            settings: Dictionary of privacy settings to update

        Returns:
            WSGI response indicating success or failure
        """
        if not user:
            return httputils.UNAUTHORIZED

        # Validate settings
        if not settings:
            return client.BAD_REQUEST, {"Content-Type": "application/json"}, json.dumps({
                "error": "No settings provided"
            })

        valid_fields = {
            "allow_name", "allow_email", "allow_phone", "allow_company",
            "allow_title", "allow_photo", "allow_birthday", "allow_address"
        }
        if not all(field in valid_fields for field in settings):
            return client.BAD_REQUEST, {"Content-Type": "application/json"}, json.dumps({
                "error": "Invalid field names",
                "valid_fields": list(valid_fields)
            })

        if not all(isinstance(settings[field], bool) for field in settings):
            return client.BAD_REQUEST, {"Content-Type": "application/json"}, json.dumps({
                "error": "All settings must be boolean values"
            })

        try:
            updated = self._privacy_db.update_user_settings(user, settings)
            if not updated:
                return httputils.NOT_FOUND
            return client.OK, {"Content-Type": "application/json"}, json.dumps({"status": "updated"})
        except Exception as e:
            return client.BAD_REQUEST, {"Content-Type": "application/json"}, json.dumps({"error": str(e)})

    def delete_settings(self, user: str) -> types.WSGIResponse:
        """Delete privacy settings for a user.

        Args:
            user: The user identifier (email or phone)

        Returns:
            WSGI response indicating success or failure
        """
        if not user:
            return httputils.UNAUTHORIZED

        try:
            deleted = self._privacy_db.delete_user_settings(user)
            if not deleted:
                return httputils.NOT_FOUND
            return client.OK, {"Content-Type": "application/json"}, json.dumps({"status": "deleted"})
        except Exception as e:
            return client.BAD_REQUEST, {"Content-Type": "application/json"}, json.dumps({"error": str(e)})
