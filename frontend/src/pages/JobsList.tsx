import { useMemo, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Archive, Briefcase, Pause, Play, Plus, Search, Trash2 } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { api } from '../api';
import { jobsApi } from '../api/jobs';
import { analyticsApi } from '../api/analytics';
import { queryKeys } from '../api/queryKeys';
import {
  BulkAction, BulkActionBar, DataTable, EmptyState, ErrorState, FilterBar, FilterBarSpacer, IconButton, LinkButton,
  PageHeader, SearchInput, StatusDot, Tabs, type Column,
} from '../components/ui';
import { useConfirm } from '../hooks/useConfirm';
import { getJobStatusVariant, isBatchLive, jobStatusLabel } from '../utils/status';
import type { Job } from '../types';

type JobStatus = 'ACTIVE' | 'PAUSED' | 'ARCHIVED';
type BulkActionKey = 'pause' | 'resume' | 'archive' | 'delete';

const BULK_ACTION_FN: Record<BulkActionKey, (jobId: number) => Promise<unknown>> = {
  pause: api.jobs.pauseJob,
  resume: api.jobs.resumeJob,
  archive: api.jobs.archiveJob,
  delete: api.jobs.deleteJob,
};

const BULK_ACTION_LABEL: Record<BulkActionKey, string> = {
  pause: 'paused',
  resume: 'resumed',
  archive: 'archived',
  delete: 'deleted',
};

const statusOf = (job: Job): JobStatus => (job.status as JobStatus) || 'ACTIVE';

