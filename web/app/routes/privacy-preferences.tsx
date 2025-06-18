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

// Mapping between API field names and user-friendly labels
const fieldMapping = {
  disallow_photo: { label: 'Photo', description: 'Profile pictures and contact photos' },
  disallow_gender: { label: 'Gender/Pronoun', description: 'Gender identity and preferred pronouns' },
  disallow_birthday: { label: 'Birthday', description: 'Date of birth and age information' },
  disallow_address: { label: 'Address', description: 'Home, work, and mailing addresses' },
  disallow_company: { label: 'Company', description: 'Employer and organization information' },
  disallow_title: { label: 'Job Title', description: 'Professional titles and positions' },
};

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
async function fetchSettings(user: string): Promise<{ ok: boolean; settings?: any; error?: string }> {
  const token = getAuthToken();
  if (!token) {
    return { ok: false, error: 'No authentication token found' };
  }

  try {
    const res = await fetch(`http://localhost:5232/privacy/settings/${encodeURIComponent(user)}`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`,
      },
    });

    if (res.status === 200) {
      const settings = await res.json();
      return { ok: true, settings };
    } else if (res.status === 401 || res.status === 403) {
      return { ok: false, error: 'Authentication required' };
    } else {
      const data = await res.json().catch(() => ({}));
      return { ok: false, error: data.error || 'Failed to fetch settings' };
    }
  } catch (e) {
    return { ok: false, error: (e as Error).message };
  }
}

// Helper function to save settings to backend
async function saveSettings(user: string, settings: Record<string, boolean>): Promise<{ ok: boolean; error?: string }> {
  const token = getAuthToken();
  if (!token) {
    return { ok: false, error: 'No authentication token found' };
  }

  try {
    const res = await fetch(`http://localhost:5232/privacy/settings/${encodeURIComponent(user)}`, {
      method: 'PUT',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(settings),
    });

    if (res.status === 200) {
      return { ok: true };
    } else if (res.status === 401 || res.status === 403) {
      return { ok: false, error: 'Authentication required' };
    } else {
      const data = await res.json().catch(() => ({}));
      return { ok: false, error: data.error || 'Failed to save settings' };
    }
  } catch (e) {
    return { ok: false, error: (e as Error).message };
  }
}

export default function PreferencesPage() {
  const [preferences, setPreferences] = useState<Record<string, boolean>>({});
  const [settings, setSettings] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [user, setUser] = useState<string>('');

  useEffect(() => {
    const loadSettings = async () => {
      // Check for token first, before making any requests
      const token = getAuthToken();
      if (!token) {
        setLoading(false);
        setError('Please log in to view your privacy preferences');
        return;
      }

      const currentUser = getUserFromToken(token);
      if (!currentUser) {
        setLoading(false);
        setError('Invalid authentication token - please log in again');
        return;
      }

      setUser(currentUser);

      setLoading(true);
      const result = await fetchSettings(currentUser);
      setLoading(false);

      if (result.ok && result.settings) {
        setSettings(result.settings);
        // Initialize preferences from API settings
        setPreferences(result.settings);
        console.log('Loaded settings:', result.settings);
      } else {
        setError(result.error || 'Failed to load settings');
      }
    };

    loadSettings();
  }, []);

  const handlePreferenceChange = (fieldId: string, checked: boolean) => {
    setPreferences(prev => ({
      ...prev,
      [fieldId]: checked,
    }));
    // Clear any existing save message when user makes changes
    setSaveMessage(null);
  };

  const handleSave = async () => {
    setSaving(true);
    setSaveMessage(null);
    setError(null);

    const result = await saveSettings(user, preferences);
    setSaving(false);

    if (result.ok) {
      setSaveMessage('Privacy preferences saved successfully!');
      // Update the settings display
      setSettings(preferences);
    } else {
      setError(result.error || 'Failed to save preferences');
    }
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

  if (error && !settings) {
    return (
      <div className="min-h-screen py-8">
        <div className="container mx-auto max-w-4xl px-6">
          <div className="text-center">
            <h1 className="text-4xl font-bold text-gray-900 mb-6">Privacy Preferences</h1>
            <div className="bg-red-50 border border-red-200 rounded-lg p-6">
              <p className="text-red-800 mb-4">Error: {error}</p>
              {error.includes('log in') && (
                <button
                  onClick={() => window.location.href = '/login'}
                  className="bg-blue-500 hover:bg-blue-600 text-white font-medium py-2 px-4 rounded-md transition-colors"
                >
                  Go to Login
                </button>
              )}
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

          {/* Success/Error Messages */}
          {saveMessage && (
            <div className="bg-green-50 border border-green-200 rounded-lg p-6">
              <p className="text-green-800">{saveMessage}</p>
            </div>
          )}

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-6">
              <p className="text-red-800">Error: {error}</p>
            </div>
          )}

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
            {Object.entries(fieldMapping).map(([fieldId, fieldInfo]) => (
              <div key={fieldId} className="flex items-start space-x-3">
                <Checkbox
                  id={fieldId}
                  checked={preferences[fieldId] || false}
                  onCheckedChange={(checked: boolean) => handlePreferenceChange(fieldId, checked)}
                  className="h-5 w-5 mt-1"
                />
                <div className="flex-1">
                  <label
                    htmlFor={fieldId}
                    className="text-lg text-gray-900 cursor-pointer select-none font-medium"
                  >
                    Keep {fieldInfo.label} private
                  </label>
                  <p className="text-sm text-gray-600 mt-1">
                    {fieldInfo.description}
                  </p>
                </div>
              </div>
            ))}
          </div>

          {/* Save Button */}
          <div className="pt-6">
            <button
              className="bg-blue-500 hover:bg-blue-600 disabled:bg-blue-300 disabled:cursor-not-allowed text-white font-medium py-2 px-6 rounded-md transition-colors"
              onClick={handleSave}
              disabled={saving}
            >
              {saving ? 'Saving...' : 'Save Privacy Preferences'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
