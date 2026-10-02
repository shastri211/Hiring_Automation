import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ArrowRight, Briefcase, Plus, Users2 } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import { api } from '../api';
import { jobsApi } from '../api/jobs';
import { queryKeys } from '../api/queryKeys';
import { useFunnel, useDecisionBreakdown, useThroughput, useJobVolume, useTimeInStage } from '../hooks/useAnalytics';
import { useMatchSuggestions } from '../hooks/useCandidateIdentity';
import {
  Alert, Card, CardHeader, CardTitle, EmptyState, ErrorState, LinkButton, PageHeader, Skeleton, Sparkline, StatTile, StatusDot,
} from '../components/ui';
import { FunnelBars } from '../components/analytics/FunnelBars';
import { getDecisionBadgeVariant } from '../utils/decision';
import { decisionLabel, formatDurationSeconds } from '../utils/format';
import { batchTypeLabel, getBatchStatusVariant, getJobStatusVariant, isBatchLive, jobStatusLabel } from '../utils/status';
import type { BadgeVariant } from '../utils/decision';

const SEGMENT_COLOR: Record<BadgeVariant, string> = {
  success: 'bg-[var(--color-success-500)]',
  warning: 'bg-[var(--color-warning-500)]',
  danger: 'bg-[var(--color-danger-500)]',
  primary: 'bg-[var(--color-primary-500)]',
  neutral: 'bg-[var(--color-neutral-400)]',
};

const PanelLink = ({ to, children }: { to: string; children: React.ReactNode }) => (
  <Link to={to} className="focus-ring transition-base inline-flex items-center gap-1 rounded text-sm font-medium text-[var(--color-primary-600)] hover:text-[var(--color-primary-700)]">
    {children} <ArrowRight size={14} aria-hidden="true" />
  </Link>
);

const PanelHeader = ({ title, action }: { title: string; action?: React.ReactNode }) => (
  <CardHeader className="flex-row items-center justify-between gap-3 py-3">
    <CardTitle className="text-sm">{title}</CardTitle>
    {action}
  </CardHeader>
);

const PanelBody = ({ isLoading, isError, onRetry, isEmpty, empty, rows = 3, children }: {
  isLoading: boolean; isError: boolean; onRetry: () => void; isEmpty: boolean; empty: React.ReactNode; rows?: number; children: React.ReactNode;
}) => {
  if (isLoading) {
    return (
      <div className="space-y-3 p-5" aria-hidden="true">
        {Array.from({ length: rows }).map((_, i) => <Skeleton key={i} className="h-5 w-full" />)}
      </div>
    );
  }
  if (isError) return <ErrorState className="py-10" title="Couldn't load this" onRetry={onRetry} />;
  if (isEmpty) return <>{empty}</>;
  return <>{children}</>;
};

