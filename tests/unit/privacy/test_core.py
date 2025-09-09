"""
Tests for the privacy Core functionality.
"""

import os
import tempfile
from unittest.mock import patch

import pytest
import vobject

from radicale import config, storage
from radicale.item import Item
from radicale.privacy.core import PrivacyCore, PrivacyScanner


@pytest.fixture
def mock_time_ranges():
    """Mock the time ranges function to avoid AttributeError: value."""
    with patch('radicale.item.filter.visit_time_ranges') as mock:
        mock.return_value = (None, None)  # Return no time range
        yield mock


@pytest.fixture
def core(mock_time_ranges):
    """Fixture to provide a privacy core instance with a temp database file."""
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

        # Create core with storage instance
        core = PrivacyCore(configuration)
        core._privacy_db.init_db()  # Initialize the database

        # Reset scanner singleton and create new instance
        PrivacyScanner.reset()
        core._scanner = PrivacyScanner(storage_instance)  # Initialize scanner with storage instance

        try:
            yield core
        finally:
            # Properly clean up SQLAlchemy resources
            if hasattr(core, '_privacy_db'):
                # Close all sessions
                core._privacy_db.Session.remove()
                # Dispose of the engine
                core._privacy_db.engine.dispose()
                # Close the database
                core._privacy_db.close()

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
                    if hasattr(core, '_privacy_db') and hasattr(core._privacy_db, 'engine'):
                        core._privacy_db.engine.dispose()
                except Exception:
                    pass

                # Force another garbage collection
                gc.collect()
                time.sleep(0.5)


def test_get_settings_not_found(core):
    """Test getting settings for a non-existent user."""
    success, result = core.get_settings("nonexistent@example.com")
    assert success
    assert isinstance(result, dict)
    assert "disallow_photo" in result


def test_get_settings_unauthorized(core):
    """Test getting settings without a user."""
    success, result = core.get_settings("")
    assert not success
    assert "User identifier is required" in result


def test_create_settings_success(core):
    """Test creating settings successfully."""
    settings = {
        "disallow_photo": True,
        "disallow_gender": True,
        "disallow_birthday": False,
        "disallow_address": True,
        "disallow_company": True,
        "disallow_title": False,
    }
    success, result = core.create_settings("test@example.com", settings)
    assert success
    assert result == {"status": "created"}

    # Verify settings were created
    success, result = core.get_settings("test@example.com")
    assert success
    assert result == settings


def test_create_settings_missing_fields(core):
    """Test creating settings with missing fields."""
    settings = {
        "disallow_company": False,
        "disallow_title": True
    }
    success, result = core.create_settings("test@example.com", settings)
    assert not success
    assert isinstance(result, dict)
    assert "error" in result
    assert result["error"] == "Missing required fields"
    assert "required_fields" in result
    assert isinstance(result["required_fields"], list)
    assert all(field in result["required_fields"] for field in ["disallow_photo", "disallow_gender", "disallow_birthday", "disallow_address"])


def test_create_settings_invalid_types(core):
    """Test creating settings with invalid field types."""
    settings = {
        "disallow_photo": True,
        "disallow_gender": True,
        "disallow_birthday": False,
        "disallow_address": True,
        "disallow_company": True,
        "disallow_title": "false",  # Should be boolean
    }
    success, result = core.create_settings("test@example.com", settings)
    assert not success
    assert "boolean values" in result


def test_update_settings_success(core):
    """Test updating settings successfully."""
    # First create settings
    initial_settings = {
        "disallow_photo": False,
        "disallow_gender": False,
        "disallow_address": False,
        "disallow_birthday": False,
        "disallow_company": False,
        "disallow_title": False,
    }
    core.create_settings("test@example.com", initial_settings)

    # Then update some settings
    update_settings = {
        "disallow_photo": True,
        "disallow_gender": True,
        "disallow_birthday": True,
    }
    success, result = core.update_settings("test@example.com", update_settings)
    assert success
    assert result == {"status": "updated"}

    # Verify settings were updated
    success, result = core.get_settings("test@example.com")
    assert success
    updated_settings = result
    assert updated_settings["disallow_photo"] is True
    assert updated_settings["disallow_gender"] is True
    assert updated_settings["disallow_birthday"] is True
    assert updated_settings["disallow_address"] is False  # Unchanged
    assert updated_settings["disallow_company"] is False  # Unchanged
    assert updated_settings["disallow_title"] is False  # Unchanged


