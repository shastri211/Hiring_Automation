import type { ReactNode } from 'react';
import { toast } from 'sonner';
import { Loader2 } from 'lucide-react';
import { useIntegrationsStatus, useTestIntegration } from '../hooks/useSettings';
import { Alert, Button, ErrorState, PageHeader, Section, Skeleton, StatusDot } from '../components/ui';
import { getErrorMessage } from '../utils/errors';

const DetailRow = ({ label, value }: { label: string; value: ReactNode }) => (
  <div className="flex items-start justify-between gap-4 border-b border-[var(--border-light)] py-2.5 text-sm last:border-b-0">
    <dt className="text-[var(--text-secondary)]">{label}</dt>
    <dd className="min-w-0 break-all text-right font-medium text-[var(--text-primary)]">{value}</dd>
  </div>
);

const TestButton = ({ onClick, pending }: { onClick: () => void; pending: boolean }) => (
  <Button variant="secondary" size="sm" className="mt-4" onClick={onClick} disabled={pending}>
    {pending ? <><Loader2 size={14} className="animate-spin" aria-hidden="true" /> Testing…</> : 'Test connection'}
  </Button>
);

export const Integrations = () => {
  const { data, isLoading, isError, error, refetch } = useIntegrationsStatus();
  // Two independent mutation instances - a single shared one would disable
  // and spinner-ize BOTH sections' buttons while only one provider is actually
  // being tested.
  const smtpTestMutation = useTestIntegration();
  const dograhTestMutation = useTestIntegration();

  const handleTest = (provider: string, mutation: typeof smtpTestMutation) => {
    mutation.mutate(provider, {
      onSuccess: (result) => {
        if (result.success) toast.success(result.message);
        else toast.error(result.message);
      },
      onError: (e: { message?: string }) => toast.error(e.message || 'Connection test failed.'),
    });
  };

  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader className="mb-6" title="Integrations" subtitle="Status of external services this platform connects to." />

      <Alert variant="info" className="mb-8">
        Integrations are configured via environment variables (<code className="font-mono text-xs">.env</code>) on the backend — no secrets are entered here.
      </Alert>

      {isLoading ? (
        <div className="grid grid-cols-1 gap-10 md:grid-cols-2" aria-hidden="true">
          {[0, 1].map((i) => <Skeleton key={i} className="h-48 w-full" />)}
        </div>
      ) : isError ? (
        <div className="rounded-lg border border-[var(--border-light)] bg-[var(--bg-surface)]">
          <ErrorState title="Failed to load integration status" message={getErrorMessage(error)} onRetry={() => refetch()} />
        </div>
      ) : data ? (
        <div className="grid grid-cols-1 gap-x-12 gap-y-10 md:grid-cols-2">
          <Section
            title="Email (SMTP)"
            action={
              <StatusDot variant={data.smtp.configured ? 'success' : 'neutral'} className="text-xs">
                {data.smtp.configured ? 'Configured' : 'Simulated'}
              </StatusDot>
            }
          >
            <dl>
              <DetailRow label="From email" value={data.smtp.detail.from_email || '—'} />
              <DetailRow label="SMTP host" value={data.smtp.detail.host || 'Not set (sends are simulated)'} />
            </dl>
            <TestButton onClick={() => handleTest('smtp', smtpTestMutation)} pending={smtpTestMutation.isPending} />
          </Section>

          <Section
            title="Dograh (voice interviews)"
            action={
              <StatusDot variant={data.dograh.configured ? 'success' : 'neutral'} className="text-xs">
                {data.dograh.configured ? 'Configured' : 'Not configured'}
              </StatusDot>
            }
          >
            <dl>
              <DetailRow label="Base URL" value={data.dograh.detail.base_url || '—'} />
              <DetailRow label="Embed token set" value={data.dograh.detail.embed_token_set ? 'Yes' : 'No'} />
              <DetailRow label="Webhook secret set" value={data.dograh.detail.webhook_secret_set ? 'Yes' : 'No'} />
              <DetailRow label="Public app URL" value={data.dograh.detail.public_app_url || '—'} />
            </dl>
            <TestButton onClick={() => handleTest('dograh', dograhTestMutation)} pending={dograhTestMutation.isPending} />
          </Section>
        </div>
      ) : null}
    </div>
  );
};
