/**
 * Centralized environment configuration
 * Load this module to ensure environment variables are available
 */

// Load environment variables from .env file
import 'dotenv/config';

export interface EnvConfig {
  // Database
  DB_FILE_NAME: string;

  // JWT
  JWT_SECRET: string;

  // AWS SES
  AWS_ACCESS_KEY_ID?: string;
  AWS_SECRET_ACCESS_KEY?: string;
  AWS_REGION?: string;
  EMAIL_FROM?: string;
  EMAIL_FROM_NAME?: string;

  // Environment
  NODE_ENV: string;
  DEV: boolean;
}

/**
 * Get environment configuration with validation and defaults
 */
export function getEnv(): EnvConfig {
  const isDev =
    process.env.NODE_ENV === 'development' ||
    process.env.NODE_ENV === undefined;

  return {
    // Database
    DB_FILE_NAME: process.env.DB_FILE_NAME || 'local.db',

    // JWT
    JWT_SECRET:
      process.env.JWT_SECRET ||
      (isDev ? 'dev-jwt-secret-key-for-testing-only' : ''),

    // AWS SES
    AWS_ACCESS_KEY_ID: process.env.AWS_ACCESS_KEY_ID,
    AWS_SECRET_ACCESS_KEY: process.env.AWS_SECRET_ACCESS_KEY,
    AWS_REGION: process.env.AWS_REGION,
    EMAIL_FROM: process.env.EMAIL_FROM,
    EMAIL_FROM_NAME: process.env.EMAIL_FROM_NAME,

    // Environment
    NODE_ENV: process.env.NODE_ENV || 'development',
    DEV: isDev,
  };
}

/**
 * Check if AWS SES is configured
 */
export function isAwsConfigured(env: EnvConfig): boolean {
  return !!(
    env.AWS_ACCESS_KEY_ID &&
    env.AWS_SECRET_ACCESS_KEY &&
    env.AWS_REGION &&
    env.EMAIL_FROM
  );
}

/**
 * Validate required environment variables
 */
export function validateEnv(env: EnvConfig): void {
  if (!env.DEV && !env.JWT_SECRET) {
    throw new Error('JWT_SECRET is required in production');
  }

  if (!env.DEV && !isAwsConfigured(env)) {
    throw new Error('AWS SES configuration is required in production');
  }
}

// Export a singleton instance
export const env = getEnv();
