import { useEffect, useRef } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import { AlertCircle, CheckCircle2, Loader2 } from 'lucide-react';
import { authApi } from '../api/auth';
import { PublicPageShell } from '../components/layout/PublicPageShell';
import { ResendVerificationForm } from '../components/auth/ResendVerificationForm';

export const VerifyEmail = () => {
  const [params] = useSearchParams();
  const token = params.get('token') ?? '';
  const verify = useMutation({ mutationFn: () => authApi.verifyEmail(token) });

  // Fire once per token (StrictMode double-mounts; the endpoint is
  // idempotent anyway, this just avoids a redundant request).
  const fired = useRef<string | null>(null);
  useEffect(() => {
    if (token && fired.current !== token) {
      fired.current = token;
      verify.mutate();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  if (token && (verify.isIdle || verify.isPending)) {
    return (
      <PublicPageShell footer={null}>
        <div className="flex flex-col items-center py-8 gap-3 text-[var(--text-secondary)]">
          <Loader2 className="w-6 h-6 animate-spin" />
          <p className="text-sm">Confirming your email...</p>
        </div>
      </PublicPageShell>
    );
  }

  if (verify.isSuccess) {
    return (
      <PublicPageShell footer={null}>
        <div className="flex flex-col items-center text-center py-4 gap-3">
          <CheckCircle2 className="w-10 h-10 text-[var(--color-success-600)]" />
          <h1 className="text-lg font-semibold text-[var(--text-primary)]">Email confirmed</h1>
          <p className="text-sm text-[var(--text-secondary)] max-w-sm">Your company account is active. You can sign in now.</p>
          <Link to="/login" className="text-sm font-medium text-[var(--color-primary-600)] hover:underline mt-2">
            Sign in
          </Link>
        </div>
      </PublicPageShell>
    );
  }

  // No token, or the server rejected it (expired, tampered, wrong kind).
  return (
    <PublicPageShell footer={<Link to="/login" className="text-[var(--color-primary-600)] hover:underline">Back to sign in</Link>}>
      <div className="flex flex-col gap-4">
        <div className="flex flex-col items-center text-center gap-3">
          <AlertCircle className="w-10 h-10 text-[var(--color-danger-600)]" />
          <h1 className="text-lg font-semibold text-[var(--text-primary)]">This link isn&apos;t valid</h1>
          <p className="text-sm text-[var(--text-secondary)] max-w-sm">
            {verify.isError && verify.error && (verify.error as { status?: number }).status !== 400
              ? 'We could not confirm your email right now. Please try again, or request a new link below.'
              : 'Confirmation links expire after 24 hours and can only be used for this purpose. Request a new one below.'}
          </p>
        </div>
        <ResendVerificationForm />
      </div>
    </PublicPageShell>
  );
};
