import {
  EllipsisIcon,
  HomeIcon,
  LogOutIcon,
  ShieldCheckIcon,
  DatabaseIcon,
} from 'lucide-react';
import { Outlet, useMatches, useNavigate } from 'react-router';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '~/components/ui/dropdown-menu';
import { Button } from '~/components/ui/button';
import { ProtectedRoute } from './protected-route';
import { isAuthenticated, clearAuthToken } from '~/lib/auth';

interface RouteHandle {
  subtitle?: string;
}

const navigationItems = [
  { to: '/', label: 'Subject Dashboard', icon: <HomeIcon />, protected: true },
  {
    to: '/subject-data-preferences',
    label: 'Subject Data Preferences',
    icon: <ShieldCheckIcon />,
    protected: true,
  },
  {
    to: '/subject-data-access',
    label: 'Subject Data Access',
    icon: <DatabaseIcon />,
    protected: true,
  },
];

export default function Layout() {
  const matches = useMatches();
  const navigate = useNavigate();
  const currentMatch = matches[matches.length - 1];
  const subtitle = (currentMatch?.handle as RouteHandle)?.subtitle || '';
  const authenticated = isAuthenticated();

  const handleLogout = () => {
    clearAuthToken();
    navigate('/login');
  };

  // Filter navigation items based on authentication status
  const visibleNavigationItems = navigationItems.filter(item => {
    if (authenticated) {
      return true; // Show all items when authenticated
    } else {
      return !item.protected; // Only show non-protected items when not authenticated
    }
  });

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
              {subtitle && (
                <span className='text-blue-600 text-xl font-medium hidden sm:block'>
                  {subtitle}
                </span>
              )}
            </div>

            {/* Dropdown Navigation */}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant='ghost'
                  size='icon'
                  className='flex items-center space-x-1'
                >
                  <EllipsisIcon className='size-6' />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align='end' className='w-48'>
                {visibleNavigationItems.map(item => (
                  <DropdownMenuItem key={item.to} asChild>
                    <Button
                      variant='ghost'
                      className='w-full justify-start text-left border-none focus:border-none focus-visible:border-none hover:border-none font-normal'
                      onClick={() => navigate(item.to)}
                    >
                      <span className='text-blue-600 mr-2'>{item.icon}</span>
                      {item.label}
                    </Button>
                  </DropdownMenuItem>
                ))}
                {authenticated && (
                  <DropdownMenuItem asChild>
                    <Button
                      variant='ghost'
                      className='w-full justify-start text-left border-none focus:border-none focus-visible:border-none hover:border-none font-normal'
                      onClick={handleLogout}
                    >
                      <span className='text-red-600 mr-2'>
                        <LogOutIcon />
                      </span>
                      Logout
                    </Button>
                  </DropdownMenuItem>
                )}
              </DropdownMenuContent>
            </DropdownMenu>
          </nav>
        </div>
      </header>

      {/* Main content */}
      <main className='flex-1'>
        <ProtectedRoute>
          <Outlet />
        </ProtectedRoute>
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
