import os
import unittest

from radicale.storage.database import DatabaseManager


class TestDatabaseManager(unittest.TestCase):
    def setUp(self):
        """Set up test environment before each test."""
        self.test_db_path = "test.db"
        self.db_manager = DatabaseManager(self.test_db_path)
        self.db_manager.init_db()

    def tearDown(self):
        """Clean up after each test."""
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)

    def test_create_user_settings(self):
        """Test creating new user settings."""
        settings = {
            "allow_name": True,
            "allow_email": False,
            "allow_phone": True
        }
        user_settings = self.db_manager.create_user_settings("test@example.com", settings)
        self.assertIsNotNone(user_settings)
        self.assertEqual(user_settings.identifier, "test@example.com")
        self.assertTrue(user_settings.allow_name)
        self.assertFalse(user_settings.allow_email)
        self.assertTrue(user_settings.allow_phone)

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

    def test_update_user_settings(self):
        """Test updating existing user settings."""
        # Create test data
        initial_settings = {"allow_name": True}
        self.db_manager.create_user_settings("test@example.com", initial_settings)

        # Update settings
        new_settings = {"allow_name": False}
        updated = self.db_manager.update_user_settings("test@example.com", new_settings)
        self.assertIsNotNone(updated)
        self.assertFalse(updated.allow_name)

    def test_get_nonexistent_user_settings(self):
        """Test retrieving settings for a non-existent user."""
        user_settings = self.db_manager.get_user_settings("nonexistent@example.com")
        self.assertIsNone(user_settings)

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


if __name__ == '__main__':
    unittest.main()
