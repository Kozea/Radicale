# Radicale Privacy Documentation

## Quick Setup

Get started quickly with Radicale and privacy features:

### 1. Create a Virtual Environment and Install Dependencies

Make sure you have [uv](https://github.com/astral-sh/uv) for fast installs
(optional) or Python 3.9+ (3.13 recommended).

```bash
uv venv --python 3.13  # or use 'python3 -m venv .venv' if you prefer
source .venv/bin/activate
uv pip install -U .  # or use 'pip install -U .' if you prefer
```

### 2. Configure Radicale

Create or edit your configuration file at `~/.config/radicale/config`:

#### Basic Configuration

```ini
[auth]
type = none

[storage]
filesystem_folder = ~/.var/lib/radicale/collections

[privacy]
type = database
database_path = ~/.local/share/radicale/privacy.db

[rights]
type = authenticated
```

> [!NOTE] The `rights` section with `type = authenticated` is required for the
> privacy features to work properly. This setting enables users to:
>
> - Access and modify their own privacy settings
> - Modify vCards that contain their information, even if they don't own those
>   cards
> - Enforce their privacy preferences across all vCards that reference them

#### Debug Configuration

For detailed logging during development or troubleshooting, add:

```ini
[logging]
level = debug
mask_passwords = True
backtrace_on_debug = True
request_header_on_debug = False
request_content_on_debug = False
response_content_on_debug = False
storage_cache_actions_on_debug = False
```

#### Authentication Configuration

For testing purposes, you can use the basic configuration with `type = none`.
However, for production use, it's recommended to use proper authentication like
htpasswd:

```ini
[auth]
type = htpasswd
htpasswd_filename = /path/to/users
htpasswd_encryption = autodetect

# BaseAuth configuration options
lc_username = false
uc_username = false
strip_domain = false
urldecode_username = false
delay = 1
cache_logins = false
cache_successful_logins_expiry = 15
cache_failed_logins_expiry = 90
```

> [!NOTE] When running integration tests, make sure to use `type = none` in the
> `[auth]` section to disable authentication. For production environments,
> always use proper authentication like htpasswd.

## Bearer Token Authentication for Privacy API

The privacy API uses **Bearer token** authentication for secure access to user
privacy settings and vCard data. The API requires a valid Bearer token in the
`Authorization` header to access any privacy endpoints.

### Environment Variable: RADICALE_TOKEN

The privacy API authentication is controlled by the `RADICALE_TOKEN` environment
variable:

```bash
export RADICALE_TOKEN="your_secret_token_here"
```

- **Purpose**: This environment variable sets the expected Bearer token for
  privacy API authentication
- **Required**: Must be set when using the privacy API endpoints
- **Security**: Use a strong, randomly generated token for production
  environments
- **Scope**: Only affects privacy API endpoints (`/privacy/*`)

### Token Usage

All privacy API requests must include the Bearer token in the `Authorization`
header:

```http
Authorization: Bearer your_secret_token_here
```

**Example:**

```bash
export RADICALE_TOKEN="abc123xyz789"
curl -H "Authorization: Bearer abc123xyz789" "http://localhost:5232/privacy/settings/user@example.com"
```

### Privacy API Authentication Flow

The privacy API uses simple Bearer token authentication. All requests must
include the `RADICALE_TOKEN` value in the `Authorization` header:

**API Request Example:**

```http
GET /privacy/settings/+41789600142 HTTP/1.1
Host: localhost:5232
Authorization: Bearer abc123xyz789
Content-Type: application/json
```

**Successful Response:**

```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "disallow_photo": true,
  "disallow_birthday": false,
  "disallow_gender": false,
  "disallow_address": true,
  "disallow_company": false,
  "disallow_title": false
}
```

**Authentication Failure Response:**

```http
HTTP/1.1 401 Unauthorized
Content-Type: application/json
WWW-Authenticate: Bearer

{
  "error": "Unauthorized. Bearer token required."
}
```

### Security Considerations

- **Token Security**: Use a strong, randomly generated token for
  `RADICALE_TOKEN`
- **Environment Protection**: Protect the environment where `RADICALE_TOKEN` is
  set
- **HTTPS**: Always use HTTPS in production to protect the Bearer token in
  transit
- **Token Rotation**: Consider rotating the token periodically for enhanced
  security

### Frontend Integration

For web applications, the Bearer token can be used directly for API calls:

```javascript
// Set the token (from environment or configuration)
const bearerToken = "abc123xyz789";

// Use for API calls
const headers = {
  Authorization: `Bearer ${bearerToken}`,
  "Content-Type": "application/json",
};

// Example API call
fetch("/privacy/settings/user@example.com", { headers })
  .then((response) => response.json())
  .then((data) => console.log(data));
```

### 3. Set Privacy API Token

Set the required environment variable for privacy API authentication:

```bash
export RADICALE_TOKEN="your_secret_token_here"
```

> [!TIP] For development, you can use a simple token like `1234`. For
> production, use a strong, randomly generated token.

### 4. Launch the Radicale Server

```bash
RADICALE_TOKEN="1234" python -m radicale
```

Or if you've already exported the token:

```bash
python -m radicale
```

- The server will be available at
  [http://127.0.0.1:5232/](http://127.0.0.1:5232/)
- You can now use the privacy API and test endpoints as described below.

---

## vCard Standard and Property Mapping

Radicale's privacy features are built around the **vCard 4.0 standard** for
contact data. The system uses a mapping between privacy settings and vCard
properties to enforce user privacy.

- **vCard 4.0**: All contact data is expected to conform to the
  [vCard 4.0 specification](https://datatracker.ietf.org/doc/html/rfc6350).
- **Property Mapping**: Each privacy setting (e.g., `disallow_photo`,
  `disallow_birthday`) corresponds to one or more vCard properties. For example:
  - `disallow_photo` → `PHOTO`
  - `disallow_gender` → `GENDER`
  - `disallow_birthday` → `BDAY`, `ANNIVERSARY`
  - `disallow_address` → `ADR`, `LABEL`
  - `disallow_company` → `ORG`, `LOGO`
  - `disallow_title` → `TITLE`, `ROLE`
- **Public Properties**: Some vCard properties are always considered public and
  are never filtered by privacy settings:
  - `FN` (Formatted Name)
  - `N` (Name)
  - `EMAIL`
  - `TEL` (Telephone)

For a full list and mapping, see
[`radicale/privacy/vcard_properties.py`](radicale/privacy/vcard_properties.py).

This design ensures that essential contact information (name, email, phone) is
always available, while sensitive fields can be restricted according to user
preferences.

---

## Privacy Configuration Settings

The privacy settings in Radicale are configured through the main configuration
file. These settings control the default privacy preferences for users and how
the system handles personal information.

### Database Configuration

```ini
[privacy]
database_path = /path/to/privacy.db
database_logging = true
```

- `database_path`: Path to the SQLite database file that stores user privacy
  settings. Default is `~/.local/share/radicale/privacy.db` (expands to your
  home directory).
- `database_logging`: Whether to log privacy events to the database for audit
  trail and statistics. Default is `false`. When enabled, the system logs user
  actions like settings changes, vCard processing, and authentication events to
  the `privacy_logs` table.

### Default Privacy Settings

The following settings control the default privacy preferences for new users.
Each setting determines whether a specific field is disallowed by default:

```ini
[privacy]
default_disallow_photo = false
default_dissalow_gender = false
default_disallow_birthday = false
default_disallow_address = false
default_disallow_company = false
default_disallow_title = false
```

- `default_disallow_photo`: Whether users' photos are disallowed by default
- `default_disallow_gender`: Whether users' gender information is disallowed by
  default
- `default_disallow_birthday`: Whether users' birthdays are disallowed by
  default
- `default_disallow_address`: Whether users' addresses are disallowed by default
- `default_disallow_company`: Whether users' company information is disallowed
  by default
- `default_disallow_title`: Whether users' job titles are disallowed by default

### How Default Settings Work

1. When a new user is created without specifying privacy settings, these default
   values are applied.
2. Users can later modify their privacy settings through the API.
3. Changes to these default settings only affect new users; existing users'
   settings remain unchanged.
4. The system enforces these privacy settings when other users try to store
   contact information.

### Example Configuration

Here's a complete example of privacy-related configuration:

```ini
[privacy]
database_path = /var/lib/radicale/privacy.db
database_logging = true
default_disallow_photo = true
default_disallow_gender = true
default_disallow_birthday = true
default_disallow_address = true
default_disallow_company = false
default_disallow_title = false
```

This configuration:

- Stores the database in `/var/lib/radicale/privacy.db`
- Enables database logging for audit trail and statistics
- Allows storing names, emails, company, and title by default (disallow = false)
- Restricts storing phone numbers, photos, birthdays, and addresses by default
  (disallow = true)

## Testing and Validation

Radicale includes both unit and integration tests to ensure the privacy features
and API endpoints work as expected. All tests are located in the `tests/`
directory and can be run easily with [tox](https://tox.readthedocs.io/).

### 1. Install Test Dependencies

If you don't have `tox` installed, add it to your environment:

```bash
uv pip install tox
```

### 2. Run All Tests

From the project root, run:

```bash
tox -c pyproject.toml -e py
```

- This will automatically set up test environments, install dependencies, and
  run all unit and integration tests.
- By default, this covers:
  - Privacy API endpoints
  - vCard upload and filtering
  - Privacy settings logic and enforcement
  - Edge cases and error handling

### 3. Code Quality: Linting, Type Checking, and Formatting

To ensure code quality and consistency, you can run the following tools via tox:

- **flake8**: Checks for Python code style and common errors (PEP8 compliance).
- **mypy**: Performs static type checking.
- **isort**: Checks import order and formatting.

Run all code quality checks at once:

```bash
tox -c pyproject.toml -e flake8,mypy,isort
```

- These checks help maintain a clean, readable, and robust codebase.

---

## Testing Privacy Functionality

This project includes scripts to generate test data and to test the privacy API
endpoints automatically. Follow these steps to generate VCF/contact data,
privacy settings, and run the upload tests.

### 1. Generate Test VCF Files

Use the `generate_vcf_data.py` script to create sample vCard (VCF) files for
testing:

```bash
python3 tests/data/privacy/generate_vcf_data.py
```

- This will create individual VCF files for each test user and a combined VCF
  file in `tests/data/privacy/vcf/`.

### 2. Generate Privacy Settings JSON Files

Use the `generate_privacy_settings_json.py` script to create JSON files with
privacy settings for each test user:

```bash
python3 tests/data/privacy/generate_privacy_settings_json.py
```

- This will create one JSON file per test user in
  `tests/data/privacy/settings/`.

### 3. Run the VCF Upload and Privacy Test

> [!NOTE] When running tests, make sure to use `type = none` in the `[auth]`
> section to disable authentication. For production environments, always use
> proper authentication like htpasswd.

Use the `run_integration.py` script to automatically upload the generated VCF
files and privacy settings to the running Radicale server, and verify privacy
enforcement:

```bash
python3 tests/data/privacy/run_integration.py
```

- Make sure your Radicale server is running and accessible at the API base URL
  specified in the script (default: `http://localhost:5232`).
- The script will print a summary of test results for each VCF file.

### Notes

- Adjust the API base URL in the test script if your server is running on a
  different address or port.
- The scripts assume the working directory is the project root.

---

## HTTP API Endpoints

The privacy management API is available at the `/privacy/` path prefix. All
endpoints require authentication and return JSON responses.

### Privacy Settings Management

#### Get User Settings

```http
GET /privacy/settings/{user}
```

Returns the privacy settings for a specific user.

**Response:**

```json
{
  "disallow_photo": true,
  "disallow_gender": true,
  "disallow_birthday": true,
  "disallow_address": true,
  "disallow_company": false,
  "disallow_title": false
}
```

#### Create User Settings

```http
POST /privacy/settings/{user}
```

Creates new privacy settings for a user. All fields are required.

**Request Body:**

```json
{
  "disallow_photo": true,
  "disallow_gender": true,
  "disallow_birthday": true,
  "disallow_address": true,
  "disallow_company": false,
  "disallow_title": false
}
```

**Response:**

```json
{
  "disallow_photo": true,
  "disallow_gender": true,
  "disallow_birthday": true,
  "disallow_address": true,
  "disallow_company": false,
  "disallow_title": false
}
```

#### Update User Settings

```http
PUT /privacy/settings/{user}
```

Updates existing privacy settings for a user. Only include the fields you want
to update.

**Request Body:**

```json
{
  "disallow_photo": false,
  "disallow_birthday": false
}
```

**Response:**

```json
{
  "disallow_photo": false,
  "disallow_gender": true,
  "disallow_birthday": false,
  "disallow_address": true,
  "disallow_company": false,
  "disallow_title": false
}
```

#### Delete User Settings

```http
DELETE /privacy/settings/{user}
```

Deletes privacy settings for a user.

**Response:**

```json
{
  "status": "deleted"
}
```

### Card Management

#### Get Matching Cards

```http
GET /privacy/cards/{user}
```

Returns all vCards that contain the user's information.

**Response:**

```json
{
  "matches": [
    {
      "vcard_uid": "123456",
      "collection_path": "/user/contacts/",
      "matching_fields": ["email", "tel"],
      "fields": {
        "fn": "John Doe",
        "email": ["john@example.com"],
        "tel": ["+14155552671"],
        "photo": true,
        "gender": "M",
        "bday": "1990-01-01",
        "adr": "123 Main St",
        "org": "Example Corp",
        "title": "Developer"
      }
    }
  ]
}
```

#### Reprocess Cards

```http
POST /privacy/cards/{user}/reprocess
```

Triggers reprocessing of all vCards for a user based on their current privacy
settings.

**Response:**

```json
{
  "status": "success",
  "reprocessed_cards": 5,
  "reprocessed_card_uids": ["123456", "abcdef", "789xyz", "..."]
}
```

- `status`: Always "success" if the operation completed successfully.
- `reprocessed_cards`: The number of vCards that were reprocessed.
- `reprocessed_card_uids`: A list of the UIDs of the vCards that were
  reprocessed.

### Error Responses

All endpoints may return the following error responses:

#### 400 Bad Request

Returned when:

- Invalid request format
- Missing required fields
- Invalid JSON in request body
- Invalid path format

Example:

```json
{
  "error": "Invalid request format"
}
```

#### 401 Unauthorized

Returned when:

- No authentication credentials provided
- Invalid session token
- Session token expired

Example:

```json
{
  "error": "Authentication required"
}
```

#### 403 Forbidden

Returned when:

- Authenticated user does not match the requested user
- User attempts to access another user's settings

Example:

```http
HTTP/1.1 403 Forbidden
Content-Type: text/plain

Action on the requested resource refused.
```

#### 404 Not Found

Returned when:

- User settings not found
- Requested resource does not exist

Example:

```json
{
  "error": "User settings not found"
}
```

#### 500 Internal Server Error

Returned when:

- Server-side error occurs
- Database operation fails
- Unexpected error during processing

Example:

```json
{
  "error": "Internal server error"
}
```

### CORS Support

The API includes CORS headers to support web browser access:

```http
Access-Control-Allow-Origin: *
Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS
Access-Control-Allow-Headers: Content-Type, Authorization
Access-Control-Max-Age: 86400
```
