import unittest
import os
from radicale.storage.database import DatabaseManager, UserSettings

class TestDatabaseManager(unittest.TestCase):
    def setUp(self):
        self.test_db_path = "test.db"
        self.db_manager = DatabaseManager(self.test_db_path)
        self.db_manager.init_db()

    def tearDown(self):
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)

    def test_create_user_settings(self):
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
        # Create test data
        settings = {"allow_name": True}
        self.db_manager.create_user_settings("test@example.com", settings)

        # Test retrieval
        user_settings = self.db_manager.get_user_settings("test@example.com")
        self.assertIsNotNone(user_settings)
        self.assertEqual(user_settings.identifier, "test@example.com")
        self.assertTrue(user_settings.allow_name)

    def test_update_user_settings(self):
        # Create test data
        initial_settings = {"allow_name": True}
        self.db_manager.create_user_settings("test@example.com", initial_settings)

        # Update settings
        new_settings = {"allow_name": False}
        updated = self.db_manager.update_user_settings("test@example.com", new_settings)
        self.assertIsNotNone(updated)
        self.assertFalse(updated.allow_name)

if __name__ == '__main__':
    unittest.main()