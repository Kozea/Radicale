"""Privacy enforcement module for Radicale.

This module handles the enforcement of privacy settings on vCard items.
"""

import logging
from typing import Dict

import radicale.item as radicale_item
from radicale.privacy.database import PrivacyDatabase
from radicale.privacy.vcard_properties import (PRIVACY_TO_VCARD_MAP,
                                               VCARD_NAME_TO_ENUM)

logger = logging.getLogger(__name__)


class PrivacyViolationError(Exception):
    """Exception raised when a vCard violates privacy settings."""
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class PrivacyEnforcement:
    """Class to handle privacy enforcement on vCard items."""

    # Class-level storage for privacy enforcement instances
    _instances: Dict[str, 'PrivacyEnforcement'] = {}

    @classmethod
    def get_instance(cls, configuration) -> 'PrivacyEnforcement':
        """Get or create a privacy enforcement instance for the given configuration.

        Args:
            configuration: The configuration object

        Returns:
            A PrivacyEnforcement instance
        """
        config_id = str(id(configuration))
        if config_id not in cls._instances:
            cls._instances[config_id] = cls(configuration)
        return cls._instances[config_id]

    @classmethod
    def close_all(cls):
        """Close all privacy enforcement instances."""
        for instance in cls._instances.values():
            instance.close()
        cls._instances.clear()

    def __init__(self, configuration):
        """Initialize the privacy enforcement with configuration."""
        self._privacy_db = None
        self._configuration = configuration

    def _ensure_db_connection(self):
        """Ensure the database connection is established."""
        if self._privacy_db is None:
            self._privacy_db = PrivacyDatabase(self._configuration)
            self._privacy_db.init_db()

    def enforce_privacy(self, item: radicale_item.Item) -> radicale_item.Item:
        """Enforce privacy settings on a vCard item by rejecting if it contains disallowed fields.

        Args:
            item: The vCard item to process

        Returns:
            The vCard item if no privacy violations are found

        Raises:
            PrivacyViolationError: If the vCard contains fields that violate privacy settings
        """
        if not item.component_name == "VCARD" and not item.name == "VCARD":
            logger.debug("Not a VCF file")
            return item

        logger.info("Intercepted vCard for privacy enforcement:")
        logger.debug("vCard content:\n%s", item.serialize())

        # Get identifiers (email and phone) from vCard
        identifiers = []
        vcard = item.vobject_item

        # Check for email
        if hasattr(vcard, "email_list"):
            for email_prop in vcard.email_list:
                if email_prop.value:
                    identifiers.append(("email", email_prop.value))
                    logger.info("Found email in vCard: %r", email_prop.value)

        # Check for phone
        if hasattr(vcard, "tel_list"):
            for tel_prop in vcard.tel_list:
                if tel_prop.value:
                    identifiers.append(("phone", tel_prop.value))
                    logger.info("Found phone in vCard: %r", tel_prop.value)

        if not identifiers:
            logger.info("No email or phone found in vCard")
            return item

        # Ensure database connection is established
        self._ensure_db_connection()

        # Get privacy settings for each identifier
        privacy_settings = None
        for id_type, id_value in identifiers:
            settings = self._privacy_db.get_user_settings(id_value)
            if settings:
                logger.info("Found privacy settings for %s %r", id_type, id_value)
                if privacy_settings is None:
                    privacy_settings = settings
                else:
                    # Apply most restrictive settings when multiple matches found
                    for privacy_field in PRIVACY_TO_VCARD_MAP.keys():
                        current_value = getattr(privacy_settings, privacy_field)
                        new_value = getattr(settings, privacy_field)
                        setattr(privacy_settings, privacy_field, current_value or new_value)

        if not privacy_settings:
            logger.info("No privacy settings found for any identifier")
            return item

        # Log all privacy settings
        logger.debug("Privacy settings details:")
        for privacy_field in PRIVACY_TO_VCARD_MAP.keys():
            logger.debug("  %s disallowed: %r", privacy_field.replace('disallow_', '').title(),
                         getattr(privacy_settings, privacy_field))

        # Check for violations
        violations = []

        # Check each property against privacy settings
        for property_name in vcard.contents.keys():
            logger.debug("Property name to check: %s", property_name)

            # Get the corresponding enum value for this property
            vcard_property = VCARD_NAME_TO_ENUM.get(property_name.lower())
            if vcard_property is None:
                logger.debug("Unknown vCard property: %s", property_name)
                continue

            # Check if this property should be removed based on privacy settings
            for privacy_field, vcard_properties in PRIVACY_TO_VCARD_MAP.items():
                if vcard_property in vcard_properties and getattr(privacy_settings, privacy_field):
                    violations.append(property_name)
                    logger.debug("Property %s matches privacy field %s", property_name, privacy_field)
                    break

        if violations:
            error_msg = f"Privacy violation: Cannot save vCard containing private fields: {', '.join(violations)}"
            logger.warning(error_msg)
            raise PrivacyViolationError(error_msg)

        logger.info("No privacy violations found in vCard")
        return item

    def close(self):
        """Close the privacy database connection."""
        if self._privacy_db:
            self._privacy_db.close()
            self._privacy_db = None
