import { LoginForm } from '~/components/login-form';
import { meta, handle } from './login-meta';

export { meta, handle };

export default function LoginPage() {
  return (
    <div className='py-30'>
      <div className='container mx-auto max-w-8xl px-6'>
        <div className='flex justify-center'>
          <div className='w-full max-w-2xl shadow-2xl rounded-2xl p-32'>
            <LoginForm />
          </div>
        </div>
      </div>
    </div>
  );
}
