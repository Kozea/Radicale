import { Contact, Menu, X } from 'lucide-react';
import { Outlet, useMatches } from 'react-router';
import { useState } from 'react';
import { NavLink } from '~/components/ui/navigation-menu';

interface RouteHandle {
  subtitle?: string;
}

const navigationItems = [
  { to: '/', label: 'Home' },
  { to: '/preferences', label: 'Preferences' },
  { to: '/data-access', label: 'Data Access' },
  { to: '/login', label: 'Login' },
];

export default function Layout() {
  const matches = useMatches();
  const currentMatch = matches[matches.length - 1];
  const subtitle = (currentMatch?.handle as RouteHandle)?.subtitle || '';
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  const closeMobileMenu = () => setIsMobileMenuOpen(false);

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="bg-accent">
        <div className="container mx-auto px-4 py-4">
          <nav className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <h1 className="text-xl font-semibold flex items-center gap-2">
                <Contact className="size-6" />
                Contact
              </h1>
              {subtitle && (
                <span className="text-blue-600 text-lg font-medium hidden sm:block">
                  {subtitle}
                </span>
              )}
            </div>

            {/* Desktop Navigation */}
            <div className="hidden md:flex items-center space-x-1">
              {navigationItems.map((item) => (
                <NavLink key={item.to} to={item.to}>
                  {item.label}
                </NavLink>
              ))}
            </div>

            {/* Mobile Menu Button */}
            <button
              className="md:hidden p-2 rounded-md hover:bg-accent-foreground/10 transition-colors"
              onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
              aria-label="Toggle menu"
            >
              {isMobileMenuOpen ? <X className="size-6" /> : <Menu className="size-6" />}
            </button>
          </nav>

          {/* Mobile Navigation */}
          {isMobileMenuOpen && (
            <div className="md:hidden mt-4 pb-4 border-t border-accent-foreground/20">
              <div className="flex flex-col space-y-2 pt-4">
                {navigationItems.map((item) => (
                  <NavLink 
                    key={item.to} 
                    to={item.to} 
                    onClick={closeMobileMenu}
                    className="justify-start"
                  >
                    {item.label}
                  </NavLink>
                ))}
              </div>
            </div>
          )}
        </div>
      </header>

      {/* Main content */}
      <main className="flex-1">
        <div className="container mx-auto px-4 py-4">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
