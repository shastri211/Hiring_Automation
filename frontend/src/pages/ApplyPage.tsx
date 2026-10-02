import { useState, type FormEvent } from 'react';
import { useParams } from 'react-router-dom';
import { useQuery, useMutation } from '@tanstack/react-query';
import { Loader2, AlertCircle, CheckCircle2, FileText, Send } from 'lucide-react';
import { publicApplicationApi } from '../api/publicApplication';
import { Alert, Button, Dropzone, Input, Label } from '../components/ui';
import { AuthState } from '../components/auth/AuthState';
import { PublicPageShell } from '../components/layout/PublicPageShell';
import type { ApiError, PublicApplyErrorReason } from '../types';

const LINK_ERROR_COPY: Record<'not_found' | 'closed', { title: string; description: string }> = {
  not_found: {
    title: 'Application link not found',
    description: "This link isn't valid or is no longer accepting applications. Please check with the recruiter for a current link.",
  },
  closed: {
    title: 'Applications are closed',
    description: 'Applications for this role are currently closed. Please check back later or contact the recruiter.',
  },
};

const SUBMIT_ERROR_COPY: Partial<Record<PublicApplyErrorReason, string>> = {
  rate_limited: 'Too many submissions from your connection. Please try again later.',
  temporarily_unavailable: 'We are temporarily unable to accept applications. Please try again in a few minutes.',
  consent_required: 'Please confirm you agree to your data being processed for this application.',
  invalid_email: 'Please enter a valid email address.',
  invalid_name: 'Please enter your full name.',
  invalid_phone: 'Please enter a shorter phone number (50 characters max).',
  not_found: LINK_ERROR_COPY.not_found.description,
  closed: LINK_ERROR_COPY.closed.description,
};

const errorReason = (error: unknown): PublicApplyErrorReason | undefined =>
  (error as ApiError | undefined)?.details?.detail?.reason;

