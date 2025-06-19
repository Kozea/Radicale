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

import datetime
import secrets
from typing import Optional, Tuple

import jwt
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

        # JWT configuration
        self._jwt_secret: str = configuration.get("auth", "jwt_secret") or secrets.token_urlsafe(32)
        self._jwt_expiry: int = configuration.get("auth", "jwt_expiry") or 3600  # 1 hour default

        logger.info("AUTH: OTP authentication initialized")

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
                verification = self._client.verify.v2.services(
                    self._service_sid
                ).verifications.create(to=login, channel="email")
            else:
                # Treat as phone number
                verification = self._client.verify.v2.services(
                    self._service_sid
                ).verifications.create(to=login, channel="sms")
            logger.debug("AUTH: OTP verification.sid: %s", verification.sid)
            return bool(verification.sid)
        except Exception as e:
            logger.error("AUTH: Failed to send OTP via Twilio: %s", str(e))
            return False

    def _check_otp(self, login: str, otp: str) -> bool:
        """Check if the OTP is valid.
        """
        try:
            verification_check = self._client.verify.v2.services(
                self._service_sid
            ).verification_checks.create(to=login, code=otp)
            logger.debug("AUTH: verification_check.status: %s", verification_check.status)
            logger.debug("AUTH: verification_check.valid: %s", verification_check.valid)
            return bool(verification_check.status == "approved")
        except Exception as e:
            logger.error("AUTH: Failed to check OTP via Twilio: %s", str(e))
            return False

    def login_with_jwt(self, login: str, password: str) -> Tuple[str, Optional[str]]:
        """Validate credentials using OTP and return JWT token.

        Args:
            login: The phone number or email address to authenticate.
            password: The OTP code to validate.

        Returns:
            Tuple of (login, jwt_token) if authentication is successful, empty strings otherwise.
        """
        # If password is empty, this is the initial request - generate and send OTP
        if not password:
            logger.info("AUTH: Initial OTP request for %s", login)
            if self._send_otp(login):
                logger.info("AUTH: OTP code sent successfully to %s", login)
            else:
                logger.warning("AUTH: Failed to send OTP code to %s", login)
            return "", None

        # If password is provided, validate it against stored OTP
        if password:
            logger.info("AUTH: OTP verification attempt for %s", login)
            if self._check_otp(login, password):
                logger.info("AUTH: OTP verification successful for %s", login)
                # Generate JWT token for successful authentication
                jwt_token = self._generate_jwt(login)
                return login, jwt_token
            else:
                logger.warning("AUTH: Invalid OTP code for %s", login)
                return "", None

        logger.warning("AUTH: Invalid OTP request for %s", login)
        return "", None

    def _login(self, login: str, password: str) -> str:
        user, _ = self.login_with_jwt(login, password)
        return user

    def is_authenticated(self, user: str, password: str) -> bool:
        """Check if the user is authenticated.

        Args:
            user: The user's login identifier.
            password: The OTP code to validate.

        Returns:
            True if the user is authenticated, False otherwise.
        """
        result, _ = self.login_with_jwt(user, password)
        return bool(result)

    def _generate_jwt(self, user: str) -> str:
        """Generate a JWT token for the authenticated user.

        Args:
            user: The authenticated user identifier

        Returns:
            JWT token string
        """
        now = datetime.datetime.now(datetime.timezone.utc)

        # Determine identifier type
        identifier_type = "email" if "@" in user else "phone"

        payload = {
            "sub": user,  # subject (user identifier)
            "iat": now,   # issued at
            "exp": now + datetime.timedelta(seconds=self._jwt_expiry),  # expiry
            "identifier_type": identifier_type,  # phone or email
            "auth_method": "otp_twilio",  # authentication method used
        }

        token = jwt.encode(payload, self._jwt_secret, algorithm="HS256")
        logger.info("AUTH: Generated JWT token for %s (type: %s, expires in %d seconds)", user, identifier_type, self._jwt_expiry)
        return token

    def _validate_jwt(self, token: str) -> Optional[str]:
        """Validate a JWT token and return the user if valid.

        Args:
            token: JWT token string

        Returns:
            User identifier if valid, None if invalid
        """
        try:
            payload = jwt.decode(token, self._jwt_secret, algorithms=["HS256"])
            user = payload.get("sub")
            logger.info("AUTH: JWT token validated for %s", user)
            return user
        except jwt.ExpiredSignatureError:
            logger.warning("AUTH: JWT token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning("AUTH: Invalid JWT token: %s", e)
            return None
