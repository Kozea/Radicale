"""
Tests for the privacy API endpoints.
"""

import json
import os
import tempfile
from http import client

import pytest

from radicale import config
from radicale.privacy.api import PrivacyAPI


@pytest.fixture
def api():
    """Fixture to provide a privacy API instance with a temp database file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db_path = os.path.join(tmpdir, "test.db")
        configuration = config.load()
        configuration.update({
            "privacy": {
                "database_path": test_db_path
            }
        }, "test")
        api = PrivacyAPI(configuration)
        api._privacy_db.init_db()  # Initialize the database
        yield api
        api._privacy_db.close()  # Clean up database connections


def test_get_settings_not_found(api):
    """Test getting settings for a non-existent user."""
    status, headers, response = api.get_settings("nonexistent@example.com")
    assert status == client.NOT_FOUND


def test_get_settings_unauthorized(api):
    """Test getting settings without a user."""
    status, headers, response = api.get_settings("")
    assert status == client.BAD_REQUEST
    response_data = json.loads(response)
    assert "error" in response_data
    assert "User identifier is required" in response_data["error"]


def test_create_settings_success(api):
    """Test creating settings successfully."""
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
    status, headers, response = api.create_settings("test@example.com", settings)
    assert status == client.CREATED
    assert json.loads(response) == {"status": "created"}

    # Verify settings were created
    status, headers, response = api.get_settings("test@example.com")
    assert status == client.OK
    assert json.loads(response) == settings


def test_create_settings_missing_fields(api):
    """Test creating settings with missing fields."""
    settings = {
        "allow_name": True,
        "allow_email": False
    }
    status, headers, response = api.create_settings("test@example.com", settings)
    assert status == client.BAD_REQUEST
    response_data = json.loads(response)
    assert "error" in response_data
    assert "required_fields" in response_data


def test_create_settings_invalid_types(api):
    """Test creating settings with invalid field types."""
    settings = {
        "allow_name": "true",  # Should be boolean
        "allow_email": False,
        "allow_phone": True,
        "allow_company": False,
        "allow_title": True,
        "allow_photo": False,
        "allow_birthday": True,
        "allow_address": False
    }
    status, headers, response = api.create_settings("test@example.com", settings)
    assert status == client.BAD_REQUEST
    response_data = json.loads(response)
    assert "error" in response_data
    assert "boolean values" in response_data["error"]


def test_update_settings_success(api):
    """Test updating settings successfully."""
    # First create settings
    initial_settings = {
        "allow_name": True,
        "allow_email": True,
        "allow_phone": True,
        "allow_company": True,
        "allow_title": True,
        "allow_photo": True,
        "allow_birthday": True,
        "allow_address": True
    }
    api.create_settings("test@example.com", initial_settings)

    # Then update some settings
    update_settings = {
        "allow_email": False,
        "allow_photo": False
    }
    status, headers, response = api.update_settings("test@example.com", update_settings)
    assert status == client.OK
    assert json.loads(response) == {"status": "updated"}

    # Verify settings were updated
    status, headers, response = api.get_settings("test@example.com")
    assert status == client.OK
    updated_settings = json.loads(response)
    assert updated_settings["allow_email"] is False
    assert updated_settings["allow_photo"] is False
    assert updated_settings["allow_name"] is True  # Unchanged


def test_update_settings_not_found(api):
    """Test updating settings for a non-existent user."""
    settings = {"allow_name": False}
    status, headers, response = api.update_settings("nonexistent@example.com", settings)
    assert status == client.NOT_FOUND


def test_update_settings_invalid_fields(api):
    """Test updating settings with invalid field names."""
    settings = {"invalid_field": True}
    status, headers, response = api.update_settings("test@example.com", settings)
    assert status == client.BAD_REQUEST
    response_data = json.loads(response)
    assert "error" in response_data
    assert "valid_fields" in response_data


def test_update_settings_empty(api):
    """Test updating settings with an empty dictionary."""
    status, headers, response = api.update_settings("test@example.com", {})
    assert status == client.BAD_REQUEST
    response_data = json.loads(response)
    assert "error" in response_data
    assert "No settings provided" in response_data["error"]


def test_update_settings_unauthorized(api):
    """Test updating settings without a user."""
    settings = {"allow_name": False}
    status, headers, response = api.update_settings("", settings)
    assert status == client.BAD_REQUEST
    response_data = json.loads(response)
    assert "error" in response_data
    assert "User identifier is required" in response_data["error"]


def test_delete_settings_success(api):
    """Test deleting settings successfully."""
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
    api.create_settings("test@example.com", settings)

    # Delete settings
    status, headers, response = api.delete_settings("test@example.com")
    assert status == client.OK
    assert json.loads(response) == {"status": "deleted"}

    # Verify settings were deleted
    status, headers, response = api.get_settings("test@example.com")
    assert status == client.NOT_FOUND


def test_delete_settings_not_found(api):
    """Test deleting settings for a non-existent user."""
    status, headers, response = api.delete_settings("nonexistent@example.com")
    assert status == client.NOT_FOUND


def test_delete_settings_unauthorized(api):
    """Test deleting settings without a user."""
    status, headers, response = api.delete_settings("")
    assert status == client.BAD_REQUEST
    response_data = json.loads(response)
    assert "error" in response_data
    assert "User identifier is required" in response_data["error"]


def test_validate_user_identifier_email(api):
    """Test email validation."""
    # Valid emails
    status, headers, response = api.get_settings("test@example.com")
    assert status == client.NOT_FOUND  # Not found is OK, we're just testing validation

    status, headers, response = api.get_settings("user.name@domain.co.uk")
    assert status == client.NOT_FOUND

    # Invalid emails
    status, headers, response = api.get_settings("invalid.email")
    assert status == client.BAD_REQUEST
    response_data = json.loads(response)
    assert "error" in response_data
    assert "Invalid identifier format" in response_data["error"]

    status, headers, response = api.get_settings("@domain.com")
    assert status == client.BAD_REQUEST
    response_data = json.loads(response)
    assert "error" in response_data
    assert "Invalid email format" in response_data["error"]

    status, headers, response = api.get_settings("user@")
    assert status == client.BAD_REQUEST
    response_data = json.loads(response)
    assert "error" in response_data
    assert "Invalid email format" in response_data["error"]


def test_validate_user_identifier_phone(api):
    """Test phone number validation."""
    # Valid phone numbers - these should pass validation but return NOT_FOUND
    # since they don't exist in the database
    status, headers, response = api.get_settings("+1234567890")
    assert status == client.NOT_FOUND

    status, headers, response = api.get_settings("+1-234-567-8900")
    assert status == client.NOT_FOUND

    status, headers, response = api.get_settings("+(123) 456-7890")
    assert status == client.NOT_FOUND

    # Invalid phone numbers - these should fail validation
    status, headers, response = api.get_settings("(123) 456-7890") # Missing +
    assert status == client.BAD_REQUEST
    response_data = json.loads(response)
    assert "error" in response_data
    assert "Invalid identifier format" in response_data["error"]

    status, headers, response = api.get_settings("1234567890")  # Missing +
    assert status == client.BAD_REQUEST
    response_data = json.loads(response)
    assert "error" in response_data
    assert "Invalid identifier format" in response_data["error"]

    status, headers, response = api.get_settings("+123")  # Too short
    assert status == client.BAD_REQUEST
    response_data = json.loads(response)
    assert "error" in response_data
    assert "Invalid identifier format" in response_data["error"]

    status, headers, response = api.get_settings("+1234567890123456")  # Too long
    assert status == client.BAD_REQUEST
    response_data = json.loads(response)
    assert "error" in response_data
    assert "Invalid identifier format" in response_data["error"]

    # Invalid identifiers (not email and not phone)
    status, headers, response = api.get_settings("justtext")
    assert status == client.BAD_REQUEST
    response_data = json.loads(response)
    assert "error" in response_data
    assert "Invalid identifier format" in response_data["error"]

    status, headers, response = api.get_settings("user.name")
    assert status == client.BAD_REQUEST
    response_data = json.loads(response)
    assert "error" in response_data
    assert "Invalid identifier format" in response_data["error"]

    status, headers, response = api.get_settings("123-456")  # Not a valid phone format
    assert status == client.BAD_REQUEST
    response_data = json.loads(response)
    assert "error" in response_data
    assert "Invalid identifier format" in response_data["error"]


def test_validate_user_identifier_empty(api):
    """Test empty user identifier validation."""
    status, headers, response = api.get_settings("")
    assert status == client.BAD_REQUEST
    response_data = json.loads(response)
    assert "error" in response_data
    assert "User identifier is required" in response_data["error"]