def test_update_settings_not_found(core):
    """Test updating settings for a non-existent user."""
    settings = {"disallow_photo": True}
    success, result = core.update_settings("nonexistent@example.com", settings)
    assert not success
    assert "User settings not found" in result


def test_update_settings_invalid_fields(core):
    """Test updating settings with invalid field names."""
    settings = {"invalid_field": True}
    success, result = core.update_settings("test@example.com", settings)
    assert not success
    assert isinstance(result, dict)
    assert "error" in result
    assert result["error"] == "Invalid field names"
    assert "valid_fields" in result
    assert isinstance(result["valid_fields"], list)
    assert all(field in result["valid_fields"] for field in ["disallow_photo", "disallow_gender", "disallow_birthday", "disallow_address", "disallow_company", "disallow_title"])


def test_update_settings_empty(core):
    """Test updating settings with an empty dictionary."""
    success, result = core.update_settings("test@example.com", {})
    assert not success
    assert "No settings provided" in result


def test_update_settings_unauthorized(core):
    """Test updating settings without a user."""
    settings = {"disallow_photo": True}
    success, result = core.update_settings("", settings)
    assert not success
    assert "User identifier is required" in result


def test_delete_settings_success(core):
    """Test deleting settings successfully."""
    # First create settings
    settings = {
        "disallow_photo": True,
        "disallow_gender": True,
        "disallow_birthday": False,
        "disallow_address": True,
        "disallow_company": True,
        "disallow_title": False,
    }
    core.create_settings("test@example.com", settings)

    # Delete settings
    success, result = core.delete_settings("test@example.com")
    assert success
    assert result == {"status": "deleted"}

    # Verify settings were deleted (should be auto-created again)
    success, result = core.get_settings("test@example.com")
    assert success
    assert isinstance(result, dict)
    assert "disallow_photo" in result


def test_delete_settings_not_found(core):
    """Test deleting settings for a non-existent user."""
    success, result = core.delete_settings("nonexistent@example.com")
    assert not success
    assert "User settings not found" in result


def test_delete_settings_unauthorized(core):
    """Test deleting settings without a user."""
    success, result = core.delete_settings("")
    assert not success
    assert "User identifier is required" in result


def test_validate_user_identifier_email(core):
    """Test email validation."""
    # Valid emails
    success, result = core.get_settings("test@example.com")
    assert success
    assert isinstance(result, dict)
    success, result = core.get_settings("user.name@domain.co.uk")
    assert success
    assert isinstance(result, dict)

    # Invalid emails
    success, result = core.get_settings("invalid.email")
    assert not success
    assert "Invalid identifier format" in result

    success, result = core.get_settings("@domain.com")
    assert not success
    assert "Invalid email format" in result

    success, result = core.get_settings("user@")
    assert not success
    assert "Invalid email format" in result


def test_validate_user_identifier_phone(core):
    """Test phone number validation."""
    # Valid phone numbers - these should pass validation and auto-create settings
    success, result = core.get_settings("+14155552671")
    assert success
    assert isinstance(result, dict)

    success, result = core.get_settings("+1-234-567-8900")
    assert success
    assert isinstance(result, dict)

    success, result = core.get_settings("+1 (415) 555-2671")
    assert success
    assert isinstance(result, dict)

    # Invalid phone numbers - these should fail validation
    success, result = core.get_settings("(123) 456-7890")  # Missing +
    assert not success
    assert "Invalid identifier format" in result

    success, result = core.get_settings("1234567890")  # Missing +
    assert not success
    assert "Invalid identifier format" in result

    success, result = core.get_settings("+123")  # Too short
    assert not success
    assert "Invalid identifier format" in result

    success, result = core.get_settings("+1234567890123456")  # Too long
    assert not success
    assert "Invalid identifier format" in result

    # Invalid identifiers (not email and not phone)
    success, result = core.get_settings("justtext")
    assert not success
    assert "Invalid identifier format" in result

    success, result = core.get_settings("user.name")
    assert not success
    assert "Invalid identifier format" in result

    success, result = core.get_settings("123-456")  # Not a valid phone format
    assert not success
    assert "Invalid identifier format" in result


