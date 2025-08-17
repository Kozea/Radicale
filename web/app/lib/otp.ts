/**
 * Communication utility functions for Cloudflare Workers using Amazon SES & SNS
 */

import {
  SESClient,
  SendEmailCommand,
  type SendEmailCommandInput,
} from '@aws-sdk/client-ses';
import {
  SNSClient,
  PublishCommand,
  type PublishCommandInput,
} from '@aws-sdk/client-sns';
import { env } from '~/lib/env';

export interface AmazonSESConfig {
  accessKeyId: string;
  secretAccessKey: string;
  region: string;
  fromEmail: string;
  fromName?: string;
}

export interface AmazonSNSConfig {
  accessKeyId: string;
  secretAccessKey: string;
  region: string;
}

/**
 * Generate a 6-digit OTP code
 */
export function generateOtpCode(): string {
  return Math.floor(100000 + Math.random() * 900000).toString();
}

/**
 * Validate email format
 */
export function isValidEmail(email: string): boolean {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email);
}

/**
 * Validate E.164 phone format, e.g. +14155550123 (1–15 digits after +)
 */
export function isValidE164(phone: string): boolean {
  return /^\+[1-9]\d{1,14}$/.test(phone);
}

/**
 * Create Amazon SES client instance
 */
function createSESClient(config: AmazonSESConfig) {
  const client = new SESClient({
    region: config.region,
    credentials: {
      accessKeyId: config.accessKeyId,
      secretAccessKey: config.secretAccessKey,
    },
    requestHandler: {
      requestTimeout: 10000,
      connectionTimeout: 5000,
    },
    maxAttempts: 1,
    endpoint: `https://email.${config.region}.amazonaws.com`,
  });

  return {
    sendEmail: async (params: SendEmailCommandInput) => {
      const command = new SendEmailCommand(params);
      const result = await client.send(command);
      return result;
    },
  };
}

/**
 * Send email using Amazon SES
 */
export async function sendEmail(
  to: string,
  subject: string,
  html: string,
  config: AmazonSESConfig,
): Promise<{ success: boolean; error?: string; messageId?: string }> {
  try {
    const sesClient = createSESClient(config);

    const params = {
      Source: config.fromName
        ? `${config.fromName} <${config.fromEmail}>`
        : config.fromEmail,
      Destination: {
        ToAddresses: [to],
      },
      Message: {
        Subject: {
          Data: subject,
          Charset: 'UTF-8',
        },
        Body: {
          Html: {
            Data: html,
            Charset: 'UTF-8',
          },
        },
      },
    };

    const result = await sesClient.sendEmail(params);

    return {
      success: true,
      messageId: result.MessageId || `ses_${Date.now()}`,
    };
  } catch (error: unknown) {
    let errorMessage = 'Unknown error occurred';

    if (
      error &&
      typeof error === 'object' &&
      'name' in error &&
      'message' in error
    ) {
      errorMessage = `${error.name}: ${error.message}`;
    } else if (error && typeof error === 'object' && 'message' in error) {
      errorMessage = String(error.message);
    }

    return {
      success: false,
      error: `Amazon SES Error: ${errorMessage}`,
    };
  }
}

/**
 * Send OTP code via email using Amazon SES
 */
export async function sendOtpEmail(
  email: string,
  otpCode: string,
  config: AmazonSESConfig,
): Promise<{ success: boolean; error?: string; messageId?: string }> {
  const subject = 'Your Verification Code';
  const html = `
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
      <div style="text-align: center; margin-bottom: 40px;">
        <h1 style="color: #1f2937; font-size: 24px; margin: 0;">Verification Code</h1>
      </div>
      
      <div style="background: #f9fafb; border-radius: 12px; padding: 24px; text-align: center; margin-bottom: 24px;">
        <p style="color: #6b7280; margin: 0 0 16px 0; font-size: 16px;">Your verification code is:</p>
        <div style="font-size: 32px; font-weight: bold; color: #1f2937; font-family: 'Courier New', monospace; letter-spacing: 4px;">${otpCode}</div>
      </div>
      
      <p style="color: #6b7280; font-size: 14px; text-align: center; margin: 0;">
        This code will expire in 5 minutes. If you didn't request this code, please ignore this email.
      </p>
    </div>
  `;

  return sendEmail(email, subject, html, config);
}

/**
 * Create SES configuration from environment variables
 */
export function createSESConfig(): AmazonSESConfig {
  if (
    !env.AWS_ACCESS_KEY_ID ||
    !env.AWS_SECRET_ACCESS_KEY ||
    !env.AWS_REGION ||
    !env.EMAIL_FROM
  ) {
    throw new Error('Missing required AWS configuration environment variables');
  }

  return {
    accessKeyId: env.AWS_ACCESS_KEY_ID,
    secretAccessKey: env.AWS_SECRET_ACCESS_KEY,
    region: env.AWS_REGION,
    fromEmail: env.EMAIL_FROM,
    fromName: env.EMAIL_FROM_NAME,
  };
}

