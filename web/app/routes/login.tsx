import { LoginForm } from '~/components/login-form';

export const handle = {
  subtitle: 'Authentication',
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
