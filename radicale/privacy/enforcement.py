"""Privacy enforcement module for Radicale.

This module handles the enforcement of privacy settings on vCard items.
"""

import logging
from typing import Dict

import radicale.item as radicale_item
from radicale.privacy.database import PrivacyDatabase

logger = logging.getLogger(__name__)


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
        """Enforce privacy settings on a vCard item by removing disallowed fields.

        Args:
            item: The vCard item to process

        Returns:
            The modified vCard item with disallowed fields removed
        """
        if not item.component_name == "VCARD" and not item.name == "VCARD":
            logger.debug("Not a VCF file")
            return item

        logger.info("Intercepted vCard for privacy enforcement:")
        logger.debug("vCard content:\n%s", item.serialize())

        # Get email from vCard
        email = None
        vcard = item.vobject_item
        if hasattr(vcard, "email_list"):
            for email_prop in vcard.email_list:
                email = email_prop.value
                logger.info("Found email in vCard: %r", email)
                break

        if not email:
            logger.info("No email found in vCard")
            return item

        # Ensure database connection is established
        self._ensure_db_connection()

        # Get privacy settings for this email
        privacy_settings = self._privacy_db.get_user_settings(email)
        logger.info("Privacy settings for %r: %r", email, privacy_settings)

        if not privacy_settings:
            logger.info("No privacy settings found for %r", email)
            return item

        # Log all privacy settings
        logger.debug("Privacy settings details:")
        logger.debug("  Name disallowed: %r", privacy_settings.disallow_name)
        logger.debug("  Email disallowed: %r", privacy_settings.disallow_email)
        logger.debug("  Phone disallowed: %r", privacy_settings.disallow_phone)
        logger.debug("  Company disallowed: %r", privacy_settings.disallow_company)
        logger.debug("  Title disallowed: %r", privacy_settings.disallow_title)
        logger.debug("  Photo disallowed: %r", privacy_settings.disallow_photo)
        logger.debug("  Birthday disallowed: %r", privacy_settings.disallow_birthday)
        logger.debug("  Address disallowed: %r", privacy_settings.disallow_address)

        # Process the vCard
        logger.info("Processing vCard for privacy enforcement")

        # Get all properties of the vCard from contents
        # Create a copy of the keys to safely iterate while modifying
        for property_name in list(vcard.contents.keys()):
            logger.debug("Prop name to check: %s", property_name)

            # Check if this property should be removed based on privacy settings
            should_remove = False

            # Map vCard properties to privacy settings
            if property_name in ('n', 'fn'):
                should_remove = privacy_settings.disallow_name
            elif property_name == 'email':
                should_remove = privacy_settings.disallow_email
            elif property_name == 'tel':
                should_remove = privacy_settings.disallow_phone
            elif property_name == 'org':
                should_remove = privacy_settings.disallow_company
            elif property_name == 'title':
                should_remove = privacy_settings.disallow_title
            elif property_name == 'photo':
                should_remove = privacy_settings.disallow_photo
            elif property_name == 'bday':
                should_remove = privacy_settings.disallow_birthday
            elif property_name == 'adr':
                should_remove = privacy_settings.disallow_address

            if should_remove:
                logger.debug("Removing disallowed field: %s", property_name)
                del vcard.contents[property_name]

        logger.info("vCard after privacy enforcement:\n%s", item.serialize())
        return item

    def close(self):
        """Close the privacy database connection."""
        if self._privacy_db:
            self._privacy_db.close()
            self._privacy_db = None
