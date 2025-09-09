import { verifyAuth } from '~/lib/auth';
import {
  getPrivacySettings,
  updatePrivacySettings,
  createPrivacySettings,
  reprocessUserCards,
} from '~/api/radicale';

// Loader function for GET requests
export async function loader({ request }: { request: Request }) {
  try {
    // Get environment variables
    const env = process.env;
    const isDevelopment = import.meta.env.DEV;
    const JWT_SECRET =
      env.JWT_SECRET || (isDevelopment ? 'dev-jwt-secret-key-for-testing-only' : undefined);

    if (!JWT_SECRET) {
      return new Response(
        JSON.stringify({
          error: 'Server configuration error: JWT_SECRET is not configured.',
        }),
        {
          status: 500,
          headers: { 'Content-Type': 'application/json' },
        }
      );
    }

    // Verify authentication
    const user = await verifyAuth(request, JWT_SECRET);
    if (!user) {
      return new Response(JSON.stringify({ error: 'Unauthorized' }), {
        status: 401,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    // Fetch preferences from Radicale (auto-creates defaults if missing)
    const formattedPreferences = await getPrivacySettings(user.contact);

    return new Response(
      JSON.stringify({
        preferences: formattedPreferences,
      }),
      {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  } catch {
    return new Response(
      JSON.stringify({
        error: 'Internal server error',
      }),
      {
        status: 500,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  }
}

// Action function for PUT requests
export async function action({ request }: { request: Request }) {
  try {
    // Get environment variables
    const env = process.env;
    const isDevelopment = import.meta.env.DEV;
    const JWT_SECRET =
      env.JWT_SECRET || (isDevelopment ? 'dev-jwt-secret-key-for-testing-only' : undefined);

    if (!JWT_SECRET) {
      return new Response(
        JSON.stringify({
          error: 'Server configuration error: JWT_SECRET is not configured.',
        }),
        {
          status: 500,
          headers: { 'Content-Type': 'application/json' },
        }
      );
    }

    // Verify authentication
    const user = await verifyAuth(request, JWT_SECRET);
    if (!user) {
      return new Response(JSON.stringify({ error: 'Unauthorized' }), {
        status: 401,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    const body = (await request.json()) as {
      preferences?: Record<string, boolean>;
      action?: string;
    };

    const { preferences, action } = body;

    // Handle sync action by triggering Radicale reprocessing
    if (action === 'sync') {
      await reprocessUserCards(user.contact);
      return new Response(JSON.stringify({ success: true, message: 'Reprocessing triggered' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    // Handle preferences update
    if (!preferences || typeof preferences !== 'object') {
      return new Response(JSON.stringify({ error: 'Invalid preferences data' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    // Update preferences in Radicale; create if missing
    try {
      await updatePrivacySettings(user.contact, preferences);
    } catch (err: any) {
      if (err?.status === 400) {
        await createPrivacySettings(user.contact, {
          disallow_photo: false,
          disallow_gender: false,
          disallow_birthday: false,
          disallow_address: false,
          disallow_company: false,
          disallow_title: false,
          ...preferences,
        });
      } else {
        throw err;
      }
    }

    return new Response(JSON.stringify({ success: true }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  } catch {
    return new Response(
      JSON.stringify({
        error: 'Internal server error',
      }),
      {
        status: 500,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  }
}
