import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { useQuery, useMutation } from '@tanstack/react-query';
import { Loader2, AlertCircle, CheckCircle2, Mic, Briefcase } from 'lucide-react';
import { publicInterviewApi } from '../api/publicInterview';
import { Button } from '../components/ui/Button';
import type { PublicInterviewErrorReason } from '../types';

type CallPhase = 'idle' | 'connecting' | 'in_call' | 'ended' | 'widget_error';

const ERROR_COPY: Record<PublicInterviewErrorReason, { title: string; description: string }> = {
  not_found: {
    title: 'Interview link not found',
    description: "This interview link isn't valid. Please double-check the link you were sent, or reach out to the recruiter for a new one.",
  },
  expired: {
    title: 'This interview link has expired',
    description: 'For security, interview links are only valid for a limited time. Please contact the recruiter to request a new link.',
  },
  already_completed: {
    title: 'Interview already completed',
    description: "This interview has already been completed, so this link can't be used again. If you think this is a mistake, please contact the recruiter.",
  },
};

const PublicPageShell = ({ children }: { children: React.ReactNode }) => (
  <div className="min-h-screen flex flex-col items-center justify-center bg-[var(--bg-app)] px-4 py-12">
    <div className="w-full max-w-lg">
      <div className="flex items-center justify-center gap-2 mb-6 text-[var(--color-primary-700)] font-bold text-lg">
        <Briefcase size={22} />
        <span>RecruitPro</span>
      </div>
      <div className="bg-[var(--bg-surface)] border border-[var(--border-light)] rounded-xl shadow-sm p-8">
        {children}
      </div>
      <p className="text-center text-xs text-[var(--text-tertiary)] mt-4">
        Having trouble? Contact the recruiter who sent you this link.
      </p>
    </div>
  </div>
);

const DOGRAH_SCRIPT_ID = 'dograh-widget-script';
const DOGRAH_INLINE_CONTAINER_ID = 'dograh-inline-container';

