import { Phone, Mail, Users } from 'lucide-react';

export const handle = {
  subtitle: 'Subject Data Access',
};

interface ContactData {
  from: string;
  company: string;
  name: string;
  nickname?: string;
  mobile?: string;
  email?: string;
  spouse?: string;
}

const contactsData: ContactData[] = [
  {
    from: 'alice@icloud.com',
    company: 'ACME Corporation',
    name: 'John Doe',
    nickname: 'Johnny',
    mobile: '+1 (234) 567-890',
    email: 'john.doe@mail.com',
    spouse: 'Jane Doe',
  },
  {
    from: 'bob@icloud.com',
    company: 'ACME',
    name: 'John Doe',
    nickname: 'Big Joe',
  },
];

function ContactCard({ contact }: { contact: ContactData }) {
  return (
    <div className="border-2 border-gray-200 rounded-xl p-6 bg-white">
      {/* Header Info */}
      <div className="mb-6">
        <div className="text-sm text-gray-500 mb-1">From: {contact.from}</div>
        <div className="text-sm text-gray-500 mb-3">{contact.company}</div>
        <h3 className="text-2xl font-semibold text-gray-900">{contact.name}</h3>
        {contact.nickname && <div className="text-lg text-gray-600 mt-1">"{contact.nickname}"</div>}
      </div>

      {/* Contact Details */}
      <div className="space-y-4">
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
            <h1 className="text-4xl font-bold text-gray-900 mb-4">Data about you</h1>
            <p className="text-gray-600 text-lg leading-relaxed">
              Here is a all of the data associated with phone number +1 (234) 567-89 in the Contacts
              of iCloud users.
            </p>
          </div>

          {/* Contact Cards */}
          <div className="space-y-6">
            {contactsData.map((contact, index) => (
              <ContactCard key={index} contact={contact} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
