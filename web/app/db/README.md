# Subject Data Preferences Database Schema

This directory contains the Drizzle ORM setup for the Subject Data Preferences application using SQLite.

## Files

- `schema.ts` - Database table definitions for users and preferences
- `index.ts` - Database connection setup
- `operations.ts` - Database operations for the application
- `test.ts` - Comprehensive test file that demonstrates all functionality

## Schema Overview

### 1. Users Table (`users`)

Stores authenticated users:

- `id` - Primary key (auto-increment)
- `contact` - Unique email or phone number for authentication
- `otpCode` - Current OTP code (nullable when no active OTP)
- `otpExpiresAt` - OTP expiration timestamp (nullable when no active OTP)
- `createdAt` - Creation timestamp

### 2. User Preferences Table (`user_preferences`)

Stores Subject Data Preferences for privacy control:

- `id` - Primary key (auto-increment)
- `userId` - Foreign key to users table
- `disallowPhoto` - Photo privacy setting (0 = allow, 1 = disallow)
- `disallowGender` - Gender/pronoun privacy setting
- `disallowBirthday` - Birthday privacy setting
- `disallowAddress` - Address privacy setting
- `disallowCompany` - Company privacy setting
- `disallowTitle` - Job title privacy setting
- `contactProviderSynced` - Sync status with contact provider (0 = out of sync, 1 = synced)
- `updatedAt` - Last update timestamp

## Available Scripts

- `pnpm db:generate` - Generate migration files
- `pnpm db:migrate` - Apply migrations to database
- `pnpm db:push` - Push schema changes directly to database
- `pnpm db:studio` - Open Drizzle Studio for database management

## Usage Examples

### User Management

```typescript
import { createUser, getUserByContact } from './app/db/operations';

// Create user with email
const user = await createUser('john@example.com');

// Create user with phone
const phoneUser = await createUser('+1234567890');

// Find user by contact (email or phone)
const foundUser = await getUserByContact('john@example.com');
```

### User Preferences Management

```typescript
import { saveUserPreferences, getUserPreferences } from './app/db/operations';

// Save privacy preferences
await saveUserPreferences(userId, {
  disallowPhoto: 1, // Keep photos private
  disallowGender: 0, // Allow gender info
  disallowBirthday: 1, // Keep birthday private
  disallowAddress: 0, // Allow address
  disallowCompany: 0, // Allow company info
  disallowTitle: 1, // Keep job title private
});

// Get user preferences
const preferences = await getUserPreferences(userId);
```

### OTP Management

```typescript
import { storeOtp, verifyOtp } from './app/db/operations';

// Store OTP for user
const user = await storeOtp('john@example.com', '123456', 5); // 5 minutes expiration

// Verify OTP
const result = await verifyOtp('john@example.com', '123456');
if (result.isValid) {
  console.log('OTP verified for user:', result.user);
}
```

## Testing

Run the comprehensive test suite:

```bash
pnpm tsx app/db/test.ts
```

This will test all functionality including:

- User creation with email or phone
- User lookup by contact
- Privacy preferences management
- OTP storage and verification

## Key Features

✅ **Flexible Authentication**: Supports email or phone authentication  
✅ **Privacy Controls**: Granular control over data field visibility  
✅ **OTP Security**: Secure OTP storage with automatic expiration  
✅ **Data Relationships**: Proper foreign keys with cascade deletion  
✅ **Timestamps**: Automatic creation and update tracking
