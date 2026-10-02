import { useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import { KeyRound, Loader2, MailCheck } from 'lucide-react';
import { authApi } from '../api/auth';
import { AuthState } from '../components/auth/AuthState';
import { authLinkClass } from '../components/auth/authStyles';
import { PublicPageShell } from '../components/layout/PublicPageShell';
import { Alert, Button, Input, Label } from '../components/ui';
import type { ApiError } from '../types';

// The server answers the same way whether or not the address has an
// account, so the success state never confirms that it does.
export const ForgotPassword = () => {
  const [email, setEmail] = useState('');
  const request = useMutation({ mutationFn: () => authApi.forgotPassword(email) });

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    request.mutate();
  };

  const footer = <Link to="/login" className={authLinkClass}>Back to sign in</Link>;

  if (request.isSuccess) {
    return (
      <PublicPageShell footer={footer}>
        <AuthState tone="success" icon={<MailCheck size={20} />} title="Check your inbox">
          If an account exists for {email}, we&apos;ve sent a link to reset its password. The link expires in 60 minutes.
        </AuthState>
      </PublicPageShell>
    );
  }

  const error = request.error as ApiError | null;
  const errorText = !error
    ? null
    : error.status === 429
      ? 'Too many requests. Please wait a while before asking for another link.'
      : error.status === 503
        ? 'Temporarily unavailable. Please try again in a few minutes.'
        : error.message || 'Could not send a reset link. Please try again.';

  return (
    <PublicPageShell footer={footer}>
      <div className="flex flex-col items-center gap-2 mb-6 text-center">
        <KeyRound className="w-8 h-8 text-[var(--color-primary-600)]" />
        <h1 className="text-lg font-semibold text-[var(--text-primary)]">Reset your password</h1>
        <p className="text-sm text-[var(--text-secondary)]">Enter your account email and we&apos;ll send you a reset link.</p>
      </div>

      {errorText && (
        <Alert variant="danger" className="mb-4">{errorText}</Alert>
      )}

      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <div>
          <Label htmlFor="forgot-email">Email</Label>
          <Input id="forgot-email" type="email" required autoComplete="email" className="mt-1.5"
            value={email} onChange={(e) => setEmail(e.target.value)} disabled={request.isPending}
            placeholder="you@company.com" />
        </div>
        <Button type="submit" disabled={request.isPending || !email.trim()} className="w-full justify-center mt-2">
          {request.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Send reset link'}
        </Button>
      </form>
    </PublicPageShell>
  );
};
