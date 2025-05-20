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

The following settings control the default privacy preferences for new users. Each setting determines whether a specific field is allowed to be stored by default:

```ini
[privacy]
default_allow_name = true
default_allow_email = true
default_allow_phone = true
default_allow_company = true
default_allow_title = true
default_allow_photo = true
default_allow_birthday = true
default_allow_address = true
```

- `default_allow_name`: Whether users' names can be stored by default
- `default_allow_email`: Whether users' email addresses can be stored by default
- `default_allow_phone`: Whether users' phone numbers can be stored by default
- `default_allow_company`: Whether users' company information can be stored by default
- `default_allow_title`: Whether users' job titles can be stored by default
- `default_allow_photo`: Whether users' photos can be stored by default
- `default_allow_birthday`: Whether users' birthdays can be stored by default
- `default_allow_address`: Whether users' addresses can be stored by default

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
default_allow_name = true
default_allow_email = true
default_allow_phone = false
default_allow_company = true
default_allow_title = true
default_allow_photo = false
default_allow_birthday = false
default_allow_address = false
```

This configuration:
- Stores the database in `/var/lib/radicale/privacy.db`
- Allows storing names, emails, company, and title by default
- Restricts storing phone numbers, photos, birthdays, and addresses by default

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