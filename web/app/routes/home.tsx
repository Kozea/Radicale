import type { Route } from './+types/home';

export function meta(_: Route.MetaArgs) {
  return [
    { title: 'New React Router App' },
    { name: 'description', content: 'Welcome to React Router!' },
  ];
}

export const handle = {
  subtitle: 'Subject Preferences',
};

export default function Home() {
  return (
    <div className="min-h-screen py-8">
      <div className="container mx-auto max-w-4xl px-6">
        <div className="space-y-8">
          <div>
            <h1 className="text-4xl font-bold text-gray-900 mb-6">Welcome to My App</h1>
            <p className="text-gray-600 text-lg leading-relaxed mb-2">
              This is the home page of your application. You can customize this content as needed.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
