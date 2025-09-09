export type PrivacySettings = {
  disallow_photo: boolean;
  disallow_gender: boolean;
  disallow_birthday: boolean;
  disallow_address: boolean;
  disallow_company: boolean;
  disallow_title: boolean;
};

function buildUrl(path: string): string {
  const baseUrl = process.env.RADICALE_URL;
  if (!baseUrl) throw new Error('RADICALE_URL is not configured');
  return `${baseUrl.replace(/\/$/, '')}${path.startsWith('/') ? '' : '/'}${path}`;
}

async function request<T = any>(path: string, init?: RequestInit): Promise<T> {
  const token = process.env.RADICALE_TOKEN;
  if (!token) throw new Error('RADICALE_TOKEN is not configured');

  const resp = await fetch(buildUrl(path), {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
      ...(init?.headers || {}),
    },
  });

  const text = await resp.text();
  let json: any = null;
  try {
    json = text ? JSON.parse(text) : null;
  } catch {}

  if (!resp.ok) {
    const message = json?.error || resp.statusText || 'Radicale request failed';
    const error = new Error(message);
    (error as any).status = resp.status;
    (error as any).body = json ?? text;
    throw error;
  }
  return json as T;
}

export async function getPrivacySettings(user: string): Promise<PrivacySettings> {
  return request<PrivacySettings>(`/privacy/settings/${encodeURIComponent(user)}`);
}

export async function createPrivacySettings(user: string, settings: PrivacySettings) {
  return request(`/privacy/settings/${encodeURIComponent(user)}`, {
    method: 'POST',
    body: JSON.stringify(settings),
  });
}

export async function updatePrivacySettings(user: string, settings: Partial<PrivacySettings>) {
  return request(`/privacy/settings/${encodeURIComponent(user)}`, {
    method: 'PUT',
    body: JSON.stringify(settings),
  });
}

export async function reprocessUserCards(user: string) {
  return request(`/privacy/cards/${encodeURIComponent(user)}/reprocess`, {
    method: 'POST',
  });
}

export type CardMatch = {
  vcard_uid: string;
  collection_path: string;
  matching_fields: Record<string, any>;
  fields: Record<string, any>;
};

export async function getUserCards(user: string): Promise<{ matches: CardMatch[] }> {
  return request(`/privacy/cards/${encodeURIComponent(user)}`);
}
