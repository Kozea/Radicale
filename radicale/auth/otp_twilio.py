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

from typing import Optional, Tuple

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
        self._service_sid: str = configuration.get("auth", "twilio_service_sid")

        if not all([self._account_sid, self._auth_token, self._service_sid]):
            raise RuntimeError("Twilio account SID, auth token and service SID are required")

        # Initialize Twilio client
        self._client: Client = Client(self._account_sid, self._auth_token)

        logger.info("OTP authentication initialized")

    def _send_otp(self, login: str) -> bool:
        """Send OTP code via SMS or email using Twilio.

        Args:
            login: The phone number or email address to send the OTP to.

        Returns:
            True if the OTP was sent successfully, False otherwise.
        """
        try:
            if "@" in login:
                # Treat as email
                # TODO: Implement email verification
                verification = self._client.messages.create(
                    channel="email",
                    to=login
                )
            else:
                # Treat as phone number
                verification = self._client.verify.v2.services(
                    self._service_sid
                ).verifications.create(to=login, channel="sms")
                logger.info("verification : %s", verification)
                logger.info("verification.sid: %s", verification.sid)
            return bool(verification.sid)
        except Exception as e:
            logger.error("Failed to send OTP via Twilio: %s", str(e))
            return False

    def _check_otp(self, login: str, otp: str) -> bool:
        """Check if the OTP is valid.
        """
        try:
            verification_check = self._client.verify.v2.services(
                self._service_sid
            ).verification_checks.create(to=login, code=otp)
            logger.info("verification_check: %s", verification_check)
            logger.info("verification_check.status: %s", verification_check.status)
            return bool(verification_check.status == "approved" and verification_check.valid == "true")
        except Exception as e:
            logger.error("Failed to check OTP via Twilio: %s", str(e))
            return False

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
            if self._send_otp(login):
                logger.info("New OTP sent to user: %s", login)
            return "", None

        # If password is provided, validate it against stored OTP
        if password:
            if self._check_otp(login, password):
                logger.info("OTP validated for user: %s", login)
                logger.info("User authenticated successfully: %s", login)
                return login, None
            else:
                logger.warning("Invalid OTP provided for user: %s", login)
                return "", None

        logger.warning("Invalid OTP provided for user: %s", login)
        return "", None

    def _login(self, login: str, password: str) -> str:
        user, _ = self.login_with_session(login, password)
        return user

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
