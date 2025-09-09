import { eq } from 'drizzle-orm';
import { db } from './index';
import { usersTable } from './schema';

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

  const users = await db.select().from(usersTable).where(eq(usersTable.contact, contact));
  return users[0];
}

export async function getUserById(id: number) {
  const users = await db.select().from(usersTable).where(eq(usersTable.id, id));
  return users[0];
}

// Simplified OTP operations
export async function storeOtp(contact: string, otpCode: string, expiresInMinutes: number = 5) {
  const expiresAt = new Date(Date.now() + expiresInMinutes * 60 * 1000).toISOString();

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
  providedCode: string
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
