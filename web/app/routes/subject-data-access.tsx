import { Phone, Mail, Users, UserIcon } from 'lucide-react';
import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { isAuthenticated, authFetch } from '~/lib/auth';
import { meta, handle } from './subject-data-access-meta';

export { meta, handle };

type CardMatch = {
  vcard_uid: string;
  collection_path: string;
  matching_fields: Record<string, any>;
  fields: Record<string, any>;
};
type CardsResponse = { matches: CardMatch[] };

function ContactCard({ contact }: { contact: CardMatch }) {
  return (
    <div className="bg-white rounded-2xl overflow-hidden border border-gray-300">
      {/* From Section */}
      <div className="px-6 py-2 bg-blue-500">
        <div className="text-sm text-white font-medium">Collection: {contact.collection_path}</div>
      </div>

      {/* Header Info */}
      <div className="p-6">
        <div className="flex items-start gap-6">
          {/* Large Contact Icon */}
          <div className="flex items-center justify-center w-16 h-16 bg-gray-300 rounded-full flex-shrink-0 mt-4">
            <UserIcon className="size-8 text-white" />
          </div>

          {/* Contact Details */}
          <div className="flex-1">
            <div className="text-sm text-gray-400 mb-2 font-medium tracking-wide">
              {contact.fields.org || ''}
            </div>
            <h3 className="text-2xl font-semibold text-gray-900 mb-1">
              {contact.fields.fn || contact.fields.n || 'Unknown'}
            </h3>
            {contact.fields.title && (
              <div className="text-base text-gray-600 font-medium">{contact.fields.title}</div>
            )}
            {contact.fields.nickname && (
              <div className="text-base text-gray-600 font-medium mt-1">
                &quot;{contact.fields.nickname}&quot;
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Contact Details */}
      <div className="px-6 pb-6 space-y-4">
        {contact.fields.tel && (
          <div className="flex items-center gap-4">
            <div className="flex items-center justify-center w-10 h-10 bg-blue-500 rounded-full ml-4 mr-4">
              <Phone className="size-5 text-white" />
            </div>
            <div className="flex-1">
              <div className="text-sm text-gray-500 font-medium">Mobile</div>
              <div className="text-base text-gray-900 font-medium">
                {Array.isArray(contact.fields.tel)
                  ? contact.fields.tel.join(', ')
                  : contact.fields.tel}
              </div>
            </div>
          </div>
        )}

        {contact.fields.email && (
          <div className="flex items-center gap-4">
            <div className="flex items-center justify-center w-10 h-10 bg-blue-500 rounded-full ml-4 mr-4">
              <Mail className="size-5 text-white" />
            </div>
            <div className="flex-1">
              <div className="text-sm text-gray-500 font-medium">Email</div>
              <div className="text-base text-gray-900 font-medium">
                {Array.isArray(contact.fields.email)
                  ? contact.fields.email.join(', ')
                  : contact.fields.email}
              </div>
            </div>
          </div>
        )}

        {contact.fields.related && (
          <div className="flex items-center gap-4">
            <div className="flex items-center justify-center w-10 h-10 bg-blue-500 rounded-full ml-4 mr-4">
              <Users className="size-5 text-white" />
            </div>
            <div className="flex-1">
              <div className="text-sm text-gray-500 font-medium">Spouse</div>
              <div className="text-base text-gray-900 font-medium">
                {Array.isArray(contact.fields.related)
                  ? contact.fields.related.join(', ')
                  : contact.fields.related}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function DataAccessPage() {
  const [syncing, setSyncing] = useState(false);
  const [cards, setCards] = useState<CardMatch[]>([]);
  const [loading, setLoading] = useState(true);

  // Client-side authentication check
  if (typeof window !== 'undefined' && !isAuthenticated()) {
    window.location.href = '/login';
  }

  const handleSyncContactProvider = async () => {
    setSyncing(true);

    try {
      const response = await authFetch('/api/user/preferences', {
        method: 'PUT',
        body: JSON.stringify({ action: 'sync' }),
      });

      if (response.ok) {
        toast.success('Contact provider synchronized!', {
          description: 'Your privacy preferences have been synchronized with the contact provider.',
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

  useEffect(() => {
    const loadCards = async () => {
      try {
        const resp = await authFetch('/api/user/cards');
        if (!resp.ok) throw new Error('Failed to load cards');
        const data: CardsResponse = await resp.json();
        setCards(data.matches || []);
      } catch (e) {
        toast.error('Failed to load data', { description: 'Unable to load contact records.' });
      } finally {
        setLoading(false);
      }
    };
    if (isAuthenticated()) loadCards();
  }, []);

  return (
    <div className="py-30">
      <div className="container mx-auto max-w-8xl px-6">
        <div className="space-y-8">
          {/* Header */}
          <div>
            <h1 className="text-5xl font-medium text-gray-900 mb-6">Data about you</h1>
            <p className="text-gray-400 text-lg leading-relaxed mb-6 max-w-4xl">
              See how your personal information is used in the contact provider system and how other
              users are storing your data. This transparency helps you make informed decisions about
              your Subject Data Preferences.
            </p>
          </div>

          {/* Contact Provider Synchronization */}
          <div className="bg-gray-100 p-6 rounded-2xl mb-6">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-medium text-gray-900 mb-2">Contact Provider Status</h3>
                <p className="text-sm text-gray-600">
                  Synchronize with the contact provider to refresh the data shown on this page and
                  ensure you see the most current information about how your data is being used.
                </p>
              </div>
              <button
                onClick={handleSyncContactProvider}
                disabled={syncing}
                className="px-6 py-3 rounded-lg font-medium text-sm transition-colors bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {syncing ? 'Synchronizing...' : 'Synchronize Contact Provider'}
              </button>
            </div>
          </div>

          {/* Contact Cards */}
          <div className="space-y-6">
            <h2 className="text-2xl font-medium text-gray-900">Contact Records</h2>
            {loading ? (
              <div className="text-gray-600">Loading cards...</div>
            ) : cards.length === 0 ? (
              <div className="text-gray-600">No contact records found.</div>
            ) : (
              cards.map(contact => (
                <ContactCard
                  key={`${contact.collection_path}-${contact.vcard_uid}`}
                  contact={contact}
                />
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