export const Dashboard = () => {
  const jobsQuery = useQuery({ queryKey: queryKeys.jobs(), queryFn: api.jobs.getJobs });
  const funnelQuery = useFunnel();
  const decisionsQuery = useDecisionBreakdown();
  const throughputQuery = useThroughput(30);
  const volumeQuery = useJobVolume();
  const timeQuery = useTimeInStage();
  const batchesQuery = useQuery({ queryKey: queryKeys.batchesOverview(), queryFn: jobsApi.getBatchesOverview });
  const { data: pendingDuplicates } = useMatchSuggestions('PENDING');

  const funnel = funnelQuery.data;
  const jobs = jobsQuery.data;
  const activeJobs = jobs?.filter((j) => (j.status || 'ACTIVE') === 'ACTIVE').length;

  const decisions = decisionsQuery.data?.items ?? [];
  const decisionsTotal = decisionsQuery.data?.total ?? 0;

  const throughput = useMemo(() => throughputQuery.data?.items.map((p) => p.count) ?? [], [throughputQuery.data]);
  const screened30d = throughput.reduce((a, b) => a + b, 0);

  const volumeByJob = useMemo(() => new Map(volumeQuery.data?.items.map((i) => [i.job_id, i.resume_count])), [volumeQuery.data]);
  const recentJobs = jobs?.slice(0, 6);

  const recentBatches = useMemo(
    () => [...(batchesQuery.data ?? [])].sort((a, b) => (b.created_at ?? '').localeCompare(a.created_at ?? '')).slice(0, 6),
    [batchesQuery.data]
  );

  const duplicateCount = pendingDuplicates?.length ?? 0;

  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader
        title="Overview"
        subtitle="Where your hiring pipeline stands right now."
        className="mb-6"
        actions={
          <LinkButton to="/jobs/new">
            <Plus size={14} aria-hidden="true" /> New Job
          </LinkButton>
        }
      />

      {duplicateCount > 0 && (
        <Alert
          className="mb-6"
          icon={<Users2 size={16} />}
          action={<PanelLink to="/candidates/duplicates">Review</PanelLink>}
        >
          {duplicateCount} possible duplicate candidate{duplicateCount === 1 ? '' : 's'} waiting for review.
        </Alert>
      )}

      <section aria-label="Key figures" className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatTile
          label="Active jobs"
          to="/jobs"
          value={activeJobs}
          isLoading={jobsQuery.isLoading}
          hint={jobs ? `${jobs.length} total` : undefined}
        />
        <StatTile
          label="Resumes uploaded"
          value={funnel?.uploaded}
          isLoading={funnelQuery.isLoading}
          hint={funnel ? `${funnel.processed} processed` : undefined}
        />
        <StatTile
          label="Screened"
          value={funnel?.screened}
          isLoading={funnelQuery.isLoading}
          hint={timeQuery.data?.resume_to_screened_seconds_approx != null ? `≈ ${formatDurationSeconds(timeQuery.data.resume_to_screened_seconds_approx)} from upload` : undefined}
        />
        <StatTile
          label="Shortlisted"
          to="/shortlisted"
          value={funnel?.shortlisted}
          isLoading={funnelQuery.isLoading}
          hint={funnel ? `${funnel.interviewed} interviewed` : undefined}
        />
      </section>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="flex flex-col gap-6 lg:col-span-2">
          <Card>
            <PanelHeader title="Hiring funnel" action={<PanelLink to="/analytics">Analytics</PanelLink>} />
            <PanelBody
              isLoading={funnelQuery.isLoading}
              isError={funnelQuery.isError}
              onRetry={() => funnelQuery.refetch()}
              isEmpty={!funnel || funnel.uploaded === 0}
              empty={
                <EmptyState
                  className="py-10"
                  title="No resumes yet"
                  description="Create a job and upload resumes to see the funnel."
                  action={<LinkButton to="/jobs/new" variant="secondary">Create a job</LinkButton>}
                />
              }
              rows={6}
            >
              <div className="p-5">{funnel && <FunnelBars funnel={funnel} />}</div>
            </PanelBody>
          </Card>

          <Card>
            <PanelHeader title="Jobs" action={<PanelLink to="/jobs">All jobs</PanelLink>} />
            <PanelBody
              isLoading={jobsQuery.isLoading}
              isError={jobsQuery.isError}
              onRetry={() => jobsQuery.refetch()}
              isEmpty={!recentJobs?.length}
              empty={
                <EmptyState
                  className="py-10"
                  icon={<Briefcase size={20} />}
                  title="No jobs yet"
                  description="Get started by creating your first job posting."
                  action={<LinkButton to="/jobs/new">Create job</LinkButton>}
                />
              }
              rows={4}
            >
              <ul className="divide-y divide-[var(--border-light)]">
                {recentJobs?.map((job) => (
                  <li key={job.id}>
                    <Link
                      to={`/jobs/${job.id}`}
                      className="transition-base focus-ring flex items-center gap-4 px-5 py-3 hover:bg-[var(--bg-hover)]"
                    >
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium text-[var(--text-primary)]">{job.title}</p>
                        <p className="text-caption truncate">{[job.department, job.location].filter(Boolean).join(' · ') || '—'}</p>
                      </div>
                      <StatusDot variant={getJobStatusVariant(job.status)} className="hidden sm:inline-flex">
                        {jobStatusLabel(job.status)}
                      </StatusDot>
                      <span className="tabular w-20 text-right text-sm text-[var(--text-secondary)]">
                        {volumeByJob.has(job.id) ? `${volumeByJob.get(job.id)} resumes` : '—'}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            </PanelBody>
          </Card>
        </div>

        <div className="flex flex-col gap-6">
          <Card>
            <PanelHeader title="Decisions" />
            <PanelBody
              isLoading={decisionsQuery.isLoading}
              isError={decisionsQuery.isError}
              onRetry={() => decisionsQuery.refetch()}
              isEmpty={decisions.length === 0 || decisionsTotal === 0}
              empty={<p className="text-body px-5 py-8 text-center">No screening decisions yet.</p>}
            >
              <div className="p-5">
                <div className="flex h-2 overflow-hidden rounded-sm bg-[var(--bg-hover)]" role="presentation">
                  {decisions.map((d) => (
                    <div
                      key={d.decision ?? 'none'}
                      className={SEGMENT_COLOR[getDecisionBadgeVariant(d.decision)]}
                      style={{ width: `${(d.count / decisionsTotal) * 100}%` }}
                    />
                  ))}
                </div>
                <ul className="mt-4 space-y-2">
                  {decisions.map((d) => (
                    <li key={d.decision ?? 'none'} className="flex items-center justify-between gap-3">
                      <StatusDot variant={getDecisionBadgeVariant(d.decision)}>{decisionLabel(d.decision)}</StatusDot>
                      <span className="tabular text-sm font-medium text-[var(--text-primary)]">{d.count}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </PanelBody>
          </Card>

          <Card>
            <PanelHeader title="Screened, last 30 days" />
            <PanelBody
              isLoading={throughputQuery.isLoading}
              isError={throughputQuery.isError}
              onRetry={() => throughputQuery.refetch()}
              isEmpty={screened30d === 0}
              empty={<p className="text-body px-5 py-8 text-center">No candidates screened in this period.</p>}
              rows={2}
            >
              <div className="p-5">
                <p className="tabular text-3xl font-semibold leading-none tracking-tight">{screened30d}</p>
                <Sparkline className="mt-3" values={throughput} label={`Candidates screened per day over the last 30 days: ${screened30d} in total`} />
              </div>
            </PanelBody>
          </Card>

          <Card>
            <PanelHeader title="Recent processing" action={<PanelLink to="/processing">All</PanelLink>} />
            <PanelBody
              isLoading={batchesQuery.isLoading}
              isError={batchesQuery.isError}
              onRetry={() => batchesQuery.refetch()}
              isEmpty={recentBatches.length === 0}
              empty={<p className="text-body px-5 py-8 text-center">Upload resumes to a job to see activity here.</p>}
            >
              <ul className="divide-y divide-[var(--border-light)]">
                {recentBatches.map((b) => (
                  <li key={b.batch_id}>
                    <Link to={`/jobs/${b.job_id}/processing`} className="transition-base focus-ring block px-5 py-3 hover:bg-[var(--bg-hover)]">
                      <div className="flex items-center justify-between gap-3">
                        <p className="truncate text-sm font-medium text-[var(--text-primary)]">{b.job_title}</p>
                        <StatusDot variant={getBatchStatusVariant(b.batch_status)} live={isBatchLive(b.batch_status)} className="text-xs">
                          {b.batch_status.charAt(0) + b.batch_status.slice(1).toLowerCase()}
                        </StatusDot>
                      </div>
                      <p className="text-caption tabular mt-0.5">
                        {batchTypeLabel(b.batch_type)} · {b.processed + b.failed}/{b.total}
                        {b.failed > 0 ? ` (${b.failed} failed)` : ''}
                        {b.created_at ? ` · ${formatDistanceToNow(new Date(b.created_at), { addSuffix: true })}` : ''}
                      </p>
                    </Link>
                  </li>
                ))}
              </ul>
            </PanelBody>
          </Card>
        </div>
      </div>
    </div>
  );
};
