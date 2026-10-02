import { useState, type FormEvent } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import { AlertCircle, CheckCircle2, KeyRound, Loader2 } from 'lucide-react';
import { authApi } from '../api/auth';
import { AuthState } from '../components/auth/AuthState';
import { authLinkClass } from '../components/auth/authStyles';
import { PublicPageShell } from '../components/layout/PublicPageShell';
import { Alert, Button, Input, Label } from '../components/ui';
import type { ApiError } from '../types';

const MIN_PASSWORD_LENGTH = 8;

export const ResetPassword = () => {
  const [params] = useSearchParams();
  const token = params.get('token') ?? '';

  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [localError, setLocalError] = useState<string | null>(null);
  const reset = useMutation({ mutationFn: () => authApi.resetPassword(token, next) });

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    setLocalError(null);
    if (next.length < MIN_PASSWORD_LENGTH) {
      setLocalError(`Password must be at least ${MIN_PASSWORD_LENGTH} characters.`);
      return;
    }
    if (next !== confirm) {
      setLocalError('Passwords do not match.');
      return;
    }
    reset.mutate();
  };

  const backToLogin = <Link to="/login" className={authLinkClass}>Back to sign in</Link>;
  const serverError = reset.error as ApiError | null;
  const linkInvalid = !token || serverError?.details?.detail?.reason === 'invalid_or_expired_token';

  if (reset.isSuccess) {
    return (
      <PublicPageShell footer={null}>
        <AuthState
          tone="success"
          icon={<CheckCircle2 size={20} />}
          title="Password updated"
          action={<Link to="/login" className={authLinkClass}>Sign in</Link>}
        >
          You&apos;ve been signed out everywhere. Sign in with your new password.
        </AuthState>
      </PublicPageShell>
    );
  }

  if (linkInvalid) {
    return (
      <PublicPageShell footer={backToLogin}>
        <AuthState
          tone="danger"
          icon={<AlertCircle size={20} />}
          title="This link isn't valid"
          action={<Link to="/forgot-password" className={authLinkClass}>Request a new link</Link>}
        >
          Reset links expire after 60 minutes and can only be used once.
        </AuthState>
      </PublicPageShell>
    );
  }

  const error = localError ?? (serverError ? serverError.message || 'Could not reset your password. Please try again.' : null);

  return (
    <PublicPageShell footer={backToLogin}>
      <div className="flex flex-col items-center gap-2 mb-6 text-center">
        <KeyRound className="w-8 h-8 text-[var(--color-primary-600)]" />
        <h1 className="text-lg font-semibold text-[var(--text-primary)]">Choose a new password</h1>
      </div>

      {error && (
        <Alert variant="danger" className="mb-4">{error}</Alert>
      )}

      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <fieldset disabled={reset.isPending} className="flex flex-col gap-4">
          <div>
            <Label htmlFor="reset-new">New password</Label>
            <Input id="reset-new" type="password" required autoComplete="new-password" className="mt-1.5"
              value={next} onChange={(e) => setNext(e.target.value)} />
            <p className="text-xs text-[var(--text-tertiary)] mt-1">At least {MIN_PASSWORD_LENGTH} characters.</p>
          </div>
          <div>
            <Label htmlFor="reset-confirm">Confirm new password</Label>
            <Input id="reset-confirm" type="password" required autoComplete="new-password" className="mt-1.5"
              value={confirm} onChange={(e) => setConfirm(e.target.value)} />
          </div>
        </fieldset>
        <Button type="submit" disabled={reset.isPending} className="w-full justify-center mt-2">
          {reset.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Save new password'}
        </Button>
      </form>
    </PublicPageShell>
  );
};
