# Radicale Privacy Documentation

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
default_disallow_name = false
default_disallow_email = false
default_disallow_phone = false
default_disallow_company = false
default_disallow_title = false
default_disallow_photo = false
default_disallow_birthday = false
default_disallow_address = false
```

- `default_disallow_name`: Whether users' names are disallowed by default
- `default_disallow_email`: Whether users' email addresses are disallowed by default
- `default_disallow_phone`: Whether users' phone numbers are disallowed by default
- `default_disallow_company`: Whether users' company information is disallowed by default
- `default_disallow_title`: Whether users' job titles are disallowed by default
- `default_disallow_photo`: Whether users' photos are disallowed by default
- `default_disallow_birthday`: Whether users' birthdays are disallowed by default
- `default_disallow_address`: Whether users' addresses are disallowed by default

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
default_disallow_name = false
default_disallow_email = false
default_disallow_phone = true
default_disallow_company = false
default_disallow_title = false
default_disallow_photo = true
default_disallow_birthday = true
default_disallow_address = true
```

This configuration:
- Stores the database in `/var/lib/radicale/privacy.db`
- Allows storing names, emails, company, and title by default (disallow = false)
- Restricts storing phone numbers, photos, birthdays, and addresses by default (disallow = true)

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
    "disallow_company": false,
    "disallow_title": false,
    "disallow_photo": true,
    "disallow_birthday": true,
    "disallow_address": true
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
    "disallow_company": false,
    "disallow_title": false,
    "disallow_photo": true,
    "disallow_birthday": true,
    "disallow_address": true
}
```

**Response:**
```json
{
    "disallow_company": false,
    "disallow_title": false,
    "disallow_photo": true,
    "disallow_birthday": true,
    "disallow_address": true
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
    "disallow_company": false,
    "disallow_title": false,
    "disallow_photo": false,
    "disallow_birthday": false,
    "disallow_address": true
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
                "org": "Example Corp",
                "title": "Developer",
                "photo": true,
                "bday": "1990-01-01",
                "adr": "123 Main St"
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

### Best Practices

1. **Security**: Keep the database file secure and restrict access to authorized users only.
2. **Backup**: Regularly backup the privacy database along with other Radicale data.
3. **Default Settings**: Choose default settings that balance privacy and functionality:
   - More restrictive defaults provide better privacy protection
   - Less restrictive defaults improve usability
4. **Documentation**: Document your chosen default settings for your users.

### Related Components

- `PrivacyCore`: Core business logic for managing privacy settings and card processing
- `PrivacyHTTP`: HTTP endpoints for privacy management
- VCF Processing: Enforces privacy settings when processing contact information