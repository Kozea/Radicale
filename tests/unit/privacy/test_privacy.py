"""Unit tests for privacy modules."""

import os
import json
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from radicale.config import Configuration
from radicale.privacy.storage import PrivacyStorage
from radicale.privacy.hash import hash_identifier, verify_identifier
from radicale.privacy.settings import PrivacySettings

class TestPrivacyHash(unittest.TestCase):
    """Test the hashing functions."""

    def test_hash_identifier_normalization(self):
        """Test that identifiers are normalized before hashing."""
        # Test case insensitivity
        self.assertEqual(
            hash_identifier("Test@example.com"),
            hash_identifier("test@example.com")
        )
        
        # Test whitespace removal
        self.assertEqual(
            hash_identifier(" test@example.com "),
            hash_identifier("test@example.com")
        )
        
        # Test phone number normalization
        self.assertEqual(
            hash_identifier(" +1 234 567 8900 "),
            hash_identifier("+12345678900")
        )

    def test_verify_identifier(self):
        """Test identifier verification."""
        identifier = "test@example.com"
        hashed = hash_identifier(identifier)
        
        self.assertTrue(verify_identifier(identifier, hashed))
        self.assertFalse(verify_identifier("wrong@example.com", hashed))

class TestPrivacyStorage(unittest.TestCase):
    """Test the privacy storage."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.config = Configuration()
        self.config.set('storage', 'filesystem_folder', self.temp_dir)
        self.storage = PrivacyStorage(self.config)
        
        # Create test settings
        self.test_settings = {
            'private_fields': ['photo', 'birthday'],
            'allowed_fields': ['name', 'email', 'phone']
        }

    def tearDown(self):
        """Clean up test environment."""
        for root, dirs, files in os.walk(self.temp_dir, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))
        os.rmdir(self.temp_dir)

    def test_save_and_get_settings(self):
        """Test saving and retrieving settings."""
        identifier = "test@example.com"
        
        # Test saving settings
        self.assertTrue(self.storage.save_settings(identifier, self.test_settings))
        
        # Test retrieving settings
        retrieved = self.storage.get_settings(identifier)
        self.assertEqual(retrieved, self.test_settings)
        
        # Test non-existent settings
        self.assertIsNone(self.storage.get_settings("nonexistent@example.com"))

    def test_delete_settings(self):
        """Test deleting settings."""
        identifier = "test@example.com"
        
        # Save settings first
        self.storage.save_settings(identifier, self.test_settings)
        
        # Test deletion
        self.assertTrue(self.storage.delete_settings(identifier))
        self.assertIsNone(self.storage.get_settings(identifier))
        
        # Test deleting non-existent settings
        self.assertTrue(self.storage.delete_settings("nonexistent@example.com"))

    def test_get_all_settings(self):
        """Test retrieving all settings."""
        # Save multiple settings
        self.storage.save_settings("test1@example.com", self.test_settings)
        self.storage.save_settings("test2@example.com", self.test_settings)
        
        # Test retrieving all settings
        all_settings = self.storage.get_all_settings()
        self.assertEqual(len(all_settings), 2)
        
        # Verify settings content
        for settings in all_settings.values():
            self.assertEqual(settings, self.test_settings)

class TestPrivacySettings(unittest.TestCase):
    """Test the privacy settings manager."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.config = Configuration()
        self.config.set('storage', 'filesystem_folder', self.temp_dir)
        self.storage = PrivacyStorage(self.config)
        self.settings = PrivacySettings(self.storage)

    def tearDown(self):
        """Clean up test environment."""
        for root, dirs, files in os.walk(self.temp_dir, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))
        os.rmdir(self.temp_dir)

    def test_set_settings_validation(self):
        """Test settings validation."""
        identifier = "test@example.com"
        
        # Test invalid private fields
        with self.assertRaises(ValueError):
            self.settings.set_settings(identifier, ['invalid_field'])
            
        # Test invalid allowed fields
        with self.assertRaises(ValueError):
            self.settings.set_settings(identifier, [], ['invalid_field'])
            
        # Test overlap between private and allowed fields
        with self.assertRaises(ValueError):
            self.settings.set_settings(
                identifier,
                ['email'],
                ['email', 'phone']
            )

    def test_field_privacy_checks(self):
        """Test field privacy checks."""
        identifier = "test@example.com"
        
        # Set some private fields
        self.settings.set_settings(identifier, ['photo', 'birthday'])
        
        # Test private fields
        self.assertTrue(self.settings.is_field_private(identifier, 'photo'))
        self.assertTrue(self.settings.is_field_private(identifier, 'birthday'))
        self.assertFalse(self.settings.is_field_private(identifier, 'name'))
        
        # Test allowed fields
        self.assertTrue(self.settings.is_field_allowed(identifier, 'name'))
        self.assertTrue(self.settings.is_field_allowed(identifier, 'email'))
        self.assertFalse(self.settings.is_field_allowed(identifier, 'photo'))

    def test_get_fields(self):
        """Test getting private and allowed fields."""
        identifier = "test@example.com"
        private_fields = ['photo', 'birthday']
        allowed_fields = ['name', 'email', 'phone']
        
        # Set settings
        self.settings.set_settings(identifier, private_fields, allowed_fields)
        
        # Test getting private fields
        self.assertEqual(
            self.settings.get_private_fields(identifier),
            set(private_fields)
        )
        
        # Test getting allowed fields
        self.assertEqual(
            self.settings.get_allowed_fields(identifier),
            set(allowed_fields)
        )
        
        # Test non-existent settings
        self.assertEqual(self.settings.get_private_fields("nonexistent@example.com"), set())
        self.assertEqual(
            self.settings.get_allowed_fields("nonexistent@example.com"),
            self.settings.ALL_FIELDS
        ) 