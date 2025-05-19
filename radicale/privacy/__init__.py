"""
Privacy module for Radicale.

This module handles privacy settings for users.
"""

from typing import Optional

from radicale import config
from radicale.log import logger

from .database import PrivacyDatabase

INTERNAL_TYPES = ("database",)


def load(configuration: "config.Configuration") -> Optional[PrivacyDatabase]:
    """Load the privacy module.

    Args:
        configuration: The Radicale configuration object

    Returns:
        The privacy database object
    """
    privacy_type = configuration.get("privacy", "type")
    if privacy_type not in INTERNAL_TYPES:
        logger.error("Unknown privacy type: %r", privacy_type)
        return None
    else:
        logger.info("privacy type is %r", privacy_type)

    database = PrivacyDatabase(configuration)
    database.init_db()
    logger.info("Privacy database path: %r", database._database_path)
    return database
