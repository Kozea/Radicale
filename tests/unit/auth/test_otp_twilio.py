"""Unit tests for the OTP Twilio authentication backend."""

import time
import unittest
from unittest.mock import MagicMock, patch

from radicale import config
from radicale.auth.otp_twilio import Auth


class TestOTPTwilioAuth(unittest.TestCase):
    """Test cases for the OTP Twilio authentication backend."""

    def setUp(self):
        """Set up test cases."""
        # Mock configuration
        self.config = MagicMock(spec=config.Configuration)
        self.config.get.side_effect = lambda section, option: {
            "auth": {
                "type": "otp_twilio",
                "twilio_account_sid": "test_sid",
                "twilio_auth_token": "test_token",
                "twilio_from_number": "+1234567890",
                "twilio_from_email": "test@example.com",
                "otp_length": 6,
                "otp_expiry": 300,  # 5 minutes
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

        # Create auth instance with mocked Twilio client
        with patch("radicale.auth.otp_twilio.Client") as mock_client:
            self.mock_twilio = mock_client.return_value
            self.mock_message = MagicMock()
            self.mock_message.sid = "test_sid"
            self.mock_twilio.messages.create.return_value = self.mock_message
            self.auth = Auth(self.config)

    def test_init(self):
        """Test initialization of the auth backend."""
        self.assertEqual(self.auth._account_sid, "test_sid")
        self.assertEqual(self.auth._auth_token, "test_token")
        self.assertEqual(self.auth._from_number, "+1234567890")
        self.assertEqual(self.auth._from_email, "test@example.com")
        self.assertEqual(self.auth._otp_length, 6)
        self.assertEqual(self.auth._otp_expiry, 300)

    def test_init_missing_credentials(self):
        """Test initialization with missing Twilio credentials."""
        self.config.get.side_effect = lambda section, option: {
            "auth": {
                "type": "otp_twilio",
                "twilio_account_sid": "",
                "twilio_auth_token": "",
                "twilio_from_number": "+1234567890",
                "twilio_from_email": "test@example.com",
                "otp_length": 6,
                "otp_expiry": 300,
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

        with self.assertRaises(RuntimeError):
            Auth(self.config)

    def test_generate_otp(self):
        """Test OTP generation."""
        otp = self.auth._generate_otp()
        self.assertEqual(len(otp), 6)
        self.assertTrue(otp.isdigit())

    def test_send_otp_sms(self):
        """Test sending OTP via SMS."""
        self.auth._otp_method = "sms"
        result = self.auth._send_otp("+1234567890", "123456")
        self.assertTrue(result)
        self.mock_twilio.messages.create.assert_called_once_with(
            body="Your Radicale authentication code is: 123456",
            from_="+1234567890",
            to="+1234567890"
        )

    def test_send_otp_email(self):
        """Test sending OTP via email."""
        self.auth._otp_method = "email"
        result = self.auth._send_otp("user@example.com", "123456")
        self.assertTrue(result)
        self.mock_twilio.messages.create.assert_called_once_with(
            body="Your Radicale authentication code is: 123456",
            from_="Radicale <test@example.com>",
            to="user@example.com"
        )

    def test_send_otp_failure(self):
        """Test OTP sending failure."""
        self.mock_twilio.messages.create.side_effect = Exception("Twilio error")
        result = self.auth._send_otp("user@example.com", "123456")
        self.assertFalse(result)

    def test_get_stored_otp(self):
        """Test retrieving stored OTP."""
        # Store an OTP
        self.auth._otp_store["user@example.com"] = ("123456", time.time() + 300)

        # Test valid OTP
        stored_otp = self.auth._get_stored_otp("user@example.com")
        self.assertIsNotNone(stored_otp)
        self.assertEqual(stored_otp[0], "123456")

        # Test expired OTP
        self.auth._otp_store["user@example.com"] = ("123456", time.time() - 1)
        stored_otp = self.auth._get_stored_otp("user@example.com")
        self.assertIsNone(stored_otp)
        self.assertNotIn("user@example.com", self.auth._otp_store)

        # Test non-existent OTP
        stored_otp = self.auth._get_stored_otp("nonexistent@example.com")
        self.assertIsNone(stored_otp)

    def test_login_initial_request(self):
        """Test initial login request (empty password)."""
        user, session_token = self.auth.login_with_session("user@example.com", "")
        self.assertEqual(user, "")
        self.assertIsNone(session_token)
        self.assertIn("user@example.com", self.auth._otp_store)
        self.mock_twilio.messages.create.assert_called_once()

    def test_login_valid_otp(self):
        """Test login with valid OTP."""
        # Store an OTP
        self.auth._otp_store["user@example.com"] = ("123456", time.time() + 300)
        # Test valid OTP
        user, session_token = self.auth.login_with_session("user@example.com", "123456")
        self.assertEqual(user, "user@example.com")
        self.assertIsInstance(session_token, str)
        self.assertNotIn("user@example.com", self.auth._otp_store)

    def test_login_invalid_otp(self):
        """Test login with invalid OTP."""
        # Store an OTP
        self.auth._otp_store["user@example.com"] = ("123456", time.time() + 300)
        # Test invalid OTP
        user, session_token = self.auth.login_with_session("user@example.com", "654321")
        self.assertEqual(user, "")
        self.assertIsNone(session_token)
        self.assertIn("user@example.com", self.auth._otp_store)

    def test_login_expired_otp(self):
        """Test login with expired OTP."""
        # Store an expired OTP
        self.auth._otp_store["user@example.com"] = ("123456", time.time() - 1)
        # Test expired OTP
        user, session_token = self.auth.login_with_session("user@example.com", "123456")
        self.assertEqual(user, "")
        self.assertIsNone(session_token)
        self.assertIn("user@example.com", self.auth._otp_store)
        self.mock_twilio.messages.create.assert_called_once()

    def test_is_authenticated(self):
        """Test is_authenticated method."""
        # Store an OTP
        self.auth._otp_store["user@example.com"] = ("123456", time.time() + 300)

        # Test valid OTP
        self.assertTrue(self.auth.is_authenticated("user@example.com", "123456"))

        # Test invalid OTP
        self.assertFalse(self.auth.is_authenticated("user@example.com", "654321"))

        # Test empty password
        self.assertFalse(self.auth.is_authenticated("user@example.com", ""))

    def test_login_valid_otp_returns_session_token(self):
        """Test login with valid OTP returns a session token."""
        self.auth._otp_store["user@example.com"] = ("123456", time.time() + 300)
        user, session_token = self.auth.login_with_session("user@example.com", "123456")
        self.assertEqual(user, "user@example.com")
        self.assertIsInstance(session_token, str)
        self.assertTrue(session_token in self.auth._session_store)

    def test_login_initial_request_no_session_token(self):
        """Test initial login request does not return a session token."""
        user, session_token = self.auth.login_with_session("user@example.com", "")
        self.assertEqual(user, "")
        self.assertIsNone(session_token)

    def test_login_invalid_otp_no_session_token(self):
        """Test login with invalid OTP does not return a session token."""
        self.auth._otp_store["user@example.com"] = ("123456", time.time() + 300)
        user, session_token = self.auth.login_with_session("user@example.com", "654321")
        self.assertEqual(user, "")
        self.assertIsNone(session_token)

    def test_validate_session_token(self):
        """Test validating a session token after successful login."""
        self.auth._otp_store["user@example.com"] = ("123456", time.time() + 300)
        user, session_token = self.auth.login_with_session("user@example.com", "123456")
        validated_user = self.auth.validate_session(session_token)
        self.assertEqual(validated_user, "user@example.com")

    def test_session_token_expiry(self):
        """Test that session tokens expire after the set time."""
        token = self.auth._generate_session_token()
        self.auth._session_store[token] = ("user@example.com", time.time() - 1)  # expired
        validated_user = self.auth.validate_session(token)
        self.assertIsNone(validated_user)
        self.assertNotIn(token, self.auth._session_store)

    def test_invalidate_session_token(self):
        """Test that session tokens can be invalidated manually."""
        token = self.auth._generate_session_token()
        self.auth._session_store[token] = ("user@example.com", time.time() + 300)
        self.auth.invalidate_session(token)
        self.assertNotIn(token, self.auth._session_store)


if __name__ == "__main__":
    unittest.main()
