"""
Privacy API for Radicale.

This module provides the core business logic for managing user privacy settings.
"""

import logging
import re
from typing import Any, Dict, List, Tuple, Union

from radicale import config, storage
from radicale.item import Item
from radicale.privacy.database import PrivacyDatabase
from radicale.privacy.reprocessor import PrivacyReprocessor
from radicale.privacy.scanner import PrivacyScanner

logger = logging.getLogger(__name__)


class PrivacyAPI:
    """Privacy API for managing user privacy settings."""

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

    def get_settings(self, user: str) -> Tuple[bool, Union[Dict[str, bool], str]]:
        """Get privacy settings for a user.

        Args:
            user: The user identifier (email or phone)

        Returns:
            Tuple of (success, result)
            If success is True, result contains the settings dictionary
            If success is False, result contains the error message
        """
        is_valid, error_msg = self._validate_user_identifier(user)
        if not is_valid:
            return False, error_msg

        settings = self._privacy_db.get_user_settings(user)
        if not settings:
            return False, "User settings not found"

        # Convert settings to dict
        settings_dict = {
            "disallow_company": settings.disallow_company,
            "disallow_title": settings.disallow_title,
            "disallow_photo": settings.disallow_photo,
            "disallow_birthday": settings.disallow_birthday,
            "disallow_address": settings.disallow_address
        }

        return True, settings_dict

    def create_settings(self, user: str, settings: Dict[str, bool]) -> Tuple[bool, Union[Dict[str, Any], str]]:
        """Create privacy settings for a user.

        Args:
            user: The user identifier (email or phone)
            settings: Dictionary of privacy settings

        Returns:
            Tuple of (success, result)
            If success is True, result contains the success message
            If success is False, result contains the error message
        """
        is_valid, error_msg = self._validate_user_identifier(user)
        if not is_valid:
            return False, error_msg

        # Validate settings
        required_fields = {
            "disallow_company", "disallow_title", "disallow_photo",
            "disallow_birthday", "disallow_address"
        }
        if not all(field in settings for field in required_fields):
            return False, {
                "error": "Missing required fields",
                "required_fields": list(required_fields)
            }

        if not all(isinstance(settings[field], bool) for field in required_fields):
            return False, "All settings must be boolean values"

        try:
            self._privacy_db.create_user_settings(user, settings)

            # After creating settings, reprocess all vCards for this user
            try:
                reprocessor = PrivacyReprocessor(self.configuration, self._scanner._storage)
                reprocessor.reprocess_vcards(user)
                return True, {"status": "created"}
            except Exception as e:
                logger.error("Error reprocessing cards: %s", str(e))
                # Still return success for settings creation, but include reprocessing error
                return True, {
                    "status": "created",
                    "reprocessing_error": str(e)
                }
        except Exception as e:
            return False, str(e)

    def update_settings(self, user: str, settings: Dict[str, bool]) -> Tuple[bool, Union[Dict[str, Any], str]]:
        """Update privacy settings for a user.

        Args:
            user: The user identifier (email or phone)
            settings: Dictionary of privacy settings to update

        Returns:
            Tuple of (success, result)
            If success is True, result contains the success message
            If success is False, result contains the error message
        """
        is_valid, error_msg = self._validate_user_identifier(user)
        if not is_valid:
            return False, error_msg

        # Validate settings
        if not settings:
            return False, "No settings provided"

        valid_fields = {
            "disallow_company", "disallow_title", "disallow_photo",
            "disallow_birthday", "disallow_address"
        }
        if not all(field in valid_fields for field in settings):
            return False, {
                "error": "Invalid field names",
                "valid_fields": list(valid_fields)
            }

        if not all(isinstance(settings[field], bool) for field in settings):
            return False, "All settings must be boolean values"

        try:
            updated = self._privacy_db.update_user_settings(user, settings)
            if not updated:
                return False, "User settings not found"

            # After updating settings, reprocess all vCards for this user
            try:
                reprocessor = PrivacyReprocessor(self.configuration, self._scanner._storage)
                reprocessor.reprocess_vcards(user)
                return True, {"status": "updated"}
            except Exception as e:
                logger.error("Error reprocessing cards: %s", str(e))
                # Still return success for settings update, but include reprocessing error
                return True, {
                    "status": "updated",
                    "reprocessing_error": str(e)
                }

        except Exception as e:
            return False, str(e)

    def delete_settings(self, user: str) -> Tuple[bool, Union[Dict[str, str], str]]:
        """Delete privacy settings for a user.

        Args:
            user: The user identifier (email or phone)

        Returns:
            Tuple of (success, result)
            If success is True, result contains the success message
            If success is False, result contains the error message
        """
        is_valid, error_msg = self._validate_user_identifier(user)
        if not is_valid:
            return False, error_msg

        try:
            deleted = self._privacy_db.delete_user_settings(user)
            if not deleted:
                return False, "User settings not found"
            return True, {"status": "deleted"}
        except Exception as e:
            return False, str(e)

    def get_matching_cards(self, user: str) -> Tuple[bool, Union[Dict[str, List[Dict[str, Any]]], str]]:
        """Get all vCards that match a user's identity.

        Args:
            user: The user identifier (email or phone)

        Returns:
            Tuple of (success, result)
            If success is True, result contains the matching cards
            If success is False, result contains the error message
        """
        # Validate user identifier
        is_valid, error_msg = self._validate_user_identifier(user)
        if not is_valid:
            return False, error_msg

        # Get user's privacy settings
        settings = self._privacy_db.get_user_settings(user)
        if not settings:
            return False, "User settings not found"

        # Find matching vCards
        try:
            matches = self._scanner.find_identity_occurrences(user)
            if not matches:
                return True, {"matches": []}

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

            return True, {"matches": vcard_matches}

        except Exception as e:
            return False, f"Error finding matching cards: {str(e)}"

    def reprocess_cards(self, user: str) -> Tuple[bool, Union[Dict[str, Union[str, int, List[str]]], str]]:
        """Trigger reprocessing of all vCards for a user.

        Args:
            user: The user identifier (email or phone)

        Returns:
            Tuple of (success, result)
            If success is True, result contains the reprocessing results
            If success is False, result contains the error message
        """
        is_valid, error_msg = self._validate_user_identifier(user)
        if not is_valid:
            return False, error_msg

        # Verify user has privacy settings
        settings = self._privacy_db.get_user_settings(user)
        if not settings:
            return False, "User settings not found"

        try:
            reprocessor = PrivacyReprocessor(self.configuration, self._scanner._storage)
            reprocessed_cards = reprocessor.reprocess_vcards(user)
            return True, {
                "status": "success",
                "reprocessed_cards": len(reprocessed_cards),
                "reprocessed_card_uids": reprocessed_cards
            }
        except Exception as e:
            return False, f"Error reprocessing cards: {str(e)}"
