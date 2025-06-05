"""Unit tests for the privacy scanner module."""

from typing import Optional

import pytest
import vobject

from radicale.item import Item
from radicale.privacy.scanner import PrivacyScanner
from radicale.storage.multifilesystem.get import CollectionPartGet


@pytest.fixture
def storage(mocker):
    """Fixture providing a mock storage instance."""
    return mocker.MagicMock()


@pytest.fixture
def scanner(storage):
    """Fixture providing a PrivacyScanner instance."""
    # Reset the singleton before each test
    PrivacyScanner.reset()
    return PrivacyScanner(storage)


@pytest.fixture
def create_test_vcard():
    """Fixture to create test vCard items."""
    def _create_vcard(uid: str, email: Optional[str] = None, phone: Optional[str] = None, collection_path: str = "test/collection") -> Item:
        vcard = vobject.vCard()
        vcard.add('uid')
        vcard.uid.value = uid
        vcard.add('fn')
        vcard.fn.value = f"Test Contact {uid}"

        if email:
            vcard.add('email')
            vcard.email.value = email
            vcard.email.type_param = 'INTERNET'

        if phone:
            vcard.add('tel')
            vcard.tel.value = phone
            vcard.tel.type_param = 'CELL'

        return Item(vobject_item=vcard, collection_path=collection_path, component_name="VCARD")
    return _create_vcard


def test_extract_identifiers(scanner, create_test_vcard):
    """Test identifier extraction from vCards."""
    # Test with both email and phone
    vcard = create_test_vcard("test1", "test@example.com", "+1234567890")
    identifiers = scanner._extract_identifiers(vcard.vobject_item)
    assert len(identifiers) == 2
    assert ("email", "test@example.com") in identifiers
    assert ("phone", "+1234567890") in identifiers

    # Test with only email
    vcard = create_test_vcard("test2", email="test2@example.com")
    identifiers = scanner._extract_identifiers(vcard.vobject_item)
    assert len(identifiers) == 1
    assert ("email", "test2@example.com") in identifiers

    # Test with only phone
    vcard = create_test_vcard("test3", phone="+1987654321")
    identifiers = scanner._extract_identifiers(vcard.vobject_item)
    assert len(identifiers) == 1
    assert ("phone", "+1987654321") in identifiers

    # Test with no identifiers
    vcard = create_test_vcard("test4")
    identifiers = scanner._extract_identifiers(vcard.vobject_item)
    assert len(identifiers) == 0


def test_scan_collection(scanner, create_test_vcard, mocker):
    """Test scanning a single collection."""
    # Create a mock collection
    collection = mocker.MagicMock(spec=CollectionPartGet)
    collection.path = "user1/contacts"

    # Create test items
    items = [
        create_test_vcard("test1", "test@example.com", "+1234567890"),
        create_test_vcard("test2", "other@example.com"),
        create_test_vcard("test3", phone="+1234567890"),
    ]
    collection.get_all.return_value = items

    # Test scanning for email
    matches = scanner._scan_collection(collection, "test@example.com")
    assert len(matches) == 1
    assert matches[0]["user_id"] == "user1"
    assert matches[0]["vcard_uid"] == "test1"
    assert matches[0]["matching_fields"] == ["email"]

    # Test scanning for phone
    matches = scanner._scan_collection(collection, "+1234567890")
    assert len(matches) == 2
    assert matches[0]["user_id"] == "user1"
    assert matches[0]["vcard_uid"] == "test1"
    assert matches[0]["matching_fields"] == ["phone"]
    assert matches[1]["user_id"] == "user1"
    assert matches[1]["vcard_uid"] == "test3"
    assert matches[1]["matching_fields"] == ["phone"]

    # Test indexing mode (identity=None)
    matches = scanner._scan_collection(collection, None)
    assert len(matches) == 4  # All identifiers should be indexed
    # Verify email matches
    email_matches = [m for m in matches if "email" in m["matching_fields"]]
    assert len(email_matches) == 2
    assert any(m["email"] == "test@example.com" for m in email_matches)
    assert any(m["email"] == "other@example.com" for m in email_matches)
    # Verify phone matches
    phone_matches = [m for m in matches if "phone" in m["matching_fields"]]
    assert len(phone_matches) == 2
    assert all(m["phone"] == "+1234567890" for m in phone_matches)


def test_find_identity_occurrences(scanner, create_test_vcard, storage, mocker):
    """Test finding identity occurrences across all collections."""
    # Create mock collections
    collection1 = mocker.MagicMock(spec=CollectionPartGet)
    collection1.path = "user1/contacts"
    collection1.get_all.return_value = [
        create_test_vcard("test1", "test@example.com")
    ]

    collection2 = mocker.MagicMock(spec=CollectionPartGet)
    collection2.path = "user2/contacts"
    collection2.get_all.return_value = [
        create_test_vcard("test2", "test@example.com")
    ]

    storage.discover.return_value = [collection1, collection2]

    # Test finding all occurrences (should build index)
    matches = scanner.find_identity_occurrences("test@example.com")
    assert len(matches) == 2

    # Verify first match
    assert matches[0]["user_id"] == "user1"
    assert matches[0]["vcard_uid"] == "test1"
    assert matches[0]["matching_fields"] == ["email"]

    # Verify second match
    assert matches[1]["user_id"] == "user2"
    assert matches[1]["vcard_uid"] == "test2"
    assert matches[1]["matching_fields"] == ["email"]

    # Test that subsequent lookups use the index
    collection1.get_all.reset_mock()
    collection2.get_all.reset_mock()
    matches = scanner.find_identity_occurrences("test@example.com")
    assert len(matches) == 2
    # Verify that get_all was not called (using index)
    collection1.get_all.assert_not_called()
    collection2.get_all.assert_not_called()


