CREATE TABLE `users` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`contact` text NOT NULL,
	`otpCode` text,
	`otpExpiresAt` text,
	`createdAt` text DEFAULT (datetime('now')) NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `users_contact_unique` ON `users` (`contact`);