"""Test suite for privacy reprocessing functionality."""

import logging

import pytest
import vobject

import radicale.item as radicale_item
from radicale import config, pathutils
from radicale.privacy.reprocessor import PrivacyReprocessor

logger = logging.getLogger(__name__)


@pytest.fixture
def create_vcard():
    """Fixture to create vCards with specified properties."""
    def _create_vcard(**properties):
        vcard = vobject.vCard()

        if 'name' in properties:
            vcard.add('n')
            vcard.n.value = vobject.vcard.Name(family=properties['name'].split())
            vcard.add('fn')
            vcard.fn.value = properties['name']

        if 'email' in properties:
            vcard.add('email')
            vcard.email.value = properties['email']
            vcard.email.type_param = 'INTERNET'

        if 'phone' in properties:
            vcard.add('tel')
            vcard.tel.value = properties['phone']
            vcard.tel.type_param = 'CELL'

        if 'company' in properties:
            vcard.add('org')
            vcard.org.value = [properties['company']]

        if 'title' in properties:
            vcard.add('title')
            vcard.title.value = properties['title']

        if 'photo' in properties:
            vcard.add('photo')
            vcard.photo.value = properties['photo']

        if 'birthday' in properties:
            vcard.add('bday')
            vcard.bday.value = properties['birthday']

        if 'address' in properties:
            vcard.add('adr')
            vcard.adr.value = vobject.vcard.Address(
                street=properties['address'],
                city='City',
                region='Region',
                code='12345',
                country='Country'
            )

        # Always add FN if not present (required by vCard spec)
        if 'fn' not in vcard.contents:
            vcard.add('fn')
            vcard.fn.value = "Unknown"

        return vcard
    return _create_vcard


@pytest.fixture
def create_item():
    """Fixture to create Radicale items from vCards."""
    def _create_item(vcard):
        # Create a properly sanitized collection path
        collection_path = pathutils.strip_path(pathutils.sanitize_path("/test/collection"))
        item = radicale_item.Item(
            collection_path=collection_path,
            vobject_item=vcard,
            text=vcard.serialize(),
            component_name="VCARD",
            name="VCARD"
        )
        return item
    return _create_item


@pytest.fixture
def privacy_reprocessor(mocker):
    """Fixture to provide a privacy reprocessor instance."""
    configuration = config.load()
    storage = mocker.Mock()
    reprocessor = PrivacyReprocessor(configuration, storage)
    reprocessor._enforcement = mocker.Mock()
    reprocessor._scanner = mocker.Mock()
    return reprocessor


def test_reprocess_vcards(privacy_reprocessor, create_vcard, create_item, mocker):
    """Test reprocessing vCards with privacy settings changes."""
    # Create test vCards
    vcard1 = create_vcard(
        name="John Doe",
        email="john@example.com",
        company="ACME Corp",
        title="Developer",
        photo="base64photo",
        birthday="1990-01-01",
        address="123 Main St"
    )
    vcard2 = create_vcard(
        name="Jane Smith",
        email="jane@example.com",
        company="XYZ Inc",
        title="Manager",
        photo="base64photo2",
        birthday="1991-02-02",
        address="456 Oak St"
    )
    item1 = create_item(vcard1)
    item2 = create_item(vcard2)

    # Mock scanner to return matching vCards
    privacy_reprocessor._scanner.find_identity_occurrences.return_value = [
        {
            'collection_path': '/test/collection1',
            'vcard_uid': 'vcard1',
            'matching_fields': ['email']
        },
        {
            'collection_path': '/test/collection2',
            'vcard_uid': 'vcard2',
            'matching_fields': ['email']
        }
    ]

    # Mock storage to return collections and items
    collection1 = mocker.Mock()
    collection1.get.return_value = item1
    collection2 = mocker.Mock()
    collection2.get.return_value = item2
    privacy_reprocessor._storage.get_collection.side_effect = [collection1, collection2]

    # Mock enforcement to modify items
    modified_item1 = create_item(create_vcard(
        name="John Doe",
        email="john@example.com",
        photo="base64photo",
        address="123 Main St"
    ))
    modified_item2 = create_item(create_vcard(
        name="Jane Smith",
        email="jane@example.com",
        photo="base64photo2",
        address="456 Oak St"
    ))
    privacy_reprocessor._enforcement.enforce_privacy.side_effect = [modified_item1, modified_item2]

    # Set privacy settings
    privacy_reprocessor._enforcement._privacy_db.get_user_settings.return_value = mocker.Mock(
        disallow_company=True,
        disallow_title=True,
        disallow_photo=False,
        disallow_birthday=True,
        disallow_address=False
    )

    # Reprocess vCards
    reprocessed = privacy_reprocessor.reprocess_vcards("john@example.com")

    # Verify results
    assert len(reprocessed) == 2
    assert "vcard1" in reprocessed
    assert "vcard2" in reprocessed
    assert collection1.upload.call_count == 1
    assert collection2.upload.call_count == 1


