import { LoginForm } from '~/components/login-form';
import type { Route } from './+types/login';

export function meta(_: Route.MetaArgs) {
  return [
    { title: 'Login' },
    { name: 'description', content: 'Access your privacy preferences with a one-time passcode. No account creation required.' },
  ];
}

export const handle = {
  subtitle: 'Login',
};

export default function LoginPage() {
  return (
    <div className="py-4">
      <div className="flex justify-center">
        <div className="w-full max-w-md">
          <LoginForm />
        </div>
      </div>
    </div>
  );
}
