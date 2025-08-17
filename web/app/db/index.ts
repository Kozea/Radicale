import { drizzle } from 'drizzle-orm/libsql';
import { createClient } from '@libsql/client';
import { env } from '~/lib/env';

const client = createClient({
  url: `file:${env.DB_FILE_NAME}`,
});
export const db = drizzle(client);
