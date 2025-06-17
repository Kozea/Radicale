import { useState } from 'react';
import type { ComponentProps, FormEvent } from 'react';
import { Contact } from 'lucide-react';

import { cn } from '~/lib/utils';
import { Button } from '~/components/ui/button';
import { Input } from '~/components/ui/input';

// Helper to request OTP
async function requestOtp(identifier: string): Promise<{ ok: boolean; error?: string }> {
  const credentials = btoa(`${identifier}:`);
  try {
    const res = await fetch(`/privacy/settings/${encodeURIComponent(identifier)}`, {
      method: 'GET',
      headers: {
        'Authorization': `Basic ${credentials}`,
        'Content-Type': 'application/json',
      },
    });
    if (res.status === 401) {
      // OTP sent, proceed to code entry
      return { ok: true };
    } else if (res.status === 200) {
      // Already authenticated (should not happen in OTP flow)
      return { ok: false, error: 'Already authenticated.' };
    } else {
      const data = await res.json().catch(() => ({}));
      return { ok: false, error: data.error || 'Unexpected error.' };
    }
  } catch (e) {
    return { ok: false, error: (e as Error).message };
  }
}

export function LoginForm({ className, ...props }: ComponentProps<'div'>) {
  const [step, setStep] = useState<'identifier' | 'code'>('identifier');
  const [identifier, setIdentifier] = useState('');
  const [code, setCode] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleIdentifierSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (identifier.trim()) {
      setLoading(true);
      const result = await requestOtp(identifier.trim());
      setLoading(false);
      if (result.ok) {
        setStep('code');
      } else {
        setError(result.error || 'Failed to send OTP.');
      }
    }
  };

  const handleCodeSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (code.trim()) {
      // Here you would verify the OTP code
      // console.log('Verifying code:', code, 'for identifier:', identifier);
    }
  };

  const handleBack = () => {
    setStep('identifier');
    setCode('');
  };

  return (
    <div className={cn('flex flex-col gap-8', className)} {...props}>
      {/* Apple-style dotted circle */}
      <div className="flex justify-center mt-8 mb-8">
        <div className="relative w-32 h-32">
          {/* Dotted circle pattern */}
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="w-32 h-32 rounded-full border-2 border-dashed border-orange-300 opacity-60"></div>
            <div className="absolute w-24 h-24 rounded-full border-2 border-dashed border-orange-300 opacity-40"></div>
            <div className="absolute w-16 h-16 rounded-full border-2 border-dashed border-orange-300 opacity-30"></div>
          </div>

          {/* Center logo placeholder */}
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="w-12 h-12 rounded-full flex items-center justify-center">
              <Contact className="w-7 h-7" />
            </div>
          </div>
        </div>
      </div>

      <div className="text-center mb-8">
        <h2 className="text-3xl font-semibold text-gray-900 mb-2">Sign in with your identifier</h2>
        <p className="text-gray-600">
        Enter your email or phone number to receive a one-time passcode. No account creation required.
        </p>
      </div>

      {step === 'identifier' ? (
        <form onSubmit={handleIdentifierSubmit} className="space-y-4">
          <div className="relative">
            <Input
              type="text"
              value={identifier}
              onChange={e => setIdentifier(e.target.value)}
              placeholder="Email or Phone Number"
              className="h-14 text-lg px-4 rounded-lg border-2 border-gray-200"
              required
              disabled={loading}
            />
          </div>
          {error && <div className="text-red-600 text-sm">{error}</div>}
          <Button
            type="submit"
            className="w-full h-12 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg"
            disabled={loading}
          >
            {loading ? 'Sending...' : 'Send Code'}
          </Button>
        </form>
      ) : (
        <form onSubmit={handleCodeSubmit} className="space-y-4">
          <div className="text-center mb-4">
            <p className="text-gray-600">Enter the verification code sent to:</p>
            <p className="font-medium text-gray-900">{identifier}</p>
          </div>
          <div className="relative">
            <Input
              type="text"
              value={identifier}
              className="h-14 text-lg px-4 rounded-lg border-2 border-gray-200 bg-gray-50"
              disabled
            />
          </div>
          <div className="relative">
            <Input
              type="text"
              value={code}
              onChange={e => setCode(e.target.value)}
              placeholder="Code"
              className="h-14 text-lg px-4 rounded-lg border-2 border-gray-200"
              required
              autoFocus
            />
          </div>
          <div className="flex gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={handleBack}
              className="flex-1 h-12 rounded-lg"
            >
              Back
            </Button>
            <Button
              type="submit"
              className="flex-1 h-12 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg"
            >
              Verify Code
            </Button>
          </div>
        </form>
      )}
    </div>
  );
}