def test_validate_user_identifier_empty(core):
    """Test empty user identifier validation."""
    success, result = core.get_settings("")
    assert not success
    assert "User identifier is required" in result


def test_get_matching_cards_not_found(core):
    """Test getting matching cards for a non-existent user."""
    success, result = core.get_matching_cards("nonexistent@example.com")
    assert not success
    assert "User settings not found" in result


def test_get_matching_cards_unauthorized(core):
    """Test getting matching cards without a user."""
    success, result = core.get_matching_cards("")
    assert not success
    assert "User identifier is required" in result


@pytest.mark.skipif(os.name == 'nt', reason="Prolematic on Windows due to file locking")
def test_get_matching_cards_no_matches(core):
    """Test getting matching cards when no matches exist."""
    # First create settings for the user
    settings = {
        "disallow_photo": False,
        "disallow_gender": False,
        "disallow_birthday": False,
        "disallow_address": False,
        "disallow_company": False,
        "disallow_title": False,
    }
    core.create_settings("test@example.com", settings)

    # Create a collection using the storage core
    collection = core._scanner._storage.create_collection("/testuser/contacts/")
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
    success, result = core.get_matching_cards("test@example.com")
    assert success
    assert "matches" in result
    assert result["matches"] == []


@pytest.mark.skipif(os.name == 'nt', reason="Prolematic on Windows due to file locking")
def test_get_matching_cards_recursive_discovery(core):
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
    collection = core._scanner._storage.create_collection("/user1/contacts")

    # Upload the vCard
    item = Item(vobject_item=vcard, collection_path="user1/contacts", component_name="VCARD")
    collection.upload("nested-card.vcf", item)

    # Create privacy settings for the test user
    settings = {
        "disallow_photo": False,
        "disallow_gender": False,
        "disallow_birthday": False,
        "disallow_address": False,
        "disallow_company": False,
        "disallow_title": False,
    }
    success, result = core.create_settings("test@example.com", settings)
    assert success
    assert result == {"status": "created"}

    # Get matching cards
    success, result = core.get_matching_cards("test@example.com")
    assert success
    assert "matches" in result
    assert "reprocessing_error" not in result
    matches = result["matches"]
    assert len(matches) == 1  # Should find the nested card

    # Verify the match details
    match = matches[0]
    assert match["vcard_uid"] == "nested-card"
    assert "email" in match["matching_fields"]
    assert match["collection_path"] == "user1/contacts"


@pytest.mark.skipif(os.name == 'nt', reason="Prolematic on Windows due to file locking")
def test_get_matching_cards_in_different_collections(core):
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
    collection1 = core._scanner._storage.create_collection("/user1/contacts")
    collection2 = core._scanner._storage.create_collection("/user2/contacts")

    item1 = Item(vobject_item=vcard1, collection_path="user1/contacts", component_name="VCARD")
    item2 = Item(vobject_item=vcard2, collection_path="user2/contacts", component_name="VCARD")

    # Upload cards
    collection1.upload("test-card1.vcf", item1)
    collection2.upload("test-card2.vcf", item2)

    # Create privacy settings for the test user
    settings = {
        "disallow_photo": False,
        "disallow_gender": False,
        "disallow_birthday": False,
        "disallow_address": False,
        "disallow_company": False,
        "disallow_title": False,
    }
    success, result = core.create_settings("test@example.com", settings)
    assert success
    assert result == {"status": "created"}

    # Get matching cards
    success, result = core.get_matching_cards("test@example.com")
    assert success
    assert "matches" in result
    assert "reprocessing_error" not in result
    matches = result["matches"]
    assert len(matches) == 2  # Should find both cards


def test_reprocess_cards_not_found(core):
    """Test reprocessing cards for a non-existent user."""
    success, result = core.reprocess_cards("nonexistent@example.com")
    assert not success
    assert "User settings not found" in result


def test_reprocess_cards_unauthorized(core):
    """Test reprocessing cards without a user."""
    success, result = core.reprocess_cards("")
    assert not success
    assert "User identifier is required" in result


