import { useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import { Loader2, MailCheck } from 'lucide-react';
import { authApi } from '../api/auth';
import { AuthState } from '../components/auth/AuthState';
import { authLinkClass } from '../components/auth/authStyles';
import { PublicPageShell } from '../components/layout/PublicPageShell';
import { Alert, Button, Input, Label } from '../components/ui';
import type { ApiError } from '../types';

const MIN_PASSWORD_LENGTH = 8;

const errorMessage = (error: ApiError | null): string | null => {
  if (!error) return null;
  const reason = error.details?.detail?.reason;
  if (error.status === 429 || reason === 'rate_limited') {
    return 'Too many sign-up attempts from your connection. Please try again later.';
  }
  if (error.status === 503 || reason === 'temporarily_unavailable') {
    return 'Sign-up is temporarily unavailable. Please try again in a few minutes.';
  }
  // 422s carry a specific {reason, message} from the server.
  return error.message || 'Something went wrong. Please try again.';
};

export const Signup = () => {
  const [companyName, setCompanyName] = useState('');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [localError, setLocalError] = useState<string | null>(null);

  const signup = useMutation({
    mutationFn: () => authApi.signup({ company_name: companyName, name, email, password }),
  });

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    setLocalError(null);
    if (password.length < MIN_PASSWORD_LENGTH) {
      setLocalError(`Password must be at least ${MIN_PASSWORD_LENGTH} characters.`);
      return;
    }
    if (password !== confirm) {
      setLocalError('Passwords do not match.');
      return;
    }
    signup.mutate();
  };

  if (signup.isSuccess) {
    // Deliberately the same message whether or not the email already had an
    // account - the server never reveals which.
    return (
      <PublicPageShell footer={null}>
        <AuthState
          tone="success"
          icon={<MailCheck size={20} />}
          title="Check your inbox"
          action={<Link to="/login" className={authLinkClass}>Go to sign in</Link>}
        >
          <p>
            If <strong className="text-[var(--text-primary)]">{email.trim()}</strong> can be used to create an account, we&apos;ve sent a link to confirm
            it. Open the link to activate your company account, then sign in.
          </p>
          <p className="text-caption mt-2">
            Didn&apos;t get it? You can request a new link from the sign-in page after trying to log in.
          </p>
        </AuthState>
      </PublicPageShell>
    );
  }

  const error = localError ?? errorMessage(signup.error as ApiError | null);
  const submitting = signup.isPending;

  return (
    <PublicPageShell footer={<>Already have an account? <Link to="/login" className={authLinkClass}>Sign in</Link></>}>
      <div className="flex flex-col gap-1 mb-6 text-center">
        <h1 className="text-lg font-semibold text-[var(--text-primary)]">Create a company account</h1>
        <p className="text-sm text-[var(--text-secondary)]">
          Your company gets its own private workspace. You&apos;ll be its admin and can add teammates later.
        </p>
      </div>

      {error && (
        <Alert variant="danger" className="mb-4">{error}</Alert>
      )}

      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <fieldset disabled={submitting} className="flex flex-col gap-4">
          <div>
            <Label htmlFor="signup-company">Company name</Label>
            <Input id="signup-company" required maxLength={255} autoComplete="organization" className="mt-1.5"
              value={companyName} onChange={(e) => setCompanyName(e.target.value)} placeholder="Acme Inc." />
          </div>
          <div>
            <Label htmlFor="signup-name">Your name</Label>
            <Input id="signup-name" required maxLength={255} autoComplete="name" className="mt-1.5"
              value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div>
            <Label htmlFor="signup-email">Work email</Label>
            <Input id="signup-email" type="email" required autoComplete="email" className="mt-1.5"
              value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@company.com" />
          </div>
          <div>
            <Label htmlFor="signup-password">Password</Label>
            <Input id="signup-password" type="password" required autoComplete="new-password" className="mt-1.5"
              value={password} onChange={(e) => setPassword(e.target.value)} />
            <p className="text-xs text-[var(--text-tertiary)] mt-1">At least {MIN_PASSWORD_LENGTH} characters.</p>
          </div>
          <div>
            <Label htmlFor="signup-confirm">Confirm password</Label>
            <Input id="signup-confirm" type="password" required autoComplete="new-password" className="mt-1.5"
              value={confirm} onChange={(e) => setConfirm(e.target.value)} />
          </div>
        </fieldset>
        <Button type="submit" disabled={submitting} className="w-full justify-center mt-2">
          {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Create account'}
        </Button>
      </form>
    </PublicPageShell>
  );
};