export const ApplyPage = () => {
  const { token } = useParams<{ token: string }>();

  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [consent, setConsent] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  // Honeypot - visually hidden, only bots fill it.
  const [website, setWebsite] = useState('');

  const { data: job, isLoading, error: jobError } = useQuery({
    queryKey: ['public-job', token],
    queryFn: () => publicApplicationApi.getJob(token as string),
    enabled: !!token,
    retry: false,
  });

  const applyMutation = useMutation({
    mutationFn: () => {
      const formData = new FormData();
      formData.append('file', file as File);
      formData.append('name', name);
      formData.append('email', email);
      if (phone.trim()) formData.append('phone', phone);
      formData.append('consent', String(consent));
      if (website) formData.append('website', website);
      return publicApplicationApi.apply(token as string, formData);
    },
  });

  if (isLoading) {
    return (
      <PublicPageShell wide>
        <div role="status" className="flex flex-col items-center gap-3 py-8 text-[var(--text-secondary)]">
          <Loader2 className="h-6 w-6 animate-spin" aria-hidden="true" />
          <p className="text-sm">Loading the role…</p>
        </div>
      </PublicPageShell>
    );
  }

  if (jobError || !job) {
    const reason = errorReason(jobError) === 'closed' ? 'closed' : 'not_found';
    const copy = LINK_ERROR_COPY[reason];
    return (
      <PublicPageShell footer={null}>
        <AuthState tone="danger" icon={<AlertCircle size={20} />} title={copy.title}>{copy.description}</AuthState>
      </PublicPageShell>
    );
  }

  if (applyMutation.isSuccess) {
    return (
      <PublicPageShell footer={null}>
        <AuthState tone="success" icon={<CheckCircle2 size={20} />} title="Application received">
          Thanks for applying for <strong className="text-[var(--text-primary)]">{job.title}</strong>. The hiring team will review your resume and
          reach out if there&apos;s a match.
        </AuthState>
      </PublicPageShell>
    );
  }

  const submitting = applyMutation.isPending;
  const submitError = applyMutation.error as ApiError | null;
  const submitReason = errorReason(submitError);
  const submitErrorMessage = submitError
    ? submitReason === 'invalid_file'
      ? (submitError.details?.detail?.message as string) || 'Please upload a PDF or DOCX resume.'
      : (submitReason && SUBMIT_ERROR_COPY[submitReason]) || 'Something went wrong submitting your application. Please try again.'
    : null;

  const canSubmit = !!file && name.trim() !== '' && email.trim() !== '' && consent && !submitting;

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;
    applyMutation.mutate();
  };

  return (
    <PublicPageShell wide footer="Questions about this role? Contact the recruiter who shared this link.">
      <div className="flex flex-col gap-6">
        <div>
          <p className="text-eyebrow text-[var(--color-primary-600)]">Apply for</p>
          <h1 className="text-page-title mt-1 text-2xl">{job.title}</h1>
          {job.role_summary ? (
            <p className="text-sm text-[var(--text-secondary)] mt-2 leading-relaxed">{job.role_summary}</p>
          ) : (
            <p className="text-sm text-[var(--text-secondary)] mt-2 leading-relaxed whitespace-pre-wrap line-clamp-6">
              {job.description}
            </p>
          )}
          {job.responsibilities.length > 0 && (
            <ul className="list-disc pl-5 mt-3 space-y-1 text-sm text-[var(--text-secondary)]">
              {job.responsibilities.map((item, index) => (
                <li key={index}>{item}</li>
              ))}
            </ul>
          )}
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4" noValidate>
          <fieldset disabled={submitting} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="apply-name">Full name</Label>
              <Input id="apply-name" value={name} onChange={(e) => setName(e.target.value)} maxLength={255} autoComplete="name" required />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="apply-email">Email</Label>
              <Input id="apply-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} maxLength={320} autoComplete="email" required />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="apply-phone">Phone <span className="text-[var(--text-tertiary)] font-normal">(optional)</span></Label>
              <Input id="apply-phone" type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} maxLength={50} autoComplete="tel" />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>Resume</Label>
              {file ? (
                <div className="flex items-center justify-between gap-3 rounded-lg border border-[var(--border-light)] bg-[var(--bg-app)] p-3">
                  <span className="flex min-w-0 items-center gap-2.5">
                    <FileText size={18} aria-hidden="true" className="shrink-0 text-[var(--text-tertiary)]" />
                    <span className="min-w-0">
                      <span className="block truncate text-sm font-medium text-[var(--text-primary)]">{file.name}</span>
                      <span className="text-caption tabular">{(file.size / 1024).toFixed(1)} KB</span>
                    </span>
                  </span>
                  <Button type="button" variant="secondary" size="sm" onClick={() => setFile(null)}>Remove</Button>
                </div>
              ) : (
                <Dropzone
                  accept={['.pdf', '.docx']}
                  title="Drop your resume here or click to browse"
                  hint="PDF or DOCX, one file"
                  browseLabel="Choose file"
                  className="py-8"
                  onFiles={(files) => setFile(files[0])}
                />
              )}
            </div>

            {/* Honeypot: off-screen and skipped by keyboard/screen readers. */}
            <div aria-hidden="true" className="absolute -left-[10000px] w-px h-px overflow-hidden">
              <label htmlFor="apply-website">Website</label>
              <input id="apply-website" tabIndex={-1} autoComplete="off" value={website} onChange={(e) => setWebsite(e.target.value)} />
            </div>

            <label className="flex items-start gap-2 text-sm text-[var(--text-secondary)]">
              <input
                type="checkbox"
                checked={consent}
                onChange={(e) => setConsent(e.target.checked)}
                className="mt-0.5"
              />
              <span>
                I agree to my resume and the details above being stored and processed by the hiring team to
                evaluate my application for this role.
              </span>
            </label>
          </fieldset>

          {submitErrorMessage && <Alert variant="danger">{submitErrorMessage}</Alert>}

          <Button type="submit" disabled={!canSubmit} className="w-full justify-center">
            {submitting ? (
              <><Loader2 size={14} className="animate-spin" aria-hidden="true" /> Submitting…</>
            ) : (
              <><Send size={14} aria-hidden="true" /> Submit application</>
            )}
          </Button>
        </form>
      </div>
    </PublicPageShell>
  );
};
