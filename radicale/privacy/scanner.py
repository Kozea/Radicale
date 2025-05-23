"""Privacy scanner module for Radicale.

This module provides functionality to scan vCards across all collections
to find occurrences of specific identities (email/phone).
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

import vobject

from radicale.item import Item
from radicale.storage.multifilesystem.get import CollectionPartGet

logger = logging.getLogger(__name__)


class PrivacyScanner:
    """Scanner for finding identity occurrences in vCards."""

    _instance = None
    _initialized = False

    def __new__(cls, storage=None):
        """Create or return the singleton instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._storage = storage
        return cls._instance

    def __init__(self, storage=None):
        """Initialize the scanner if not already initialized."""
        if not self._initialized:
            self._index = {}  # Maps identity to list of matches
            self._index_initialized = False
            self._initialized = True
            logging.info("PrivacyScanner initialized with storage %s", storage)

    @property
    def _storage(self):
        """Get the storage instance."""
        return self.__class__._storage

    def _extract_identifiers(self, vcard: vobject.vCard) -> List[Tuple[str, str]]:
        """Extract all identifiers (email and phone) from a vCard.

        Args:
            vcard: The vCard to process

        Returns:
            List of tuples (type, value) for each identifier found
        """
        identifiers: List[Tuple[str, str]] = []

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

    def _build_index(self) -> None:
        """Build an index of all identities across all collections."""
        if self._index_initialized:
            return

        logger.info("Building identity index...")
        try:
            # Get all collections
            collections = self._storage.discover("")
            for collection in collections:
                if not isinstance(collection, CollectionPartGet):
                    continue

                # Scan each collection
                matches = self._scan_collection(collection, None)  # None means index all identities
                for match in matches:
                    for field in match["matching_fields"]:
                        identity = match.get(field)
                        if identity:
                            if identity not in self._index:
                                self._index[identity] = []
                            self._index[identity].append(match)

            self._index_initialized = True
            logger.info("Identity index built successfully")
        except Exception as e:
            logger.error("Error building identity index: %s", e)
            raise

    def _scan_collection(self, collection: CollectionPartGet, identity: Optional[str] = None) -> List[Dict[str, Any]]:
        """Scan a single collection for identity occurrences.

        Args:
            collection: The collection to scan (must support get_all())
            identity: The identity to search for. If None, index all identities.

        Returns:
            List of dictionaries containing match information
        """
        matches: List[Dict[str, Any]] = []
        user_id = collection.path.split("/")[0]  # First part of path is user ID

        try:
            # Get all items in the collection
            for item in collection.get_all():
                if not isinstance(item, Item) or not item.component_name == "VCARD":
                    continue

                # Extract identifiers from the vCard
                identifiers = self._extract_identifiers(item.vobject_item)
                matching_fields: List[str] = []

                # Check each identifier against the search identity
                for id_type, id_value in identifiers:
                    if identity is None or id_value == identity:
                        matching_fields.append(id_type)
                        if identity is None:
                            # When indexing, store the actual value
                            matches.append({
                                'user_id': user_id,
                                'vcard_uid': item.vobject_item.uid.value if hasattr(item.vobject_item, 'uid') else None,
                                'matching_fields': [id_type],
                                'collection_path': collection.path,
                                id_type: id_value  # Store the actual value for indexing
                            })

                if identity is not None and matching_fields:
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

    def find_identity_occurrences(self, identity: str) -> List[Dict[str, Any]]:
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

        # Build index if not initialized
        if not self._index_initialized:
            self._build_index()

        # Try to use the index first
        if identity in self._index:
            logger.info("Found identity in index")
            return self._index[identity]

        # If not in index, do a full scan
        logger.info("Identity not found in index, performing full scan")
        all_matches: List[Dict[str, Any]] = []

        try:
            # Get all collections
            collections = self._storage.discover("")
            for collection in collections:
                if not isinstance(collection, CollectionPartGet):
                    continue

                # Scan each collection
                matches = self._scan_collection(collection, identity)
                all_matches.extend(matches)

            # Update the index with the new matches
            if all_matches:
                self._index[identity] = all_matches

        except Exception as e:
            logger.error("Error during identity scan: %s", e)
            raise

        logger.info("Scan complete. Found %d matches", len(all_matches))
        return all_matches

    def refresh_index(self) -> None:
        """Force a refresh of the identity index."""
        self._index.clear()
        self._index_initialized = False
        self._build_index()

    @classmethod
    def reset(cls):
        """Reset the singleton instance for testing."""
        cls._instance = None
        cls._initialized = False
        cls._storage = None
