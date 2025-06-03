# Radicale Twilio OTP Authentication Documentation

## Overview

Radicale's Twilio OTP (One-Time Password) authentication provides a secure two-factor authentication mechanism using SMS or email delivery through the Twilio service. This authentication method enhances security by requiring users to verify their identity using a time-limited code sent to their phone or email.

## Quick Setup

### 1. Prerequisites

- A Twilio account with:
  - Account SID
  - Auth Token
  - A verified phone number for SMS delivery
  - A verified email address for email delivery (if using email OTP)
- Python 3.9+ (3.13 recommended)

### 2. Install Dependencies

```bash
uv venv --python 3.13  # or use 'python3 -m venv .venv' if you prefer
source .venv/bin/activate
uv pip install -U .  # or use 'pip install -U .' if you prefer
```

### 3. Configure Radicale

Add the following to your Radicale configuration file (`~/.config/radicale/config`):

```ini
[auth]
type = otp_twilio
twilio_account_sid = your_account_sid
twilio_auth_token = your_auth_token
twilio_from_number = +1234567890  # Your Twilio phone number
twilio_from_email = your@email.com  # Your Twilio verified email
otp_length = 6
otp_expiry = 300  # 5 minutes in seconds
otp_method = sms  # or 'email'

# Required by BaseAuth
lc_username = false
uc_username = false
strip_domain = false
urldecode_username = false
delay = 1
cache_logins = false
cache_successful_logins_expiry = 15
cache_failed_logins_expiry = 90
```

### 4. Launch the Radicale Server

```bash
python -m radicale
```

The server will be available at [http://127.0.0.1:5232/](http://127.0.0.1:5232/)

## Configuration Settings

### Twilio Configuration

- `twilio_account_sid`: Your Twilio account SID (required)
- `twilio_auth_token`: Your Twilio auth token (required)
- `twilio_from_number`: The Twilio phone number to send SMS from (required for SMS delivery)
- `twilio_from_email`: The Twilio verified email to send from (required for email delivery)

### OTP Settings

- `otp_length`: Length of the OTP code (default: 6)
- `otp_expiry`: Time in seconds before the OTP expires (default: 300)
- `otp_method`: Delivery method, either "sms" or "email" (default: "sms")

### Base Authentication Settings

These settings are inherited from the base authentication class:

- `lc_username`: Convert usernames to lowercase
- `uc_username`: Convert usernames to uppercase
- `strip_domain`: Remove domain part from usernames
- `urldecode_username`: URL-decode usernames
- `delay`: Delay between login attempts in seconds
- `cache_logins`: Cache successful logins
- `cache_successful_logins_expiry`: Cache expiry for successful logins
- `cache_failed_logins_expiry`: Cache expiry for failed logins

## Authentication Flow

1. **Initial Login Attempt**:
   - User provides their phone number or email address
   - System generates a random OTP code
   - Code is sent via SMS or email using Twilio
   - User receives the code

2. **OTP Verification**:
   - User enters the received OTP code
   - System validates the code against the stored value
   - If valid and not expired, access is granted
   - If invalid or expired, user must request a new code

## Security Considerations

1. **OTP Expiration**:
   - OTP codes expire after the configured time (default: 5 minutes)
   - Expired codes are automatically invalidated
   - Users must request a new code after expiration

2. **Rate Limiting**:
   - The system enforces delays between login attempts
   - Failed attempts are tracked and cached
   - Excessive failed attempts may trigger additional security measures

3. **Code Generation**:
   - OTP codes are randomly generated using secure methods
   - Codes are numeric and configurable in length
   - Each code is single-use

## Testing

### Unit Tests

The Twilio OTP authentication module includes comprehensive unit tests. Run them using:

```bash
pytest tests/unit/auth/test_otp_twilio.py -v
```

Tests cover:
- Configuration validation
- OTP generation and validation
- SMS and email delivery
- Error handling
- Login flow with various scenarios
- OTP expiration
- Storage and cleanup of OTP codes

### Manual Testing

To test the authentication flow:

1. Start the Radicale server with Twilio OTP authentication enabled
2. Attempt to log in with a phone number or email
3. Check for OTP delivery via SMS or email
4. Verify the OTP code works
5. Test expiration by waiting for the OTP to expire
6. Test invalid codes and error handling

## Troubleshooting

### Common Issues

1. **OTP Not Received**:
   - Verify Twilio credentials
   - Check phone number/email format
   - Ensure Twilio account has sufficient credits
   - Check Twilio logs for delivery status

2. **Authentication Failures**:
   - Verify OTP code is entered correctly
   - Check if OTP has expired
   - Ensure correct phone number/email is used
   - Check server logs for detailed error messages

3. **Configuration Issues**:
   - Verify all required settings are present
   - Check Twilio credentials are correct
   - Ensure phone number/email is properly formatted
   - Verify OTP settings are within acceptable ranges

### Logging

Enable debug logging to troubleshoot issues:

```ini
[logging]
level = debug
mask_passwords = true
```

## API Integration

The Twilio OTP authentication can be integrated with other systems through Radicale's API. The authentication flow follows standard HTTP authentication mechanisms:

1. Initial request returns 401 Unauthorized
2. Client must provide valid credentials
3. OTP is sent to the user
4. Client must provide the OTP code
5. Upon successful verification, access is granted

## Best Practices

1. **Security**:
   - Use HTTPS for all communications
   - Keep Twilio credentials secure
   - Regularly rotate auth tokens
   - Monitor failed login attempts

2. **Configuration**:
   - Use appropriate OTP length (6-8 digits recommended)
   - Set reasonable expiration times
   - Configure proper rate limiting
   - Enable logging for monitoring

3. **User Experience**:
   - Provide clear error messages
   - Implement proper timeout handling
   - Consider implementing a resend mechanism
   - Add support for multiple delivery methods

## Support

For issues and support:
1. Check the Radicale documentation
2. Review Twilio's documentation
3. Check server logs for detailed error messages
4. Contact the Radicale community for assistance