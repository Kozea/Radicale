import { useState } from 'react';
import { Checkbox } from '~/components/ui/checkbox';

export const handle = {
  subtitle: 'Subject Data Preferences',
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

export default function PreferencesPage() {
  const [preferences, setPreferences] = useState<Record<string, boolean>>(
    Object.fromEntries(preferenceFields.map(field => [field.id, field.defaultChecked]))
  );

  const handlePreferenceChange = (fieldId: string, checked: boolean) => {
    setPreferences(prev => ({
      ...prev,
      [fieldId]: checked,
    }));
  };

  return (
    <div className="min-h-screen py-8">
      <div className="container mx-auto max-w-4xl px-6">
        <div className="space-y-8">
          {/* Header */}
          <div>
            <h1 className="text-4xl font-bold text-gray-900 mb-6">Your preferences</h1>
            <p className="text-gray-600 text-lg leading-relaxed mb-2">
              Please select the contact card fields that you do{' '}
              <span className="font-semibold">not</span> want to be synced on iCloud.
            </p>
          </div>

          {/* Description */}
          <div className="text-gray-700 text-base leading-relaxed">
            <p>
              Whenever an iCloud user creates a contact card that contains phone number +1 (234)
              567-890 , the following fields will <span className="font-semibold">not</span> be
              synced on iCloud servers.
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
                  {field.label}
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
              Save Preferences
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
