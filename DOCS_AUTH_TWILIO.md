# Radicale Twilio OTP Authentication Documentation

## Overview

Radicale's Twilio OTP (One-Time Password) authentication provides a secure two-factor authentication mechanism using SMS or email delivery through the Twilio service. This authentication method enhances security by requiring users to verify their identity using a time-limited code sent to their phone or email.

**Key Features:**
- **OTP Delivery**: SMS and email delivery via Twilio
- **JWT Token Authentication**: Secure session tokens with detailed payload
- **Automatic Type Detection**: Phone vs email identifier recognition
- **CORS Support**: Full cross-origin request support for web applications

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
twilio_service_sid = your_service_sid

# JWT Configuration
jwt_secret = your_secret_key_here  # Auto-generated if not provided
jwt_expiry = 3600  # Token expiry in seconds (default: 1 hour)

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
- `twilio_service_sid`: Your Twilio service SID (required)

- **Delivery method is determined automatically:**
  - If the user identifier contains an `@`, the OTP is sent via email.
  - Otherwise, the OTP is sent via SMS.

### JWT Configuration

- `jwt_secret`: Secret key for signing JWT tokens (auto-generated if not provided)
- `jwt_expiry`: Token expiration time in seconds (default: 3600 = 1 hour)

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

## JWT Token Authentication

After successful OTP verification, the system issues a **JWT (JSON Web Token)** containing user information and session metadata. This token provides secure, stateless authentication for subsequent API requests.

### JWT Payload Structure

The JWT token contains the following claims:

```json
{
  "sub": "+41789600142",           // Subject: User identifier (phone/email)
  "iat": 1640995200,               // Issued At: Unix timestamp
  "exp": 1640998800,               // Expires: Unix timestamp
  "identifier_type": "phone",      // Type: "phone" or "email"
  "auth_method": "otp_twilio",     // Authentication method used
  "iss": "radicale-idp"           // Issuer: Token issuer identifier
}
```

**Payload Claims:**
- **`sub`** (Subject): The user's phone number or email address
- **`iat`** (Issued At): Timestamp when the token was created
- **`exp`** (Expires): Timestamp when the token expires
- **`identifier_type`**: Automatically detected as "phone" or "email" based on the presence of `@`
- **`auth_method`**: Always "otp_twilio" for this authentication method
- **`iss`** (Issuer): Always "radicale-idp" to identify the token source

### JWT Authentication Flow

1. **OTP Verification Success**:
   ```http
   GET /privacy/settings/+41789600142 HTTP/1.1
   Authorization: Basic KzQxNzg5NjAwMTQyOjEyMzQ1Ng==
   ```
   *(Basic auth: +41789600142:123456)*

   **Response:**
   ```http
   HTTP/1.1 200 OK
   Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
   Content-Type: application/json

   {
     "disallow_photo": true,
     "disallow_birthday": false,
     ...
   }
   ```

2. **Subsequent Authenticated Requests**:
   ```http
   GET /privacy/settings/+41789600142 HTTP/1.1
   Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
   ```

   **Response:**
   ```http
   HTTP/1.1 200 OK
   Content-Type: application/json

   {
     "disallow_photo": true,
     "disallow_birthday": false,
     ...
   }
   ```

### JWT Token Validation

The server validates JWT tokens by:
1. **Signature Verification**: Using the configured `jwt_secret`
2. **Expiration Check**: Ensuring the token hasn't expired
3. **Claim Validation**: Verifying required claims are present
4. **User Authorization**: Ensuring the token user matches the requested resource

### JWT Security Features

- **Stateless**: No server-side session storage required
- **Tamper-Proof**: Cryptographically signed with HS256 algorithm
- **Time-Limited**: Automatic expiration prevents long-term abuse
- **User-Specific**: Each token is tied to a specific user identifier
- **Method Tracking**: Records the authentication method used

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

   **Server Response:**
   ```http
   HTTP/1.1 200 OK
   Content-Type: application/json
   Authorization: Bearer <jwt_token>

   {
     "disallow_photo": true,
     "disallow_birthday": false,
     ...
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
Access-Control-Expose-Headers: Authorization
Access-Control-Max-Age: 86400
```

Note that `Access-Control-Expose-Headers` is configured to allow web clients to read the `Authorization` header from the response, which contains the JWT Bearer token.

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