export const JobsList = () => {
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<JobStatus>('ACTIVE');
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const queryClient = useQueryClient();
  const confirm = useConfirm();
  const navigate = useNavigate();

  const { data: jobs, isLoading, error, refetch } = useQuery({
    queryKey: queryKeys.jobs(),
    queryFn: () => api.jobs.getJobs(),
  });

  // Per-job resume counts and in-flight batches. Both are secondary to the
  // list itself, so a failure here just leaves those cells as "—".
  const { data: volume } = useQuery({ queryKey: queryKeys.analyticsJobVolume(), queryFn: analyticsApi.getJobVolume });
  const { data: batches } = useQuery({
    queryKey: queryKeys.batchesOverview(),
    queryFn: jobsApi.getBatchesOverview,
    refetchInterval: (query) => (query.state.data?.some((b) => isBatchLive(b.batch_status)) ? 5000 : false),
  });

  const resumeCount = useMemo(() => new Map(volume?.items.map((i) => [i.job_id, i.resume_count])), [volume]);
  const liveBatchByJob = useMemo(() => {
    const map = new Map<number, { processed: number; failed: number; total: number }>();
    for (const b of batches ?? []) {
      if (!isBatchLive(b.batch_status)) continue;
      const prev = map.get(b.job_id) ?? { processed: 0, failed: 0, total: 0 };
      map.set(b.job_id, { processed: prev.processed + b.processed, failed: prev.failed + b.failed, total: prev.total + b.total });
    }
    return map;
  }, [batches]);

  const invalidateJobs = () => queryClient.invalidateQueries({ queryKey: queryKeys.jobs() });
  const pauseMutation = useMutation({ mutationFn: (jobId: number) => api.jobs.pauseJob(jobId), onSuccess: invalidateJobs });
  const resumeMutation = useMutation({ mutationFn: (jobId: number) => api.jobs.resumeJob(jobId), onSuccess: invalidateJobs });
  const archiveMutation = useMutation({ mutationFn: (jobId: number) => api.jobs.archiveJob(jobId), onSuccess: invalidateJobs });
  const deleteMutation = useMutation({ mutationFn: (jobId: number) => api.jobs.deleteJob(jobId), onSuccess: invalidateJobs });

  const anyPending = pauseMutation.isPending || resumeMutation.isPending || archiveMutation.isPending || deleteMutation.isPending;

  const bulkMutation = useMutation({
    mutationFn: async ({ action, ids }: { action: BulkActionKey; ids: number[] }) => {
      const fn = BULK_ACTION_FN[action];
      const results = await Promise.allSettled(ids.map((id) => fn(id)));
      const failed = results.filter((r) => r.status === 'rejected').length;
      return { action, total: ids.length, failed };
    },
    onSuccess: ({ action, total, failed }) => {
      invalidateJobs();
      setSelectedIds([]);
      const past = BULK_ACTION_LABEL[action];
      if (failed === 0) {
        toast.success(`${total} job${total === 1 ? '' : 's'} ${past}.`);
      } else {
        toast.error(`${total - failed} of ${total} jobs ${past}; ${failed} failed.`);
      }
    },
    onError: () => toast.error('Bulk action failed. Please try again.'),
  });

  const handleStatusFilterChange = (status: JobStatus) => {
    setStatusFilter(status);
    setSelectedIds([]); // selection only makes sense within the currently visible tab
  };

  const handleBulkAction = async (action: BulkActionKey) => {
    if (selectedIds.length === 0) return;
    if (action === 'delete') {
      const ok = await confirm({
        title: `Delete ${selectedIds.length} job${selectedIds.length === 1 ? '' : 's'}?`,
        description: `Delete ${selectedIds.length === 1 ? 'this job' : `these ${selectedIds.length} jobs`} and all associated data? This cannot be undone.`,
        confirmLabel: 'Delete',
        danger: true,
      });
      if (!ok) return;
    }
    bulkMutation.mutate({ action, ids: selectedIds });
  };

  const handleDelete = async (job: Job) => {
    const ok = await confirm({
      title: 'Delete job?',
      description: `Delete "${job.title}" and all associated data? This cannot be undone.`,
      confirmLabel: 'Delete',
      danger: true,
    });
    if (ok) deleteMutation.mutate(job.id);
  };

  const term = searchTerm.trim().toLowerCase();
  const filteredJobs = jobs?.filter((job) => {
    const matchesSearch = !term || job.title.toLowerCase().includes(term) || job.description.toLowerCase().includes(term);
    return matchesSearch && statusOf(job) === statusFilter;
  });
  const countFor = (status: JobStatus) => jobs?.filter((j) => statusOf(j) === status).length ?? 0;

  const columns: Column<Job>[] = [
    {
      id: 'title',
      header: 'Job',
      mobile: 'title',
      skeleton: 'avatar',
      cell: (job) => (
        <div className="min-w-0">
          <Link
            to={`/jobs/${job.id}`}
            onClick={(e) => e.stopPropagation()}
            className="focus-ring rounded text-sm font-medium text-[var(--text-primary)] hover:underline"
          >
            {job.title}
          </Link>
          <p className="text-caption mt-0.5 truncate">
            {[job.department, job.location, job.employment_type].filter(Boolean).join(' · ') || 'No details'}
          </p>
        </div>
      ),
    },
    {
      id: 'status',
      header: 'Status',
      skeleton: 'badge',
      cell: (job) => (
        <StatusDot variant={getJobStatusVariant(job.status)}>{jobStatusLabel(job.status)}</StatusDot>
      ),
    },
    {
      id: 'resumes',
      header: 'Resumes',
      align: 'right',
      className: 'w-44',
      skeleton: 'text',
      cell: (job) => {
        const live = liveBatchByJob.get(job.id);
        return (
          <div className="flex flex-col items-end gap-1">
            <span className="tabular text-sm text-[var(--text-primary)]">{resumeCount.has(job.id) ? resumeCount.get(job.id) : '—'}</span>
            {live && (
              <StatusDot variant="primary" live className="text-xs text-[var(--text-secondary)]">
                Processing {live.processed + live.failed}/{live.total}
              </StatusDot>
            )}
          </div>
        );
      },
    },
    {
      id: 'summary',
      header: 'Summary',
      hideBelow: 'xl',
      mobile: 'hidden',
      className: 'w-[28%]',
      cell: (job) => <p className="line-clamp-2 text-sm text-[var(--text-secondary)]">{job.role_summary || job.description}</p>,
    },
    {
      id: 'actions',
      header: <span className="sr-only">Actions</span>,
      align: 'right',
      mobile: 'actions',
      className: 'w-36',
      skeleton: 'actions',
      cell: (job) => {
        const status = statusOf(job);
        return (
          <div className="flex items-center justify-end gap-0.5">
            {status === 'ACTIVE' && (
              <IconButton label="Pause job" tone="warning" icon={<Pause size={15} />} disabled={anyPending} onClick={() => pauseMutation.mutate(job.id)} />
            )}
            {status === 'PAUSED' && (
              <IconButton label="Resume job" tone="success" icon={<Play size={15} />} disabled={anyPending} onClick={() => resumeMutation.mutate(job.id)} />
            )}
            {status !== 'ARCHIVED' && (
              <IconButton label="Archive job" icon={<Archive size={15} />} disabled={anyPending} onClick={() => archiveMutation.mutate(job.id)} />
            )}
            <IconButton label="Delete job" tone="danger" icon={<Trash2 size={15} />} disabled={anyPending} onClick={() => handleDelete(job)} />
          </div>
        );
      },
    },
  ];

  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader
        title="Jobs"
        subtitle="Manage your open positions and screening batches."
        className="mb-6"
        actions={
          <LinkButton to="/jobs/new">
            <Plus size={14} aria-hidden="true" /> Create Job
          </LinkButton>
        }
      />

      <Tabs
        aria-label="Job status"
        value={statusFilter}
        onChange={handleStatusFilterChange}
        tabs={[
          { value: 'ACTIVE', label: 'Active', count: jobs ? countFor('ACTIVE') : null },
          { value: 'PAUSED', label: 'Paused', count: jobs ? countFor('PAUSED') : null },
          { value: 'ARCHIVED', label: 'Archived', count: jobs ? countFor('ARCHIVED') : null },
        ]}
      />

      <FilterBar className="my-4">
        <SearchInput aria-label="Search jobs" placeholder="Search jobs…" value={searchTerm} onValueChange={setSearchTerm} />
        <FilterBarSpacer />
        {jobs && filteredJobs && (
          <span className="text-caption tabular">
            {filteredJobs.length} job{filteredJobs.length === 1 ? '' : 's'}
          </span>
        )}
      </FilterBar>

      {error ? (
        <div className="rounded-lg border border-[var(--border-light)] bg-[var(--bg-surface)]">
          <ErrorState title="Failed to load jobs" message={(error as { message?: string })?.message || 'An unexpected error occurred'} onRetry={() => refetch()} />
        </div>
      ) : (
        <DataTable
          aria-label="Jobs"
          rows={filteredJobs ?? []}
          columns={columns}
          getRowId={(job) => job.id}
          isLoading={isLoading}
          onRowClick={(job) => navigate(`/jobs/${job.id}`)}
          selection={{ selected: selectedIds, onChange: (ids) => setSelectedIds(ids as number[]) }}
          empty={
            !jobs?.length ? (
              <EmptyState
                icon={<Briefcase size={20} />}
                title="No jobs yet"
                description="Create a job, then upload resumes to start screening."
                action={<LinkButton to="/jobs/new" variant="secondary">Create first job</LinkButton>}
              />
            ) : term ? (
              <EmptyState
                icon={<Search size={20} />}
                title="No jobs match your search"
                description="Try different search terms, or switch tabs."
                action={<button type="button" onClick={() => setSearchTerm('')} className="focus-ring rounded text-sm font-medium text-[var(--color-primary-600)] hover:underline">Clear search</button>}
              />
            ) : (
              <EmptyState icon={<Briefcase size={20} />} title={`No ${statusFilter.toLowerCase()} jobs`} description="Jobs you move here will show up in this tab." />
            )
          }
        />
      )}

      <BulkActionBar count={selectedIds.length} noun="job" onClear={() => setSelectedIds([])}>
        {statusFilter === 'ACTIVE' && (
          <BulkAction onClick={() => handleBulkAction('pause')} disabled={bulkMutation.isPending}>
            <Pause size={15} aria-hidden="true" /> Pause
          </BulkAction>
        )}
        {statusFilter === 'PAUSED' && (
          <BulkAction onClick={() => handleBulkAction('resume')} disabled={bulkMutation.isPending}>
            <Play size={15} aria-hidden="true" /> Resume
          </BulkAction>
        )}
        {statusFilter !== 'ARCHIVED' && (
          <BulkAction onClick={() => handleBulkAction('archive')} disabled={bulkMutation.isPending}>
            <Archive size={15} aria-hidden="true" /> Archive
          </BulkAction>
        )}
        <BulkAction onClick={() => handleBulkAction('delete')} disabled={bulkMutation.isPending}>
          <Trash2 size={15} aria-hidden="true" /> Delete
        </BulkAction>
      </BulkActionBar>
    </div>
  );
};
