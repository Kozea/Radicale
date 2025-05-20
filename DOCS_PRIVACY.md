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

### Best Practices

1. **Security**: Keep the database file secure and restrict access to authorized users only.
2. **Backup**: Regularly backup the privacy database along with other Radicale data.
3. **Default Settings**: Choose default settings that balance privacy and functionality:
   - More restrictive defaults provide better privacy protection
   - Less restrictive defaults improve usability
4. **Documentation**: Document your chosen default settings for your users.

### Related Components

- `PrivacyDatabase`: Handles storage and retrieval of privacy settings
- `UserSettings`: Database model for storing user privacy preferences
- VCF Processing: Enforces privacy settings when processing contact information