import { verifyAuth } from '~/lib/auth';
import { getUserCards } from '~/api/radicale';

export async function loader({ request }: { request: Request }) {
  try {
    const env = process.env;
    const isDevelopment = import.meta.env.DEV;
    const JWT_SECRET =
      env.JWT_SECRET || (isDevelopment ? 'dev-jwt-secret-key-for-testing-only' : undefined);

    if (!JWT_SECRET) {
      return new Response(
        JSON.stringify({ error: 'Server configuration error: JWT_SECRET is not configured.' }),
        { status: 500, headers: { 'Content-Type': 'application/json' } }
      );
    }

    const user = await verifyAuth(request, JWT_SECRET);
    if (!user) {
      return new Response(JSON.stringify({ error: 'Unauthorized' }), {
        status: 401,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    const cards = await getUserCards(user.contact);
    return new Response(JSON.stringify(cards), {
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
