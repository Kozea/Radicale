"""
Tests for the OTP Twilio authentication module.
"""

import datetime
from unittest.mock import MagicMock, patch

import pytest

from radicale import config
from radicale.auth.otp_twilio import Auth


@pytest.fixture
def auth_config():
    """Fixture to provide test configuration for OTP authentication."""
    configuration = config.load()
    configuration.update({
        "auth": {
            "type": "otp_twilio",
            "twilio_account_sid": "test_account_sid",
            "twilio_auth_token": "test_auth_token",
            "twilio_service_sid": "test_service_sid",
            "jwt_secret": "test_jwt_secret_key_for_testing_only",
            "jwt_expiry": "3600"
        }
    }, "test")
    return configuration


@pytest.fixture
def otp_auth(auth_config):
    """Fixture to provide an OTP authentication instance with mocked Twilio client."""
    with patch('radicale.auth.otp_twilio.Client') as mock_client:
        # Mock the Twilio client
        mock_client.return_value = MagicMock()
        auth_instance = Auth(auth_config)
        yield auth_instance


def test_init_with_valid_config(auth_config):
    """Test initialization with valid configuration."""
    with patch('radicale.auth.otp_twilio.Client') as mock_client:
        mock_client.return_value = MagicMock()
        auth_instance = Auth(auth_config)

        assert auth_instance._account_sid == "test_account_sid"
        assert auth_instance._auth_token == "test_auth_token"
        assert auth_instance._service_sid == "test_service_sid"
        assert auth_instance._jwt_secret == "test_jwt_secret_key_for_testing_only"
        assert auth_instance._jwt_expiry == 3600


def test_init_with_missing_twilio_config():
    """Test initialization with missing Twilio configuration."""
    configuration = config.load()
    configuration.update({
        "auth": {
            "type": "otp_twilio",
            # Missing Twilio credentials
        }
    }, "test")

    with pytest.raises(RuntimeError, match="Twilio account SID, auth token and service SID are required"):
        Auth(configuration)


def test_init_with_auto_generated_jwt_secret():
    """Test initialization with auto-generated JWT secret."""
    # Create a fresh configuration without jwt_secret
    configuration = config.load()
    configuration.update({
        "auth": {
            "type": "otp_twilio",
            "twilio_account_sid": "test_account_sid",
            "twilio_auth_token": "test_auth_token",
            "twilio_service_sid": "test_service_sid",
            # No jwt_secret - should auto-generate
        }
    }, "test")

    with patch('radicale.auth.otp_twilio.Client') as mock_client:
        with patch('radicale.auth.otp_twilio.secrets.token_urlsafe') as mock_secrets:
            mock_secrets.return_value = "auto_generated_secret"
            mock_client.return_value = MagicMock()
            auth_instance = Auth(configuration)

            assert auth_instance._jwt_secret == "auto_generated_secret"


def test_send_otp_email_success(otp_auth):
    """Test successful OTP sending via email."""
    # Mock the Twilio verification response
    mock_verification = MagicMock()
    mock_verification.sid = "test_verification_sid"
    otp_auth._client.verify.v2.services.return_value.verifications.create.return_value = mock_verification

    result = otp_auth._send_otp("test@example.com")

    assert result is True
    otp_auth._client.verify.v2.services.assert_called_once_with("test_service_sid")
    otp_auth._client.verify.v2.services.return_value.verifications.create.assert_called_once_with(
        to="test@example.com", channel="email"
    )


def test_send_otp_sms_success(otp_auth):
    """Test successful OTP sending via SMS."""
    # Mock the Twilio verification response
    mock_verification = MagicMock()
    mock_verification.sid = "test_verification_sid"
    otp_auth._client.verify.v2.services.return_value.verifications.create.return_value = mock_verification

    result = otp_auth._send_otp("+1234567890")

    assert result is True
    otp_auth._client.verify.v2.services.assert_called_once_with("test_service_sid")
    otp_auth._client.verify.v2.services.return_value.verifications.create.assert_called_once_with(
        to="+1234567890", channel="sms"
    )


def test_send_otp_failure(otp_auth):
    """Test OTP sending failure."""
    # Mock Twilio exception
    otp_auth._client.verify.v2.services.return_value.verifications.create.side_effect = Exception("Twilio error")

    result = otp_auth._send_otp("test@example.com")

    assert result is False


