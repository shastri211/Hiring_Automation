import { useState, type FormEvent } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Loader2, MailWarning } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';
import { PublicPageShell } from '../components/layout/PublicPageShell';
import { Alert, Button, Input, Label } from '../components/ui';
import { authLinkClass } from '../components/auth/authStyles';
import { ResendVerificationForm } from '../components/auth/ResendVerificationForm';
import type { ApiError } from '../types';

export const Login = () => {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  // Correct password, but the signup email was never confirmed.
  const [unverified, setUnverified] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setUnverified(false);
    setIsSubmitting(true);
    try {
      await login(email, password);
      const from = (location.state as { from?: Location })?.from?.pathname || '/';
      navigate(from, { replace: true });
    } catch (err) {
      const apiError = err as ApiError;
      if (apiError.details?.detail?.reason === 'email_not_verified') {
        setUnverified(true);
      } else {
        setError(apiError.message || 'Incorrect email or password');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <PublicPageShell
      footer={
        <>
          New company?{' '}
          <Link to="/signup" className={authLinkClass}>Create a company account</Link>
          . Joining an existing team? Ask your admin to add you.
        </>
      }
    >
      <div className="flex flex-col gap-1 mb-6 text-center">
        <h1 className="text-lg font-semibold text-[var(--text-primary)]">Sign in</h1>
        <p className="text-sm text-[var(--text-secondary)]">Use your HR account to access RecruitPro.</p>
      </div>

      {error && <Alert variant="danger" className="mb-4">{error}</Alert>}

      {unverified && (
        <Alert variant="warning" icon={<MailWarning size={16} />} className="mb-4">
          <p>Please confirm your email address first - open the link we sent when you signed up. Need a new one?</p>
          <div className="mt-3"><ResendVerificationForm initialEmail={email} /></div>
        </Alert>
      )}

      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <div>
          <Label htmlFor="email">Email</Label>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-1.5"
            placeholder="you@company.com"
          />
        </div>
        <div>
          <div className="flex items-center justify-between">
            <Label htmlFor="password">Password</Label>
            <Link to="/forgot-password" className={authLinkClass}>
              Forgot password?
            </Link>
          </div>
          <Input
            id="password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1.5"
            placeholder="••••••••"
          />
        </div>
        <Button type="submit" disabled={isSubmitting} className="w-full justify-center mt-2">
          {isSubmitting ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Sign in'}
        </Button>
      </form>
    </PublicPageShell>
  );
};
