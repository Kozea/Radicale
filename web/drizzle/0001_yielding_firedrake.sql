-- Custom migration to consolidate email/phone into contact field
-- Step 1: Add the new contact column as nullable first
ALTER TABLE `users` ADD `contact` text;

-- Step 2: Copy data from email or phone to contact
UPDATE `users` SET `contact` = COALESCE(`email`, `phone`) WHERE `contact` IS NULL;

-- Step 3: Make contact NOT NULL and UNIQUE
-- First drop existing unique indexes
DROP INDEX IF EXISTS `users_email_unique`;
DROP INDEX IF EXISTS `users_phone_unique`;

-- Create new unique index on contact
CREATE UNIQUE INDEX `users_contact_unique` ON `users` (`contact`);

-- Step 4: Drop old columns
ALTER TABLE `users` DROP COLUMN `email`;
ALTER TABLE `users` DROP COLUMN `phone`;