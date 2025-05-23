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

    # Test finding all occurrences
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
