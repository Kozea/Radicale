import type { Route } from './+types/home';

export function meta(_: Route.MetaArgs) {
  return [
    { title: 'User Privacy' },
    { name: 'description', content: 'Set your privacy preferences for the contact management system without creating an account. Control how your personal information is handled.' },
    { name: 'keywords', content: 'privacy preferences, contact manager privacy, data protection, no account, anonymous privacy settings, GDPR preferences' },
    { property: 'og:title', content: 'User Privacy' },
    { property: 'og:description', content: 'Anonymous privacy preference management for contact systems.' },
    { property: 'og:type', content: 'website' },
  ];
}

export const handle = {
  subtitle: 'User Privacy',
};

export default function Home() {
  return (
    <div className="min-h-screen py-8">
      <div className="container mx-auto max-w-4xl px-6">
        <div className="space-y-8">
          <div>
            <h1 className="text-4xl font-bold text-gray-900 mb-6">User Privacy</h1>
            <p className="text-gray-600 text-lg leading-relaxed mb-6">
              Define your privacy preferences for the contact management system without the need to create an account. 
              Set your data handling preferences to control how your information is processed.
            </p>
          </div>

          <div className="grid md:grid-cols-2 gap-6">
            <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm">
              <h2 className="text-xl font-semibold text-gray-900 mb-3">Privacy Preferences</h2>
              <p className="text-gray-600 mb-4">
                Declare how you want your personal information to be handled when stored 
                in the contact management system with a one-time passcode.
              </p>
              <a 
                href="/privacy-preferences" 
                className="inline-flex items-center text-blue-600 hover:text-blue-700 font-medium"
              >
                Set Your Privacy Preferences →
              </a>
            </div>

            <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm">
              <h2 className="text-xl font-semibold text-gray-900 mb-3">Data Access</h2>
              <p className="text-gray-600 mb-4">
                See how your data is used in the contact management system and how other users are using it.
                Make informed decisions about your privacy and data usage.
              </p>
              <a 
                href="/data-access" 
                className="inline-flex items-center text-blue-600 hover:text-blue-700 font-medium"
              >
                View Your Data Access →
              </a>
            </div>
          </div>

          <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
            <h3 className="text-lg font-semibold text-blue-900 mb-2">No accounts needed, just a one-time passcode</h3>
            <p className="text-blue-800">
              Simply set your privacy preferences and have them applied to the contact management system. 
              Your preferences are yours to control, without compromising your privacy.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
