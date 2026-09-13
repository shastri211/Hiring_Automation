import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Briefcase, Plus, Search, Pause, Play, Archive, Trash2 } from 'lucide-react';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';
import { api } from '../api';
import { queryKeys } from '../api/queryKeys';
import { Button, Card, CardHeader, CardTitle, CardContent, CardFooter, Badge, EmptyState, Spinner, Input } from '../components/ui';
import { useConfirm } from '../hooks/useConfirm';
import type { Job } from '../types';

type BulkAction = 'pause' | 'resume' | 'archive' | 'delete';

const BULK_ACTION_FN: Record<BulkAction, (jobId: number) => Promise<unknown>> = {
  pause: api.jobs.pauseJob,
  resume: api.jobs.resumeJob,
  archive: api.jobs.archiveJob,
  delete: api.jobs.deleteJob,
};

const BULK_ACTION_LABEL: Record<BulkAction, { verb: string; pastTense: string }> = {
  pause: { verb: 'Pause', pastTense: 'paused' },
  resume: { verb: 'Resume', pastTense: 'resumed' },
  archive: { verb: 'Archive', pastTense: 'archived' },
  delete: { verb: 'Delete', pastTense: 'deleted' },
};

export const JobsList = () => {
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<'ACTIVE' | 'PAUSED' | 'ARCHIVED'>('ACTIVE');
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const queryClient = useQueryClient();
  const confirm = useConfirm();

  const { data: jobs, isLoading, error } = useQuery({
    queryKey: queryKeys.jobs(),
    queryFn: () => api.jobs.getJobs()
  });

  const pauseMutation = useMutation({
    mutationFn: (jobId: number) => api.jobs.pauseJob(jobId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.jobs() }),
  });

  const resumeMutation = useMutation({
    mutationFn: (jobId: number) => api.jobs.resumeJob(jobId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.jobs() }),
  });

  const archiveMutation = useMutation({
    mutationFn: (jobId: number) => api.jobs.archiveJob(jobId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.jobs() }),
  });

  const deleteMutation = useMutation({
    mutationFn: (jobId: number) => api.jobs.deleteJob(jobId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.jobs() }),
  });

  const anyPending = pauseMutation.isPending || resumeMutation.isPending || archiveMutation.isPending || deleteMutation.isPending;

  const bulkMutation = useMutation({
    mutationFn: async ({ action, ids }: { action: BulkAction; ids: number[] }) => {
      const fn = BULK_ACTION_FN[action];
      const results = await Promise.allSettled(ids.map((id) => fn(id)));
      const failed = results.filter((r) => r.status === 'rejected').length;
      return { action, total: ids.length, failed };
    },
    onSuccess: ({ action, total, failed }) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.jobs() });
      setSelectedIds(new Set());
      const { pastTense } = BULK_ACTION_LABEL[action];
      if (failed === 0) {
        toast.success(`${total} job${total === 1 ? '' : 's'} ${pastTense}.`);
      } else {
        toast.error(`${total - failed} of ${total} jobs ${pastTense}; ${failed} failed.`);
      }
    },
    onError: () => toast.error('Bulk action failed. Please try again.'),
  });

  const handleStatusFilterChange = (status: 'ACTIVE' | 'PAUSED' | 'ARCHIVED') => {
    setStatusFilter(status);
    setSelectedIds(new Set()); // selection only makes sense within the currently visible tab
  };

  const toggleSelected = (jobId: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(jobId)) next.delete(jobId);
      else next.add(jobId);
      return next;
    });
  };

  const handleBulkAction = async (action: BulkAction) => {
    const ids = Array.from(selectedIds);
    if (ids.length === 0) return;
    if (action === 'delete') {
      const ok = await confirm({
        title: `Delete ${ids.length} job${ids.length === 1 ? '' : 's'}?`,
        description: `Delete ${ids.length === 1 ? 'this job' : `these ${ids.length} jobs`} and all associated data? This cannot be undone.`,
        confirmLabel: 'Delete',
        danger: true,
      });
      if (!ok) return;
    }
    bulkMutation.mutate({ action, ids });
  };

  const filteredJobs = jobs?.filter(job => {
    const term = searchTerm.toLowerCase();
    const matchesSearch = job.title.toLowerCase().includes(term) || job.description.toLowerCase().includes(term);
    const matchesStatus = (job.status || 'ACTIVE') === statusFilter;
    return matchesSearch && matchesStatus;
  });

  if (isLoading) {
    return (
      <div className="flex justify-center p-16">
        <Spinner size={32} />
      </div>
    );
  }

  if (error) {
    return (
      <EmptyState 
        title="Failed to load jobs"
        description={(error as any)?.message || 'An unexpected error occurred'}
      />
    );
  }

  return (
    <div className="max-w-6xl mx-auto">
      <div className="flex justify-between items-start mb-6 flex-wrap gap-4">
        <div>
          <h2 className="text-2xl font-semibold text-slate-900">Jobs</h2>
          <p className="text-slate-500 mt-1">Manage your open positions and screening batches.</p>
        </div>
        <div className="flex items-center gap-4">
          <div className="relative">
            <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <Input 
              type="text" 
              placeholder="Search jobs..." 
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-64 pl-10"
            />
          </div>
          <Link to="/jobs/new">
            <Button variant="primary">
              <Plus size={16} className="mr-2" />
              Create Job
            </Button>
          </Link>
        </div>
      </div>

      <div className="flex items-center gap-2 border-b border-slate-200 mb-6 pb-2 overflow-x-auto">
        {(['ACTIVE', 'PAUSED', 'ARCHIVED'] as const).map(status => (
          <button
            key={status}
            onClick={() => handleStatusFilterChange(status)}
            className={`px-4 py-2 text-sm font-medium rounded-t-md border-b-2 transition-colors ${
              statusFilter === status 
                ? 'border-[var(--primary)] text-[var(--primary)]' 
                : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
            }`}
          >
            {status.charAt(0) + status.slice(1).toLowerCase()}
            <span className="ml-2 text-xs py-0.5 px-2 rounded-full bg-slate-100 text-slate-600">
              {jobs?.filter(j => (j.status || 'ACTIVE') === status).length || 0}
            </span>
          </button>
        ))}
      </div>

      {!jobs?.length ? (
        <EmptyState 
          icon={<Briefcase size={48} />}
          title="No jobs found"
          description="Get started by creating a new job."
          action={
            <Link to="/jobs/new">
              <Button variant="secondary">Create First Job</Button>
            </Link>
          }
        />
      ) : !filteredJobs?.length ? (
         <EmptyState 
          icon={<Search size={48} />}
          title="No jobs match your search"
          description="Try adjusting your search terms or switch tabs."
          action={
            <Button variant="ghost" onClick={() => setSearchTerm('')}>Clear Search</Button>
          }
        />
      ) : (
        <>
          {selectedIds.size > 0 && (
            <div className="bg-indigo-50 border border-indigo-200 p-4 rounded-xl mb-4 flex items-center justify-between flex-wrap gap-3">
              <div className="flex items-center gap-4">
                <span className="text-indigo-800 font-medium text-sm">{selectedIds.size} job{selectedIds.size === 1 ? '' : 's'} selected</span>
                <div className="h-4 w-px bg-indigo-200" />
                <button onClick={() => setSelectedIds(new Set())} className="text-sm text-indigo-600 hover:text-indigo-800">Clear</button>
              </div>
              <div className="flex gap-2 flex-wrap">
                {statusFilter === 'ACTIVE' && (
                  <button onClick={() => handleBulkAction('pause')} disabled={bulkMutation.isPending} className="px-3 py-1.5 bg-white text-amber-700 border border-amber-200 rounded text-sm hover:bg-amber-50 focus-ring font-medium disabled:opacity-50">Pause</button>
                )}
                {statusFilter === 'PAUSED' && (
                  <button onClick={() => handleBulkAction('resume')} disabled={bulkMutation.isPending} className="px-3 py-1.5 bg-white text-green-700 border border-green-200 rounded text-sm hover:bg-green-50 focus-ring font-medium disabled:opacity-50">Resume</button>
                )}
                {statusFilter !== 'ARCHIVED' && (
                  <button onClick={() => handleBulkAction('archive')} disabled={bulkMutation.isPending} className="px-3 py-1.5 bg-white text-slate-700 border border-slate-200 rounded text-sm hover:bg-slate-50 focus-ring font-medium disabled:opacity-50">Archive</button>
                )}
                <button onClick={() => handleBulkAction('delete')} disabled={bulkMutation.isPending} className="px-3 py-1.5 bg-white text-rose-700 border border-rose-200 rounded text-sm hover:bg-rose-50 focus-ring font-medium disabled:opacity-50">Delete</button>
              </div>
            </div>
          )}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredJobs.map(job => (
              <JobCard
                key={job.id}
                job={job}
                isPending={anyPending}
                isSelected={selectedIds.has(job.id)}
                onToggleSelected={() => toggleSelected(job.id)}
                onPause={() => pauseMutation.mutate(job.id)}
                onResume={() => resumeMutation.mutate(job.id)}
                onArchive={() => archiveMutation.mutate(job.id)}
                onDelete={async () => {
                  const ok = await confirm({
                    title: 'Delete job?',
                    description: `Delete "${job.title}" and all associated data? This cannot be undone.`,
                    confirmLabel: 'Delete',
                    danger: true,
                  });
                  if (ok) deleteMutation.mutate(job.id);
                }}
              />
            ))}
          </div>
        </>
      )}
    </div>
  );
};