def test_check_otp_success(otp_auth):
    """Test successful OTP validation."""
    # Mock the Twilio verification check response
    mock_verification_check = MagicMock()
    mock_verification_check.status = "approved"
    otp_auth._client.verify.v2.services.return_value.verification_checks.create.return_value = mock_verification_check

    result = otp_auth._check_otp("test@example.com", "123456")

    assert result is True
    otp_auth._client.verify.v2.services.assert_called_once_with("test_service_sid")
    otp_auth._client.verify.v2.services.return_value.verification_checks.create.assert_called_once_with(
        to="test@example.com", code="123456"
    )


def test_check_otp_failure(otp_auth):
    """Test OTP validation failure."""
    # Mock the Twilio verification check response
    mock_verification_check = MagicMock()
    mock_verification_check.status = "denied"
    otp_auth._client.verify.v2.services.return_value.verification_checks.create.return_value = mock_verification_check

    result = otp_auth._check_otp("test@example.com", "123456")

    assert result is False


def test_check_otp_exception(otp_auth):
    """Test OTP validation with Twilio exception."""
    # Mock Twilio exception
    otp_auth._client.verify.v2.services.return_value.verification_checks.create.side_effect = Exception("Twilio error")

    result = otp_auth._check_otp("test@example.com", "123456")

    assert result is False


def test_login_with_jwt_initial_request_email(otp_auth):
    """Test initial OTP request for email."""
    with patch.object(otp_auth, '_send_otp', return_value=True) as mock_send:
        user, jwt_token = otp_auth.login_with_jwt("test@example.com", "")

        assert user == ""
        assert jwt_token is None
        mock_send.assert_called_once_with("test@example.com")


def test_login_with_jwt_initial_request_phone(otp_auth):
    """Test initial OTP request for phone."""
    with patch.object(otp_auth, '_send_otp', return_value=True) as mock_send:
        user, jwt_token = otp_auth.login_with_jwt("+1234567890", "")

        assert user == ""
        assert jwt_token is None
        mock_send.assert_called_once_with("+1234567890")


def test_login_with_jwt_otp_verification_success(otp_auth):
    """Test successful OTP verification."""
    with patch.object(otp_auth, '_check_otp', return_value=True) as mock_check:
        with patch.object(otp_auth, '_generate_jwt', return_value="test_jwt_token") as mock_generate:
            user, jwt_token = otp_auth.login_with_jwt("test@example.com", "123456")

            assert user == "test@example.com"
            assert jwt_token == "test_jwt_token"
            mock_check.assert_called_once_with("test@example.com", "123456")
            mock_generate.assert_called_once_with("test@example.com")


def test_login_with_jwt_otp_verification_failure(otp_auth):
    """Test failed OTP verification."""
    with patch.object(otp_auth, '_check_otp', return_value=False) as mock_check:
        user, jwt_token = otp_auth.login_with_jwt("test@example.com", "123456")

        assert user == ""
        assert jwt_token is None
        mock_check.assert_called_once_with("test@example.com", "123456")


def test_login_with_jwt_otp_verification_exception(otp_auth):
    """Test OTP verification with exception."""
    with patch.object(otp_auth, '_check_otp', return_value=False) as mock_check:
        user, jwt_token = otp_auth.login_with_jwt("test@example.com", "123456")

        assert user == ""
        assert jwt_token is None
        mock_check.assert_called_once_with("test@example.com", "123456")


def test_check_otp_exception_handling(otp_auth):
    """Test that exceptions in _check_otp are properly handled."""
    # Mock Twilio exception in _check_otp
    otp_auth._client.verify.v2.services.return_value.verification_checks.create.side_effect = Exception("Twilio error")

    result = otp_auth._check_otp("test@example.com", "123456")

    assert result is False


