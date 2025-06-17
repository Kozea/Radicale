import { Phone, Mail, Users } from 'lucide-react';
import type { Route } from './+types/data-access';

export function meta(_: Route.MetaArgs) {
  return [
    { title: 'Data Access' },
    { name: 'description', content: 'View how your personal information is used in the contact management system. See what data others have stored about you and make informed privacy decisions.' },
    { name: 'keywords', content: 'data access, personal information, contact data, privacy transparency, data usage, contact management privacy' },
    { property: 'og:title', content: 'Data Access' },
    { property: 'og:description', content: 'Transparent view of your personal information in contact management systems.' },
    { property: 'og:type', content: 'website' },
  ];
}

export const handle = {
  subtitle: 'Data Access',
};

interface ContactData {
  from: string;
  company: string;
  name: string;
  nickname?: string;
  jobTitle?: string;
  mobile?: string;
  email?: string;
  spouse?: string;
}

const contactsData: ContactData[] = [
  {
    from: 'alice@icloud.com',
    company: 'ACME Corporation',
    name: 'John Doe',
    jobTitle: 'Software Engineer',
    nickname: 'Johnny',
    mobile: '+1 (234) 567-890',
    email: 'john.doe@mail.com',
    spouse: 'Jane Doe',
  },
  {
    from: 'sketchy.steve@email.com',
    company: 'Sleazy Sales & Scams LLC',
    name: 'John Doe',
    jobTitle: 'Professional Time Waster',
    nickname: 'Gym Creep',
    mobile: '+1 (234) 567-890',
    email: 'john.doe@mail.com',
    spouse: 'His Imaginary Girlfriend',
  },
];

function ContactCard({ contact }: { contact: ContactData }) {
  return (
    <div className="border-2 border-gray-200 rounded-xl bg-white overflow-hidden">
      {/* From Section */}
      <div className="px-6 py-3 bg-gray-50 border-b border-gray-200">
        <div className="text-sm text-gray-600 font-medium">From: {contact.from}</div>
      </div>
      
      {/* Header Info */}
      <div className="p-6 mb-6">
        <div className="text-sm text-gray-500 mb-3">{contact.company}</div>
        <h3 className="text-2xl font-semibold text-gray-900">{contact.name}</h3>
        {contact.jobTitle && <div className="text-lg text-gray-600 mt-1">{contact.jobTitle}</div>}
        {contact.nickname && <div className="text-lg text-gray-600 mt-1">"{contact.nickname}"</div>}
      </div>

      {/* Contact Details */}
      <div className="px-6 pb-6 space-y-4">
        {contact.mobile && (
          <div className="flex items-center gap-3">
            <Phone className="size-5 text-gray-400" />
            <div>
              <div className="text-sm text-gray-500">Mobile</div>
              <div className="font-medium text-gray-900">{contact.mobile}</div>
            </div>
          </div>
        )}

        {contact.email && (
          <div className="flex items-center gap-3">
            <Mail className="size-5 text-gray-400" />
            <div>
              <div className="text-sm text-gray-500">Email</div>
              <div className="font-medium text-gray-900">{contact.email}</div>
            </div>
          </div>
        )}

        {contact.spouse && (
          <div className="flex items-center gap-3">
            <Users className="size-5 text-gray-400" />
            <div>
              <div className="text-sm text-gray-500">Spouse</div>
              <div className="font-medium text-gray-900">{contact.spouse}</div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function DataAccessPage() {
  return (
    <div className="min-h-screen py-8">
      <div className="container mx-auto max-w-4xl px-6">
        <div className="space-y-8">
          {/* Header */}
          <div>
            <h1 className="text-4xl font-bold text-gray-900 mb-6">Your Data Access</h1>
            <p className="text-gray-600 text-lg leading-relaxed mb-6">
              See how your personal information is used in the contact management system and how other users are storing your data.
              This transparency helps you make informed decisions about your privacy preferences.
            </p>
          </div>

          {/* Info Section */}
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
            <h3 className="text-lg font-semibold text-blue-900 mb-2">Data Transparency</h3>
            <p className="text-blue-800">
              Below is all the contact information associated with your details in the contact management system. 
              This shows you exactly what data is being stored and by whom, giving you full visibility into your digital footprint.
            </p>
          </div>

          {/* Contact Cards */}
          <div className="space-y-6">
            <h2 className="text-2xl font-semibold text-gray-900">Contact Records</h2>
            {contactsData.map((contact, index) => (
              <ContactCard key={index} contact={contact} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
