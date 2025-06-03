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
import string
import time
from typing import Dict, Tuple

from twilio.base.exceptions import TwilioRestException
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
        self._otp_method: str = configuration.get("auth", "otp_method")

        # Store OTP codes and their expiry times
        self._otp_store: Dict[str, Tuple[str, float]] = {}

        # Initialize Twilio client
        self._twilio_client: Client = Client(self._account_sid, self._auth_token)

        logger.info("OTP authentication initialized with method: %s", self._otp_method)

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
            if self._otp_method == "sms":
                message = self._twilio_client.messages.create(
                    body=f"Your Radicale authentication code is: {otp}",
                    from_=self._from_number,
                    to=login
                )
                return bool(message.sid)
            else:  # email
                message = self._twilio_client.messages.create(
                    body=f"Your Radicale authentication code is: {otp}",
                    from_=f"Radicale <{self._from_email}>",
                    to=login
                )
                return bool(message.sid)
        except TwilioRestException as e:
            logger.error("Failed to send OTP via Twilio: %s", str(e))
            return False

    def _login(self, login: str, password: str) -> str:
        """Validate credentials using OTP.

        Args:
            login: The phone number or email address to authenticate.
            password: The OTP code to validate.

        Returns:
            The login string if authentication is successful, empty string otherwise.
        """
        # Check if we have a stored OTP for this login
        if login in self._otp_store:
            stored_otp, expiry_time = self._otp_store[login]

            # Check if OTP is expired
            if time.time() > expiry_time:
                del self._otp_store[login]
                logger.warning("OTP expired for user: %s", login)
                return ""

            # Verify OTP
            if password == stored_otp:
                del self._otp_store[login]  # OTP used, remove it
                return login

        # If no OTP exists or it's invalid, generate and send a new one
        otp = self._generate_otp()
        if self._send_otp(login, otp):
            self._otp_store[login] = (otp, time.time() + self._otp_expiry)
            logger.info("New OTP sent to user: %s", login)

        return ""  # Authentication failed or OTP sent
