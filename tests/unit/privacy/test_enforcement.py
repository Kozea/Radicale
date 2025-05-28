"""Test suite for privacy enforcement functionality."""

import logging

import pytest
import vobject

import radicale.item as radicale_item
from radicale import config, pathutils
from radicale.privacy.enforcement import (PrivacyEnforcement,
                                          PrivacyViolationError)

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


def test_basic_property_removal(privacy_enforcement, create_vcard, create_item, mocker):
    """Test basic property rejection based on privacy settings."""
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

    # Mock privacy settings to disallow company and title
    privacy_enforcement._privacy_db.get_user_settings.return_value = mocker.Mock(
        disallow_company=True,
        disallow_title=True,
        disallow_photo=False,
        disallow_birthday=False,
        disallow_address=False
    )

    # Verify that privacy enforcement raises an exception
    with pytest.raises(PrivacyViolationError) as exc_info:
        privacy_enforcement.enforce_privacy(item)

    # Verify the error message contains the violated fields
    error_msg = str(exc_info.value)
    assert "Privacy violation" in error_msg
    assert "org" in error_msg  # vCard property name for company
    assert "title" in error_msg  # vCard property name for title

    # Verify that the vCard was not modified
    assert 'org' in vcard.contents
    assert 'title' in vcard.contents
    assert vcard.org.value == ["ACME Corp"]
    assert vcard.title.value == "Developer"


def test_multiple_identifiers(privacy_enforcement, create_vcard, create_item, mocker):
    """Test privacy enforcement with multiple identifiers (email and phone)."""
    vcard = create_vcard(
        name="John Doe",
        email="john@example.com",
        phone="+1234567890",
        company="ACME Corp",
        title="Developer",
    )
    item = create_item(vcard)

    # Mock privacy settings for both identifiers
    def get_settings(identifier):
        return mocker.Mock(disallow_company=True, disallow_title=True)

    privacy_enforcement._privacy_db.get_user_settings.side_effect = get_settings

    # Verify that privacy enforcement raises an exception
    with pytest.raises(PrivacyViolationError) as exc_info:
        privacy_enforcement.enforce_privacy(item)

    # Verify the error message contains all violated fields
    error_msg = str(exc_info.value)
    assert "Privacy violation" in error_msg
    assert "org" in error_msg
    assert "title" in error_msg

    # Verify that the vCard was not modified
    assert 'n' in vcard.contents
    assert 'fn' in vcard.contents
    assert 'email' in vcard.contents
    assert 'tel' in vcard.contents
    assert 'org' in vcard.contents
    assert 'title' in vcard.contents
    assert vcard.n.value.family == ["John", "Doe"]
    assert vcard.fn.value == "John Doe"
    assert vcard.email.value == "john@example.com"
    assert vcard.tel.value == "+1234567890"
    assert vcard.org.value == ["ACME Corp"]
    assert vcard.title.value == "Developer"


def test_most_restrictive_settings(privacy_enforcement, create_vcard, create_item, mocker):
    """Test that the most restrictive settings are applied when multiple matches exist."""
    vcard = create_vcard(
        name="John Doe",
        email="john@example.com",
        phone="+1234567890",
        company="ACME Corp",
        title="Developer",
        photo="base64photo"
    )
    item = create_item(vcard)

    # Mock privacy settings with different restrictions
    def get_settings(identifier):
        if identifier == "john@example.com":
            return mocker.Mock(
                disallow_company=True,
                disallow_title=True,
                disallow_photo=False,
            )
        elif identifier == "+1234567890":
            return mocker.Mock(
                disallow_company=False,
                disallow_title=False,
                disallow_photo=True,
            )
        return None

    privacy_enforcement._privacy_db.get_user_settings.side_effect = get_settings

    # Verify that privacy enforcement raises an exception
    with pytest.raises(PrivacyViolationError) as exc_info:
        privacy_enforcement.enforce_privacy(item)

    # Verify the error message contains all violated fields
    error_msg = str(exc_info.value)
    assert "Privacy violation" in error_msg
    assert "org" in error_msg
    assert "title" in error_msg
    assert "photo" in error_msg

    # Verify that the vCard was not modified
    assert 'n' in vcard.contents
    assert 'fn' in vcard.contents
    assert 'email' in vcard.contents
    assert 'tel' in vcard.contents
    assert 'org' in vcard.contents
    assert 'title' in vcard.contents
    assert 'photo' in vcard.contents
    assert vcard.n.value.family == ["John", "Doe"]
    assert vcard.fn.value == "John Doe"
    assert vcard.email.value == "john@example.com"
    assert vcard.tel.value == "+1234567890"
    assert vcard.org.value == ["ACME Corp"]
    assert vcard.title.value == "Developer"
    assert vcard.photo.value == "base64photo"


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


