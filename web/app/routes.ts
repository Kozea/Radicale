import {
  type RouteConfig,
  index,
  route,
  layout,
} from '@react-router/dev/routes';

export default [
  // Public routes (no authentication required)
  layout('components/login-layout.tsx', [route('/login', 'routes/login.tsx')]),

  // Protected routes (authentication required)
  layout('components/protected-layout.tsx', [
    index('routes/home.tsx'),
    route('/subject-data-preferences', 'routes/subject-data-preferences.tsx'),
    route('/subject-data-access', 'routes/subject-data-access.tsx'),
  ]),
  // API routes for authentication
  route('/api/auth/request-otp', 'routes/api.auth.request-otp.tsx'),
  route('/api/auth/verify-otp', 'routes/api.auth.verify-otp.tsx'),
  // API routes for user preferences
  route('/api/user/preferences', 'routes/api.user.preferences.tsx'),
] satisfies RouteConfig;
