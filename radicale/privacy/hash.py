"""Hashing functions for privacy identifiers."""

import hashlib
import re


def normalize_phone(phone: str) -> str:
    """Normalize a phone number by removing all non-digit characters except +.

    Args:
        phone: The phone number to normalize.

    Returns:
        The normalized phone number.
    """
    # Keep the + if it's at the start
    has_plus = phone.startswith("+")
    # Remove all non-digit characters
    digits = re.sub(r"\D", "", phone)
    # Add back the + if it was there
    return "+" + digits if has_plus else digits


def hash_identifier(identifier: str, salt: str) -> str:
    """Hash an identifier (email or phone) for privacy.

    Args:
        identifier: The email address or phone number to hash.
        salt: The salt to use for hashing.

    Returns:
        The hashed identifier.

    Raises:
        ValueError: If the identifier is empty.
    """
    if not identifier:
        raise ValueError("Identifier cannot be empty")

    # Normalize the identifier (lowercase, remove spaces)
    normalized = identifier.lower().strip()

    # If it looks like a phone number, normalize it
    if re.match(r"^\+?[\d\s-]+$", normalized):
        normalized = normalize_phone(normalized)

    # Create a salted hash
    salted = f"{normalized}:{salt}"
    return hashlib.sha256(salted.encode()).hexdigest()


def verify_identifier(identifier: str, hashed_id: str, salt: str) -> bool:
    """Verify if an identifier matches a hashed value.

    Args:
        identifier: The email address or phone number to verify.
        hashed_id: The hashed identifier to check against.
        salt: The salt used for hashing.

    Returns:
        True if the identifier matches the hash, False otherwise.
    """
    try:
        return hash_identifier(identifier, salt) == hashed_id
    except ValueError:
        return False
