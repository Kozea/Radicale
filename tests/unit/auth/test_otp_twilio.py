import time
from unittest.mock import MagicMock, Mock, patch

import pytest
from twilio.base.exceptions import TwilioRestException

from radicale import config
from radicale.auth.otp_twilio import Auth


@pytest.fixture
def mock_config():
    """Create a mock configuration for testing."""
    config_mock = Mock(spec=config.Configuration)
    config_mock.get.side_effect = lambda section, option: {
        "auth": {
            "type": "otp_twilio",
            "twilio_account_sid": "test_account_sid",
            "twilio_auth_token": "test_auth_token",
            "twilio_from_number": "+1234567890",
            "twilio_from_email": "test@example.com",
            "otp_length": 6,
            "otp_expiry": 300,  # 5 minutes
            "otp_method": "sms",
            # Required by BaseAuth
            "lc_username": False,
            "uc_username": False,
            "strip_domain": False,
            "urldecode_username": False,
            "delay": 1,
            "cache_logins": False,
            "cache_successful_logins_expiry": 15,
            "cache_failed_logins_expiry": 90,
        }
    }[section][option]
    return config_mock


@pytest.fixture
def mock_twilio_client():
    """Create a mock Twilio client."""
    mock_client = MagicMock()
    mock_messages = MagicMock()
    mock_client.messages = mock_messages
    return mock_client


@pytest.fixture
def auth_instance(mock_config, mock_twilio_client):
    """Create an instance of the Auth class for testing."""
    with patch('twilio.rest.Client', return_value=mock_twilio_client):
        auth = Auth(mock_config)
        auth._twilio_client = mock_twilio_client
        return auth


def test_init_with_valid_config(mock_config):
    """Test initialization with valid configuration."""
    with patch('twilio.rest.Client'):
        auth = Auth(mock_config)
        assert auth._account_sid == "test_account_sid"
        assert auth._auth_token == "test_auth_token"
        assert auth._from_number == "+1234567890"
        assert auth._from_email == "test@example.com"
        assert auth._otp_length == 6
        assert auth._otp_expiry == 300
        assert auth._otp_method == "sms"


def test_init_with_missing_credentials(mock_config):
    """Test initialization with missing Twilio credentials."""
    mock_config.get.side_effect = lambda section, option: {
        "auth": {
            "type": "otp_twilio",
            "twilio_account_sid": "",
            "twilio_auth_token": "",
            "twilio_from_number": "+1234567890",
            "twilio_from_email": "test@example.com",
            "otp_length": 6,
            "otp_expiry": 300,
            "otp_method": "sms",
            # Required by BaseAuth
            "lc_username": False,
            "uc_username": False,
            "strip_domain": False,
            "urldecode_username": False,
            "delay": 1,
            "cache_logins": False,
            "cache_successful_logins_expiry": 15,
            "cache_failed_logins_expiry": 90,
        }
    }[section][option]

    with pytest.raises(RuntimeError, match="Twilio account SID and auth token are required"):
        Auth(mock_config)


def test_generate_otp(auth_instance):
    """Test OTP generation."""
    otp = auth_instance._generate_otp()
    assert len(otp) == 6
    assert otp.isdigit()


def test_send_otp_sms(auth_instance, mock_twilio_client):
    """Test sending OTP via SMS."""
    mock_message = MagicMock()
    mock_message.sid = "test_sid"
    mock_twilio_client.messages.create.return_value = mock_message

    result = auth_instance._send_otp("+1234567890", "123456")
    assert result is True
    mock_twilio_client.messages.create.assert_called_once_with(
        body="Your Radicale authentication code is: 123456",
        from_="+1234567890",
        to="+1234567890"
    )


def test_send_otp_email(auth_instance, mock_twilio_client):
    """Test sending OTP via email."""
    auth_instance._otp_method = "email"
    mock_message = MagicMock()
    mock_message.sid = "test_sid"
    mock_twilio_client.messages.create.return_value = mock_message

    result = auth_instance._send_otp("test@example.com", "123456")
    assert result is True
    mock_twilio_client.messages.create.assert_called_once_with(
        body="Your Radicale authentication code is: 123456",
        from_="Radicale <test@example.com>",
        to="test@example.com"
    )


def test_send_otp_failure(auth_instance, mock_twilio_client):
    """Test OTP sending failure."""
    mock_twilio_client.messages.create.side_effect = TwilioRestException(
        msg="Twilio error",
        uri="test_uri",
        code=12345,
        status=500
    )
    result = auth_instance._send_otp("+1234567890", "123456")
    assert result is False


def test_login_with_valid_otp(auth_instance, mock_twilio_client):
    """Test login with valid OTP."""
    # Mock successful OTP sending
    mock_message = MagicMock()
    mock_message.sid = "test_sid"
    mock_twilio_client.messages.create.return_value = mock_message

    # First attempt should generate and send OTP
    result = auth_instance._login("+1234567890", "any_password")
    assert result == ""
    assert "+1234567890" in auth_instance._otp_store

    # Get the stored OTP
    stored_otp, _ = auth_instance._otp_store["+1234567890"]

    # Second attempt with correct OTP should succeed
    result = auth_instance._login("+1234567890", stored_otp)
    assert result == "+1234567890"
    assert "+1234567890" not in auth_instance._otp_store


def test_login_with_expired_otp(auth_instance):
    """Test login with expired OTP."""
    # Store an expired OTP
    auth_instance._otp_store["+1234567890"] = ("123456", time.time() - 1)

    result = auth_instance._login("+1234567890", "123456")
    assert result == ""
    assert "+1234567890" not in auth_instance._otp_store


def test_login_with_invalid_otp(auth_instance):
    """Test login with invalid OTP."""
    # Store a valid OTP
    auth_instance._otp_store["+1234567890"] = ("123456", time.time() + 300)

    result = auth_instance._login("+1234567890", "wrong_otp")
    assert result == ""
    assert "+1234567890" in auth_instance._otp_store  # OTP should still be valid