def test_error_handling(scanner, storage, mocker):
    """Test error handling during scanning."""
    # Create a mock collection that raises an exception
    collection = mocker.MagicMock(spec=CollectionPartGet)
    collection.path = "user1/contacts"
    collection.get_all.side_effect = Exception("Test error")

    storage.discover.return_value = [collection]

    # Test that errors are logged but don't crash the scan
    matches = scanner.find_identity_occurrences("test@example.com")
    assert len(matches) == 0


def test_index_refresh(scanner, create_test_vcard, storage, mocker):
    """Test index refresh functionality."""
    # Create initial mock collection
    collection1 = mocker.MagicMock(spec=CollectionPartGet)
    collection1.path = "user1/contacts"
    collection1.get_all.return_value = [
        create_test_vcard("test1", "test@example.com")
    ]
    storage.discover.return_value = [collection1]

    # Build initial index
    matches = scanner.find_identity_occurrences("test@example.com")
    assert len(matches) == 1
    assert matches[0]["vcard_uid"] == "test1"

    # Update collection with new data
    collection1.get_all.return_value = [
        create_test_vcard("test2", "test@example.com")
    ]

    # Test that old index is used
    matches = scanner.find_identity_occurrences("test@example.com")
    assert len(matches) == 1
    assert matches[0]["vcard_uid"] == "test1"

    # Refresh index
    scanner.refresh_index()

    # Test that new data is found
    matches = scanner.find_identity_occurrences("test@example.com")
    assert len(matches) == 1
    assert matches[0]["vcard_uid"] == "test2"


def test_index_initialization(scanner, create_test_vcard, storage, mocker):
    """Test index initialization and building."""
    # Create mock collections
    collection1 = mocker.MagicMock(spec=CollectionPartGet)
    collection1.path = "user1/contacts"
    collection1.get_all.return_value = [
        create_test_vcard("test1", "test@example.com", "+1234567890"),
        create_test_vcard("test2", "other@example.com")
    ]

    collection2 = mocker.MagicMock(spec=CollectionPartGet)
    collection2.path = "user2/contacts"
    collection2.get_all.return_value = [
        create_test_vcard("test3", "test@example.com", "+1987654321")
    ]

    storage.discover.return_value = [collection1, collection2]

    # Test that index is built on first use
    assert not scanner._index_initialized
    matches = scanner.find_identity_occurrences("test@example.com")
    assert scanner._index_initialized
    assert len(matches) == 2

    # Verify index contents
    assert "test@example.com" in scanner._index
    assert "+1234567890" in scanner._index
    assert "+1987654321" in scanner._index
    assert "other@example.com" in scanner._index

    # Verify index structure
    email_matches = scanner._index["test@example.com"]
    assert len(email_matches) == 2
    assert all(m["matching_fields"] == ["email"] for m in email_matches)
    assert {m["vcard_uid"] for m in email_matches} == {"test1", "test3"}


def test_singleton_pattern(storage, mocker):
    """Test that PrivacyScanner follows the singleton pattern."""
    # Create first instance
    scanner1 = PrivacyScanner(storage)
    # Save the storage actually used
    first_storage = scanner1._storage

    # Create second instance with different storage
    different_storage = mocker.MagicMock()
    scanner2 = PrivacyScanner(different_storage)

    # Verify both instances are the same
    assert scanner1 is scanner2

    # Verify initialization only happened once
    assert scanner1._initialized
    assert scanner2._initialized
    # The storage should not change after the first initialization
    assert scanner1._storage is first_storage
    assert scanner1._storage is not different_storage


def test_scan_collection_phone_normalization(scanner, create_test_vcard, mocker):
    """Test that phone numbers in various formats are normalized and matched."""
    collection = mocker.MagicMock(spec=CollectionPartGet)
    collection.path = "user1/contacts"

    # List of phone number formats that should all normalize to +14155552671
    phone_variants = [
        "+1 415-555-2671",
        "+1 (415) 555-2671",
        "(415) 555-2671",  # Should match, default region assumed US
        "+14155552671",
        "+1-415-555-2671",
        "+1 415 555 2671",
        "+1.415.555.2671",
    ]
    items = [
        create_test_vcard(f"test{idx}", phone=phone, collection_path="user1/contacts")
        for idx, phone in enumerate(phone_variants)
    ]
    collection.get_all.return_value = items

    # The normalized E.164 number to search for
    search_number = "+14155552671"
    matches = scanner._scan_collection(collection, search_number)
    # All variants should match
    assert len(matches) == len(phone_variants)
    found_uids = {m["vcard_uid"] for m in matches}
    assert found_uids == {f"test{idx}" for idx in range(len(phone_variants))}

    # Also test that searching with a variant format finds the same cards
    for variant in phone_variants:
        matches_variant = scanner._scan_collection(collection, variant)
        found_uids_variant = {m["vcard_uid"] for m in matches_variant}
        assert found_uids_variant == found_uids