def test_reprocess_vcards_multiple_identifiers(privacy_reprocessor, create_vcard, create_item, mocker):
    """Test reprocessing vCards with multiple identifiers and different privacy settings."""
    # Create test vCard with both email and phone
    vcard = create_vcard(
        name="John Doe",
        email="john@example.com",
        phone="+1234567890",
        company="ACME Corp",
        title="Developer",
        photo="base64photo"
    )
    item = create_item(vcard)

    # Mock scanner to return matching vCard
    privacy_reprocessor._scanner.find_identity_occurrences.return_value = [
        {
            'collection_path': '/test/collection',
            'vcard_uid': 'vcard1',
            'matching_fields': ['email', 'phone']
        }
    ]

    # Mock storage to return collection and item
    collection = mocker.Mock()
    collection.get.return_value = item
    privacy_reprocessor._storage.get_collection.return_value = collection

    # Mock enforcement to modify item
    modified_item = create_item(create_vcard(
        name="John Doe",
        email="john@example.com",
        phone="+1234567890"
    ))
    privacy_reprocessor._enforcement.enforce_privacy.return_value = modified_item

    # Set different privacy settings for email and phone
    def get_settings(identifier):
        if identifier == "john@example.com":
            return mocker.Mock(
                disallow_company=True,
                disallow_title=False,
                disallow_photo=False,
                disallow_birthday=False,
                disallow_address=False
            )
        elif identifier == "+1234567890":
            return mocker.Mock(
                disallow_company=False,
                disallow_title=True,
                disallow_photo=True,
                disallow_birthday=False,
                disallow_address=False
            )
        return None

    privacy_reprocessor._enforcement._privacy_db.get_user_settings.side_effect = get_settings

    # Reprocess vCards
    reprocessed = privacy_reprocessor.reprocess_vcards("john@example.com")

    # Verify results
    assert len(reprocessed) == 1
    assert "vcard1" in reprocessed
    assert collection.upload.call_count == 1


def test_reprocess_vcards_no_changes(privacy_reprocessor, create_vcard, create_item, mocker):
    """Test reprocessing vCards when no changes are needed."""
    # Create test vCard
    vcard = create_vcard(
        name="John Doe",
        email="john@example.com",
        company="ACME Corp",
        title="Developer"
    )
    item = create_item(vcard)

    # Mock scanner to return matching vCard
    privacy_reprocessor._scanner.find_identity_occurrences.return_value = [
        {
            'collection_path': '/test/collection',
            'vcard_uid': 'vcard1',
            'matching_fields': ['email']
        }
    ]

    # Mock storage to return collection and item
    collection = mocker.Mock()
    collection.get.return_value = item
    privacy_reprocessor._storage.get_collection.return_value = collection

    # Mock enforcement to return unchanged item
    privacy_reprocessor._enforcement.enforce_privacy.return_value = item

    # Set privacy settings to allow all fields
    privacy_reprocessor._enforcement._privacy_db.get_user_settings.return_value = mocker.Mock(
        disallow_company=False,
        disallow_title=False,
        disallow_photo=False,
        disallow_birthday=False,
        disallow_address=False
    )

    # Reprocess vCards
    reprocessed = privacy_reprocessor.reprocess_vcards("john@example.com")

    # Verify results
    assert len(reprocessed) == 0
    assert collection.upload.call_count == 0


def test_reprocess_vcards_with_errors(privacy_reprocessor, create_vcard, create_item, mocker):
    """Test reprocessing vCards with various error conditions."""
    # Create test vCard
    vcard = create_vcard(
        name="John Doe",
        email="john@example.com",
        company="ACME Corp",
        title="Developer"
    )
    item = create_item(vcard)

    # Mock scanner to return matching vCard
    privacy_reprocessor._scanner.find_identity_occurrences.return_value = [
        {
            'collection_path': '/test/collection',
            'vcard_uid': 'vcard1',
            'matching_fields': ['email']
        }
    ]

    # Test error when getting collection
    privacy_reprocessor._storage.get_collection.side_effect = Exception("Collection not found")

    # Reprocess vCards
    reprocessed = privacy_reprocessor.reprocess_vcards("john@example.com")

    # Verify results
    assert len(reprocessed) == 0

    # Test error when getting vCard
    collection = mocker.Mock()
    collection.get.side_effect = Exception("vCard not found")
    privacy_reprocessor._storage.get_collection.return_value = collection

    # Reprocess vCards
    reprocessed = privacy_reprocessor.reprocess_vcards("john@example.com")

    # Verify results
    assert len(reprocessed) == 0

    # Test error when saving vCard
    collection.get.return_value = item
    collection.upload.side_effect = Exception("Failed to save vCard")

    # Reprocess vCards
    reprocessed = privacy_reprocessor.reprocess_vcards("john@example.com")

    # Verify results
    assert len(reprocessed) == 0
