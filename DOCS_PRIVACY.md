# Radicale Privacy Documentation

## Quick Setup

Get started quickly with Radicale and privacy features:

### 1. Create a Virtual Environment and Install Dependencies

Make sure you have [uv](https://github.com/astral-sh/uv) for fast installs (optional) or Python 3.9+ (3.13 recommended).


```bash
uv venv --python 3.13  # or use 'python3 -m venv .venv' if you prefer
source .venv/bin/activate
uv pip install -U .  # or use 'pip install -U .' if you prefer
```

### 2. Configure Radicale

Create or edit your configuration file at `~/.config/radicale/config`:

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

[logging]
level = debug
mask_passwords = True
backtrace_on_debug = True
request_header_on_debug = False
request_content_on_debug = False
response_content_on_debug = False
storage_cache_actions_on_debug = False
```

### 3. Launch the Radicale Server

```bash
python -m radicale
```

- The server will be available at [http://127.0.0.1:5232/](http://127.0.0.1:5232/)
- You can now use the privacy API and test endpoints as described below.

---

## vCard Standard and Property Mapping

Radicale's privacy features are built around the **vCard 4.0 standard** for contact data. The system uses a mapping between privacy settings and vCard properties to enforce user privacy.

- **vCard 4.0**: All contact data is expected to conform to the [vCard 4.0 specification](https://datatracker.ietf.org/doc/html/rfc6350).
- **Property Mapping**: Each privacy setting (e.g., `disallow_photo`, `disallow_birthday`) corresponds to one or more vCard properties. For example:
  - `disallow_photo` → `PHOTO`
  - `disallow_gender` → `GENDER`
  - `disallow_birthday` → `BDAY`, `ANNIVERSARY`
  - `disallow_address` → `ADR`, `LABEL`
  - `disallow_company` → `ORG`, `LOGO`
  - `disallow_title` → `TITLE`, `ROLE`
- **Public Properties**: Some vCard properties are always considered public and are never filtered by privacy settings:
  - `FN` (Formatted Name)
  - `N` (Name)
  - `EMAIL`
  - `TEL` (Telephone)

For a full list and mapping, see [`radicale/privacy/vcard_properties.py`](radicale/privacy/vcard_properties.py).

This design ensures that essential contact information (name, email, phone) is always available, while sensitive fields can be restricted according to user preferences.

---

## Privacy Configuration Settings

The privacy settings in Radicale are configured through the main configuration file. These settings control the default privacy preferences for users and how the system handles personal information.

### Database Configuration

```ini
[privacy]
database_path = /path/to/privacy.db
```

- `database_path`: Path to the SQLite database file that stores user privacy settings. Default is `~/.local/share/radicale/privacy.db` (expands to your home directory).

### Default Privacy Settings

The following settings control the default privacy preferences for new users. Each setting determines whether a specific field is disallowed by default:

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
- `default_disallow_gender`: Whether users' gender information is disallowed by default
- `default_disallow_birthday`: Whether users' birthdays are disallowed by default
- `default_disallow_address`: Whether users' addresses are disallowed by default
- `default_disallow_company`: Whether users' company information is disallowed by default
- `default_disallow_title`: Whether users' job titles are disallowed by default

### How Default Settings Work

1. When a new user is created without specifying privacy settings, these default values are applied.
2. Users can later modify their privacy settings through the API.
3. Changes to these default settings only affect new users; existing users' settings remain unchanged.
4. The system enforces these privacy settings when other users try to store contact information.

### Example Configuration

Here's a complete example of privacy-related configuration:

```ini
[privacy]
database_path = /var/lib/radicale/privacy.db
default_disallow_photo = true
default_disallow_gender = true
default_disallow_birthday = true
default_disallow_address = true
default_disallow_company = false
default_disallow_title = false
```

This configuration:
- Stores the database in `/var/lib/radicale/privacy.db`
- Allows storing names, emails, company, and title by default (disallow = false)
- Restricts storing phone numbers, photos, birthdays, and addresses by default (disallow = true)

## Testing and Validation

Radicale includes both unit and integration tests to ensure the privacy features and API endpoints work as expected. All tests are located in the `tests/` directory and can be run easily with [tox](https://tox.readthedocs.io/).

### 1. Install Test Dependencies

If you don't have `tox` installed, add it to your environment:

```bash
uv pip install tox
```

### 2. Run All Tests

From the project root, run:

```bash
tox -e py
```

- This will automatically set up test environments, install dependencies, and run all unit and integration tests.
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
tox -e flake8,mypy,isort
```

- These checks help maintain a clean, readable, and robust codebase.

---

## Testing Privacy Functionality

This project includes scripts to generate test data and to test the privacy API endpoints automatically. Follow these steps to generate VCF/contact data, privacy settings, and run the upload tests.

### 1. Generate Test VCF Files

Use the `generate_vcf_data.py` script to create sample vCard (VCF) files for testing:

```bash
python3 tests/data/privacy/generate_vcf_data.py
```

- This will create individual VCF files for each test user and a combined VCF file in `tests/data/privacy/vcf/`.

### 2. Generate Privacy Settings JSON Files

Use the `generate_privacy_settings_json.py` script to create JSON files with privacy settings for each test user:

```bash
python3 tests/data/privacy/generate_privacy_settings_json.py
```

- This will create one JSON file per test user in `tests/data/privacy/settings/`.

### 3. Run the VCF Upload and Privacy Test

Use the `test_vcf_upload.py` script to automatically upload the generated VCF files and privacy settings to the running Radicale server, and verify privacy enforcement:

```bash
python3 tests/data/privacy/test_vcf_upload.py
```

- Make sure your Radicale server is running and accessible at the API base URL specified in the script (default: `http://localhost:5232`).
- The script will print a summary of test results for each VCF file.

### Notes

- Adjust the API base URL in the test script if your server is running on a different address or port.
- The scripts assume the working directory is the project root.

---

## HTTP API Endpoints

The privacy management API is available at the `/privacy/` path prefix. All endpoints require authentication and return JSON responses.

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

Updates existing privacy settings for a user. Only include the fields you want to update.

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
                "tel": ["+1234567890"],
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

Triggers reprocessing of all vCards for a user based on their current privacy settings.

**Response:**
```json
{
    "status": "success",
    "reprocessed_cards": 5
}
```

### Error Responses

All endpoints may return the following error responses:

- `400 Bad Request`: Invalid request format or missing required fields
- `401 Unauthorized`: Authentication required
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: User or resource not found
- `500 Internal Server Error`: Server-side error

Example error response:
```json
{
    "error": "Invalid request format"
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