def test_generate_jwt_email(otp_auth):
    """Test JWT generation for email user."""
    with patch('radicale.auth.otp_twilio.datetime') as mock_datetime:
        mock_now = datetime.datetime(2023, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)
        mock_datetime.datetime.now.return_value = mock_now

        # Mock timedelta to return a real timedelta object
        def mock_timedelta(seconds):
            return datetime.timedelta(seconds=seconds)
        mock_datetime.timedelta = mock_timedelta

        with patch('radicale.auth.otp_twilio.jwt.encode') as mock_encode:
            mock_encode.return_value = "test_jwt_token"

            result = otp_auth._generate_jwt("test@example.com")

            assert result == "test_jwt_token"
            mock_encode.assert_called_once()

            # Check the payload
            call_args = mock_encode.call_args
            payload = call_args[0][0]  # First argument is the payload

            assert payload["sub"] == "test@example.com"
            assert payload["iat"] == mock_now
            assert payload["exp"] == mock_now + datetime.timedelta(seconds=3600)
            assert payload["identifier_type"] == "email"
            assert payload["auth_method"] == "otp_twilio"


def test_generate_jwt_phone(otp_auth):
    """Test JWT generation for phone user."""
    with patch('radicale.auth.otp_twilio.datetime') as mock_datetime:
        mock_now = datetime.datetime(2023, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)
        mock_datetime.datetime.now.return_value = mock_now

        # Mock timedelta to return a real timedelta object
        def mock_timedelta(seconds):
            return datetime.timedelta(seconds=seconds)
        mock_datetime.timedelta = mock_timedelta

        with patch('radicale.auth.otp_twilio.jwt.encode') as mock_encode:
            mock_encode.return_value = "test_jwt_token"

            result = otp_auth._generate_jwt("+1234567890")

            assert result == "test_jwt_token"
            mock_encode.assert_called_once()

            # Check the payload
            call_args = mock_encode.call_args
            payload = call_args[0][0]  # First argument is the payload

            assert payload["sub"] == "+1234567890"
            assert payload["identifier_type"] == "phone"


def test_validate_jwt_success(otp_auth):
    """Test successful JWT validation."""
    with patch('radicale.auth.otp_twilio.jwt.decode') as mock_decode:
        mock_decode.return_value = {"sub": "test@example.com"}

        result = otp_auth._validate_jwt("valid_jwt_token")

        assert result == "test@example.com"
        mock_decode.assert_called_once_with(
            "valid_jwt_token",
            "test_jwt_secret_key_for_testing_only",
            algorithms=["HS256"]
        )


def test_validate_jwt_expired(otp_auth):
    """Test JWT validation with expired token."""
    with patch('radicale.auth.otp_twilio.jwt.decode') as mock_decode:
        from jwt import ExpiredSignatureError
        mock_decode.side_effect = ExpiredSignatureError("Token expired")

        result = otp_auth._validate_jwt("expired_jwt_token")

        assert result is None


def test_validate_jwt_invalid(otp_auth):
    """Test JWT validation with invalid token."""
    with patch('radicale.auth.otp_twilio.jwt.decode') as mock_decode:
        from jwt import InvalidTokenError
        mock_decode.side_effect = InvalidTokenError("Invalid token")

        result = otp_auth._validate_jwt("invalid_jwt_token")

        assert result is None


def test_validate_jwt_missing_subject(otp_auth):
    """Test JWT validation with missing subject."""
    with patch('radicale.auth.otp_twilio.jwt.decode') as mock_decode:
        mock_decode.return_value = {}  # No 'sub' field

        result = otp_auth._validate_jwt("jwt_token_without_subject")

        assert result is None


def test_login_method_compatibility(otp_auth):
    """Test the _login method for compatibility with base auth."""
    with patch.object(otp_auth, 'login_with_jwt', return_value=("test@example.com", "jwt_token")):
        result = otp_auth._login("test@example.com", "123456")

        assert result == "test@example.com"


def test_is_authenticated_method(otp_auth):
    """Test the is_authenticated method."""
    with patch.object(otp_auth, 'login_with_jwt', return_value=("test@example.com", "jwt_token")):
        result = otp_auth.is_authenticated("test@example.com", "123456")

        assert result is True


def test_is_authenticated_method_failure(otp_auth):
    """Test the is_authenticated method with failed authentication."""
    with patch.object(otp_auth, 'login_with_jwt', return_value=("", None)):
        result = otp_auth.is_authenticated("test@example.com", "wrong_otp")

        assert result is False


def test_jwt_expiry_from_config():
    """Test JWT expiry configuration."""
    configuration = config.load()
    configuration.update({
        "auth": {
            "type": "otp_twilio",
            "twilio_account_sid": "test_account_sid",
            "twilio_auth_token": "test_auth_token",
            "twilio_service_sid": "test_service_sid",
            "jwt_secret": "test_secret",
            "jwt_expiry": "7200"  # 2 hours
        }
    }, "test")

    with patch('radicale.auth.otp_twilio.Client') as mock_client:
        mock_client.return_value = MagicMock()
        auth_instance = Auth(configuration)

        assert auth_instance._jwt_expiry == 7200


