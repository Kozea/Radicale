"""Test suite for privacy enforcement functionality."""

import pytest
import vobject

import radicale.item as radicale_item
from radicale import config, pathutils
from radicale.privacy.enforcement import PrivacyEnforcement


@pytest.fixture
def privacy_enforcement(mocker):
    """Fixture to provide a privacy enforcement instance."""
    configuration = config.load()
    enforcement = PrivacyEnforcement.get_instance(configuration)
    enforcement._privacy_db = mocker.Mock()
    return enforcement


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

        return vcard
    return _create_vcard


@pytest.fixture
def create_item():
    """Fixture to create Radicale items from vCards."""
    def _create_item(vcard):
        collection_path = pathutils.sanitize_path("/test/collection")
        item = radicale_item.Item(
            collection_path=collection_path,
            vobject_item=vcard,
            text=vcard.serialize()
        )
        item.component_name = "VCARD"
        item.name = "VCARD"
        return item
    return _create_item


def test_basic_property_removal(privacy_enforcement, create_vcard, create_item, mocker):
    """Test basic property removal based on privacy settings."""
    # Create a vCard with all properties
    vcard = create_vcard(
        name="John Doe",
        email="john@example.com",
        phone="+1234567890",
        company="ACME Corp",
        title="Developer",
        photo="base64photo",
        birthday="1990-01-01",
        address="123 Main St"
    )
    item = create_item(vcard)

    # Mock privacy settings to disallow name and email
    privacy_enforcement._privacy_db.get_user_settings.return_value = mocker.Mock(
        disallow_name=True,
        disallow_email=True,
        disallow_phone=False,
        disallow_company=False,
        disallow_title=False,
        disallow_photo=False,
        disallow_birthday=False,
        disallow_address=False
    )

    # Apply privacy enforcement
    modified_item = privacy_enforcement.enforce_privacy(item)
    modified_vcard = modified_item.vobject_item

    # Verify properties were removed
    assert 'n' not in modified_vcard.contents
    assert 'fn' not in modified_vcard.contents
    assert 'email' not in modified_vcard.contents

    # Verify other properties remain
    assert 'tel' in modified_vcard.contents
    assert 'org' in modified_vcard.contents
    assert 'title' in modified_vcard.contents
    assert 'photo' in modified_vcard.contents
    assert 'bday' in modified_vcard.contents
    assert 'adr' in modified_vcard.contents


def test_multiple_identifiers(privacy_enforcement, create_vcard, create_item, mocker):
    """Test privacy enforcement with multiple identifiers (email and phone)."""
    vcard = create_vcard(
        name="John Doe",
        email="john@example.com",
        phone="+1234567890"
    )
    item = create_item(vcard)

    # Mock privacy settings for both identifiers
    def get_settings(identifier):
        if identifier == "john@example.com":
            return mocker.Mock(disallow_name=True, disallow_email=True)
        elif identifier == "+1234567890":
            return mocker.Mock(disallow_phone=True)
        return None

    privacy_enforcement._privacy_db.get_user_settings.side_effect = get_settings

    # Apply privacy enforcement
    modified_item = privacy_enforcement.enforce_privacy(item)
    modified_vcard = modified_item.vobject_item

    # Verify properties were removed based on both identifiers
    assert 'n' not in modified_vcard.contents
    assert 'fn' not in modified_vcard.contents
    assert 'email' not in modified_vcard.contents
    assert 'tel' not in modified_vcard.contents


def test_most_restrictive_settings(privacy_enforcement, create_vcard, create_item, mocker):
    """Test that the most restrictive settings are applied when multiple matches exist."""
    vcard = create_vcard(
        name="John Doe",
        email="john@example.com",
        phone="+1234567890"
    )
    item = create_item(vcard)

    # Mock privacy settings with different restrictions
    def get_settings(identifier):
        if identifier == "john@example.com":
            return mocker.Mock(
                disallow_name=True,
                disallow_email=True,
                disallow_phone=False
            )
        elif identifier == "+1234567890":
            return mocker.Mock(
                disallow_name=False,
                disallow_email=False,
                disallow_phone=True
            )
        return None

    privacy_enforcement._privacy_db.get_user_settings.side_effect = get_settings

    # Apply privacy enforcement
    modified_item = privacy_enforcement.enforce_privacy(item)
    modified_vcard = modified_item.vobject_item

    # Verify that the most restrictive settings were applied
    assert 'n' not in modified_vcard.contents  # Disallowed by email settings
    assert 'fn' not in modified_vcard.contents  # Disallowed by email settings
    assert 'email' not in modified_vcard.contents  # Disallowed by email settings
    assert 'tel' not in modified_vcard.contents  # Disallowed by phone settings


def test_edge_cases(privacy_enforcement, create_vcard, create_item, mocker):
    """Test edge cases in privacy enforcement."""
    # Test empty vCard
    empty_vcard = vobject.vCard()
    empty_item = create_item(empty_vcard)
    privacy_enforcement._privacy_db.get_user_settings.return_value = None
    modified_item = privacy_enforcement.enforce_privacy(empty_item)
    assert modified_item.vobject_item.contents == {}

    # Test vCard with only required properties
    minimal_vcard = vobject.vCard()
    minimal_vcard.add('fn')
    minimal_vcard.fn.value = "John Doe"
    minimal_item = create_item(minimal_vcard)
    privacy_enforcement._privacy_db.get_user_settings.return_value = mocker.Mock(
        disallow_name=True
    )
    modified_item = privacy_enforcement.enforce_privacy(minimal_item)
    assert 'fn' not in modified_item.vobject_item.contents

    # Test vCard with unknown properties
    unknown_vcard = vobject.vCard()
    unknown_vcard.add('x-custom')
    unknown_vcard['x-custom'].value = "Custom Value"
    unknown_item = create_item(unknown_vcard)
    privacy_enforcement._privacy_db.get_user_settings.return_value = None
    modified_item = privacy_enforcement.enforce_privacy(unknown_item)
    assert 'x-custom' in modified_item.vobject_item.contents


def test_non_vcard_item(privacy_enforcement, mocker):
    """Test that non-vCard items are returned unchanged."""
    # Create a non-vCard item
    item = radicale_item.Item()
    item.component_name = "VCALENDAR"
    item.name = "VCALENDAR"

    # Apply privacy enforcement
    modified_item = privacy_enforcement.enforce_privacy(item)

    # Verify the item was returned unchanged
    assert modified_item.component_name == "VCALENDAR"
    assert modified_item.name == "VCALENDAR"
