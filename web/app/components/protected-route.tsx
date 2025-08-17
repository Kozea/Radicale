import { useEffect } from 'react';
import { useNavigate } from 'react-router';
import { isAuthenticated } from '~/lib/auth';

interface ProtectedRouteProps {
  children: React.ReactNode;
}

export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const navigate = useNavigate();

  useEffect(() => {
    if (!isAuthenticated()) {
      navigate('/login');
    }
  }, [navigate]);

  // Don't render children if not authenticated
  if (!isAuthenticated()) {
    return null;
  }

  return <>{children}</>;
}
