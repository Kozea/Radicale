"""Test suite for privacy enforcement functionality."""

import logging

import pytest
import vobject

import radicale.item as radicale_item
from radicale import config, pathutils
from radicale.privacy.enforcement import PrivacyEnforcement

logger = logging.getLogger(__name__)


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

        if 'photo' in properties:
            vcard.add('photo')
            vcard.photo.value = properties['photo']

        if 'gender' in properties:
            vcard.add('gender')
            vcard.gender.value = properties['gender']

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

        if 'company' in properties:
            vcard.add('org')
            vcard.org.value = [properties['company']]

        if 'title' in properties:
            vcard.add('title')
            vcard.title.value = properties['title']

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


def test_basic_property_enforcement(privacy_enforcement, create_vcard, create_item, mocker):
    """Test basic property enforcement based on privacy settings."""
    # Create a vCard with all properties
    vcard = create_vcard(
        name="John Doe",
        email="john@example.com",
        phone="+1234567890",
        photo="base64photo",
        gender="M",
        birthday="1990-01-01",
        address="123 Main St",
        company="ACME Corp",
        title="Developer",
    )
    item = create_item(vcard)

    # Mock privacy settings to disallow company and title
    privacy_enforcement._privacy_db.get_user_settings.return_value = mocker.Mock(
        disallow_photo=False,
        disallow_gender=True,
        disallow_birthday=False,
        disallow_address=False,
        disallow_company=True,
        disallow_title=True,
    )

    # Apply privacy enforcement
    modified_item = privacy_enforcement.enforce_privacy(item)
    modified_vcard = modified_item.vobject_item

    # Verify properties were removed
    assert 'org' not in vcard.contents
    assert 'title' not in vcard.contents
    assert 'gender' not in vcard.contents

    # Verify other properties remain
    assert 'n' in modified_vcard.contents
    assert 'fn' in modified_vcard.contents
    assert 'email' in modified_vcard.contents
    assert 'tel' in modified_vcard.contents
    assert 'photo' in modified_vcard.contents
    assert 'bday' in modified_vcard.contents
    assert 'adr' in modified_vcard.contents


def test_most_restrictive_settings(privacy_enforcement, create_vcard, create_item, mocker):
    """Test that the most restrictive settings are applied when multiple matches exist."""
    vcard = create_vcard(
        name="John Doe",
        email="john@example.com",
        phone="+1234567890",
        photo="base64photo",
        gender="M",
        birthday="1990-01-01",
        address="123 Main St",
        company="ACME Corp",
        title="Developer",
    )
    item = create_item(vcard)

    # Mock privacy settings with different restrictions
    def get_settings(identifier):
        if identifier == "john@example.com":
            return mocker.Mock(
                disallow_photo=False,
                disallow_gender=False,
                disallow_company=True,
                disallow_title=True,
                disallow_birthday=False,
                disallow_address=False,
            )
        elif identifier == "+1234567890":
            return mocker.Mock(
                disallow_photo=True,
                disallow_gender=True,
                disallow_company=False,
                disallow_title=False,
                disallow_birthday=False,
                disallow_address=False,
            )
        return None

    privacy_enforcement._privacy_db.get_user_settings.side_effect = get_settings

    # Apply privacy enforcement
    modified_item = privacy_enforcement.enforce_privacy(item)
    modified_vcard = modified_item.vobject_item

    # Verify properties were removed based on both identifiers
    assert 'org' not in modified_vcard.contents
    assert 'title' not in modified_vcard.contents
    assert 'photo' not in modified_vcard.contents
    assert 'gender' not in modified_vcard.contents

    # Verify other properties remain
    assert 'n' in modified_vcard.contents
    assert 'fn' in modified_vcard.contents
    assert 'email' in modified_vcard.contents
    assert 'tel' in modified_vcard.contents
    assert 'bday' in modified_vcard.contents
    assert 'adr' in modified_vcard.contents


def test_non_vcard_item(privacy_enforcement, mocker):
    """Test that non-vCard items are returned unchanged."""
    # Create a non-vCard item with required properties
    item = radicale_item.Item(
        collection_path=pathutils.strip_path(pathutils.sanitize_path("/test/collection")),
        text="BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n",
        component_name="VCALENDAR",
        name="VCALENDAR"
    )

    # Apply privacy enforcement
    modified_item = privacy_enforcement.enforce_privacy(item)

    # Verify the item was returned unchanged
    assert modified_item.component_name == "VCALENDAR"
    assert modified_item.name == "VCALENDAR"


def test_privacy_violation_enforcement(privacy_enforcement, create_vcard, create_item, mocker):
    """Test that vCards violating privacy settings are enforced."""
    vcard = create_vcard(
        name="John Doe",
        email="john@example.com",
        phone="+1234567890",
        photo="base64photo",
        birthday="1990-01-01",
        address="123 Main St",
        gender="M",
        company="ACME Corp",
        title="Developer",
    )
    item = create_item(vcard)

    # Mock privacy settings to disallow company and title
    privacy_enforcement._privacy_db.get_user_settings.return_value = mocker.Mock(
        disallow_photo=False,
        disallow_gender=True,
        disallow_birthday=False,
        disallow_address=False,
        disallow_company=True,
        disallow_title=True,
    )

    # Apply privacy enforcement
    modified_item = privacy_enforcement.enforce_privacy(item)
    modified_vcard = modified_item.vobject_item

    # Verify properties were removed
    assert 'org' not in modified_vcard.contents
    assert 'title' not in modified_vcard.contents
    assert 'gender' not in modified_vcard.contents

    # Verify other properties remain
    assert 'n' in modified_vcard.contents
    assert 'fn' in modified_vcard.contents
    assert 'email' in modified_vcard.contents
    assert 'tel' in modified_vcard.contents
    assert 'photo' in modified_vcard.contents
    assert 'bday' in modified_vcard.contents
    assert 'adr' in modified_vcard.contents
