/**
 * Simplified authentication utilities
 */

import { SignJWT, jwtVerify } from 'jose';

export interface AuthUser {
  contact: string; // email or phone
  userId: number;
}

interface AuthTokenPayload {
  contact: string;
  userId: number;
  exp: number;
  iat: number;
  [key: string]: string | number; // Allow additional JWT properties
}

/**
 * Create an authentication token (24 hours)
 */
export async function createAuthToken(
  contact: string,
  userId: number,
  secret: string,
): Promise<string> {
  const key = new TextEncoder().encode(secret);
  const now = Math.floor(Date.now() / 1000);

  const payload: AuthTokenPayload = {
    contact,
    userId,
    exp: now + 24 * 60 * 60, // 24 hours
    iat: now,
  };

  const jwt = await new SignJWT(payload)
    .setProtectedHeader({ alg: 'HS256' })
    .setIssuedAt()
    .setExpirationTime(new Date(payload.exp * 1000))
    .sign(key);

  return jwt;
}

/**
 * Verify an authentication token
 */
export async function verifyAuthToken(
  token: string,
  secret: string,
): Promise<AuthTokenPayload> {
  const key = new TextEncoder().encode(secret);

  try {
    const { payload } = await jwtVerify(token, key);

    // Validate required properties
    if (
      typeof payload.contact !== 'string' ||
      typeof payload.userId !== 'number'
    ) {
      throw new Error('Invalid token payload');
    }

    return payload as AuthTokenPayload;
  } catch {
    throw new Error('Invalid or expired token');
  }
}

/**
 * Client-side: Get auth token from localStorage
 */
export function getAuthToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('auth_token');
}

/**
 * Client-side: Store auth token in localStorage
 */
export function setAuthToken(token: string): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem('auth_token', token);
}

/**
 * Client-side: Remove auth token
 */
export function clearAuthToken(): void {
  if (typeof window === 'undefined') return;
  localStorage.removeItem('auth_token');
}

/**
 * Client-side: Check if user is authenticated
 */
export function isAuthenticated(): boolean {
  const token = getAuthToken();
  return !!token;
}

/**
 * Server-side: Extract auth token from request headers
 */
export function extractAuthToken(request: Request): string | null {
  const authHeader = request.headers.get('Authorization');
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return null;
  }
  return authHeader.substring(7); // Remove 'Bearer ' prefix
}

/**
 * Server-side: Verify auth token and return user info
 */
export async function verifyAuth(
  request: Request,
  jwtSecret: string,
): Promise<AuthUser | null> {
  try {
    const token = extractAuthToken(request);
    if (!token) {
      return null;
    }

    const payload = await verifyAuthToken(token, jwtSecret);
    return { contact: payload.contact, userId: payload.userId };
  } catch {
    return null;
  }
}

/**
 * Server-side: Require authentication middleware
 */
export async function requireAuth(
  request: Request,
  jwtSecret: string,
): Promise<AuthUser> {
  const user = await verifyAuth(request, jwtSecret);
  if (!user) {
    throw new Response('Unauthorized', { status: 401 });
  }
  return user;
}

/**
 * Client-side: Add auth header to fetch requests
 */
export function createAuthHeaders(): HeadersInit {
  const token = getAuthToken();
  if (!token) {
    return {};
  }
  return {
    Authorization: `Bearer ${token}`,
  };
}

/**
 * Client-side: Authenticated fetch wrapper
 */
export async function authFetch(
  url: string,
  options: RequestInit = {},
): Promise<Response> {
  const authHeaders = createAuthHeaders();

  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders,
      ...options.headers,
    },
  });

  // If unauthorized, clear token and redirect to login
  if (response.status === 401) {
    clearAuthToken();
    if (typeof window !== 'undefined') {
      window.location.href = '/login';
    }
  }

  return response;
}
