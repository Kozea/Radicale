"""Privacy module initialization."""

import logging
from typing import Sequence

from radicale import config
from .settings import PrivacySettings
from .storage import PrivacyStorage

logger = logging.getLogger(__name__)

__all__ = ["PrivacySettings", "PrivacyStorage"]

INTERNAL_TYPES: Sequence[str] = ("filesystem")

def load(configuration: config.Configuration) -> PrivacySettings:
    """Load the privacy module."""
    logger.debug("Loading privacy module")
    storage = PrivacyStorage(configuration)
    return PrivacySettings(storage)