// -- Job Card ------------------------------------------------------------------

interface JobCardProps {
  job: Job;
  isPending: boolean;
  isSelected: boolean;
  onToggleSelected: () => void;
  onPause: () => void;
  onResume: () => void;
  onArchive: () => void;
  onDelete: () => void;
}

const JobCard = ({ job, isPending, isSelected, onToggleSelected, onPause, onResume, onArchive, onDelete }: JobCardProps) => {
  const status = job.status || 'ACTIVE';

  return (
    <Card className={`flex flex-col h-full transition-colors ${isSelected ? 'border-indigo-300 ring-1 ring-indigo-200' : 'hover:border-[var(--border-focus)]'}`}>
      <CardHeader>
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-start gap-3 flex-1 min-w-0">
            <input
              type="checkbox"
              checked={isSelected}
              onChange={onToggleSelected}
              aria-label={`Select job "${job.title}"`}
              className="mt-1 rounded border-slate-300 text-indigo-600 focus:ring-indigo-600 shrink-0"
            />
            <CardTitle className="flex-1 min-w-0">{job.title}</CardTitle>
          </div>
          {status === 'PAUSED' && (
            <Badge variant="warning" className="shrink-0">Paused</Badge>
          )}
          {status === 'ARCHIVED' && (
            <Badge variant="neutral" className="shrink-0">Archived</Badge>
          )}
        </div>
        <div className="flex flex-wrap gap-2 mt-2">
           {job.department && <Badge>{job.department}</Badge>}
           {job.location && <Badge variant="neutral">{job.location}</Badge>}
           {job.employment_type && <Badge variant="primary">{job.employment_type}</Badge>}
        </div>
      </CardHeader>
      <CardContent className="flex-1 py-2">
        <p className="text-slate-500 text-sm line-clamp-3">
          {job.description}
        </p>
      </CardContent>
      <CardFooter className="flex items-center justify-between gap-2 flex-wrap">
        {/* Lifecycle actions */}
        <div className="flex items-center gap-1">
          {status === 'ACTIVE' && (
            <button
              onClick={onPause}
              disabled={isPending}
              title="Pause job"
              className="p-1.5 rounded text-slate-400 hover:text-amber-600 hover:bg-amber-50 transition-colors disabled:opacity-50"
            >
              <Pause size={15} />
            </button>
          )}
          {status === 'PAUSED' && (
            <button
              onClick={onResume}
              disabled={isPending}
              title="Resume job"
              className="p-1.5 rounded text-slate-400 hover:text-green-600 hover:bg-green-50 transition-colors disabled:opacity-50"
            >
              <Play size={15} />
            </button>
          )}
          {status !== 'ARCHIVED' && (
            <button
              onClick={onArchive}
              disabled={isPending}
              title="Archive job"
              className="p-1.5 rounded text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors disabled:opacity-50"
            >
              <Archive size={15} />
            </button>
          )}
          <button
            onClick={onDelete}
            disabled={isPending}
            title="Delete job"
            className="p-1.5 rounded text-slate-400 hover:text-red-600 hover:bg-red-50 transition-colors disabled:opacity-50"
          >
            <Trash2 size={15} />
          </button>
        </div>
        <Link to={`/jobs/${job.id}`} className="focus-ring rounded-md inline-block">
          <Button variant="secondary" size="sm" tabIndex={-1}>View Workspace</Button>
        </Link>
      </CardFooter>
    </Card>
  );
};
