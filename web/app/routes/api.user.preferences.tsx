import { verifyAuth } from '~/lib/auth';
import {
  getUserByContact,
  getUserPreferences,
  saveUserPreferences,
  markContactProviderSynced,
} from '~/db/operations';

// Loader function for GET requests
export async function loader({ request }: { request: Request }) {
  try {
    // Get environment variables
    const env = process.env;
    const isDevelopment = import.meta.env.DEV;
    const JWT_SECRET =
      env.JWT_SECRET ||
      (isDevelopment ? 'dev-jwt-secret-key-for-testing-only' : undefined);

    if (!JWT_SECRET) {
      return new Response(
        JSON.stringify({
          error: 'Server configuration error: JWT_SECRET is not configured.',
        }),
        {
          status: 500,
          headers: { 'Content-Type': 'application/json' },
        },
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

    // Get user from database
    const dbUser = await getUserByContact(user.contact);
    if (!dbUser) {
      return new Response(JSON.stringify({ error: 'User not found' }), {
        status: 404,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    // Get user preferences
    const preferences = await getUserPreferences(dbUser.id);

    // Convert database format to frontend format
    const formattedPreferences = preferences
      ? {
          disallow_photo: preferences.disallowPhoto === 1,
          disallow_gender: preferences.disallowGender === 1,
          disallow_birthday: preferences.disallowBirthday === 1,
          disallow_address: preferences.disallowAddress === 1,
          disallow_company: preferences.disallowCompany === 1,
          disallow_title: preferences.disallowTitle === 1,
        }
      : {
          disallow_photo: false,
          disallow_gender: false,
          disallow_birthday: false,
          disallow_address: false,
          disallow_company: false,
          disallow_title: false,
        };

    const contactProviderSynced = preferences
      ? preferences.contactProviderSynced === 1
      : true;

    return new Response(
      JSON.stringify({
        preferences: formattedPreferences,
        contactProviderSynced,
      }),
      {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      },
    );
  } catch {
    return new Response(
      JSON.stringify({
        error: 'Internal server error',
      }),
      {
        status: 500,
        headers: { 'Content-Type': 'application/json' },
      },
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
      env.JWT_SECRET ||
      (isDevelopment ? 'dev-jwt-secret-key-for-testing-only' : undefined);

    if (!JWT_SECRET) {
      return new Response(
        JSON.stringify({
          error: 'Server configuration error: JWT_SECRET is not configured.',
        }),
        {
          status: 500,
          headers: { 'Content-Type': 'application/json' },
        },
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

    // Get user from database
    const dbUser = await getUserByContact(user.contact);
    if (!dbUser) {
      return new Response(JSON.stringify({ error: 'User not found' }), {
        status: 404,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    const body = (await request.json()) as {
      preferences?: Record<string, boolean>;
      action?: string;
    };

    const { preferences, action } = body;

    // Handle sync action
    if (action === 'sync') {
      await markContactProviderSynced(dbUser.id);
      return new Response(
        JSON.stringify({
          success: true,
          message: 'Contact provider synchronized',
        }),
        {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        },
      );
    }

    // Handle preferences update
    if (!preferences || typeof preferences !== 'object') {
      return new Response(
        JSON.stringify({ error: 'Invalid preferences data' }),
        {
          status: 400,
          headers: { 'Content-Type': 'application/json' },
        },
      );
    }

    // Convert frontend format to database format
    const dbPreferences = {
      disallowPhoto: preferences.disallow_photo ? 1 : 0,
      disallowGender: preferences.disallow_gender ? 1 : 0,
      disallowBirthday: preferences.disallow_birthday ? 1 : 0,
      disallowAddress: preferences.disallow_address ? 1 : 0,
      disallowCompany: preferences.disallow_company ? 1 : 0,
      disallowTitle: preferences.disallow_title ? 1 : 0,
    };

    await saveUserPreferences(dbUser.id, dbPreferences);

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
      },
    );
  }
}
