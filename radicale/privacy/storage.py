"""Storage for privacy settings."""

import os
import json
import logging
from typing import Dict, List, Optional, Set
from ..config import Configuration
from .hash import hash_identifier

logger = logging.getLogger(__name__)

class PrivacyStorage:
    """Storage for privacy settings."""

    def __init__(self, configuration: Configuration):
        """Initialize the privacy storage.
        
        Args:
            configuration: The Radicale configuration object.
        """
        self.configuration = configuration
        self.settings_dir = os.path.join(
            configuration.get('storage', 'filesystem_folder'),
            '.Radicale.privacy'
        )
        os.makedirs(self.settings_dir, exist_ok=True)

    def _get_settings_file(self, hashed_id: str) -> str:
        """Get the path to the settings file for a hashed identifier.
        
        Args:
            hashed_id: The hashed identifier (email or phone).
            
        Returns:
            The path to the settings file.
        """
        return os.path.join(self.settings_dir, f"{hashed_id}.json")

    def get_settings(self, identifier: str) -> Optional[Dict]:
        """Get privacy settings for an identifier.
        
        Args:
            identifier: The email or phone number.
            
        Returns:
            The privacy settings dictionary or None if not found.
        """
        hashed_id = hash_identifier(identifier)
        settings_file = self._get_settings_file(hashed_id)
        
        if not os.path.exists(settings_file):
            return None
            
        try:
            with open(settings_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error("Failed to read privacy settings for %s: %s", 
                        identifier, str(e))
            return None

    def save_settings(self, identifier: str, settings: Dict) -> bool:
        """Save privacy settings for an identifier.
        
        Args:
            identifier: The email or phone number.
            settings: The privacy settings dictionary.
            
        Returns:
            True if successful, False otherwise.
        """
        hashed_id = hash_identifier(identifier)
        settings_file = self._get_settings_file(hashed_id)
        
        try:
            with open(settings_file, 'w') as f:
                json.dump(settings, f, indent=2)
            return True
        except IOError as e:
            logger.error("Failed to save privacy settings for %s: %s",
                        identifier, str(e))
            return False

    def delete_settings(self, identifier: str) -> bool:
        """Delete privacy settings for an identifier.
        
        Args:
            identifier: The email or phone number.
            
        Returns:
            True if successful, False otherwise.
        """
        hashed_id = hash_identifier(identifier)
        settings_file = self._get_settings_file(hashed_id)
        
        if not os.path.exists(settings_file):
            return True
            
        try:
            os.remove(settings_file)
            return True
        except IOError as e:
            logger.error("Failed to delete privacy settings for %s: %s",
                        identifier, str(e))
            return False

    def get_all_settings(self) -> Dict[str, Dict]:
        """Get all privacy settings.
        
        Returns:
            A dictionary mapping hashed identifiers to their settings.
        """
        settings = {}
        for filename in os.listdir(self.settings_dir):
            if not filename.endswith('.json'):
                continue
                
            try:
                with open(os.path.join(self.settings_dir, filename), 'r') as f:
                    settings[filename[:-5]] = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.error("Failed to read privacy settings file %s: %s",
                            filename, str(e))
                
        return settings 