import { useState, type FormEvent } from 'react';
import { useMutation } from '@tanstack/react-query';
import { Loader2 } from 'lucide-react';
import { authApi } from '../../api/auth';
import { Alert, Button, Input, Label } from '../ui';
import type { ApiError } from '../../types';

// Shared by the login page (unverified-account state) and the
// verify-email page (expired/invalid link). The server answers the same way
// whether or not the address has an unverified account.
export const ResendVerificationForm = ({ initialEmail = '' }: { initialEmail?: string }) => {
  const [email, setEmail] = useState(initialEmail);
  const resend = useMutation({ mutationFn: () => authApi.resendVerification(email) });

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    resend.mutate();
  };

  if (resend.isSuccess) {
    return (
      <Alert variant="success" icon={null}>
        If that address has an account waiting for confirmation, a new link is on its way.
      </Alert>
    );
  }

  const error = resend.error as ApiError | null;
  const errorText = !error
    ? null
    : error.status === 429
      ? 'Too many requests. Please wait a while before asking for another link.'
      : error.status === 503
        ? 'Temporarily unavailable. Please try again in a few minutes.'
        : error.message || 'Could not send a new link. Please try again.';

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-2">
      <Label htmlFor="resend-email">Email</Label>
      <div className="flex gap-2">
        <Input id="resend-email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
          disabled={resend.isPending} placeholder="you@company.com" />
        <Button type="submit" variant="secondary" disabled={resend.isPending || !email.trim()}>
          {resend.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Resend link'}
        </Button>
      </div>
      {errorText && <Alert variant="danger" className="mt-1">{errorText}</Alert>}
    </form>
  );
};
