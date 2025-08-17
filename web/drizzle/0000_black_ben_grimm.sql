CREATE TABLE `contact_records` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`userId` integer NOT NULL,
	`fromContact` text NOT NULL,
	`company` text,
	`name` text,
	`nickname` text,
	`jobTitle` text,
	`mobile` text,
	`email` text,
	`spouse` text,
	`createdAt` text DEFAULT (datetime('now')) NOT NULL,
	FOREIGN KEY (`userId`) REFERENCES `users`(`id`) ON UPDATE no action ON DELETE cascade
);
--> statement-breakpoint
CREATE TABLE `user_preferences` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`userId` integer NOT NULL,
	`disallowPhoto` integer DEFAULT 0 NOT NULL,
	`disallowGender` integer DEFAULT 0 NOT NULL,
	`disallowBirthday` integer DEFAULT 0 NOT NULL,
	`disallowAddress` integer DEFAULT 0 NOT NULL,
	`disallowCompany` integer DEFAULT 0 NOT NULL,
	`disallowTitle` integer DEFAULT 0 NOT NULL,
	`updatedAt` text DEFAULT (datetime('now')) NOT NULL,
	FOREIGN KEY (`userId`) REFERENCES `users`(`id`) ON UPDATE no action ON DELETE cascade
);
--> statement-breakpoint
CREATE TABLE `users` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`email` text,
	`phone` text,
	`createdAt` text DEFAULT (datetime('now')) NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `users_email_unique` ON `users` (`email`);--> statement-breakpoint
CREATE UNIQUE INDEX `users_phone_unique` ON `users` (`phone`);