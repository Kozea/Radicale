import { int, sqliteTable, text } from 'drizzle-orm/sqlite-core';
import { sql } from 'drizzle-orm';

// Users table - stores authenticated users by email or phone
export const usersTable = sqliteTable('users', {
  id: int().primaryKey({ autoIncrement: true }),
  contact: text().notNull().unique(), // email or phone number
  otpCode: text(), // current OTP code (nullable when no active OTP)
  otpExpiresAt: text(), // OTP expiration timestamp (nullable when no active OTP)
  createdAt: text()
    .notNull()
    .default(sql`(datetime('now'))`),
});
