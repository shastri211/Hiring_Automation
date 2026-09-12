import { toast } from 'sonner';
import { Loader2, Puzzle, CheckCircle2 } from 'lucide-react';
import { useIntegrationsStatus, useTestIntegration } from '../hooks/useSettings';
import { Card, CardContent, Badge, Button } from '../components/ui';

const DetailRow = ({ label, value }: { label: string; value: React.ReactNode }) => (
  <div className="flex items-center justify-between text-sm py-1.5">
    <span className="text-[var(--text-secondary)]">{label}</span>
    <span className="text-[var(--text-primary)] font-medium">{value}</span>
  </div>
);

export const Integrations = () => {
  const { data, isLoading, isError, refetch } = useIntegrationsStatus();
  const testMutation = useTestIntegration();

  const handleTest = (provider: string) => {
    testMutation.mutate(provider, {
      onSuccess: (result) => {
        if (result.success) toast.success(result.message);
        else toast.error(result.message);
      },
      onError: (e: { message?: string }) => toast.error(e.message || 'Connection test failed.'),
    });
  };

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="flex items-center space-x-3 mb-2">
        <div className="w-10 h-10 bg-[var(--color-primary-subtle-bg)] text-[var(--color-primary-subtle-text)] rounded-lg flex items-center justify-center">
          <Puzzle className="w-6 h-6" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">Integrations</h1>
          <p className="text-sm text-[var(--text-secondary)]">Status of external services this platform connects to.</p>
        </div>
      </div>
      <p className="text-xs text-[var(--text-tertiary)] mb-8 bg-[var(--bg-app)] border border-[var(--border-light)] rounded-md px-4 py-2 inline-block">
        Integrations are configured via environment variables (<code>.env</code>) on the backend — no secrets are entered here.
      </p>

      {isLoading ? (
        <div className="flex justify-center py-12"><Loader2 className="w-8 h-8 animate-spin text-[var(--color-primary-500)]" /></div>
      ) : isError ? (
        <div className="text-center py-12">
          <p className="text-[var(--color-danger-600)] mb-4">Failed to load integration status.</p>
          <Button variant="secondary" onClick={() => refetch()}>Retry</Button>
        </div>
      ) : data ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <Card className={!data.resend.configured ? 'opacity-80' : undefined}>
            <CardContent className="p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-semibold text-[var(--text-primary)]">Resend (Email)</h3>
                <Badge variant={data.resend.configured ? 'success' : 'neutral'}>
                  {data.resend.configured ? (
                    <span className="flex items-center gap-1"><CheckCircle2 className="w-3 h-3" /> Configured</span>
                  ) : 'Not Configured'}
                </Badge>
              </div>
              <DetailRow label="From Email" value={data.resend.detail.from_email || '—'} />
              <Button
                variant="secondary"
                size="sm"
                className="mt-4"
                onClick={() => handleTest('resend')}
                disabled={testMutation.isPending}
              >
                {testMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Test Connection'}
              </Button>
            </CardContent>
          </Card>

          <Card className={!data.dograh.configured ? 'opacity-80' : undefined}>
            <CardContent className="p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-semibold text-[var(--text-primary)]">Dograh (Voice Interviews)</h3>
                <Badge variant={data.dograh.configured ? 'success' : 'neutral'}>
                  {data.dograh.configured ? (
                    <span className="flex items-center gap-1"><CheckCircle2 className="w-3 h-3" /> Configured</span>
                  ) : 'Not Configured'}
                </Badge>
              </div>
              <DetailRow label="Base URL" value={data.dograh.detail.base_url || '—'} />
              <DetailRow label="Embed token set" value={data.dograh.detail.embed_token_set ? 'Yes' : 'No'} />
              <DetailRow label="Webhook secret set" value={data.dograh.detail.webhook_secret_set ? 'Yes' : 'No'} />
              <DetailRow label="Public app URL" value={data.dograh.detail.public_app_url || '—'} />
              <Button
                variant="secondary"
                size="sm"
                className="mt-4"
                onClick={() => handleTest('dograh')}
                disabled={testMutation.isPending}
              >
                {testMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Test Connection'}
              </Button>
            </CardContent>
          </Card>
        </div>
      ) : null}
    </div>
  );
};
