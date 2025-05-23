"""Privacy scanner module for Radicale.

This module provides functionality to scan vCards across all collections
to find occurrences of specific identities (email/phone).
"""

import logging
from typing import Dict, List, Tuple

import vobject

from radicale.item import Item
from radicale.storage.multifilesystem.get import CollectionPartGet

logger = logging.getLogger(__name__)


class PrivacyScanner:
    """Class to scan vCards for identity occurrences."""

    def __init__(self, storage):
        """Initialize the privacy scanner.

        Args:
            storage: The Radicale storage instance
        """
        self._storage = storage

    def _extract_identifiers(self, vcard: vobject.vCard) -> List[Tuple[str, str]]:
        """Extract all identifiers (email and phone) from a vCard.

        Args:
            vcard: The vCard to process

        Returns:
            List of tuples (type, value) for each identifier found
        """
        identifiers = []

        # Extract emails
        if hasattr(vcard, "email_list"):
            for email_prop in vcard.email_list:
                if email_prop.value:
                    identifiers.append(("email", email_prop.value))
                    logger.debug("Found email in vCard: %r", email_prop.value)

        # Extract phones
        if hasattr(vcard, "tel_list"):
            for tel_prop in vcard.tel_list:
                if tel_prop.value:
                    identifiers.append(("phone", tel_prop.value))
                    logger.debug("Found phone in vCard: %r", tel_prop.value)

        return identifiers

    def _scan_collection(self, collection: CollectionPartGet, identity: str) -> List[Dict]:
        """Scan a single collection for identity occurrences.

        Args:
            collection: The collection to scan (must support get_all())
            identity: The identity to search for

        Returns:
            List of dictionaries containing match information
        """
        matches = []
        user_id = collection.path.split("/")[0]  # First part of path is user ID

        try:
            # Get all items in the collection
            for item in collection.get_all():
                if not isinstance(item, Item) or not item.component_name == "VCARD":
                    continue

                # Extract identifiers from the vCard
                identifiers = self._extract_identifiers(item.vobject_item)
                matching_fields = []

                # Check each identifier against the search identity
                for id_type, id_value in identifiers:
                    if id_value == identity:
                        matching_fields.append(id_type)

                if matching_fields:
                    matches.append({
                        'user_id': user_id,
                        'vcard_uid': item.vobject_item.uid.value if hasattr(item.vobject_item, 'uid') else None,
                        'matching_fields': matching_fields,
                        'collection_path': collection.path
                    })
                    logger.info("Found match in collection %r: %r", collection.path, matching_fields)

        except Exception as e:
            logger.error("Error scanning collection %r: %s", collection.path, e)

        return matches

    def find_identity_occurrences(self, identity: str) -> List[Dict]:
        """Find all occurrences of an identity (email/phone) across all vCards.

        Args:
            identity: The email or phone number to search for

        Returns:
            List of dictionaries containing:
            {
                'user_id': str,  # The user who owns the collection
                'vcard_uid': str,  # The UID of the matching vCard
                'matching_fields': List[str],  # Which fields matched (email/phone)
                'collection_path': str  # Path to the collection
            }
        """
        logger.info("Starting scan for identity: %r", identity)
        all_matches = []

        try:
            # Get all collections
            collections = self._storage.discover("")
            for collection in collections:
                if not isinstance(collection, CollectionPartGet):
                    continue

                # Scan each collection
                matches = self._scan_collection(collection, identity)
                all_matches.extend(matches)

        except Exception as e:
            logger.error("Error during identity scan: %s", e)
            raise

        logger.info("Scan complete. Found %d matches", len(all_matches))
        return all_matches