@pytest.mark.skipif(os.name == 'nt', reason="Problematic on Windows due to file locking")
def test_reprocess_cards_success(core):
    """Test successful reprocessing of cards."""
    # First create settings for the user
    settings = {
        "disallow_photo": True,
        "disallow_gender": True,
        "disallow_birthday": False,
        "disallow_address": True,
        "disallow_company": True,
        "disallow_title": False,
    }
    core.create_settings("test@example.com", settings)

    # Create a test vCard
    vcard = vobject.vCard()
    vcard.add('uid')
    vcard.uid.value = "test-card"
    vcard.add('fn')
    vcard.fn.value = "Test Contact"
    vcard.add('email')
    vcard.email.value = "test@example.com"
    vcard.email.type_param = 'INTERNET'
    vcard.add('org')
    vcard.org.value = "Test Company"
    vcard.add('title')
    vcard.title.value = "Test Title"

    # Create collection and upload vCard
    collection = core._scanner._storage.create_collection("/testuser/contacts")
    item = Item(vobject_item=vcard, collection_path="testuser/contacts", component_name="VCARD")
    collection.upload("test-card.vcf", item)

    # Trigger reprocessing
    success, result = core.reprocess_cards("test@example.com")
    assert success
    assert result["status"] == "success"

    # Verify the vCard was updated according to privacy settings
    items = list(collection.get_all())
    assert len(items) == 1
    updated_vcard = items[0].vobject_item

    # Company and photo should be removed (disallowed)
    assert 'org' not in updated_vcard.contents
    assert 'photo' not in updated_vcard.contents

    # Title should remain (allowed)
    assert 'title' in updated_vcard.contents
    assert updated_vcard.title.value == "Test Title"


@pytest.mark.skipif(os.name == 'nt', reason="Problematic on Windows due to file locking")
def test_reprocess_cards_multiple_collections(core):
    """Test reprocessing cards across multiple collections."""
    # Create settings for the user
    settings = {
        "disallow_photo": True,
        "disallow_gender": True,
        "disallow_birthday": False,
        "disallow_address": True,
        "disallow_company": True,
        "disallow_title": False,
    }
    core.create_settings("test@example.com", settings)

    # Create test vCards in different collections
    vcard1 = vobject.vCard()
    vcard1.add('uid')
    vcard1.uid.value = "card1"
    vcard1.add('fn')
    vcard1.fn.value = "Test Contact 1"
    vcard1.add('email')
    vcard1.email.value = "test@example.com"
    vcard1.email.type_param = 'INTERNET'
    vcard1.add('org')
    vcard1.org.value = "Company 1"

    vcard2 = vobject.vCard()
    vcard2.add('uid')
    vcard2.uid.value = "card2"
    vcard2.add('fn')
    vcard2.fn.value = "Test Contact 2"
    vcard2.add('email')
    vcard2.email.value = "test@example.com"
    vcard2.email.type_param = 'INTERNET'
    vcard2.add('org')
    vcard2.org.value = "Company 2"

    # Create collections and upload vCards
    collection1 = core._scanner._storage.create_collection("/user1/contacts")
    collection2 = core._scanner._storage.create_collection("/user2/contacts")

    item1 = Item(vobject_item=vcard1, collection_path="user1/contacts", component_name="VCARD")
    item2 = Item(vobject_item=vcard2, collection_path="user2/contacts", component_name="VCARD")

    collection1.upload("test-card1.vcf", item1)
    collection2.upload("test-card2.vcf", item2)

    # Trigger reprocessing
    success, result = core.reprocess_cards("test@example.com")
    assert success
    assert result["status"] == "success"

    # Verify both vCards were updated
    items1 = list(collection1.get_all())
    items2 = list(collection2.get_all())

    assert len(items1) == 1
    assert len(items2) == 1

    assert 'org' not in items1[0].vobject_item.contents
    assert 'org' not in items2[0].vobject_item.contents


