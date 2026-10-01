import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import { toast } from 'sonner';
import { AlertCircle, KeyRound, Loader2 } from 'lucide-react';
import { authApi } from '../api/auth';
import { useAuth } from '../hooks/useAuth';
import { PublicPageShell } from '../components/layout/PublicPageShell';
import { Button, Input, Label } from '../components/ui';
import type { ApiError } from '../types';

const MIN_PASSWORD_LENGTH = 8;

// Rendered without the app chrome: while an admin-issued temporary password
// is still in place, every other API call is refused, so the normal layout
// (sidebar badges, header data) couldn't load anyway. Also reachable
// voluntarily from the user menu.
export const ChangePassword = () => {
  const { user, refreshMe, logout } = useAuth();
  const navigate = useNavigate();
  const forced = !!user?.must_change_password;

  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [localError, setLocalError] = useState<string | null>(null);

  const change = useMutation({
    mutationFn: () => authApi.changePassword({ current_password: current, new_password: next }),
    onSuccess: async () => {
      await refreshMe();
      toast.success('Password changed.');
      navigate('/', { replace: true });
    },
  });

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    setLocalError(null);
    if (next.length < MIN_PASSWORD_LENGTH) {
      setLocalError(`New password must be at least ${MIN_PASSWORD_LENGTH} characters.`);
      return;
    }
    if (next !== confirm) {
      setLocalError('New passwords do not match.');
      return;
    }
    change.mutate();
  };

  const serverError = change.error as ApiError | null;
  const error =
    localError ??
    (serverError
      ? serverError.details?.detail?.reason === 'wrong_current_password'
        ? 'Your current password is incorrect.'
        : serverError.message || 'Could not change your password. Please try again.'
      : null);

  return (
    <PublicPageShell
      footer={
        forced ? (
          <button type="button" onClick={() => logout()} className="text-[var(--color-primary-600)] hover:underline">
            Sign out
          </button>
        ) : (
          <Link to="/" className="text-[var(--color-primary-600)] hover:underline">Back to the app</Link>
        )
      }
    >
      <div className="flex flex-col items-center gap-2 mb-6 text-center">
        <KeyRound className="w-8 h-8 text-[var(--color-primary-600)]" />
        <h1 className="text-lg font-semibold text-[var(--text-primary)]">
          {forced ? 'Choose your own password' : 'Change password'}
        </h1>
        {forced && (
          <p className="text-sm text-[var(--text-secondary)]">
            Your account was created with a temporary password. Replace it to continue.
          </p>
        )}
      </div>

      {error && (
        <div role="alert" className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 text-red-800 px-3 py-2.5 text-sm mb-4">
          <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <fieldset disabled={change.isPending} className="flex flex-col gap-4">
          <div>
            <Label htmlFor="pw-current">{forced ? 'Temporary password' : 'Current password'}</Label>
            <Input id="pw-current" type="password" required autoComplete="current-password" className="mt-1.5"
              value={current} onChange={(e) => setCurrent(e.target.value)} />
          </div>
          <div>
            <Label htmlFor="pw-new">New password</Label>
            <Input id="pw-new" type="password" required autoComplete="new-password" className="mt-1.5"
              value={next} onChange={(e) => setNext(e.target.value)} />
            <p className="text-xs text-[var(--text-tertiary)] mt-1">At least {MIN_PASSWORD_LENGTH} characters.</p>
          </div>
          <div>
            <Label htmlFor="pw-confirm">Confirm new password</Label>
            <Input id="pw-confirm" type="password" required autoComplete="new-password" className="mt-1.5"
              value={confirm} onChange={(e) => setConfirm(e.target.value)} />
          </div>
        </fieldset>
        <Button type="submit" disabled={change.isPending} className="w-full justify-center mt-2">
          {change.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Save new password'}
        </Button>
      </form>
    </PublicPageShell>
  );
};
