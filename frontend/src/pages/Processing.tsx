import { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { formatDistanceToNow } from 'date-fns';
import { ListChecks } from 'lucide-react';
import { jobsApi } from '../api/jobs';
import { queryKeys } from '../api/queryKeys';
import { DataTable, EmptyState, ErrorState, LinkButton, PageHeader, Progress, StatTile, StatusDot, type Column } from '../components/ui';
import { batchTypeLabel, getBatchStatusVariant, isBatchLive } from '../utils/status';
import { getErrorMessage } from '../utils/errors';
import type { JobBatchOverviewItem } from '../types';

const statusLabel = (b: JobBatchOverviewItem) =>
  b.batch_status.charAt(0) + b.batch_status.slice(1).toLowerCase().replace(/_/g, ' ');

export const Processing = () => {
  const navigate = useNavigate();

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: queryKeys.batchesOverview(),
    queryFn: jobsApi.getBatchesOverview,
    refetchInterval: (query) => (query.state.data?.some((b) => isBatchLive(b.batch_status)) ? 5000 : false),
  });

  // Newest first; the API order isn't guaranteed.
  const batches = useMemo(
    () => [...(data ?? [])].sort((a, b) => (b.created_at ?? '').localeCompare(a.created_at ?? '') || b.batch_id - a.batch_id),
    [data]
  );
  const running = batches.filter((b) => isBatchLive(b.batch_status)).length;
  const failed = batches.filter((b) => b.batch_status === 'FAILED').length;

  const columns: Column<JobBatchOverviewItem>[] = [
    {
      id: 'job',
      header: 'Job',
      mobile: 'title',
      skeleton: 'text',
      cell: (b) => <span className="text-sm font-medium text-[var(--text-primary)]">{b.job_title}</span>,
    },
    {
      id: 'batch',
      header: 'Batch',
      className: 'w-40',
      cell: (b) => <span className="text-sm text-[var(--text-secondary)]">{batchTypeLabel(b.batch_type)} #{b.batch_id}</span>,
    },
    {
      id: 'status',
      header: 'Status',
      className: 'w-36',
      skeleton: 'badge',
      cell: (b) => (
        <StatusDot variant={getBatchStatusVariant(b.batch_status)} live={isBatchLive(b.batch_status)}>
          {statusLabel(b)}
        </StatusDot>
      ),
    },
    {
      id: 'progress',
      header: 'Progress',
      className: 'w-64',
      skeleton: 'text',
      cell: (b) => {
        const done = b.processed + b.failed;
        const pct = b.total > 0 ? Math.min(100, Math.round((done / b.total) * 100)) : 0;
        return (
          <div>
            <Progress value={pct} tone={b.failed > 0 ? 'danger' : 'default'} aria-label={`${b.job_title} batch ${b.batch_id} progress`} />
            <div className="text-caption tabular mt-1.5 flex justify-between">
              <span>{done} / {b.total}{b.failed > 0 ? ` · ${b.failed} failed` : ''}</span>
              <span>{pct}%</span>
            </div>
          </div>
        );
      },
    },
    {
      id: 'started',
      header: 'Started',
      className: 'w-36',
      cell: (b) => (
        <span className="text-caption">{b.created_at ? formatDistanceToNow(new Date(b.created_at), { addSuffix: true }) : '—'}</span>
      ),
    },
  ];

  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader
        className="mb-6"
        title="Processing"
        subtitle="Resume extraction and screening batches, across every job."
      />

      {data && data.length > 0 && (
        <section aria-label="Batch summary" className="mb-6 grid grid-cols-3 gap-4">
          <StatTile label="Running now" value={running} />
          <StatTile label="Batches" value={batches.length} />
          <StatTile label="Failed" value={failed} tone={failed > 0 ? 'danger' : 'default'} />
        </section>
      )}

      {isError ? (
        <div className="rounded-lg border border-[var(--border-light)] bg-[var(--bg-surface)]">
          <ErrorState
            title="Failed to load processing batches"
            message={getErrorMessage(error)}
            onRetry={() => refetch()}
          />
        </div>
      ) : (
        <DataTable
          aria-label="Processing batches"
          rows={batches}
          columns={columns}
          getRowId={(b) => b.batch_id}
          isLoading={isLoading}
          onRowClick={(b) => navigate(`/jobs/${b.job_id}/processing`)}
          empty={
            <EmptyState
              icon={<ListChecks size={20} />}
              title="No batches yet"
              description="Upload resumes to a job to see processing activity here."
              action={<LinkButton to="/jobs" variant="secondary">Go to jobs</LinkButton>}
            />
          }
        />
      )}
    </div>
  );
};
