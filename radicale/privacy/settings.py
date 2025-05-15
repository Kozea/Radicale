"""Privacy settings management."""

from typing import Dict, List, Optional, Set

from .storage import PrivacyStorage


class PrivacySettings:
    """Manage privacy settings for users."""

    # All possible vCard fields that can be private
    ALL_FIELDS = {
        "name",
        "email",
        "phone",
        "company",
        "title",
        "photo",
        "birthday",
        "address",
    }

    def __init__(self, storage: PrivacyStorage):
        """Initialize the privacy settings manager.

        Args:
            storage: The privacy settings storage instance.
        """
        self.storage = storage

    def get_settings(self, identifier: str) -> Optional[Dict]:
        """Get privacy settings for an identifier.

        Args:
            identifier: The email or phone number.

        Returns:
            The privacy settings dictionary or None if not found.
        """
        return self.storage.get_settings(identifier)

    def set_settings(
        self,
        identifier: str,
        private_fields: List[str],
        allowed_fields: Optional[List[str]] = None,
    ) -> bool:
        """Set privacy settings for an identifier.

        Args:
            identifier: The email or phone number.
            private_fields: List of fields that should be private.
            allowed_fields: List of fields that are allowed to be stored.
            If None, all non-private fields are allowed.

        Returns:
            True if successful, False otherwise.
        """
        # Validate fields
        private_set = set(private_fields)
        if not private_set.issubset(self.ALL_FIELDS):
            invalid = private_set - self.ALL_FIELDS
            raise ValueError(f"Invalid private fields: {invalid}")

        if allowed_fields is not None:
            allowed_set = set(allowed_fields)
            if not allowed_set.issubset(self.ALL_FIELDS):
                invalid = allowed_set - self.ALL_FIELDS
                raise ValueError(f"Invalid allowed fields: {invalid}")

            # Check for overlap
            overlap = private_set.intersection(allowed_set)
            if overlap:
                raise ValueError(
                    f"Fields cannot be both private and allowed: {overlap}"
                )
        else:
            allowed_set = self.ALL_FIELDS - private_set

        settings = {
            "private_fields": list(private_set),
            "allowed_fields": list(allowed_set),
        }

        return self.storage.save_settings(identifier, settings)

    def delete_settings(self, identifier: str) -> bool:
        """Delete privacy settings for an identifier.

        Args:
            identifier: The email or phone number.

        Returns:
            True if successful, False otherwise.
        """
        return self.storage.delete_settings(identifier)

    def is_field_private(self, identifier: str, field: str) -> bool:
        """Check if a field is private for an identifier.

        Args:
            identifier: The email or phone number.
            field: The field to check.

        Returns:
            True if the field is private, False otherwise.
        """
        settings = self.get_settings(identifier)
        if not settings:
            return False

        return field in settings.get("private_fields", [])

    def is_field_allowed(self, identifier: str, field: str) -> bool:
        """Check if a field is allowed to be stored for an identifier.

        Args:
            identifier: The email or phone number.
            field: The field to check.

        Returns:
            True if the field is allowed, False otherwise.
        """
        settings = self.get_settings(identifier)
        if not settings:
            return True  # If no settings, everything is allowed

        return field in settings.get("allowed_fields", [])

    def get_private_fields(self, identifier: str) -> Set[str]:
        """Get all private fields for an identifier.

        Args:
            identifier: The email or phone number.

        Returns:
            Set of private fields.
        """
        settings = self.get_settings(identifier)
        if not settings:
            return set()

        return set(settings.get("private_fields", []))

    def get_allowed_fields(self, identifier: str) -> Set[str]:
        """Get all allowed fields for an identifier.

        Args:
            identifier: The email or phone number.

        Returns:
            Set of allowed fields.
        """
        settings = self.get_settings(identifier)
        if not settings:
            return self.ALL_FIELDS  # If no settings, everything is allowed

        return set(settings.get("allowed_fields", []))
