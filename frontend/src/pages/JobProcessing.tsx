import { useParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Loader2, Play, Upload, ListChecks } from 'lucide-react';
import { toast } from 'sonner';
import { jobsApi } from '../api/jobs';
import { queryKeys } from '../api/queryKeys';
import { useBreadcrumbs } from '../hooks/useBreadcrumbs';
import {
  Alert, Button, EmptyState, ErrorState, LinkButton, PageHeader, Progress, Skeleton, StatusDot,
} from '../components/ui';
import { batchTypeLabel, isBatchLive } from '../utils/status';
import type { BadgeVariant } from '../utils/decision';
import type { BatchProgressDetail } from '../types';

export const JobProcessing = () => {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const jobId = parseInt(id || '0', 10);

  const { data: job } = useQuery({
    queryKey: queryKeys.job(jobId),
    queryFn: () => jobsApi.getJob(jobId),
    enabled: jobId > 0,
  });
  useBreadcrumbs([{ label: 'Jobs', to: '/jobs' }, { label: job?.title || 'Job', to: `/jobs/${id}` }, { label: 'Processing' }]);

  const { data: progressData, isLoading, isError, error, refetch } = useQuery({
    queryKey: queryKeys.jobProgress(jobId),
    queryFn: () => jobsApi.getJobProgress(jobId),
    refetchInterval: (query) => {
      // Poll every 3 seconds if there are batches and any batch is not COMPLETED/FAILED
      const data = query.state.data;
      if (!data || !data.batches || data.batches.length === 0) return false;
      return data.batches.some((b) => isBatchLive(b.status)) ? 3000 : false;
    },
    staleTime: 0,
  });

  const screenMutation = useMutation({
    mutationFn: () => jobsApi.screenJob(jobId),
    onSuccess: () => {
      // Invalidate to fetch the new PROCESSING batch immediately
      queryClient.invalidateQueries({ queryKey: queryKeys.jobProgress(jobId) });
      // The cross-job Processing page reads a separate query key - without
      // this, the new SCREEN batch is invisible there until its 5-minute
      // staleTime lapses.
      queryClient.invalidateQueries({ queryKey: queryKeys.batchesOverview() });
      toast.success('Screening started. Results will appear as processing completes.');
    },
    onError: (error: { message?: string }) => {
      toast.error(error.message || 'Unable to start screening. Please try again.');
    },
  });

  const batches = progressData?.batches || [];
  const unScreenedCount = progressData?.unscreened ?? 0;
  const hasRunningBatch = batches.some((b) => b.status === 'PROCESSING');
  const screening = hasRunningBatch || screenMutation.isPending;

  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader
        className="mb-6"
        title="Processing"
        subtitle={job?.title ? `Extraction and screening progress for ${job.title}.` : 'Monitor extraction and screening progress.'}
        actions={
          <>
            <LinkButton to={`/jobs/${id}/upload`} variant="secondary">
              <Upload size={14} aria-hidden="true" /> Upload resumes
            </LinkButton>
            {unScreenedCount > 0 && (
              <Button onClick={() => screenMutation.mutate()} disabled={screening}>
                {screening ? (
                  <><Loader2 size={14} className="animate-spin" aria-hidden="true" /> Screening…</>
                ) : (
                  <><Play size={14} aria-hidden="true" /> Start screening ({unScreenedCount})</>
                )}
              </Button>
            )}
          </>
        }
      />

      {isLoading ? (
        <div className="space-y-4" aria-hidden="true">
          {[0, 1].map((i) => <Skeleton key={i} className="h-36 w-full" />)}
        </div>
      ) : isError ? (
        <div className="rounded-lg border border-[var(--border-light)] bg-[var(--bg-surface)]">
          <ErrorState title="Error loading progress" message={error instanceof Error ? error.message : undefined} onRetry={() => refetch()} />
        </div>
      ) : batches.length === 0 ? (
        <div className="rounded-lg border border-[var(--border-light)] bg-[var(--bg-surface)]">
          <EmptyState
            icon={<ListChecks size={20} />}
            title="No batches yet"
            description="Upload resumes and start screening to see progress here."
            action={<LinkButton to={`/jobs/${id}/upload`}>Upload resumes</LinkButton>}
          />
        </div>
      ) : (
        <>
          {unScreenedCount > 0 && !screening && (
            <Alert variant="info" className="mb-4">
              {unScreenedCount} processed resume{unScreenedCount === 1 ? ' is' : 's are'} waiting for screening.
            </Alert>
          )}
          <ul className="space-y-4">
            {batches.map((b) => (
              <li key={b.batch_id}>
                <BatchPanel batch={b} jobId={jobId} />
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
};

const Count = ({ value, label, variant }: { value: number; label: string; variant?: BadgeVariant }) => (
  <div>
    <dt className="text-eyebrow flex items-center gap-1.5">
      {variant && <span aria-hidden="true" className={`h-1.5 w-1.5 rounded-full ${DOT[variant]}`} />}
      {label}
    </dt>
    <dd className="tabular mt-1 text-xl font-semibold text-[var(--text-primary)]">{value}</dd>
  </div>
);

const DOT: Record<BadgeVariant, string> = {
  success: 'bg-[var(--color-success-500)]',
  warning: 'bg-[var(--color-warning-500)]',
  danger: 'bg-[var(--color-danger-500)]',
  primary: 'bg-[var(--color-primary-500)]',
  neutral: 'bg-[var(--color-neutral-400)]',
};

const BatchPanel = ({ batch, jobId }: { batch: BatchProgressDetail; jobId: number }) => {
  // batch_type is the only reliable signal for a screening run (the old
  // `total === 0` guess stopped holding once SCREEN batches reported their
  // real count).
  const isScreening = batch.batch_type === 'SCREEN';
  const live = isBatchLive(batch.status);

  const statusLabel =
    batch.status === 'PROCESSING'
      ? isScreening ? 'Screening' : 'Processing'
      : batch.status === 'COMPLETED'
        ? isScreening ? 'Screening complete' : 'Ready'
        : batch.status.charAt(0) + batch.status.slice(1).toLowerCase();

  // A "completed" screening run is a success; a "completed" upload batch is
  // simply ready (primary), matching how the two read elsewhere.
  const variant: BadgeVariant =
    batch.status === 'FAILED' ? 'danger'
    : batch.status === 'COMPLETED' ? (isScreening ? 'success' : 'primary')
    : isScreening ? 'primary' : 'neutral';

  const done = (batch.completed || 0) + (batch.failed || 0);
  const total = batch.total || 0;
  const pct = total > 0 ? Math.min(100, Math.round((done / total) * 100)) : 0;

  return (
    <section
      aria-label={`${batchTypeLabel(batch.batch_type)} ${batch.batch_id}`}
      className={`rounded-lg border bg-[var(--bg-surface)] p-5 ${batch.status === 'FAILED' ? 'border-[var(--color-danger-border)]' : 'border-[var(--border-light)]'}`}
    >
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-card-title">
          {isScreening ? 'Screening run' : batchTypeLabel(batch.batch_type)} #{batch.batch_id}
        </h2>
        <StatusDot variant={variant} live={live}>{statusLabel}</StatusDot>
      </div>

      {!isScreening && (
        <div className="mt-4">
          <Progress value={pct} tone={batch.status === 'FAILED' ? 'danger' : 'default'} aria-label={`Batch ${batch.batch_id} progress`} />
          <div className="text-caption tabular mt-1.5 flex justify-between">
            <span>{done} / {total} resumes</span>
            <span>{pct}%</span>
          </div>
        </div>
      )}

      <dl className="mt-5 grid grid-cols-2 gap-x-6 gap-y-4 border-t border-[var(--border-light)] pt-4 sm:grid-cols-4">
        {isScreening ? (
          <>
            <Count value={batch.shortlisted || 0} label="Shortlist" variant="success" />
            <Count value={batch.review || 0} label="Review" variant="warning" />
            <Count value={batch.rejected || 0} label="Rejected" variant="danger" />
            {(batch.pre_screened_out ?? 0) > 0 && <Count value={batch.pre_screened_out || 0} label="Pre-screened out" variant="neutral" />}
          </>
        ) : (
          <>
            <Count value={total} label="Total" />
            <Count value={batch.processing || 0} label="Processing" variant="primary" />
            <Count value={batch.completed || 0} label="Ready" variant="success" />
            <Count value={batch.failed || 0} label="Failed" variant="danger" />
          </>
        )}
      </dl>

      {isScreening && batch.status === 'COMPLETED' && (
        <div className="mt-4">
          <LinkButton to={`/jobs/${jobId}/candidates`} variant="secondary" size="sm">View results →</LinkButton>
        </div>
      )}
    </section>
  );
};