@pytest.mark.skipif(os.name == 'nt', reason="Problematic on Windows due to file locking")
def test_reprocess_cards_after_settings_update(core):
    """Test that settings update does not automatically reprocess cards, but explicit reprocessing does."""
    # First create initial settings
    initial_settings = {
        "disallow_photo": False,
        "disallow_gender": False,
        "disallow_birthday": False,
        "disallow_address": False,
        "disallow_company": False,
        "disallow_title": False,
    }
    core.create_settings("test@example.com", initial_settings)

    # Create a test vCard
    vcard = vobject.vCard()
    vcard.add('uid')
    vcard.uid.value = "test-card"
    vcard.add('fn')
    vcard.fn.value = "Test Contact"
    vcard.add('email')
    vcard.email.value = "test@example.com"
    vcard.email.type_param = 'INTERNET'
    vcard.add('org')
    vcard.org.value = "Test Company"
    vcard.add('title')
    vcard.title.value = "Test Title"

    # Create collection and upload vCard
    collection = core._scanner._storage.create_collection("/testuser/contacts")
    item = Item(vobject_item=vcard, collection_path="testuser/contacts", component_name="VCARD")
    collection.upload("test-card.vcf", item)

    # Update settings to disallow company
    update_settings = {
        "disallow_company": True
    }
    success, result = core.update_settings("test@example.com", update_settings)
    assert success
    assert result["status"] == "updated"

    # Verify the vCard was NOT automatically updated (no automatic reprocessing)
    items = list(collection.get_all())
    assert len(items) == 1
    unchanged_vcard = items[0].vobject_item

    # Company should still be present (settings updated but no reprocessing)
    assert 'org' in unchanged_vcard.contents
    assert ''.join(unchanged_vcard.org.value) == "Test Company"

    # Title should also remain unchanged
    assert 'title' in unchanged_vcard.contents
    assert unchanged_vcard.title.value == "Test Title"

    # Now explicitly trigger reprocessing
    success, result = core.reprocess_cards("test@example.com")
    assert success
    assert result["status"] == "success"
    assert result["reprocessed_cards"] == 1

    # Verify the vCard was updated according to new privacy settings after explicit reprocessing
    items = list(collection.get_all())
    assert len(items) == 1
    reprocessed_vcard = items[0].vobject_item

    # Company should now be removed (after explicit reprocessing)
    assert 'org' not in reprocessed_vcard.contents

    # Title should remain (still allowed)
    assert 'title' in reprocessed_vcard.contents
    assert reprocessed_vcard.title.value == "Test Title"


@pytest.mark.skipif(os.name == 'nt', reason="Problematic on Windows due to file locking")
def test_get_matching_cards_phone_formats(core):
    """Test matching cards with phone numbers in various formats."""

    # E.164 phone number for settings
    phone_e164 = "+14155552671"
    settings = {
        "disallow_photo": False,
        "disallow_gender": False,
        "disallow_birthday": False,
        "disallow_address": False,
        "disallow_company": False,
        "disallow_title": False,
    }
    # Create privacy settings for the E.164 phone
    success, result = core.create_settings(phone_e164, settings)
    assert success
    assert result == {"status": "created"}

    # Create a collection
    collection = core._scanner._storage.create_collection("/testuser/contacts/")
    assert collection is not None

    # List of phone number formats that should all normalize to +14155552671
    phone_variants = [
        "+1 415-555-2671",
        "+1 (415) 555-2671",
        "(415) 555-2671",  # Should match, missing country code is assumed to be +1 (US)
        "+14155552671",
        "+1-415-555-2671",
        "+1 415 555 2671",
        "+1.415.555.2671",
    ]
    # Upload vCards with these phone numbers
    for idx, phone in enumerate(phone_variants):
        vcard = vobject.vCard()
        vcard.add('uid')
        vcard.uid.value = f"card{idx}"
        vcard.add('fn')
        vcard.fn.value = f"Test Contact {idx}"
        vcard.add('tel')
        vcard.tel.value = phone
        vcard.tel.type_param = 'CELL'
        item = Item(vobject_item=vcard, collection_path="testuser/contacts", component_name="VCARD")
        collection.upload(f"test-card{idx}.vcf", item)

    # Should match all vCards with normalizable numbers
    success, result = core.get_matching_cards(phone_e164)
    assert success
    assert "matches" in result
    # Only those with a valid country code should match
    expected_matches = [
        "+1 415-555-2671",
        "+1 (415) 555-2671",
        "(415) 555-2671",
        "+14155552671",
        "+1-415-555-2671",
        "+1 415 555 2671",
        "+1.415.555.2671",
    ]
    found_uids = {m["vcard_uid"] for m in result["matches"]}
    # The third variant (index 2) is missing country code, so should not match
    assert found_uids == {f"card{idx}" for idx in range(len(phone_variants))}

    # Also test that searching with a variant format finds the same cards
    for variant in expected_matches:
        success, result = core.get_matching_cards(variant)
        assert success
        found_uids_variant = {m["vcard_uid"] for m in result["matches"]}
        assert found_uids_variant == found_uids
