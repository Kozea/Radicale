"""Unit tests for privacy modules."""

import os
import tempfile
import unittest

from radicale.config import Configuration
from radicale.privacy.hash import hash_identifier, verify_identifier
from radicale.privacy.settings import PrivacySettings
from radicale.privacy.storage import PrivacyStorage


class TestPrivacyHash(unittest.TestCase):
    """Test the hashing functions."""

    def setUp(self):
        """Set up test environment."""
        self.salt = "test_salt"

    def test_hash_identifier_normalization(self):
        """Test that identifiers are normalized before hashing."""
        # Test case insensitivity
        self.assertEqual(
            hash_identifier("Test@example.com", self.salt),
            hash_identifier("test@example.com", self.salt)
        )

        # Test whitespace removal
        self.assertEqual(
            hash_identifier(" test@example.com ", self.salt),
            hash_identifier("test@example.com", self.salt)
        )

        # Test phone number normalization
        self.assertEqual(
            hash_identifier(" +1 234 567 8900 ", self.salt),
            hash_identifier("+12345678900", self.salt)
        )

    def test_verify_identifier(self):
        """Test identifier verification."""
        identifier = "test@example.com"
        hashed = hash_identifier(identifier, self.salt)

        self.assertTrue(verify_identifier(identifier, hashed, self.salt))
        self.assertFalse(verify_identifier("wrong@example.com", hashed, self.salt))

    def test_hash_edge_cases(self):
        """Test edge cases for hashing."""
        # Test empty identifier
        with self.assertRaises(ValueError):
            hash_identifier("", self.salt)

        # Test very long identifier
        long_id = "a" * 1000
        hashed = hash_identifier(long_id, self.salt)
        self.assertTrue(verify_identifier(long_id, hashed, self.salt))

        # Test special characters
        special_id = "test+special@example.com"
        hashed = hash_identifier(special_id, self.salt)
        self.assertTrue(verify_identifier(special_id, hashed, self.salt))


class TestPrivacyStorage(unittest.TestCase):
    """Test the privacy storage."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        schema = {
            "storage": {"filesystem_folder": {"value": self.temp_dir, "type": str}},
            "privacy": {"salt": {"value": "test_salt", "type": str}}
        }
        self.config = Configuration(schema)
        self.storage = PrivacyStorage(self.config)

        # Create test settings
        self.test_settings = {
            "private_fields": ["photo", "birthday"],
            "allowed_fields": ["name", "email", "phone"],
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

    def test_storage_edge_cases(self):
        """Test edge cases for storage."""
        identifier = "test@example.com"

        # Test file permission issues
        settings_file = self.storage._get_settings_file(
            hash_identifier(identifier, self.storage.salt)
        )
        self.storage.save_settings(identifier, self.test_settings)
        os.chmod(settings_file, 0o444)  # Read-only
        self.assertFalse(self.storage.save_settings(identifier, self.test_settings))
        os.chmod(settings_file, 0o666)  # Restore permissions

        # Test corrupted JSON file
        with open(settings_file, "w") as f:
            f.write("invalid json")
        self.assertIsNone(self.storage.get_settings(identifier))

        # Test very large settings file
        large_settings = {
            "private_fields": ["photo"] * 1000,
            "allowed_fields": ["name"] * 1000,
        }
        self.assertTrue(self.storage.save_settings(identifier, large_settings))
        retrieved = self.storage.get_settings(identifier)
        self.assertEqual(retrieved, large_settings)

        # Test invalid JSON content
        with open(settings_file, "w") as f:
            f.write('{"invalid": "json"')  # Missing closing brace
        self.assertIsNone(self.storage.get_settings(identifier))


class TestPrivacySettings(unittest.TestCase):
    """Test the privacy settings manager."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        schema = {
            "storage": {"filesystem_folder": {"value": self.temp_dir, "type": str}},
            "privacy": {"salt": {"value": "test_salt", "type": str}}
        }
        self.config = Configuration(schema)
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
            self.settings.set_settings(identifier, ["invalid_field"])

        # Test invalid allowed fields
        with self.assertRaises(ValueError):
            self.settings.set_settings(identifier, [], ["invalid_field"])

        # Test overlap between private and allowed fields
        with self.assertRaises(ValueError):
            self.settings.set_settings(identifier, ["email"], ["email", "phone"])

    def test_field_privacy_checks(self):
        """Test field privacy checks."""
        identifier = "test@example.com"

        # Set some private fields
        self.settings.set_settings(identifier, ["photo", "birthday"])

        # Test private fields
        self.assertTrue(self.settings.is_field_private(identifier, "photo"))
        self.assertTrue(self.settings.is_field_private(identifier, "birthday"))
        self.assertFalse(self.settings.is_field_private(identifier, "name"))

        # Test allowed fields
        self.assertTrue(self.settings.is_field_allowed(identifier, "name"))
        self.assertTrue(self.settings.is_field_allowed(identifier, "email"))
        self.assertFalse(self.settings.is_field_allowed(identifier, "photo"))

    def test_get_fields(self):
        """Test getting private and allowed fields."""
        identifier = "test@example.com"
        private_fields = ["photo", "birthday"]
        allowed_fields = ["name", "email", "phone"]

        # Set settings
        self.settings.set_settings(identifier, private_fields, allowed_fields)

        # Test getting private fields
        self.assertEqual(
            self.settings.get_private_fields(identifier), set(private_fields)
        )

        # Test getting allowed fields
        self.assertEqual(
            self.settings.get_allowed_fields(identifier), set(allowed_fields)
        )

        # Test non-existent settings
        self.assertEqual(
            self.settings.get_private_fields("nonexistent@example.com"), set()
        )
        self.assertEqual(
            self.settings.get_allowed_fields("nonexistent@example.com"),
            self.settings.ALL_FIELDS,
        )

    def test_settings_edge_cases(self):
        """Test edge cases for settings."""
        identifier = "test@example.com"

        # Test empty field lists
        self.settings.set_settings(identifier, [], [])
        self.assertEqual(self.settings.get_private_fields(identifier), set())
        self.assertEqual(self.settings.get_allowed_fields(identifier), set())

        # Test all fields private
        all_fields = list(self.settings.ALL_FIELDS)
        self.settings.set_settings(identifier, all_fields)
        self.assertEqual(self.settings.get_private_fields(identifier), set(all_fields))
        self.assertEqual(self.settings.get_allowed_fields(identifier), set())

        # Test all fields allowed
        self.settings.set_settings(identifier, [], all_fields)
        self.assertEqual(self.settings.get_private_fields(identifier), set())
        self.assertEqual(self.settings.get_allowed_fields(identifier), set(all_fields))

        # Test duplicate fields
        self.settings.set_settings(identifier, ["photo", "photo"], ["name", "name"])
        self.assertEqual(self.settings.get_private_fields(identifier), {"photo"})
        self.assertEqual(self.settings.get_allowed_fields(identifier), {"name"})

        # Test case sensitivity in field names
        self.settings.set_settings(identifier, ["photo"], ["name"])
        self.assertTrue(self.settings.is_field_private(identifier, "photo"))
        self.assertTrue(self.settings.is_field_allowed(identifier, "name"))
