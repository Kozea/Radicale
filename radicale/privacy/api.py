"""
Privacy API endpoints for Radicale.

This module provides RESTful endpoints for managing user privacy settings.
"""

import json
import re
from http import client
from typing import Dict, Tuple

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

    def _validate_user_identifier(self, user: str) -> Tuple[bool, str]:
        """Validate user identifier format.

        Args:
            user: The user identifier to validate (email or phone)

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not user:
            return False, "User identifier is required"

        # Check if it's an email
        if '@' in user:
            # Basic email validation
            if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', user):
                return False, "Invalid email format"
            return True, ""

        # If not an email, must be a phone number
        # Remove any spaces, dashes, or parentheses
        phone = re.sub(r'[\s\-\(\)]', '', user)
        # Check if it's a valid phone number (E.164 format)
        if not re.match(r'^\+[1-9]\d{6,14}$', phone):
            return False, "Invalid identifier format. Must be a valid email or phone number in E.164 format (e.g., +1234567890)"
        return True, ""

    def get_settings(self, user: str) -> types.WSGIResponse:
        """Get privacy settings for a user.

        Args:
            user: The user identifier (email or phone)

        Returns:
            WSGI response with the user's privacy settings
        """
        is_valid, error_msg = self._validate_user_identifier(user)
        if not is_valid:
            return client.BAD_REQUEST, {"Content-Type": "application/json"}, json.dumps({
                "error": error_msg
            })

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
        is_valid, error_msg = self._validate_user_identifier(user)
        if not is_valid:
            return client.BAD_REQUEST, {"Content-Type": "application/json"}, json.dumps({
                "error": error_msg
            })

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
        is_valid, error_msg = self._validate_user_identifier(user)
        if not is_valid:
            return client.BAD_REQUEST, {"Content-Type": "application/json"}, json.dumps({
                "error": error_msg
            })

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
        is_valid, error_msg = self._validate_user_identifier(user)
        if not is_valid:
            return client.BAD_REQUEST, {"Content-Type": "application/json"}, json.dumps({
                "error": error_msg
            })

        try:
            deleted = self._privacy_db.delete_user_settings(user)
            if not deleted:
                return httputils.NOT_FOUND
            return client.OK, {"Content-Type": "application/json"}, json.dumps({"status": "deleted"})
        except Exception as e:
            return client.BAD_REQUEST, {"Content-Type": "application/json"}, json.dumps({"error": str(e)})
