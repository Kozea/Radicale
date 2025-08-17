import type { Route } from './+types/api.auth.request-otp';
import {
  generateOtpCode,
  sendOtpUnified,
  isValidEmail,
  isValidE164,
} from '~/lib/otp';
import { storeOtp } from '~/db/operations';

/**
 * Accepts either an email or an E.164 phone number and sends an OTP via
 * SES (email) or SNS (SMS) accordingly. Keeps the 15s timeout behavior.
 */
export async function action({ request }: Route.ActionArgs) {
  try {
    // Parse request body (supports legacy { email } and new { identifier })
    const body = (await request.json()) as {
      email?: string;
      identifier?: string;
    };
    const identifier = (body.identifier || body.email || '').trim();

    // Validate input presence
    if (!identifier) {
      return new Response(
        JSON.stringify({ error: 'Email or phone number is required' }),
        { status: 400, headers: { 'Content-Type': 'application/json' } },
      );
    }

    // Validate identifier format (must be email OR E.164 phone)
    const isEmail = isValidEmail(identifier);
    const isPhone = isValidE164(identifier);
    if (!isEmail && !isPhone) {
      return new Response(
        JSON.stringify({
          error:
            'Provide a valid email or E.164 phone number (e.g. +14155550123)',
        }),
        { status: 400, headers: { 'Content-Type': 'application/json' } },
      );
    }

    // Generate and store OTP under the identifier key
    const otpCode = generateOtpCode();

    try {
      await storeOtp(identifier, otpCode);
    } catch {
      return new Response(
        JSON.stringify({ error: 'Failed to store verification code' }),
        { status: 500, headers: { 'Content-Type': 'application/json' } },
      );
    }

    // Send OTP via the appropriate channel with a 15s timeout
    const otpPromise = sendOtpUnified(identifier, otpCode);
    const timeoutPromise = new Promise((_, reject) =>
      setTimeout(
        () => reject(new Error('OTP sending timeout after 15 seconds')),
        15000,
      ),
    );

    try {
      const otpResult = (await Promise.race([otpPromise, timeoutPromise])) as {
        success: boolean;
        error?: string;
        messageId?: string;
      };

      if (!otpResult?.success) {
        return new Response(
          JSON.stringify({
            error: otpResult?.error || 'Failed to send verification code',
          }),
          { status: 500, headers: { 'Content-Type': 'application/json' } },
        );
      }
    } catch {
      return new Response(
        JSON.stringify({ error: 'Failed to send verification code' }),
        { status: 500, headers: { 'Content-Type': 'application/json' } },
      );
    }

    // Return success response
    const responseData = {
      message: 'Verification code sent successfully',
      expiresIn: 300, // 5 minutes
    };

    return new Response(JSON.stringify(responseData), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  } catch {
    return new Response(JSON.stringify({ error: 'Internal server error' }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' },
    });
  }
}
