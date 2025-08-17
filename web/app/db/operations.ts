import { eq } from 'drizzle-orm';
import { db } from './index';
import { usersTable, userPreferencesTable } from './schema';

// User operations
export async function createUser(contact: string) {
  if (!contact) {
    throw new Error('Contact (email or phone) must be provided');
  }

  const user = await db
    .insert(usersTable)
    .values({
      contact,
    })
    .returning();
  return user[0];
}

export async function getUserByContact(contact: string) {
  if (!contact) {
    return null;
  }

  const users = await db
    .select()
    .from(usersTable)
    .where(eq(usersTable.contact, contact));
  return users[0];
}

export async function getUserById(id: number) {
  const users = await db.select().from(usersTable).where(eq(usersTable.id, id));
  return users[0];
}

// User preferences operations
export async function getUserPreferences(userId: number) {
  const preferences = await db
    .select()
    .from(userPreferencesTable)
    .where(eq(userPreferencesTable.userId, userId));
  return preferences[0];
}

export async function saveUserPreferences(
  userId: number,
  preferences: {
    disallowPhoto?: number;
    disallowGender?: number;
    disallowBirthday?: number;
    disallowAddress?: number;
    disallowCompany?: number;
    disallowTitle?: number;
  },
) {
  // Try to update existing preferences first
  const existing = await getUserPreferences(userId);

  if (existing) {
    const updated = await db
      .update(userPreferencesTable)
      .set({
        ...preferences,
        contactProviderSynced: 0, // Mark as out of sync when preferences change
        updatedAt: new Date().toISOString(),
      })
      .where(eq(userPreferencesTable.userId, userId))
      .returning();
    return updated[0];
  } else {
    // Create new preferences record
    const created = await db
      .insert(userPreferencesTable)
      .values({ userId, ...preferences, contactProviderSynced: 0 })
      .returning();
    return created[0];
  }
}

// New function to mark contact provider as synced
export async function markContactProviderSynced(userId: number) {
  const updated = await db
    .update(userPreferencesTable)
    .set({
      contactProviderSynced: 1,
      updatedAt: new Date().toISOString(),
    })
    .where(eq(userPreferencesTable.userId, userId))
    .returning();
  return updated[0];
}

// Simplified OTP operations
export async function storeOtp(
  contact: string,
  otpCode: string,
  expiresInMinutes: number = 5,
) {
  const expiresAt = new Date(
    Date.now() + expiresInMinutes * 60 * 1000,
  ).toISOString();

  // Find or create user
  let user = await getUserByContact(contact);

  if (!user) {
    user = await createUser(contact);
  }

  // Store OTP
  await db
    .update(usersTable)
    .set({ otpCode, otpExpiresAt: expiresAt })
    .where(eq(usersTable.id, user.id));

  return user;
}

export async function verifyOtp(
  contact: string,
  providedCode: string,
): Promise<{ isValid: boolean; user?: typeof usersTable.$inferSelect }> {
  // Find user
  const user = await getUserByContact(contact);

  if (!user || !user.otpCode || !user.otpExpiresAt) {
    return { isValid: false };
  }

  // Check if OTP is expired
  const now = new Date();
  const expiresAt = new Date(user.otpExpiresAt);

  if (now > expiresAt) {
    // Clear expired OTP
    await db
      .update(usersTable)
      .set({ otpCode: null, otpExpiresAt: null })
      .where(eq(usersTable.id, user.id));
    return { isValid: false };
  }

  const isValid = user.otpCode === providedCode;

  // Clear OTP after verification attempt
  await db
    .update(usersTable)
    .set({ otpCode: null, otpExpiresAt: null })
    .where(eq(usersTable.id, user.id));

  return { isValid, user: isValid ? user : undefined };
}
