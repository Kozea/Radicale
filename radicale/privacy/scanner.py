"""Privacy scanner module for Radicale.

This module provides functionality to scan vCards across all collections
to find occurrences of specific identities (email/phone).
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

import vobject

from radicale.item import Item
from radicale.storage.multifilesystem.get import CollectionPartGet
from radicale.utils import normalize_phone_e164

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
            logger.info("Privacy scanner initialized")

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
                    logger.debug("PRIVACY: Found id (email) in vCard: %r", email_prop.value)

        # Extract phones
        if hasattr(vcard, "tel_list"):
            for tel_prop in vcard.tel_list:
                if tel_prop.value:
                    try:
                        normalized = normalize_phone_e164(tel_prop.value)
                        identifiers.append(("phone", normalized))
                    except Exception:
                        # If normalization fails, still append the original value to ensure
                        # all phone numbers present in the vCard are captured, even if not valid E.164.
                        # This preserves visibility of malformed or non-normalizable numbers for diagnostics.
                        identifiers.append(("phone", tel_prop.value))
                    logger.debug("PRIVACY: Found id (phone) in vCard: %r", tel_prop.value)

        return identifiers

    def _build_index(self) -> None:
        """Build an index of all identities across all collections."""
        if self._index_initialized:
            return

        logger.info("PRIVACY: Building identity index...")
        try:
            # Get all collections
            collections = self._storage.discover("/")
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
            logger.info("PRIVACY: Identity index built successfully")
        except Exception as e:
            logger.error("PRIVACY: Error building identity index: %s", e)
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
        logger.info("PRIVACY: Scanning collection %r for user %r", collection.path, user_id)

        try:
            # Get all items in the collection
            items = list(collection.get_all())
            logger.debug("PRIVACY: Found %d items in collection %r", len(items), collection.path)

            for item in items:
                if not isinstance(item, Item):
                    logger.debug("PRIVACY: Skipping non-Item: %r", item)
                    continue
                if not (item.component_name == "VCARD" or item.name == "VCARD"):
                    logger.debug("PRIVACY: Skipping non-VCARD item: %r", item.component_name)
                    continue

                logger.info("PRIVACY: Processing vCard in %r", collection.path)
                # Extract identifiers from the vCard
                identifiers = self._extract_identifiers(item.vobject_item)
                logger.debug("PRIVACY: Found identifiers: %r", identifiers)
                matching_fields: List[str] = []

                # Check each identifier against the search identity
                for id_type, id_value in identifiers:
                    if identity is not None and id_type == "phone":
                        try:
                            normalized_identity = normalize_phone_e164(identity)
                        except Exception:
                            normalized_identity = identity
                        if id_value == normalized_identity:
                            matching_fields.append(id_type)
                    elif identity is None or id_value == identity:
                        matching_fields.append(id_type)

                if identity is not None and matching_fields:
                    matches.append({
                        'user_id': user_id,
                        'vcard_uid': item.vobject_item.uid.value if hasattr(item.vobject_item, 'uid') else None,
                        'matching_fields': matching_fields,
                        'collection_path': collection.path
                    })
                    logger.debug("PRIVACY: Found match in collection %r: %r", collection.path, matching_fields)
                elif identity is None and matching_fields:
                    for id_type, id_value in identifiers:
                        matches.append({
                            'user_id': user_id,
                            'vcard_uid': item.vobject_item.uid.value if hasattr(item.vobject_item, 'uid') else None,
                            'matching_fields': [id_type],
                            'collection_path': collection.path,
                            id_type: id_value
                        })

        except Exception as e:
            logger.error("PRIVACY: Error scanning collection %r: %s", collection.path, str(e))

        logger.info("PRIVACY: Scan complete for %r. Found %d matches", collection.path, len(matches))
        return matches

    def find_identity_occurrences(self, identity: str) -> List[Dict[str, Any]]:
        """Find all occurrences of an identity (email/phone) across all vCards.

        Args:
            identity: The email or phone number to search for

        Returns:
            List of dictionaries containing:
            {
                'user_id': str,    # The user who owns the collection
                'vcard_uid': str,  # The UID of the matching vCard
                'matching_fields': List[str],  # Which fields matched (email/phone)
                'collection_path': str  # Path to the collection
            }
        """
        logger.info("PRIVACY: Starting scan for identity: %r", identity)

        # Build index if not initialized
        if not self._index_initialized:
            logger.debug("PRIVACY: Index not initialized, building index...")
            self._build_index()

        # Try to use the index first
        if identity in self._index:
            logger.debug("PRIVACY: Found identity in index")
            return self._index[identity]

        # If not in index, do a full scan
        logger.debug("PRIVACY: Identity not found in index, performing full scan")
        all_matches: List[Dict[str, Any]] = []

        try:
            # Get root collections
            root_collections = list(self._storage.discover("/", depth="1"))
            logger.debug("PRIVACY: Found %d root collections", len(root_collections))

            # Try to get paths from collection objects
            root_paths = []
            for collection in root_collections:
                # Try to get path from href first, then path attribute
                collection_path = getattr(collection, 'href', None)
                if collection_path is None:
                    collection_path = getattr(collection, 'path', None)
                if collection_path is not None:
                    # Remove leading slash if present
                    if collection_path.startswith('/'):
                        collection_path = collection_path[1:]
                    root_paths.append(collection_path)

            logger.debug("PRIVACY: Found root collections: %r", root_paths)

            for collection in root_collections:
                if not isinstance(collection, CollectionPartGet):
                    logger.debug("PRIVACY: Skipping non-CollectionPartGet: %r", collection)
                    continue

                # Get collection path from path attribute
                collection_path = getattr(collection, 'path', None)

                # Remove leading slash if present
                if collection_path is not None and collection_path.startswith('/'):
                    collection_path = collection_path[1:]

                # Skip root collection
                if collection_path == '':
                    logger.debug("PRIVACY: Skipping root collection")
                    continue

                # Scan each root collection
                logger.debug("PRIVACY: Scanning root collection: %r", collection_path)
                matches = self._scan_collection(collection, identity)
                logger.debug("PRIVACY: Found %d matches in root collection %r", len(matches), collection_path)
                all_matches.extend(matches)

                # Discover and scan sub-collections
                try:
                    # Ensure path starts with a slash for discover()
                    discover_path = "/" + collection_path if collection_path else "/"
                    sub_collections = list(self._storage.discover(discover_path, depth="1"))
                    logger.debug("PRIVACY: Found %d sub-collections under %r", len(sub_collections), discover_path)
                except Exception as e:
                    logger.error("PRIVACY: Error discovering sub-collections: %r", e)
                    raise

                # Try to get paths from sub-collection objects
                sub_paths = []
                for sub_collection in sub_collections:
                    # Try to get path from href first, then path attribute
                    sub_collection_path = getattr(sub_collection, 'href', None)
                    if sub_collection_path is None:
                        sub_collection_path = getattr(sub_collection, 'path', None)
                    if sub_collection_path is not None:
                        # Remove leading slash if present
                        if sub_collection_path.startswith('/'):
                            sub_collection_path = sub_collection_path[1:]
                        sub_paths.append(sub_collection_path)

                logger.debug("PRIVACY: Found sub-collections: %r", sub_paths)

                for sub_collection in sub_collections:
                    if not isinstance(sub_collection, CollectionPartGet):
                        logger.debug("PRIVACY: Skipping non-CollectionPartGet sub-collection: %r", sub_collection)
                        continue

                    # Get sub-collection path from href or path attribute
                    sub_collection_path = getattr(sub_collection, 'href', None)
                    if sub_collection_path is None:
                        sub_collection_path = getattr(sub_collection, 'path', None)
                    if sub_collection_path is None:
                        continue

                    # Remove leading slash if present
                    if sub_collection_path.startswith('/'):
                        sub_collection_path = sub_collection_path[1:]

                    logger.debug("PRIVACY: Scanning sub-collection: %r", sub_collection_path)
                    sub_matches = self._scan_collection(sub_collection, identity)
                    logger.debug("PRIVACY: Found %d matches in sub-collection %r", len(sub_matches), sub_collection_path)
                    all_matches.extend(sub_matches)

            # Update the index with the new matches
            if all_matches:
                logger.debug("PRIVACY: Updating index with %d new matches", len(all_matches))
                self._index[identity] = all_matches

        except Exception as e:
            logger.error("PRIVACY: Error during identity scan: %s", str(e), exc_info=True)
            raise

        logger.info("PRIVACY: Scan complete. Found %d total matches", len(all_matches))
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
