import os
import unittest
from datetime import datetime

from radicale.storage.database import DatabaseManager


class TestDatabaseManager(unittest.TestCase):
    def setUp(self):
        """Set up test environment before each test."""
        self.test_db_path = "test.db"
        self.db_manager = DatabaseManager(self.test_db_path)
        self.db_manager.init_db()

    def tearDown(self):
        """Clean up after each test."""
        # Close the database connection and cleanup resources
        self.db_manager.close()

        # Try to remove the test database file
        if os.path.exists(self.test_db_path):
            try:
                os.remove(self.test_db_path)
            except PermissionError:
                # If we can't delete, log a warning but don't fail the test
                import warnings
                warnings.warn(f"Could not delete test database file: {self.test_db_path}")

    def test_create_user_settings(self):
        """Test creating new user settings with all fields."""
        settings = {
            "allow_name": True,
            "allow_email": False,
            "allow_phone": True,
            "allow_company": False,
            "allow_title": True,
            "allow_photo": False,
            "allow_birthday": True,
            "allow_address": False
        }
        user_settings = self.db_manager.create_user_settings("test@example.com", settings)
        self.assertIsNotNone(user_settings)
        self.assertEqual(user_settings.identifier, "test@example.com")
        self.assertTrue(user_settings.allow_name)
        self.assertFalse(user_settings.allow_email)
        self.assertTrue(user_settings.allow_phone)
        self.assertFalse(user_settings.allow_company)
        self.assertTrue(user_settings.allow_title)
        self.assertFalse(user_settings.allow_photo)
        self.assertTrue(user_settings.allow_birthday)
        self.assertFalse(user_settings.allow_address)
        self.assertIsInstance(user_settings.created_at, datetime)
        self.assertIsNone(user_settings.updated_at)  # No update yet

    def test_create_user_settings_with_defaults(self):
        """Test creating user settings with minimal fields (using defaults)."""
        settings = {"allow_name": False}  # Only specify one field
        user_settings = self.db_manager.create_user_settings("test@example.com", settings)
        self.assertIsNotNone(user_settings)
        self.assertEqual(user_settings.identifier, "test@example.com")
        self.assertFalse(user_settings.allow_name)
        # All other fields should have default values (True)
        self.assertTrue(user_settings.allow_email)
        self.assertTrue(user_settings.allow_phone)
        self.assertTrue(user_settings.allow_company)
        self.assertTrue(user_settings.allow_title)
        self.assertTrue(user_settings.allow_photo)
        self.assertTrue(user_settings.allow_birthday)
        self.assertTrue(user_settings.allow_address)

    def test_get_user_settings(self):
        """Test retrieving user settings."""
        # Create test data
        settings = {"allow_name": True}
        self.db_manager.create_user_settings("test@example.com", settings)

        # Test retrieval
        user_settings = self.db_manager.get_user_settings("test@example.com")
        self.assertIsNotNone(user_settings)
        self.assertEqual(user_settings.identifier, "test@example.com")
        self.assertTrue(user_settings.allow_name)

    def test_get_nonexistent_user_settings(self):
        """Test retrieving settings for a non-existent user."""
        user_settings = self.db_manager.get_user_settings("nonexistent@example.com")
        self.assertIsNone(user_settings)

    def test_update_user_settings(self):
        """Test updating existing user settings."""
        # Create test data
        initial_settings = {"allow_name": True}
        self.db_manager.create_user_settings("test@example.com", initial_settings)

        # Update settings
        new_settings = {"allow_name": False, "allow_email": False}
        updated = self.db_manager.update_user_settings("test@example.com", new_settings)
        self.assertIsNotNone(updated)
        self.assertFalse(updated.allow_name)
        self.assertFalse(updated.allow_email)
        self.assertIsNotNone(updated.updated_at)  # Should have update timestamp

    def test_update_nonexistent_user_settings(self):
        """Test updating settings for a non-existent user."""
        new_settings = {"allow_name": False}
        updated = self.db_manager.update_user_settings("nonexistent@example.com", new_settings)
        self.assertIsNone(updated)

    def test_create_duplicate_user_settings(self):
        """Test creating settings for an existing user."""
        settings = {"allow_name": True}
        self.db_manager.create_user_settings("test@example.com", settings)

        # Attempt to create duplicate
        with self.assertRaises(Exception):  # SQLAlchemy will raise an integrity error
            self.db_manager.create_user_settings("test@example.com", settings)

    def test_update_timestamp(self):
        """Test that updated_at timestamp is set on updates."""
        # Create initial settings
        settings = {"allow_name": True}
        user_settings = self.db_manager.create_user_settings("test@example.com", settings)
        self.assertIsNone(user_settings.updated_at)  # No update yet

        # Update settings
        new_settings = {"allow_name": False}
        updated = self.db_manager.update_user_settings("test@example.com", new_settings)
        self.assertIsNotNone(updated.updated_at)  # Should have update timestamp
        self.assertIsInstance(updated.updated_at, datetime)

    def test_invalid_settings_field(self):
        """Test handling of invalid settings field."""
        settings = {"invalid_field": True}
        with self.assertRaises(Exception):  # SQLAlchemy will raise an error
            self.db_manager.create_user_settings("test@example.com", settings)


if __name__ == '__main__':
    unittest.main()
