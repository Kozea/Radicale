import { useState, useEffect } from 'react';
import { Checkbox } from '~/components/ui/checkbox';
import type { Route } from './+types/privacy-preferences';

export function meta(_: Route.MetaArgs) {
  return [
    { title: 'Privacy Preferences' },
    { name: 'description', content: 'Set your privacy preferences for the contact management system. Control which personal information fields can be synced and how your data is handled.' },
    { name: 'keywords', content: 'privacy preferences, contact manager privacy, data protection, personal information control, contact field preferences, GDPR preferences' },
    { property: 'og:title', content: 'Privacy Preferences' },
    { property: 'og:description', content: 'Control your personal information in the contact management system.' },
    { property: 'og:type', content: 'website' },
  ];
}

export const handle = {
  subtitle: 'Privacy Preferences',
};

interface PreferenceField {
  id: string;
  label: string;
  defaultChecked: boolean;
}

const preferenceFields: PreferenceField[] = [
  { id: 'pronoun', label: 'Pronoun', defaultChecked: true },
  { id: 'company', label: 'Company', defaultChecked: false },
  { id: 'jobTitle', label: 'Job title', defaultChecked: false },
  { id: 'photo', label: 'Photo', defaultChecked: true },
  { id: 'birthday', label: 'Birthday', defaultChecked: true },
  { id: 'relatedPerson', label: 'Related person', defaultChecked: false },
  { id: 'address', label: 'Address', defaultChecked: false },
];

// Helper function to get JWT token from localStorage
function getAuthToken(): string | null {
  if (typeof window !== 'undefined') {
    return localStorage.getItem('auth_token');
  }
  return null;
}

// Helper function to get user identifier from JWT token (simple decode)
function getUserFromToken(token: string): string | null {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    return payload.sub; // JWT subject is the user identifier
  } catch (e) {
    console.error('Failed to decode JWT token:', e);
    return null;
  }
}

// Helper function to fetch settings from backend
async function fetchSettings(): Promise<{ ok: boolean; settings?: any; error?: string }> {
  const token = getAuthToken();
  if (!token) {
    return { ok: false, error: 'No authentication token found' };
  }

  const user = getUserFromToken(token);
  if (!user) {
    return { ok: false, error: 'Invalid authentication token' };
  }

  try {
    const res = await fetch(`/privacy/settings/${encodeURIComponent(user)}`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    });

    if (res.status === 200) {
      const settings = await res.json();
      return { ok: true, settings };
    } else if (res.status === 401) {
      return { ok: false, error: 'Authentication expired' };
    } else {
      const data = await res.json().catch(() => ({}));
      return { ok: false, error: data.error || 'Failed to fetch settings' };
    }
  } catch (e) {
    return { ok: false, error: (e as Error).message };
  }
}

export default function PreferencesPage() {
  const [preferences, setPreferences] = useState<Record<string, boolean>>(
    Object.fromEntries(preferenceFields.map(field => [field.id, field.defaultChecked]))
  );
  const [settings, setSettings] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadSettings = async () => {
      // Check if user is authenticated
      const token = getAuthToken();
      if (!token) {
        // Redirect to login if no token
        window.location.href = '/login';
        return;
      }

      setLoading(true);
      const result = await fetchSettings();
      setLoading(false);

      if (result.ok && result.settings) {
        setSettings(result.settings);
        console.log('Loaded settings:', result.settings);
      } else {
        setError(result.error || 'Failed to load settings');
        if (result.error === 'Authentication expired') {
          // Clear token and redirect to login
          localStorage.removeItem('auth_token');
          window.location.href = '/login';
        }
      }
    };

    loadSettings();
  }, []);

  const handlePreferenceChange = (fieldId: string, checked: boolean) => {
    setPreferences(prev => ({
      ...prev,
      [fieldId]: checked,
    }));
  };

  if (loading) {
    return (
      <div className="min-h-screen py-8">
        <div className="container mx-auto max-w-4xl px-6">
          <div className="text-center">
            <h1 className="text-4xl font-bold text-gray-900 mb-6">Privacy Preferences</h1>
            <p className="text-gray-600">Loading your settings...</p>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen py-8">
        <div className="container mx-auto max-w-4xl px-6">
          <div className="text-center">
            <h1 className="text-4xl font-bold text-gray-900 mb-6">Privacy Preferences</h1>
            <div className="bg-red-50 border border-red-200 rounded-lg p-6">
              <p className="text-red-800">Error: {error}</p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen py-8">
      <div className="container mx-auto max-w-4xl px-6">
        <div className="space-y-8">
          {/* Header */}
          <div>
            <h1 className="text-4xl font-bold text-gray-900 mb-6">Privacy Preferences</h1>
            <p className="text-gray-600 text-lg leading-relaxed mb-2">
              Control how your personal information is handled in the contact management system.
              Select which contact fields you want to keep private and prevent from being synced.
            </p>
          </div>

          {/* Settings JSON Display */}
          <div className="bg-gray-50 border border-gray-200 rounded-lg p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Current Settings (JSON)</h3>
            <pre className="bg-white p-4 rounded border text-sm overflow-auto">
              {JSON.stringify(settings, null, 2)}
            </pre>
          </div>

          {/* Description */}
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-6 mb-6">
            <h3 className="text-lg font-semibold text-blue-900 mb-2">Your Privacy Control</h3>
            <p className="text-blue-800">
              These preferences apply to your contact information across the system.
              Fields marked as private will not be synced or shared when your contact details are accessed.
            </p>
          </div>

          <div className="text-gray-700 text-base leading-relaxed">
            <p>
              When someone creates a contact card with your information, the following fields will{' '}
              <span className="font-semibold">not</span> be included if you've marked them as private:
            </p>
          </div>

          {/* Preferences Form */}
          <div className="space-y-6">
            {preferenceFields.map(field => (
              <div key={field.id} className="flex items-center space-x-3">
                <Checkbox
                  id={field.id}
                  checked={preferences[field.id]}
                  onCheckedChange={(checked: boolean) => handlePreferenceChange(field.id, checked)}
                  className="h-5 w-5"
                />
                <label
                  htmlFor={field.id}
                  className="text-lg text-gray-900 cursor-pointer select-none"
                >
                  Keep {field.label} private
                </label>
              </div>
            ))}
          </div>

          {/* Save Button */}
          <div className="pt-6">
            <button
              className="bg-blue-500 hover:bg-blue-600 text-white font-medium py-2 px-6 rounded-md transition-colors"
              onClick={() => {
                // Here you would typically save to a backend
                // console.log('Saved preferences:', preferences);
              }}
            >
              Save Privacy Preferences
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