def test_privacy_violation_rejection(privacy_enforcement, create_vcard, create_item, mocker):
    """Test that vCards violating privacy settings are rejected."""
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

    # Mock privacy settings to disallow company and title
    privacy_enforcement._privacy_db.get_user_settings.return_value = mocker.Mock(
        disallow_company=True,
        disallow_title=True,
        disallow_photo=False,
        disallow_birthday=False,
        disallow_address=False
    )

    # Verify that privacy enforcement raises an exception
    with pytest.raises(PrivacyViolationError) as exc_info:
        privacy_enforcement.enforce_privacy(item)

    # Verify the error message contains the violated fields
    error_msg = str(exc_info.value)
    assert "Privacy violation" in error_msg
    assert "org" in error_msg
    assert "title" in error_msg

    # Verify that the vCard was not modified
    assert 'n' in vcard.contents
    assert 'fn' in vcard.contents
    assert 'email' in vcard.contents
    assert 'tel' in vcard.contents
    assert 'org' in vcard.contents
    assert 'title' in vcard.contents
    assert 'photo' in vcard.contents
    assert 'bday' in vcard.contents
    assert 'adr' in vcard.contents
    assert vcard.n.value.family == ["John", "Doe"]
    assert vcard.fn.value == "John Doe"
    assert vcard.email.value == "john@example.com"
    assert vcard.tel.value == "+1234567890"
    assert vcard.org.value == ["ACME Corp"]
    assert vcard.title.value == "Developer"
    assert vcard.photo.value == "base64photo"
    assert vcard.bday.value == "1990-01-01"
    assert vcard.adr.value.street == "123 Main St"


def test_multiple_privacy_violations(privacy_enforcement, create_vcard, create_item, mocker):
    """Test that multiple privacy violations are reported correctly."""
    vcard = create_vcard(
        name="John Doe",
        email="john@example.com",
        phone="+1234567890",
        company="ACME Corp",
        title="Developer"
    )
    item = create_item(vcard)

    # Mock privacy settings to disallow multiple fields
    privacy_enforcement._privacy_db.get_user_settings.return_value = mocker.Mock(
        disallow_company=True,
        disallow_title=True,
        disallow_photo=False,
        disallow_birthday=False,
        disallow_address=False
    )

    # Verify that privacy enforcement raises an exception
    with pytest.raises(PrivacyViolationError) as exc_info:
        privacy_enforcement.enforce_privacy(item)

    # Verify the error message contains all violated fields
    error_msg = str(exc_info.value)
    assert "Privacy violation" in error_msg
    assert "org" in error_msg
    assert "title" in error_msg

    # Verify that the vCard was not modified
    assert 'n' in vcard.contents
    assert 'fn' in vcard.contents
    assert 'email' in vcard.contents
    assert 'tel' in vcard.contents
    assert 'org' in vcard.contents
    assert 'title' in vcard.contents
    assert vcard.n.value.family == ["John", "Doe"]
    assert vcard.fn.value == "John Doe"
    assert vcard.email.value == "john@example.com"
    assert vcard.tel.value == "+1234567890"
    assert vcard.org.value == ["ACME Corp"]
    assert vcard.title.value == "Developer"
