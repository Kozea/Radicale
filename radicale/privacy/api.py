"""
Privacy API endpoints for Radicale.

This module provides RESTful endpoints for managing user privacy settings.
"""

import json
import logging
import re
from http import client
from typing import Dict, Tuple

from radicale import config, httputils, storage, types
from radicale.item import Item
from radicale.privacy.database import PrivacyDatabase
from radicale.privacy.scanner import PrivacyScanner

logger = logging.getLogger(__name__)


class PrivacyAPI:
    """Privacy API endpoints."""

    def __init__(self, configuration: "config.Configuration") -> None:
        """Initialize the privacy API.

        Args:
            configuration: The Radicale configuration object
        """
        self.configuration = configuration
        self._privacy_db = PrivacyDatabase(configuration)
        storage_instance = storage.load(configuration)
        self._scanner = PrivacyScanner(storage_instance)

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
            "disallow_name": settings.disallow_name,
            "disallow_email": settings.disallow_email,
            "disallow_phone": settings.disallow_phone,
            "disallow_company": settings.disallow_company,
            "disallow_title": settings.disallow_title,
            "disallow_photo": settings.disallow_photo,
            "disallow_birthday": settings.disallow_birthday,
            "disallow_address": settings.disallow_address
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
            "disallow_name", "disallow_email", "disallow_phone", "disallow_company",
            "disallow_title", "disallow_photo", "disallow_birthday", "disallow_address"
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
            "disallow_name", "disallow_email", "disallow_phone", "disallow_company",
            "disallow_title", "disallow_photo", "disallow_birthday", "disallow_address"
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

    def get_matching_cards(self, user: str) -> types.WSGIResponse:
        """Get all vCards that match a user's identity.

        Args:
            user: The user identifier (email or phone)

        Returns:
            WSGI response with matching vCards
        """
        # Validate user identifier
        is_valid, error_msg = self._validate_user_identifier(user)
        if not is_valid:
            return client.BAD_REQUEST, {"Content-Type": "application/json"}, json.dumps({
                "error": error_msg
            })

        # Get user's privacy settings
        settings = self._privacy_db.get_user_settings(user)
        if not settings:
            return httputils.NOT_FOUND

        # Find matching vCards
        try:
            matches = self._scanner.find_identity_occurrences(user)
            if not matches:
                return client.OK, {"Content-Type": "application/json"}, json.dumps({
                    "matches": []
                })

            # Get the vCards
            vcard_matches = []
            for match in matches:
                try:
                    logger.debug("Attempting to discover collection: %r", match["collection_path"])
                    # Ensure path starts with a slash for discover()
                    discover_path = "/" + match["collection_path"] if match["collection_path"] else "/"
                    logger.debug("Using discover path: %r", discover_path)
                    collections = list(self._scanner._storage.discover(discover_path))
                    logger.debug("Discover returned %d collections", len(collections))
                    collection = next(iter(collections), None)
                except Exception as e:
                    logger.info("Error discovering collection: %r", e)
                    continue

                if not collection:
                    logger.debug("No collection found for path: %r", match["collection_path"])
                    continue

                # Get the vCard
                vcard = None
                for item in collection.get_all():
                    if (isinstance(item, Item) and
                        item.component_name == "VCARD" and
                            hasattr(item.vobject_item, "uid") and
                            item.vobject_item.uid.value == match["vcard_uid"]):
                        vcard = item.vobject_item
                        break

                if not vcard:
                    continue

                # Create a simplified version of the vCard
                vcard_match = {
                    "vcard_uid": match["vcard_uid"],
                    "collection_path": match["collection_path"],
                    "matching_fields": match["matching_fields"],
                    "fields": {}
                }

                # Add all available fields
                if hasattr(vcard, "fn"):
                    vcard_match["fields"]["fn"] = vcard.fn.value
                if hasattr(vcard, "n"):
                    vcard_match["fields"]["n"] = vcard.n.value
                if hasattr(vcard, "nickname"):
                    vcard_match["fields"]["nickname"] = vcard.nickname.value
                if hasattr(vcard, "email_list"):
                    vcard_match["fields"]["email"] = [e.value for e in vcard.email_list if e.value]
                if hasattr(vcard, "tel_list"):
                    vcard_match["fields"]["tel"] = [t.value for t in vcard.tel_list if t.value]
                if hasattr(vcard, "org"):
                    vcard_match["fields"]["org"] = vcard.org.value
                if hasattr(vcard, "title"):
                    vcard_match["fields"]["title"] = vcard.title.value
                if hasattr(vcard, "photo"):
                    vcard_match["fields"]["photo"] = True  # Just indicate presence, don't include data
                if hasattr(vcard, "bday"):
                    vcard_match["fields"]["bday"] = vcard.bday.value
                if hasattr(vcard, "adr"):
                    vcard_match["fields"]["adr"] = vcard.adr.value

                vcard_matches.append(vcard_match)

            return client.OK, {"Content-Type": "application/json"}, json.dumps({
                "matches": vcard_matches
            })

        except Exception as e:
            return client.INTERNAL_SERVER_ERROR, {"Content-Type": "application/json"}, json.dumps({
                "error": f"Error finding matching cards: {str(e)}"
            })
