import { useEffect, useRef } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import { AlertCircle, CheckCircle2, Loader2 } from 'lucide-react';
import { authApi } from '../api/auth';
import { PublicPageShell } from '../components/layout/PublicPageShell';
import { ResendVerificationForm } from '../components/auth/ResendVerificationForm';
import { AuthState } from '../components/auth/AuthState';
import { authLinkClass } from '../components/auth/authStyles';

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
        <div role="status" className="flex flex-col items-center gap-3 py-8 text-[var(--text-secondary)]">
          <Loader2 className="h-6 w-6 animate-spin" aria-hidden="true" />
          <p className="text-sm">Confirming your email…</p>
        </div>
      </PublicPageShell>
    );
  }

  if (verify.isSuccess) {
    return (
      <PublicPageShell footer={null}>
        <AuthState
          tone="success"
          icon={<CheckCircle2 size={20} />}
          title="Email confirmed"
          action={<Link to="/login" className={authLinkClass}>Sign in</Link>}
        >
          Your company account is active. You can sign in now.
        </AuthState>
      </PublicPageShell>
    );
  }

  // No token, or the server rejected it (expired, tampered, wrong kind).
  return (
    <PublicPageShell footer={<Link to="/login" className={authLinkClass}>Back to sign in</Link>}>
      <div className="flex flex-col gap-5">
        <AuthState tone="danger" icon={<AlertCircle size={20} />} title="This link isn't valid">
          {verify.isError && verify.error && (verify.error as { status?: number }).status !== 400
            ? 'We could not confirm your email right now. Please try again, or request a new link below.'
            : 'Confirmation links expire after 24 hours and can only be used for this purpose. Request a new one below.'}
        </AuthState>
        <ResendVerificationForm />
      </div>
    </PublicPageShell>
  );
};
