"""Hashing functions for privacy identifiers."""

import hashlib
import os
from typing import Optional

# Get salt from environment variable or use a default
SALT = os.environ.get('RADICALE_PRIVACY_SALT', 'default_salt_change_me')

def hash_identifier(identifier: str) -> str:
    """Hash an identifier (email or phone) for privacy.
    
    Args:
        identifier: The email address or phone number to hash.
        
    Returns:
        The hashed identifier.
    """
    # Normalize the identifier (lowercase, remove spaces)
    normalized = identifier.lower().strip()
    
    # Create a salted hash
    salted = f"{normalized}:{SALT}"
    return hashlib.sha256(salted.encode()).hexdigest()

def verify_identifier(identifier: str, hashed_id: str) -> bool:
    """Verify if an identifier matches a hashed value.
    
    Args:
        identifier: The email address or phone number to verify.
        hashed_id: The hashed identifier to check against.
        
    Returns:
        True if the identifier matches the hash, False otherwise.
    """
    return hash_identifier(identifier) == hashed_id 