export const InterviewRoom = () => {
  const { token } = useParams<{ token: string }>();
  const [phase, setPhase] = useState<CallPhase>('idle');

  const { data, isLoading, error } = useQuery({
    queryKey: ['public-interview', token],
    queryFn: () => publicInterviewApi.get(token as string),
    enabled: !!token,
    retry: false,
  });

  const startedMutation = useMutation({
    mutationFn: () => publicInterviewApi.markStarted(token as string),
  });

  // Clean up the injected widget script if the candidate navigates away mid-call.
  useEffect(() => {
    return () => {
      document.getElementById(DOGRAH_SCRIPT_ID)?.remove();
    };
  }, []);

  const handleStart = () => {
    if (!data) return;
    if (!data.dograh_base_url || !data.dograh_embed_token) {
      // Dograh isn't configured on this deployment yet (missing base URL/embed token) -
      // fail gracefully instead of injecting a broken script.
      setPhase('widget_error');
      return;
    }

    setPhase('connecting');

    const script = document.createElement('script');
    script.id = DOGRAH_SCRIPT_ID;
    const params = new URLSearchParams({
      token: data.dograh_embed_token,
      environment: data.dograh_environment || 'production',
      apiEndpoint: data.dograh_api_endpoint || data.dograh_base_url,
    });
    script.src = `${data.dograh_base_url.replace(/\/$/, '')}/embed/dograh-widget.js?${params.toString()}`;

    script.onload = () => {
      // The widget's exact JS call signature (beyond method/callback *names*
      // confirmed from Dograh's docs - start/end/setContext/onCallConnected/
      // onCallDisconnected/onCallEnd/onError) should be verified against the
      // live widget once real Dograh credentials are configured; this is
      // written defensively so a shape mismatch degrades to the error state
      // rather than throwing an unhandled exception in the candidate's browser.
      try {
        const widget = (window as unknown as { DograhWidget?: any }).DograhWidget;
        if (!widget) {
          setPhase('widget_error');
          return;
        }
        widget.setContext?.(data.initial_context);
        widget.onCallConnected = () => {
          setPhase('in_call');
          startedMutation.mutate();
        };
        widget.onCallDisconnected = () => setPhase('ended');
        widget.onCallEnd = () => setPhase('ended');
        widget.onError = () => setPhase('widget_error');
        widget.start?.();
      } catch {
        setPhase('widget_error');
      }
    };
    script.onerror = () => setPhase('widget_error');
    document.body.appendChild(script);
  };

  if (isLoading) {
    return (
      <PublicPageShell>
        <div className="flex flex-col items-center py-8 gap-3 text-[var(--text-secondary)]">
          <Loader2 className="w-6 h-6 animate-spin" />
          <p className="text-sm">Loading your interview...</p>
        </div>
      </PublicPageShell>
    );
  }

  if (error) {
    const details = (error as { details?: { detail?: { reason?: PublicInterviewErrorReason } } })?.details;
    const reason = details?.detail?.reason || 'not_found';
    const copy = ERROR_COPY[reason] || ERROR_COPY.not_found;
    return (
      <PublicPageShell>
        <div className="flex flex-col items-center text-center py-4 gap-3">
          <AlertCircle className="w-10 h-10 text-[var(--color-danger-600)]" />
          <h1 className="text-lg font-semibold text-[var(--text-primary)]">{copy.title}</h1>
          <p className="text-sm text-[var(--text-secondary)] max-w-sm">{copy.description}</p>
        </div>
      </PublicPageShell>
    );
  }

  if (!data) return null;

  return (
    <PublicPageShell>
      <div className="flex flex-col gap-4">
        <div className="text-center">
          <h1 className="text-lg font-semibold text-[var(--text-primary)]">Hi {data.candidate_name},</h1>
          <p className="text-sm text-[var(--text-secondary)] mt-1">
            You&apos;re about to start your interview for <strong>{data.job_title}</strong>.
          </p>
        </div>

        {phase === 'idle' && (
          <div className="flex flex-col items-center gap-4 py-4">
            <p className="text-xs text-[var(--text-tertiary)] text-center max-w-xs">
              This interview happens right here in your browser. When you&apos;re ready, make sure your
              microphone is enabled, then click below to begin.
            </p>
            <Button onClick={handleStart} className="w-full justify-center">
              <Mic className="w-4 h-4 mr-2" /> Start Interview
            </Button>
          </div>
        )}

        {phase === 'connecting' && (
          <div className="flex flex-col items-center gap-3 py-6 text-[var(--text-secondary)]">
            <Loader2 className="w-6 h-6 animate-spin" />
            <p className="text-sm">Connecting...</p>
          </div>
        )}

        {/* Dograh's inline widget mode looks for this container id. */}
        {(phase === 'connecting' || phase === 'in_call') && (
          <div id={DOGRAH_INLINE_CONTAINER_ID} className="min-h-[220px]" />
        )}

        {phase === 'ended' && (
          <div className="flex flex-col items-center text-center gap-3 py-6">
            <CheckCircle2 className="w-10 h-10 text-[var(--color-success-600)]" />
            <h2 className="text-base font-medium text-[var(--text-primary)]">Thanks for your time!</h2>
            <p className="text-sm text-[var(--text-secondary)] max-w-sm">
              Your interview has ended. The hiring team will review it and follow up with you soon. You can
              safely close this window now.
            </p>
          </div>
        )}

        {phase === 'widget_error' && (
          <div className="flex flex-col items-center text-center gap-3 py-6">
            <AlertCircle className="w-10 h-10 text-[var(--color-danger-600)]" />
            <h2 className="text-base font-medium text-[var(--text-primary)]">We couldn&apos;t start the interview</h2>
            <p className="text-sm text-[var(--text-secondary)] max-w-sm">
              Something went wrong connecting to the interview service. Please refresh the page to try again,
              or contact the recruiter if the problem continues.
            </p>
            <Button variant="secondary" onClick={() => window.location.reload()}>Retry</Button>
          </div>
        )}
      </div>
    </PublicPageShell>
  );
};
