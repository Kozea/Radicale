"""
Tests for the privacy API endpoints.
"""

import json
import os
import tempfile
from http import client
from unittest.mock import patch

import pytest
import vobject

from radicale import config, storage
from radicale.item import Item
from radicale.privacy.api import PrivacyAPI, PrivacyScanner


@pytest.fixture
def mock_time_ranges():
    """Mock the time ranges function to avoid AttributeError: value."""
    with patch('radicale.item.filter.visit_time_ranges') as mock:
        mock.return_value = (None, None)  # Return no time range
        yield mock


@pytest.fixture
def api(mock_time_ranges):
    """Fixture to provide a privacy API instance with a temp database file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db_path = os.path.join(tmpdir, "test.db")

        # Create collection-root directory
        collection_root = os.path.join(tmpdir, "collection-root")
        os.makedirs(collection_root, exist_ok=True)

        configuration = config.load()
        configuration.update({
            "privacy": {
                "database_path": test_db_path
            },
            "storage": {
                "type": "multifilesystem",
                "filesystem_folder": tmpdir  # Use tmpdir as base, let storage add collection-root
            }
        }, "test")

        # Initialize storage
        storage_instance = storage.load(configuration)

        # Create API with storage instance
        api = PrivacyAPI(configuration)
        api._privacy_db.init_db()  # Initialize the database

        # Reset scanner singleton and create new instance
        PrivacyScanner.reset()
        api._scanner = PrivacyScanner(storage_instance)  # Initialize scanner with storage instance

        try:
            yield api
        finally:
            # Properly clean up SQLAlchemy resources
            if hasattr(api, '_privacy_db'):
                # Close all sessions
                api._privacy_db.Session.remove()
                # Dispose of the engine
                api._privacy_db.engine.dispose()
                # Close the database
                api._privacy_db.close()

            # On Windows, we need to be extra careful about file handles
            if os.name == 'nt':
                import gc
                import time

                # Force garbage collection to help release file handles
                gc.collect()
                # Give Windows time to release file handles
                time.sleep(0.5)

                # Try to explicitly close any remaining file handles
                try:
                    if hasattr(api, '_privacy_db') and hasattr(api._privacy_db, 'engine'):
                        api._privacy_db.engine.dispose()
                except Exception:
                    pass

                # Force another garbage collection
                gc.collect()
                time.sleep(0.5)


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
        "disallow_name": False,
        "disallow_email": True,
        "disallow_phone": False,
        "disallow_company": True,
        "disallow_title": False,
        "disallow_photo": True,
        "disallow_birthday": False,
        "disallow_address": True
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
        "disallow_name": False,
        "disallow_email": True
    }
    status, headers, response = api.create_settings("test@example.com", settings)
    assert status == client.BAD_REQUEST
    response_data = json.loads(response)
    assert "error" in response_data
    assert "required_fields" in response_data


def test_create_settings_invalid_types(api):
    """Test creating settings with invalid field types."""
    settings = {
        "disallow_name": "false",  # Should be boolean
        "disallow_email": True,
        "disallow_phone": False,
        "disallow_company": True,
        "disallow_title": False,
        "disallow_photo": True,
        "disallow_birthday": False,
        "disallow_address": True
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
        "disallow_name": False,
        "disallow_email": False,
        "disallow_phone": False,
        "disallow_company": False,
        "disallow_title": False,
        "disallow_photo": False,
        "disallow_birthday": False,
        "disallow_address": False
    }
    api.create_settings("test@example.com", initial_settings)

    # Then update some settings
    update_settings = {
        "disallow_email": True,
        "disallow_photo": True
    }
    status, headers, response = api.update_settings("test@example.com", update_settings)
    assert status == client.OK
    assert json.loads(response) == {"status": "updated"}

    # Verify settings were updated
    status, headers, response = api.get_settings("test@example.com")
    assert status == client.OK
    updated_settings = json.loads(response)
    assert updated_settings["disallow_email"] is True
    assert updated_settings["disallow_photo"] is True
    assert updated_settings["disallow_name"] is False  # Unchanged


def test_update_settings_not_found(api):
    """Test updating settings for a non-existent user."""
    settings = {"disallow_name": True}
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
    settings = {"disallow_name": True}
    status, headers, response = api.update_settings("", settings)
    assert status == client.BAD_REQUEST
    response_data = json.loads(response)
    assert "error" in response_data
    assert "User identifier is required" in response_data["error"]


def test_delete_settings_success(api):
    """Test deleting settings successfully."""
    # First create settings
    settings = {
        "disallow_name": False,
        "disallow_email": True,
        "disallow_phone": False,
        "disallow_company": True,
        "disallow_title": False,
        "disallow_photo": True,
        "disallow_birthday": False,
        "disallow_address": True
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


def test_get_matching_cards_not_found(api):
    """Test getting matching cards for a non-existent user."""
    status, headers, response = api.get_matching_cards("nonexistent@example.com")
    assert status == client.NOT_FOUND


def test_get_matching_cards_unauthorized(api):
    """Test getting matching cards without a user."""
    status, headers, response = api.get_matching_cards("")
    assert status == client.BAD_REQUEST
    response_data = json.loads(response)
    assert "error" in response_data
    assert "User identifier is required" in response_data["error"]


def test_get_matching_cards_no_matches(api):
    """Test getting matching cards when no matches exist."""
    # First create settings for the user
    settings = {
        "disallow_name": False,
        "disallow_email": False,
        "disallow_phone": False,
        "disallow_company": False,
        "disallow_title": False,
        "disallow_photo": False,
        "disallow_birthday": False,
        "disallow_address": False
    }
    api.create_settings("test@example.com", settings)

    # Create a collection using the storage API
    collection = api._scanner._storage.create_collection("/testuser/contacts/")
    assert collection is not None

    # Upload a minimal vCard to ensure the collection is recognized
    minimal_vcard = (
        "BEGIN:VCARD\r\n"
        "VERSION:3.0\r\n"
        "UID:dummy-card\r\n"
        "FN:Dummy User\r\n"
        "EMAIL:dummy@example.com\r\n"
        "END:VCARD\r\n"
    )
    vobj = vobject.readOne(minimal_vcard)
    # Monkeypatch vobject to add a .vcard property for Radicale's filter logic, avoiding recursion
    if not hasattr(vobj.__class__, "vcard"):
        vobj.__class__.vcard = property(lambda self: self)
    item = Item(collection=collection, vobject_item=vobj, component_name="VCARD")
    collection.upload("dummy-card.vcf", item)

    # Then try to get matches
    status, headers, response = api.get_matching_cards("test@example.com")
    assert status == client.OK
    response_data = json.loads(response)
    assert "matches" in response_data
    assert response_data["matches"] == []


def test_get_matching_cards_recursive_discovery(api):
    """Test that get_matching_cards can discover and search nested collections."""
    # Create test vCard in a nested collection
    vcard = vobject.vCard()
    vcard.add('uid')
    vcard.uid.value = "nested-card"
    vcard.add('fn')
    vcard.fn.value = "Nested Contact"
    vcard.add('email')
    vcard.email.value = "test@example.com"
    vcard.email.type_param = 'INTERNET'

    # Create a nested collection structure: user1/contacts/personal
    collection = api._scanner._storage.create_collection("/user1/contacts")

    # Upload the vCard
    item = Item(vobject_item=vcard, collection_path="user1/contacts", component_name="VCARD")
    collection.upload("nested-card.vcf", item)

    # Create privacy settings for the test user
    settings = {
        "disallow_name": False,
        "disallow_email": False,
        "disallow_phone": False,
        "disallow_company": False,
        "disallow_title": False,
        "disallow_photo": False,
        "disallow_birthday": False,
        "disallow_address": False
    }
    api.create_settings("test@example.com", settings)

    # Get matching cards
    status, headers, response = api.get_matching_cards("test@example.com")

    assert status == client.OK
    response_data = json.loads(response)
    assert "matches" in response_data
    matches = response_data["matches"]
    assert len(matches) == 1  # Should find the nested card

    # Verify the match details
    match = matches[0]
    assert match["vcard_uid"] == "nested-card"
    assert "email" in match["matching_fields"]
    assert match["collection_path"] == "user1/contacts"


def test_get_matching_cards_in_different_collections(api):
    """Test finding cards matching a user's identity in different collections."""
    # Create test vCards in different collections
    vcard1 = vobject.vCard()
    vcard1.add('uid')
    vcard1.uid.value = "card1"
    vcard1.add('fn')
    vcard1.fn.value = "Test Contact 1"
    vcard1.add('email')
    vcard1.email.value = "test@example.com"
    vcard1.email.type_param = 'INTERNET'

    vcard2 = vobject.vCard()
    vcard2.add('uid')
    vcard2.uid.value = "card2"
    vcard2.add('fn')
    vcard2.fn.value = "Test Contact 2"
    vcard2.add('email')
    vcard2.email.value = "test@example.com"
    vcard2.email.type_param = 'INTERNET'
    vcard2.add('tel')
    vcard2.tel.value = "+1234567890"
    vcard2.tel.type_param = 'CELL'

    # Create collections and add vCards
    collection1 = api._scanner._storage.create_collection("/user1/contacts")
    collection2 = api._scanner._storage.create_collection("/user2/contacts")

    item1 = Item(vobject_item=vcard1, collection_path="user1/contacts", component_name="VCARD")
    item2 = Item(vobject_item=vcard2, collection_path="user2/contacts", component_name="VCARD")

    # Upload cards
    collection1.upload("test-card1.vcf", item1)
    collection2.upload("test-card2.vcf", item2)

    # Create privacy settings for the test user
    settings = {
        "disallow_name": False,
        "disallow_email": False,  # Allow email to be stored
        "disallow_phone": False,
        "disallow_company": False,
        "disallow_title": False,
        "disallow_photo": False,
        "disallow_birthday": False,
        "disallow_address": False
    }
    api.create_settings("test@example.com", settings)

    # Get matching cards
    status, headers, response = api.get_matching_cards("test@example.com")
    assert status == client.OK
    response_data = json.loads(response)

    # Verify response structure
    assert "matches" in response_data
    matches = response_data["matches"]
    assert len(matches) == 2  # Should find both cards
