import os
import tempfile
from datetime import datetime

import pytest

from radicale import config
from radicale.privacy.database import PrivacyDatabase


@pytest.fixture
def db_manager():
    """Fixture to provide a database manager instance with a temp database file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db_path = os.path.join(tmpdir, "test.db")
        configuration = config.load()
        configuration.update({
            "privacy": {
                "database_path": test_db_path
            }
        }, "test")
        manager = PrivacyDatabase(configuration)
        manager.init_db()
        yield manager
        manager.close()


def test_create_user_settings(db_manager):
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
    user_settings = db_manager.create_user_settings("test@example.com", settings)
    assert user_settings is not None
    assert user_settings.identifier == "test@example.com"
    assert user_settings.allow_name is True
    assert user_settings.allow_email is False
    assert user_settings.allow_phone is True
    assert user_settings.allow_company is False
    assert user_settings.allow_title is True
    assert user_settings.allow_photo is False
    assert user_settings.allow_birthday is True
    assert user_settings.allow_address is False
    assert isinstance(user_settings.created_at, datetime)
    assert user_settings.updated_at is None  # No update yet


def test_create_user_settings_with_defaults(db_manager):
    """Test creating user settings with minimal fields (using defaults)."""
    settings = {"allow_name": False}  # Only specify one field
    user_settings = db_manager.create_user_settings("test@example.com", settings)
    assert user_settings is not None
    assert user_settings.identifier == "test@example.com"
    assert user_settings.allow_name is False
    # All other fields should have default values (True)
    assert user_settings.allow_email is True
    assert user_settings.allow_phone is True
    assert user_settings.allow_company is True
    assert user_settings.allow_title is True
    assert user_settings.allow_photo is True
    assert user_settings.allow_birthday is True
    assert user_settings.allow_address is True


def test_get_user_settings(db_manager):
    """Test retrieving user settings."""
    # Create test data
    settings = {"allow_name": True}
    db_manager.create_user_settings("test@example.com", settings)

    # Test retrieval
    user_settings = db_manager.get_user_settings("test@example.com")
    assert user_settings is not None
    assert user_settings.identifier == "test@example.com"
    assert user_settings.allow_name is True


def test_get_nonexistent_user_settings(db_manager):
    """Test retrieving settings for a non-existent user."""
    user_settings = db_manager.get_user_settings("nonexistent@example.com")
    assert user_settings is None


def test_update_user_settings(db_manager):
    """Test updating existing user settings."""
    # Create test data
    initial_settings = {"allow_name": True}
    db_manager.create_user_settings("test@example.com", initial_settings)

    # Update settings
    new_settings = {"allow_name": False, "allow_email": False}
    updated = db_manager.update_user_settings("test@example.com", new_settings)
    assert updated is not None
    assert updated.allow_name is False
    assert updated.allow_email is False
    assert updated.updated_at is not None  # Should have update timestamp


def test_update_nonexistent_user_settings(db_manager):
    """Test updating settings for a non-existent user."""
    new_settings = {"allow_name": False}
    updated = db_manager.update_user_settings("nonexistent@example.com", new_settings)
    assert updated is None


def test_create_duplicate_user_settings(db_manager):
    """Test creating settings for an existing user."""
    settings = {"allow_name": True}
    db_manager.create_user_settings("test@example.com", settings)

    # Attempt to create duplicate
    with pytest.raises(Exception):  # SQLAlchemy will raise an integrity error
        db_manager.create_user_settings("test@example.com", settings)


def test_update_timestamp(db_manager):
    """Test that updated_at timestamp is set on updates."""
    # Create initial settings
    settings = {"allow_name": True}
    user_settings = db_manager.create_user_settings("test@example.com", settings)
    assert user_settings.updated_at is None  # No update yet

    # Update settings
    new_settings = {"allow_name": False}
    updated = db_manager.update_user_settings("test@example.com", new_settings)
    assert updated.updated_at is not None  # Should have update timestamp
    assert isinstance(updated.updated_at, datetime)


def test_invalid_settings_field(db_manager):
    """Test handling of invalid settings field."""
    settings = {"invalid_field": True}
    with pytest.raises(Exception):  # SQLAlchemy will raise an error
        db_manager.create_user_settings("test@example.com", settings)


def test_delete_user_settings_success(db_manager):
    """Test successfully deleting user settings."""
    # First create settings
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
    db_manager.create_user_settings("test@example.com", settings)

    # Delete settings
    deleted = db_manager.delete_user_settings("test@example.com")
    assert deleted is True

    # Verify settings were deleted
    user_settings = db_manager.get_user_settings("test@example.com")
    assert user_settings is None


def test_delete_nonexistent_user_settings(db_manager):
    """Test deleting settings for a non-existent user."""
    deleted = db_manager.delete_user_settings("nonexistent@example.com")
    assert deleted is False


def test_delete_and_recreate_user_settings(db_manager):
    """Test that a user can be recreated after deletion."""
    # Create initial settings
    initial_settings = {"allow_name": True}
    db_manager.create_user_settings("test@example.com", initial_settings)

    # Delete settings
    deleted = db_manager.delete_user_settings("test@example.com")
    assert deleted is True

    # Create new settings
    new_settings = {"allow_name": False}
    user_settings = db_manager.create_user_settings("test@example.com", new_settings)
    assert user_settings is not None
    assert user_settings.identifier == "test@example.com"
    assert user_settings.allow_name is False


def test_default_settings_from_config(db_manager):
    """Test that default settings from config are properly applied."""
    # Create settings with no fields specified
    user_settings = db_manager.create_user_settings("test@example.com", {})

    # Verify each field matches the config default
    config = db_manager._configuration
    assert user_settings.allow_name == config.get("privacy", "default_allow_name")
    assert user_settings.allow_email == config.get("privacy", "default_allow_email")
    assert user_settings.allow_phone == config.get("privacy", "default_allow_phone")
    assert user_settings.allow_company == config.get("privacy", "default_allow_company")
    assert user_settings.allow_title == config.get("privacy", "default_allow_title")
    assert user_settings.allow_photo == config.get("privacy", "default_allow_photo")
    assert user_settings.allow_birthday == config.get("privacy", "default_allow_birthday")
    assert user_settings.allow_address == config.get("privacy", "default_allow_address")


def test_config_changes_affect_new_users(db_manager):
    """Test that changes to config defaults affect new users."""
    # Create initial user with current defaults
    db_manager.create_user_settings("user1@example.com", {})

    # Change config defaults
    db_manager._configuration.update({
        "privacy": {
            "default_allow_name": False,
            "default_allow_email": False
        }
    }, "test")

    # Create new user, should get new defaults
    user2 = db_manager.create_user_settings("user2@example.com", {})
    assert user2.allow_name is False
    assert user2.allow_email is False

    # Verify other fields still have their original defaults
    config = db_manager._configuration
    assert user2.allow_phone == config.get("privacy", "default_allow_phone")
    assert user2.allow_company == config.get("privacy", "default_allow_company")
    assert user2.allow_title == config.get("privacy", "default_allow_title")
    assert user2.allow_photo == config.get("privacy", "default_allow_photo")
    assert user2.allow_birthday == config.get("privacy", "default_allow_birthday")
    assert user2.allow_address == config.get("privacy", "default_allow_address")
