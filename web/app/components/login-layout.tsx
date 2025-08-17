import { Outlet } from 'react-router';

export default function LoginLayout() {
  return (
    <div className='min-h-screen bg-background flex flex-col'>
      {/* Header */}
      <header className='bg-accent w-full'>
        <div className='px-4 py-1'>
          <nav className='flex items-center justify-between'>
            <div className='flex items-center space-x-1'>
              <img
                src='/logo.svg'
                alt='Logo'
                style={{ width: '82px', height: '31px', marginTop: '-1px' }}
              />
            </div>
          </nav>
        </div>
      </header>

      {/* Main content */}
      <main className='flex-1'>
        <Outlet />
      </main>

      {/* Footer */}
      <footer className='bg-gray-100 py-4 px-4 mt-auto'>
        <div className='container mx-auto max-w-8xl px-6'>
          <div className='flex flex-col sm:flex-row justify-between items-center space-y-2 sm:space-y-0'>
            <div className='flex flex-wrap justify-center sm:justify-start space-x-6 text-sm'>
              <span className='text-gray-400'>Privacy Policy</span>
              <span className='text-gray-400'>Terms & Conditions</span>
            </div>
            <div className='text-gray-400 text-sm'>
              Copyright © 2025 Apple Inc. All rights reserved.
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