def test_jwt_expiry_default():
    """Test default JWT expiry when not specified."""
    configuration = config.load()
    configuration.update({
        "auth": {
            "type": "otp_twilio",
            "twilio_account_sid": "test_account_sid",
            "twilio_auth_token": "test_auth_token",
            "twilio_service_sid": "test_service_sid",
            "jwt_secret": "test_secret",
            # No jwt_expiry specified
        }
    }, "test")

    with patch('radicale.auth.otp_twilio.Client') as mock_client:
        mock_client.return_value = MagicMock()
        auth_instance = Auth(configuration)

        assert auth_instance._jwt_expiry == 3600  # Default 1 hour


def test_send_otp_no_verification_sid(otp_auth):
    """Test OTP sending when verification has no SID."""
    # Mock the Twilio verification response without SID
    mock_verification = MagicMock()
    mock_verification.sid = None
    otp_auth._client.verify.v2.services.return_value.verifications.create.return_value = mock_verification

    result = otp_auth._send_otp("test@example.com")

    assert result is False


def test_check_otp_no_verification_sid(otp_auth):
    """Test OTP checking when verification check has no SID."""
    # Mock the Twilio verification check response without SID
    mock_verification_check = MagicMock()
    mock_verification_check.sid = None
    otp_auth._client.verify.v2.services.return_value.verification_checks.create.return_value = mock_verification_check

    result = otp_auth._check_otp("test@example.com", "123456")

    assert result is False


def test_login_with_jwt_send_otp_failure(otp_auth):
    """Test initial OTP request when sending fails."""
    with patch.object(otp_auth, '_send_otp', return_value=False) as mock_send:
        user, jwt_token = otp_auth.login_with_jwt("test@example.com", "")

        assert user == ""
        assert jwt_token is None
        mock_send.assert_called_once_with("test@example.com")


def test_real_jwt_generation_and_validation(otp_auth):
    """Test real JWT generation and validation (integration test)."""
    # Generate a real JWT
    user = "test@example.com"
    jwt_token = otp_auth._generate_jwt(user)

    # Validate the JWT
    validated_user = otp_auth._validate_jwt(jwt_token)

    assert validated_user == user
    assert jwt_token is not None
    assert len(jwt_token) > 0


def test_jwt_token_expiry(otp_auth):
    """Test that JWT tokens actually expire."""
    # Generate a JWT with very short expiry
    original_expiry = otp_auth._jwt_expiry
    otp_auth._jwt_expiry = 1  # 1 second

    user = "test@example.com"
    jwt_token = otp_auth._generate_jwt(user)

    # Token should be valid immediately
    validated_user = otp_auth._validate_jwt(jwt_token)
    assert validated_user == user

    # Wait for token to expire
    import time
    time.sleep(2)

    # Token should be expired now
    expired_user = otp_auth._validate_jwt(jwt_token)
    assert expired_user is None

    # Restore original expiry
    otp_auth._jwt_expiry = original_expiry


def test_identifier_type_detection():
    """Test automatic identifier type detection."""
    configuration = config.load()
    configuration.update({
        "auth": {
            "type": "otp_twilio",
            "twilio_account_sid": "test_account_sid",
            "twilio_auth_token": "test_auth_token",
            "twilio_service_sid": "test_service_sid",
            "jwt_secret": "test_secret",
        }
    }, "test")

    with patch('radicale.auth.otp_twilio.Client') as mock_client:
        mock_client.return_value = MagicMock()
        auth_instance = Auth(configuration)

        # Test email detection
        with patch('radicale.auth.otp_twilio.jwt.encode') as mock_encode:
            auth_instance._generate_jwt("user@example.com")
            payload = mock_encode.call_args[0][0]
            assert payload["identifier_type"] == "email"

        # Test phone detection
        with patch('radicale.auth.otp_twilio.jwt.encode') as mock_encode:
            auth_instance._generate_jwt("+1234567890")
            payload = mock_encode.call_args[0][0]
            assert payload["identifier_type"] == "phone"
