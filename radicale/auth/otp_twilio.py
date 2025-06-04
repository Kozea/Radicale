# This file is part of Radicale Server - Calendar Server
#
# This library is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Radicale.  If not, see <http://www.gnu.org/licenses/>.

"""
Authentication backend that implements OTP (One-Time Password) authentication
using Twilio for sending OTP codes via SMS or email.
"""

import random
import secrets
import string
import time
from typing import Dict, Optional, Tuple

from twilio.rest import Client

from radicale import auth, config
from radicale.log import logger


class Auth(auth.BaseAuth):
    def __init__(self, configuration: config.Configuration) -> None:
        """Initialize the OTP authentication plugin.

        Args:
            configuration: The Radicale configuration object.
        """
        super().__init__(configuration)
        # Twilio configuration
        self._account_sid: str = configuration.get("auth", "twilio_account_sid")
        self._auth_token: str = configuration.get("auth", "twilio_auth_token")
        self._from_number: str = configuration.get("auth", "twilio_from_number")
        self._from_email: str = configuration.get("auth", "twilio_from_email")

        if not all([self._account_sid, self._auth_token]):
            raise RuntimeError("Twilio account SID and auth token are required")

        # OTP configuration
        self._otp_length: int = configuration.get("auth", "otp_length")
        self._otp_expiry: int = configuration.get("auth", "otp_expiry")

        # Store OTP codes and their expiry times
        self._otp_store: Dict[str, Tuple[str, float]] = {}

        # Initialize Twilio client
        self._twilio_client: Client = Client(self._account_sid, self._auth_token)

        # Session configuration
        self._session_expiry: int = 3600  # 1 hour session expiry (can be made configurable)
        self._session_store: Dict[str, Tuple[str, float]] = {}  # token -> (user, expiry)

        logger.info("OTP authentication initialized")

    def _generate_otp(self) -> str:
        """Generate a random OTP code.

        Returns:
            A string containing the generated OTP code.
        """
        return ''.join(random.choices(string.digits, k=self._otp_length))

    def _send_otp(self, login: str, otp: str) -> bool:
        """Send OTP code via SMS or email using Twilio.

        Args:
            login: The phone number or email address to send the OTP to.
            otp: The OTP code to send.

        Returns:
            True if the OTP was sent successfully, False otherwise.
        """
        try:
            if "@" in login:
                # Treat as email
                message = self._twilio_client.messages.create(
                    body=f"Your Radicale authentication code is: {otp}",
                    from_=f"Radicale <{self._from_email}>",
                    to=login
                )
            else:
                # Treat as phone number
                message = self._twilio_client.messages.create(
                    body=f"Your Radicale authentication code is: {otp}",
                    from_=self._from_number,
                    to=login
                )
            return bool(message.sid)
        except Exception as e:
            logger.error("Failed to send OTP via Twilio: %s", str(e))
            return False

    def _get_stored_otp(self, login: str) -> Optional[Tuple[str, float]]:
        """Get the stored OTP for a user if it exists and is not expired.

        Args:
            login: The user's login identifier.

        Returns:
            Tuple of (OTP, expiry_time) if valid OTP exists, None otherwise.
        """
        if login not in self._otp_store:
            return None

        stored_otp, expiry_time = self._otp_store[login]
        if time.time() > expiry_time:
            del self._otp_store[login]
            logger.warning("OTP expired for user: %s", login)
            return None

        return stored_otp, expiry_time

    def _generate_session_token(self) -> str:
        return secrets.token_urlsafe(32)

    def login_with_session(self, login: str, password: str) -> Tuple[str, Optional[str]]:
        """Validate credentials using OTP.

        Args:
            login: The phone number or email address to authenticate.
            password: The OTP code to validate.

        Returns:
            Tuple of (login, session_token) if authentication is successful, empty strings otherwise.
        """
        # If password is empty, this is the initial request - generate and send OTP
        if not password:
            otp = self._generate_otp()
            if self._send_otp(login, otp):
                self._otp_store[login] = (otp, time.time() + self._otp_expiry)
                logger.info("New OTP sent to user: %s", login)
            return "", None

        # If password is provided, validate it against stored OTP
        stored_otp_data = self._get_stored_otp(login)
        if not stored_otp_data:
            otp = self._generate_otp()
            if self._send_otp(login, otp):
                self._otp_store[login] = (otp, time.time() + self._otp_expiry)
                logger.info("New OTP sent to user: %s", login)
            return "", None

        stored_otp, _ = stored_otp_data
        if password == stored_otp:
            del self._otp_store[login]
            logger.info("User authenticated successfully: %s", login)
            session_token = self._generate_session_token()
            self._session_store[session_token] = (login, time.time() + self._session_expiry)
            return login, session_token

        logger.warning("Invalid OTP provided for user: %s", login)
        return "", None

    def _login(self, login: str, password: str) -> str:
        user, _ = self.login_with_session(login, password)
        return user

    def validate_session(self, token: str) -> Optional[str]:
        data = self._session_store.get(token)
        if not data:
            return None
        user, expiry = data
        if time.time() > expiry:
            del self._session_store[token]
            return None
        return user

    def invalidate_session(self, token: str) -> None:
        if token in self._session_store:
            del self._session_store[token]

    def is_authenticated(self, user: str, password: str) -> bool:
        """Check if the user is authenticated.

        Args:
            user: The user's login identifier.
            password: The OTP code to validate.

        Returns:
            True if the user is authenticated, False otherwise.
        """
        result, _ = self.login_with_session(user, password)
        return bool(result)
