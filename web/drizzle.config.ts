import 'dotenv/config';
import { defineConfig } from 'drizzle-kit';

export default defineConfig({
  out: './drizzle',
  schema: './app/db/schema.ts',
  dialect: 'sqlite',
  dbCredentials: {
    url: `file:${process.env.DB_FILE_NAME || 'local.db'}`,
  },
});