/**
 * Send OTP code via email (simplified for email-only)
 */
export async function sendOtp(
  email: string,
  otpCode: string,
  sesConfig?: AmazonSESConfig,
): Promise<{ success: boolean; error?: string; messageId?: string }> {
  if (!isValidEmail(email)) {
    return {
      success: false,
      error: 'Invalid email format. Please enter a valid email address.',
    };
  }

  const config = sesConfig || createSESConfig();
  return sendOtpEmail(email, otpCode, config);
}

// ---------------------------------------------------------------------------
//                              SNS (SMS) SUPPORT
// ---------------------------------------------------------------------------

/**
 * Create Amazon SNS client instance
 */
function createSNSClient(config: AmazonSNSConfig) {
  const client = new SNSClient({
    region: config.region,
    credentials: {
      accessKeyId: config.accessKeyId,
      secretAccessKey: config.secretAccessKey,
    },
    requestHandler: {
      requestTimeout: 10000,
      connectionTimeout: 5000,
    },
    maxAttempts: 1,
    endpoint: `https://sns.${config.region}.amazonaws.com`,
  });

  return {
    publish: async (params: PublishCommandInput) => {
      const command = new PublishCommand(params);
      const result = await client.send(command);
      return result;
    },
  };
}

/**
 * Send an SMS via Amazon SNS.
 * - `to` must be an E.164 phone number, e.g. +14155550123
 */
export async function sendSms(
  to: string,
  message: string,
  config: AmazonSNSConfig,
): Promise<{ success: boolean; error?: string; messageId?: string }> {
  if (!isValidE164(to)) {
    return {
      success: false,
      error: 'Invalid phone number. Use E.164 format like +14155550123.',
    };
  }

  try {
    const sns = createSNSClient(config);

    const result = await sns.publish({
      PhoneNumber: to,
      Message: message,
      MessageAttributes: {
        'AWS.SNS.SMS.SMSType': {
          DataType: 'String',
          StringValue: 'Transactional',
        },
      },
    });

    return {
      success: true,
      messageId: result.MessageId || `sns_${Date.now()}`,
    };
  } catch (error: unknown) {
    let errorMessage = 'Unknown error occurred';

    if (
      error &&
      typeof error === 'object' &&
      'name' in error &&
      'message' in error
    ) {
      errorMessage = `${error.name}: ${error.message}`;
    } else if (error && typeof error === 'object' && 'message' in error) {
      errorMessage = String(error.message);
    }

    return {
      success: false,
      error: `Amazon SNS Error: ${errorMessage}`,
    };
  }
}

/**
 * Send an OTP via SMS using SNS
 */
export async function sendOtpSms(
  phone: string,
  otpCode: string,
  config: AmazonSNSConfig,
  domain?: string,
): Promise<{ success: boolean; error?: string; messageId?: string }> {
  const humanLine = `Your verification code is ${otpCode}. It expires in 5 minutes.`;
  const domainLine = domain ? `\n@${domain} #${otpCode}` : ""; // <-- Safari looks for this format
  const msg = humanLine + domainLine;
  return sendSms(phone, msg, config);
}

/**
 * Create SNS configuration from environment variables
 */
export function createSNSConfig(): AmazonSNSConfig {
  if (!env.AWS_ACCESS_KEY_ID || !env.AWS_SECRET_ACCESS_KEY || !env.AWS_REGION) {
    throw new Error('Missing required AWS configuration environment variables');
  }

  return {
    accessKeyId: env.AWS_ACCESS_KEY_ID,
    secretAccessKey: env.AWS_SECRET_ACCESS_KEY,
    region: env.AWS_REGION,
  };
}

/**
 * Example: unified helper that decides channel by identifier
 */
export async function sendOtpUnified(
  identifier: string,
  otpCode: string,
  sesConfig?: AmazonSESConfig,
  snsConfig?: AmazonSNSConfig,
): Promise<{
  success: boolean;
  error?: string;
  messageId?: string;
  channel?: 'email' | 'sms';
}> {
  if (isValidEmail(identifier)) {
    const cfg = sesConfig || createSESConfig();
    const res = await sendOtpEmail(identifier, otpCode, cfg);
    return { ...res, channel: 'email' };
  }
  if (isValidE164(identifier)) {
    const cfg = snsConfig || createSNSConfig();
    const res = await sendOtpSms(identifier, otpCode, cfg, 'localhost');
    return { ...res, channel: 'sms' };
  }
  return {
    success: false,
    error:
      'Identifier must be an email or E.164 phone number (e.g. +14155550123).',
  };
}
