import { useState, useEffect } from 'react';
import { toast } from 'sonner';
import { isAuthenticated, authFetch } from '~/lib/auth';
import { meta, handle } from './subject-data-preferences-meta';

export { meta, handle };

// Mapping between API field names and user-friendly labels
const fieldMapping = {
  disallow_photo: {
    label: 'Photo',
    description: 'Profile pictures and contact photos',
  },
  disallow_gender: {
    label: 'Gender/Pronoun',
    description: 'Gender identity and preferred pronouns',
  },
  disallow_birthday: {
    label: 'Birthday',
    description: 'Date of birth and age information',
  },
  disallow_address: {
    label: 'Address',
    description: 'Home, work, and mailing addresses',
  },
  disallow_company: {
    label: 'Company',
    description: 'Employer and organization information',
  },
  disallow_title: {
    label: 'Job Title',
    description: 'Professional titles and positions',
  },
};

export default function PreferencesPage() {
  const [preferences, setPreferences] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [syncing, setSyncing] = useState(false);

  // Client-side authentication check
  useEffect(() => {
    if (typeof window !== 'undefined' && !isAuthenticated()) {
      window.location.href = '/login';
    }
  }, []);

  // Load preferences from backend
  useEffect(() => {
    const loadPreferences = async () => {
      try {
        const response = await authFetch('/api/user/preferences');
        if (response.ok) {
          const data = await response.json();
          setPreferences(data.preferences);
        } else {
          toast.error('Failed to load preferences', {
            description: 'Unable to load your current privacy settings. Please refresh the page.',
          });
        }
      } catch {
        toast.error('Failed to load preferences', {
          description: 'Network error. Please check your connection and refresh the page.',
        });
      } finally {
        setLoading(false);
      }
    };

    if (isAuthenticated()) {
      loadPreferences();
    }
  }, []);

  const handlePreferenceChange = async (fieldId: string, checked: boolean) => {
    const newPreferences = {
      ...preferences,
      [fieldId]: checked,
    };

    setPreferences(newPreferences);
    setSaving(true);

    try {
      const response = await authFetch('/api/user/preferences', {
        method: 'PUT',
        body: JSON.stringify({ preferences: newPreferences }),
      });

      if (response.ok) {
        toast.success('Preferences saved successfully!', {
          description: `${fieldMapping[fieldId as keyof typeof fieldMapping].label} privacy setting updated`,
        });
      } else {
        toast.error('Failed to save preferences', {
          description: 'Please try again. If the problem persists, contact support.',
        });
        // Revert the change on error
        setPreferences(prev => ({
          ...prev,
          [fieldId]: !checked,
        }));
      }
    } catch {
      toast.error('Failed to save preferences', {
        description: 'Network error. Please check your connection and try again.',
      });
      // Revert the change on error
      setPreferences(prev => ({
        ...prev,
        [fieldId]: !checked,
      }));
    } finally {
      setSaving(false);
    }
  };

  const handleSyncContactProvider = async () => {
    setSyncing(true);

    try {
      const response = await authFetch('/api/user/preferences', {
        method: 'PUT',
        body: JSON.stringify({ action: 'sync' }),
      });

      if (response.ok) {
        toast.success('Reprocessing triggered!', {
          description: 'Your data will be reprocessed according to your privacy preferences.',
        });
      } else {
        toast.error('Failed to synchronize', {
          description: 'Please try again. If the problem persists, contact support.',
        });
      }
    } catch {
      toast.error('Failed to synchronize', {
        description: 'Network error. Please check your connection and try again.',
      });
    } finally {
      setSyncing(false);
    }
  };

  if (loading) {
    return (
      <div className="py-30">
        <div className="container mx-auto max-w-8xl px-6">
          <div className="flex items-center justify-center">
            <div className="text-gray-600">Loading preferences...</div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="py-30">
      <div className="container mx-auto max-w-8xl px-6">
        <div className="space-y-8">
          {/* Header */}
          <div>
            <h1 className="text-5xl font-medium text-gray-900 mb-6">Subject Data Preferences</h1>
            <p className="text-gray-600 text-lg leading-relaxed mb-2 max-w-4xl">
              Control how your personal information is handled in the contact management system.
              Select which contact fields you want to keep private and prevent from being synced.
            </p>
          </div>

          {/* Reprocess Contacts Action */}
          <div className="bg-gray-100 p-6 rounded-2xl mb-6">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-medium text-gray-900 mb-2">
                  Apply Preferences to Contacts
                </h3>
                <p className="text-sm text-gray-600">
                  Trigger a reprocessing of contact cards so changes take effect.
                </p>
              </div>
              <button
                onClick={handleSyncContactProvider}
                disabled={syncing || saving}
                className="px-6 py-3 rounded-lg font-medium text-sm transition-colors bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {syncing ? 'Reprocessing...' : 'Reprocess Contacts'}
              </button>
            </div>
          </div>

          <div className="text-gray-700 text-base leading-relaxed">
            <p>
              When someone creates a contact card with your information, the following fields will{' '}
              <span className="font-medium">not</span> be included if you&apos;ve marked them as
              private:
            </p>
          </div>

          {/* Preferences Form */}
          <div className="space-y-6">
            {Object.entries(fieldMapping).map(([fieldId, fieldInfo]) => (
              <div key={fieldId} className="flex items-start space-x-3">
                <input
                  type="checkbox"
                  checked={preferences[fieldId] || false}
                  onChange={e => handlePreferenceChange(fieldId, e.target.checked)}
                  className="h-5 w-5 mt-1 rounded border-gray-300 text-blue-600 focus:ring-blue-500 disabled:opacity-50"
                  disabled={saving}
                />
                <div className="flex-1">
                  <label className="text-lg text-gray-900 cursor-pointer select-none font-medium">
                    Keep {fieldInfo.label} private
                  </label>
                  <p className="text-sm text-gray-600 mt-1">{fieldInfo.description}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
