import type { Route } from './+types/api.auth.verify-otp';
import { createAuthToken } from '~/lib/auth';
import { verifyOtp } from '~/db/operations';
import { env } from '~/lib/env';

export async function action({ request }: Route.ActionArgs) {
  try {
    const JWT_SECRET = env.JWT_SECRET;

    if (!JWT_SECRET) {
      return new Response(
        JSON.stringify({
          error: 'Server configuration error: JWT_SECRET is not configured',
        }),
        { status: 500, headers: { 'Content-Type': 'application/json' } },
      );
    }

    // Parse request body
    const body = (await request.json()) as { email?: string; code?: string };
    const { email, code } = body;

    // Validate input
    if (!email || !code) {
      return new Response(
        JSON.stringify({ error: 'Email and verification code are required' }),
        { status: 400, headers: { 'Content-Type': 'application/json' } },
      );
    }

    if (typeof code !== 'string' || !/^\d{6}$/.test(code)) {
      return new Response(
        JSON.stringify({ error: 'Invalid verification code format' }),
        { status: 400, headers: { 'Content-Type': 'application/json' } },
      );
    }

    // Verify OTP
    const result = await verifyOtp(email, code);

    if (!result.isValid || !result.user) {
      return new Response(
        JSON.stringify({ error: 'Invalid or expired verification code' }),
        { status: 400, headers: { 'Content-Type': 'application/json' } },
      );
    }

    // Create authentication token
    const authToken = await createAuthToken(
      result.user.contact,
      result.user.id,
      JWT_SECRET,
    );
    return new Response(
      JSON.stringify({
        authToken,
        expiresIn: 86400, // 24 hours
        message: 'Authentication successful',
        user: {
          contact: result.user.contact,
          userId: result.user.id,
        },
      }),
      { status: 200, headers: { 'Content-Type': 'application/json' } },
    );
  } catch {
    return new Response(JSON.stringify({ error: 'Internal server error' }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' },
    });
  }
}
