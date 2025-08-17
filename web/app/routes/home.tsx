import { MoveUpRightIcon } from 'lucide-react';
import { meta, handle } from './home-meta';

export { meta, handle };

export default function Home() {
  return (
    <div className='py-30'>
      <div className='container mx-auto max-w-8xl px-6'>
        <div className='space-y-8'>
          <div>
            <h1 className='text-5xl font-medium text-gray-900 mb-6'>
              Take control of your privacy
            </h1>
            <p className='text-gray-400 text-lg leading-relaxed mb-6 max-w-4xl'>
              Define your Subject Data Preferences for the contact management
              system without the need to create an account. Set your data
              handling preferences to control how your information is processed.
            </p>
          </div>

          <div className='grid md:grid-cols-2 gap-6'>
            <div className='bg-gray-100 p-6 rounded-2xl'>
              <h2 className='text-xl font-medium text-gray-900 mb-3'>
                Subject Data Preferences
              </h2>
              <p className='text-gray-600 mb-4'>
                Declare how you want your personal information to be handled
                when stored in the contact management system with a one-time
                passcode.
              </p>
              <a
                href='/subject-data-preferences'
                className='inline-flex items-center text-blue-600 hover:text-blue-700 font-normal'
              >
                Set Your Subject Data Preferences{' '}
                <MoveUpRightIcon className='w-4 h-4 ml-2' />
              </a>
            </div>

            <div className='bg-gray-100 p-6 rounded-2xl'>
              <h2 className='text-xl font-medium text-gray-900 mb-3'>
                Subject Data Access
              </h2>
              <p className='text-gray-600 mb-4'>
                See how your data is used in the contact management system and
                how other users are using it. Make informed decisions about your
                privacy and data usage.
              </p>
              <a
                href='/subject-data-access'
                className='inline-flex items-center text-blue-600 hover:text-blue-700 font-normal'
              >
                View Subject Subject Data Access{' '}
                <MoveUpRightIcon className='w-4 h-4 ml-2' />
              </a>
            </div>
          </div>

          <div className='bg-blue-50 p-6 rounded-2xl'>
            <h3 className='text-xl font-medium text-gray-900 mb-3'>
              No accounts needed, just a one-time passcode
            </h3>
            <p className='text-gray-600 mb-4'>
              Simply set your Subject Data Preferences and have them applied to
              the contact management system. Your preferences are yours to
              control, without compromising your privacy.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
