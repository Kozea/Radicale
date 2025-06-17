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
session_expiry = 3600  # Session token expiry in seconds (default: 1 hour)

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
- `session_expiry`: Session token expiry time in seconds (default: 3600, i.e., 1 hour). Determines how long a session token remains valid after successful OTP authentication.
- **Delivery method is determined automatically:**
  - If the user identifier contains an `@`, the OTP is sent via email.
  - Otherwise, the OTP is sent via SMS.

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
   - System returns empty string (authentication fails)

2. **OTP Verification**:
   - User enters the received OTP code
   - System validates the code against the stored value
   - If valid and not expired:
     - OTP is invalidated (removed from store)
     - User is authenticated
     - System returns the user's identifier
   - If invalid or expired:
     - System generates and sends a new OTP
     - Authentication fails
     - System returns empty string

## Session Token Authentication

After successful OTP authentication, the backend issues a session token in the `X-Radicale-Session-Token` response header. The client must include this token in the `Authorization: Bearer <token>` header for all subsequent API requests. Session tokens are stored temporarily in memory on the backend and expire after a set time (default: 1 hour).

### Example Flow

1. **Initial Login Attempt**:
   ```http
   GET /privacy/settings/user@example.com HTTP/1.1
   Authorization: Basic dXNlckBleGFtcGxlLmNvbTo=
   ```
   Note: The Basic Auth password is empty (base64 encode of "user@example.com:")

   **Server Response:**
   ```http
   HTTP/1.1 401 Unauthorized
   ```
   The server also sends OTP via Twilio (SMS or email)

2. **OTP Verification**:
   ```http
   GET /privacy/settings/user@example.com HTTP/1.1
   Authorization: Basic dXNlckBleGFtcGxlLmNvbTo1MjM0NTY=
   ```
   Note: The Basic Auth is now username:OTP (base64 encode of "user@example.com:523456")

   **Server Response (Success):**
   ```http
   HTTP/1.1 200 OK
   Content-Type: application/json
   X-Radicale-Session-Token: <session_token>

   {
     "settings": { ... }
   }
   ```

3. **Authenticated Requests**:
   ```http
   GET /privacy/settings/user@example.com HTTP/1.1
   Authorization: Bearer <session_token>
   ```

   **Server Response:**
   ```http
   HTTP/1.1 200 OK
   Content-Type: application/json

   {
     "settings": { ... }
   }
   ```

4. **Session Expiry**:
   - Session tokens expire after a set time (default: 1 hour)
   - After expiry, requests with the token will receive 401 Unauthorized
   - The client must re-authenticate using the OTP flow

### CORS Considerations

For web clients making cross-origin requests, the server includes the following CORS headers:

```http
Access-Control-Allow-Origin: *
Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS
Access-Control-Allow-Headers: Content-Type, Authorization
Access-Control-Expose-Headers: X-Radicale-Session-Token
Access-Control-Max-Age: 86400
```

Note that `Access-Control-Expose-Headers` is specifically configured to allow web clients to read the `X-Radicale-Session-Token` header from the response.

## Logout Endpoint

To log out and invalidate a session token, send a POST request to `/logout` with the session token in the `Authorization: Bearer <token>` header.

### Example Request

```http
POST /logout HTTP/1.1
Host: example.com
Authorization: Bearer <session_token>
```

### Example Response (Success)
```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "logout": "success"
}
```

### Example Response (No Session Token)
```http
HTTP/1.1 401 Unauthorized
Content-Type: application/json

{
  "error": "No session token"
}
```

- After logout, the session token is invalidated and cannot be used for further requests
- If no Bearer token is provided, the server responds with 401 Unauthorized
- The logout endpoint is accessible at the root path `/logout`

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

## Detailed Authentication Flow

### 1. Initial Authentication Request

When a client makes an initial request to a protected endpoint:

1. The server responds with a 401 Unauthorized status
2. The client must provide the user's phone number or email address as the username
3. The password field should be empty
4. The server will:
   - Generate a random OTP code
   - Send it via Twilio (SMS or email)
   - Store the OTP with an expiration time
   - Return 401 Unauthorized

Example HTTP request:
```http
GET / HTTP/1.1
Host: example.com
Authorization: Basic dXNlckBleGFtcGxlLmNvbTo=
```

### 2. OTP Generation and Delivery

Upon receiving the initial request:

1. The server generates a random OTP code (default: 6 digits)
2. The code is stored in memory with an expiration time (default: 5 minutes)
3. The code is sent to the user via:
   - SMS: Using the configured Twilio phone number
   - Email: Using the configured Twilio email address
4. The server responds with 401 Unauthorized

### 3. OTP Verification

The client must then make a second request with the OTP code:

1. Use the same username (phone/email) as before
2. Use the received OTP code as the password
3. The server validates:
   - The OTP code matches the stored value
   - The OTP has not expired
   - If valid:
     - The OTP is invalidated (removed from store)
     - The server responds with 200 OK
   - If invalid or expired:
     - A new OTP is generated and sent
     - The server responds with 401 Unauthorized

Example HTTP request with OTP:
```http
GET / HTTP/1.1
Host: example.com
Authorization: Basic dXNlckBleGFtcGxlLmNvbToxMjM0NTY=
```

### 4. Successful Authentication

Upon successful verification:

1. The OTP is invalidated (single-use)
2. The server responds with 200 OK
3. The client can now access protected resources

### 5. Failed Authentication

If authentication fails:

1. The server responds with 401 Unauthorized
2. If the OTP is expired or invalid:
   - A new OTP is automatically generated and sent
   - The client must use the new OTP
3. Previous OTPs are invalidated

## HTTP API Integration Requirements

To ensure proper integration with the Twilio OTP authentication:

1. **Client Implementation**:
   - Must handle 401 responses appropriately
   - Should implement proper retry logic
   - Must store and manage session tokens
   - Should handle OTP expiration gracefully

2. **Server Configuration**:
   - Enable HTTPS for secure communication
   - Configure proper CORS headers if needed
   - Set appropriate timeouts for OTP expiration
   - Configure rate limiting to prevent abuse

3. **Error Handling**:
   - Handle network failures gracefully
   - Implement proper timeout handling
   - Provide clear error messages to users
   - Log authentication failures for monitoring

4. **Security Considerations**:
   - Use HTTPS for all communications
   - Implement proper session management
   - Monitor failed authentication attempts
   - Regularly rotate Twilio credentials
   - Implement proper rate limiting

5. **Testing Requirements**:
   - Test both SMS and email delivery methods
   - Verify OTP expiration handling
   - Test rate limiting functionality
   - Validate error handling
   - Test session management

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