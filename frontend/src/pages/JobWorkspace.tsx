import { useParams, Link, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Upload, Users, Pause, Play, Archive, Trash2, ListChecks } from 'lucide-react';
import { api } from '../api';
import { queryKeys } from '../api/queryKeys';
import { useFunnel } from '../hooks/useAnalytics';
import {
  Badge, Button, EmptyState, ErrorState, LinkButton, LoadingState, PageHeader,
  Section, Skeleton, StatTile, StatusDot,
} from '../components/ui';
import { useConfirm } from '../hooks/useConfirm';
import { useBreadcrumbs } from '../hooks/useBreadcrumbs';
import { ApplicationLinkCard } from '../components/job/ApplicationLinkCard';
import { FunnelBars } from '../components/analytics/FunnelBars';
import { batchTypeLabel, getBatchStatusVariant, getJobStatusVariant, isBatchLive, jobStatusLabel } from '../utils/status';

const NoneSpecified = () => <span className="text-sm italic text-[var(--text-tertiary)]">None specified</span>;

export const JobWorkspace = () => {
  const { id } = useParams<{ id: string }>();
  const jobId = parseInt(id || '0', 10);
  const confirm = useConfirm();

  const { data: job, isLoading: jobLoading, error: jobError, refetch: refetchJob } = useQuery({
    queryKey: queryKeys.job(jobId),
    queryFn: () => api.jobs.getJob(jobId),
    enabled: jobId > 0,
  });

  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const afterLifecycleChange = () => {
    queryClient.invalidateQueries({ queryKey: queryKeys.job(jobId) });
    queryClient.invalidateQueries({ queryKey: queryKeys.jobs() });
  };
  const pauseMutation = useMutation({ mutationFn: () => api.jobs.pauseJob(jobId), onSuccess: afterLifecycleChange });
  const resumeMutation = useMutation({ mutationFn: () => api.jobs.resumeJob(jobId), onSuccess: afterLifecycleChange });
  const archiveMutation = useMutation({ mutationFn: () => api.jobs.archiveJob(jobId), onSuccess: afterLifecycleChange });
  const deleteMutation = useMutation({
    mutationFn: () => api.jobs.deleteJob(jobId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.jobs() });
      navigate('/jobs');
    },
  });

  const progressQuery = useQuery({
    queryKey: queryKeys.jobProgress(jobId),
    queryFn: () => api.jobs.getJobProgress(jobId),
    enabled: jobId > 0,
  });
  const funnelQuery = useFunnel(jobId > 0 ? jobId : undefined);
  useBreadcrumbs([{ label: 'Jobs', to: '/jobs' }, { label: job?.title || 'Job' }]);
  const progress = progressQuery.data;
  // Screening runs re-count already-uploaded resumes; only upload and
  // application batches contribute to the resume totals.
  const resumeBatches = progress?.batches?.filter((b) => b.batch_type !== 'SCREEN');
  const sum = (pick: (b: NonNullable<typeof resumeBatches>[number]) => number | undefined) =>
    resumeBatches ? resumeBatches.reduce((acc, b) => acc + (pick(b) || 0), 0) : undefined;
  const recentBatches = progress ? [...progress.batches].sort((a, b) => b.batch_id - a.batch_id).slice(0, 5) : [];

  if (jobLoading) {
    return (
      <div className="mx-auto max-w-6xl" aria-hidden="true">
        <Skeleton className="mb-6 h-4 w-48" />
        <Skeleton className="mb-3 h-8 w-80" />
        <Skeleton className="mb-8 h-4 w-56" />
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-24 w-full" />)}
        </div>
      </div>
    );
  }

  if (jobError || !job) {
    return (
      <ErrorState
        title="Job not found"
        message="The job you are looking for does not exist or failed to load."
        onRetry={() => refetchJob()}
        action={<LinkButton to="/jobs" variant="secondary">Back to jobs</LinkButton>}
      />
    );
  }

  const status = job.status || 'ACTIVE';
  const failedFilterState = { params: { page: 1, sort_by: 'score', status: 'FAILED' } };

  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader
        className="mb-6"
        title={job.title}
        subtitle={
          <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <StatusDot variant={getJobStatusVariant(status)}>{jobStatusLabel(status)}</StatusDot>
            {[job.department, job.location, job.employment_type].filter(Boolean).map((part) => (
              <span key={part} className="before:mr-3 before:text-[var(--border-strong)] before:content-['/']">{part}</span>
            ))}
          </span>
        }
        actions={
          <>
            <LinkButton to={`/jobs/${jobId}/upload`} variant="secondary">
              <Upload size={14} aria-hidden="true" /> Upload resumes
            </LinkButton>
            <LinkButton to={`/jobs/${jobId}/processing`} variant="secondary">
              <ListChecks size={14} aria-hidden="true" /> Processing
            </LinkButton>
            <LinkButton to={`/jobs/${jobId}/candidates`}>
              <Users size={14} aria-hidden="true" /> View candidates
            </LinkButton>
          </>
        }
      />

      <div className="mb-6 flex flex-wrap items-center gap-1 border-y border-[var(--border-light)] py-2" role="toolbar" aria-label="Job controls">
        <span className="text-eyebrow mr-2">Job controls</span>
        {status === 'ACTIVE' && (
          <Button variant="ghost" size="sm" onClick={() => pauseMutation.mutate()} disabled={pauseMutation.isPending}>
            <Pause size={14} aria-hidden="true" /> Pause
          </Button>
        )}
        {status === 'PAUSED' && (
          <Button variant="ghost" size="sm" onClick={() => resumeMutation.mutate()} disabled={resumeMutation.isPending}>
            <Play size={14} aria-hidden="true" /> Resume
          </Button>
        )}
        {status !== 'ARCHIVED' && (
          <Button variant="ghost" size="sm" onClick={() => archiveMutation.mutate()} disabled={archiveMutation.isPending}>
            <Archive size={14} aria-hidden="true" /> Archive
          </Button>
        )}
        <Button
          variant="ghost"
          size="sm"
          className="text-[var(--color-danger-600)] hover:not-disabled:bg-[var(--color-danger-subtle-bg)] hover:not-disabled:text-[var(--color-danger-600)]"
          disabled={deleteMutation.isPending}
          onClick={async () => {
            const ok = await confirm({
              title: 'Delete job?',
              description: 'Are you sure you want to delete this job and all associated data? This cannot be undone.',
              confirmLabel: 'Delete',
              danger: true,
            });
            if (ok) deleteMutation.mutate();
          }}
        >
          <Trash2 size={14} aria-hidden="true" /> Delete
        </Button>
      </div>

      <section aria-label="Resume counts" className="mb-8 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatTile label="Total resumes" to={`/jobs/${jobId}/candidates`} value={sum((b) => b.total)} isLoading={progressQuery.isLoading} />
        <StatTile label="Processed" to={`/jobs/${jobId}/candidates`} value={sum((b) => b.completed)} isLoading={progressQuery.isLoading} />
        <StatTile
          label="Awaiting screening"
          value={progress?.unscreened}
          isLoading={progressQuery.isLoading}
          hint="Processed, no result yet"
        />
        <StatTile
          label="Failed"
          tone={(sum((b) => b.failed) ?? 0) > 0 ? 'danger' : 'default'}
          to={`/jobs/${jobId}/candidates`}
          linkState={failedFilterState}
          value={sum((b) => b.failed)}
          isLoading={progressQuery.isLoading}
        />
      </section>
      {progressQuery.isError && (
        <p className="text-caption -mt-5 mb-6">Resume counts couldn&apos;t be loaded.</p>
      )}

      <div className="grid grid-cols-1 gap-10 lg:grid-cols-3">
        <div className="flex flex-col gap-8 lg:col-span-2">
          <Section title="Job description">
            {job.role_summary ? (
              <div className="flex flex-col gap-6">
                <p className="leading-relaxed text-[var(--text-secondary)]">{job.role_summary}</p>
                {job.responsibilities && job.responsibilities.length > 0 && (
                  <div>
                    <h4 className="text-card-title mb-2">Key responsibilities</h4>
                    <ul className="list-disc space-y-1.5 pl-5 text-[var(--text-secondary)]">
                      {job.responsibilities.map((item, index) => <li key={index}>{item}</li>)}
                    </ul>
                  </div>
                )}
                <details className="text-sm">
                  <summary className="transition-base cursor-pointer select-none text-[var(--text-tertiary)] hover:text-[var(--text-secondary)]">
                    View original job description
                  </summary>
                  <div className="mt-3 whitespace-pre-wrap border-t border-[var(--border-light)] pt-3 leading-relaxed text-[var(--text-secondary)]">
                    {job.description}
                  </div>
                </details>
              </div>
            ) : (
              <div className="whitespace-pre-wrap leading-relaxed text-[var(--text-secondary)]">{job.description}</div>
            )}
          </Section>

          <Section title="Requirements">
            {job.requirements && job.requirements.length > 0 ? (
              <ul className="list-disc space-y-1.5 pl-5 text-[var(--text-secondary)]">
                {job.requirements.map((req, index) => <li key={index}>{req}</li>)}
              </ul>
            ) : <NoneSpecified />}
          </Section>
        </div>

        <div className="flex flex-col gap-8">
          {status !== 'ARCHIVED' && <ApplicationLinkCard job={job} />}

          <Section title="Pipeline">
            {funnelQuery.isLoading ? (
              <LoadingState className="py-6" />
            ) : funnelQuery.isError || !funnelQuery.data ? (
              <p className="text-caption">Pipeline figures couldn&apos;t be loaded.</p>
            ) : funnelQuery.data.uploaded === 0 ? (
              <EmptyState className="py-6" title="No resumes yet" description="Upload resumes to start screening." />
            ) : (
              <FunnelBars funnel={funnelQuery.data} />
            )}
          </Section>

          {recentBatches.length > 0 && (
            <Section title="Recent batches" action={<Link to={`/jobs/${jobId}/processing`} className="focus-ring rounded text-xs font-medium text-[var(--color-primary-600)] hover:underline">View all</Link>}>
              <ul className="divide-y divide-[var(--border-light)]">
                {recentBatches.map((b) => (
                  <li key={b.batch_id} className="flex items-center justify-between gap-3 py-2 text-sm">
                    <span className="text-[var(--text-secondary)]">{batchTypeLabel(b.batch_type)} #{b.batch_id}</span>
                    <span className="tabular text-caption">{b.completed + b.failed}/{b.total}</span>
                    <StatusDot variant={getBatchStatusVariant(b.status)} live={isBatchLive(b.status)} className="text-xs">
                      {b.status.charAt(0) + b.status.slice(1).toLowerCase()}
                    </StatusDot>
                  </li>
                ))}
              </ul>
            </Section>
          )}

          <Section title="Required skills">
            {job.required_skills && job.required_skills.length > 0 ? (
              <div className="flex flex-wrap gap-1.5">
                {job.required_skills.map((skill, index) => <Badge key={index} variant="primary">{skill}</Badge>)}
              </div>
            ) : <NoneSpecified />}
          </Section>

          <Section title="Preferred skills">
            {job.preferred_skills && job.preferred_skills.length > 0 ? (
              <div className="flex flex-wrap gap-1.5">
                {job.preferred_skills.map((skill, index) => <Badge key={index}>{skill}</Badge>)}
              </div>
            ) : <NoneSpecified />}
          </Section>
        </div>
      </div>
    </div>
  );
};
