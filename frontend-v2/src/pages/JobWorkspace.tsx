
import { useParams, Link, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Upload, Users, ChevronLeft, Pause, Play, Archive, Trash2 } from 'lucide-react';
import { api } from '../api';
import { queryKeys } from '../api/queryKeys';
import { Button, Card, EmptyState, Spinner, Badge, PageHeader } from '../components/ui';
import { useConfirm } from '../hooks/useConfirm';

export const JobWorkspace = () => {
  const { id } = useParams<{ id: string }>();
  const jobId = parseInt(id || '0', 10);
  const confirm = useConfirm();

  const { data: job, isLoading: jobLoading, error: jobError } = useQuery({
    queryKey: ['job', jobId],
    queryFn: () => api.jobs.getJob(jobId),
    enabled: jobId > 0
  });

  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const pauseMutation = useMutation({
    mutationFn: () => api.jobs.pauseJob(jobId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['job', jobId] });
      queryClient.invalidateQueries({ queryKey: queryKeys.jobs() });
    }
  });

  const resumeMutation = useMutation({
    mutationFn: () => api.jobs.resumeJob(jobId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['job', jobId] });
      queryClient.invalidateQueries({ queryKey: queryKeys.jobs() });
    }
  });

  const archiveMutation = useMutation({
    mutationFn: () => api.jobs.archiveJob(jobId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['job', jobId] });
      queryClient.invalidateQueries({ queryKey: queryKeys.jobs() });
    }
  });

  const deleteMutation = useMutation({
    mutationFn: () => api.jobs.deleteJob(jobId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.jobs() });
      navigate('/jobs');
    }
  });

  const { data: progress } = useQuery({
    queryKey: ['job-progress', jobId],
    queryFn: () => api.jobs.getJobProgress(jobId),
    enabled: jobId > 0
  });

  if (jobLoading) {
    return (
      <div className="flex justify-center p-16">
        <Spinner size={32} />
      </div>
    );
  }

  if (jobError || !job) {
    return (
      <EmptyState
        title="Job not found"
        description="The job you are looking for does not exist or failed to load."
        action={<Link to="/jobs"><Button variant="secondary">Back to Jobs</Button></Link>}
      />
    );
  }

  return (
    <div className="max-w-6xl mx-auto py-4">
      <Link to="/jobs" className="transition-base focus-ring inline-flex items-center text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] mb-6 font-medium">
        <ChevronLeft size={16} className="mr-1" /> Back to Jobs
      </Link>

      <PageHeader
        className="mb-8"
        title={
          <span className="flex items-center gap-3">
            {job.title}
            <Badge variant={job.status === 'PAUSED' ? 'warning' : job.status === 'ARCHIVED' ? 'neutral' : 'success'}>
              {job.status || 'ACTIVE'}
            </Badge>
          </span>
        }
        subtitle={
          <span className="flex flex-wrap gap-4 font-medium">
            {job.department && <span>{job.department}</span>}
            {job.location && <span>&bull; {job.location}</span>}
            {job.employment_type && <span>&bull; {job.employment_type}</span>}
          </span>
        }
        actions={
          <>
            {(!job.status || job.status === 'ACTIVE') && (
              <Button variant="secondary" onClick={() => pauseMutation.mutate()} disabled={pauseMutation.isPending}>
                <Pause size={16} className="mr-2" /> Pause
              </Button>
            )}
            {job.status === 'PAUSED' && (
              <Button variant="secondary" onClick={() => resumeMutation.mutate()} disabled={resumeMutation.isPending}>
                <Play size={16} className="mr-2" /> Resume
              </Button>
            )}
            {job.status !== 'ARCHIVED' && (
              <Button variant="secondary" onClick={() => archiveMutation.mutate()} disabled={archiveMutation.isPending}>
                <Archive size={16} className="mr-2" /> Archive
              </Button>
            )}
            <Button variant="ghost" className="text-[var(--color-danger-600)] hover:text-[var(--color-danger-600)] hover:bg-[var(--color-danger-subtle-bg)]" onClick={async () => {
              const ok = await confirm({
                title: 'Delete job?',
                description: 'Are you sure you want to delete this job and all associated data? This cannot be undone.',
                confirmLabel: 'Delete',
                danger: true,
              });
              if (ok) deleteMutation.mutate();
            }} disabled={deleteMutation.isPending}>
              <Trash2 size={16} className="mr-2" /> Delete
            </Button>

            <div className="w-px h-8 bg-[var(--border-light)] mx-2 hidden sm:block"></div>

            <Link to={`/jobs/${jobId}/upload`}>
              <Button variant="secondary">
                <Upload size={16} className="mr-2" /> Upload Resumes
              </Button>
            </Link>
            <Link to={`/jobs/${jobId}/candidates`}>
              <Button variant="primary">
                <Users size={16} className="mr-2" /> View Candidates
              </Button>
            </Link>
          </>
        }
      />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        <Card className="p-6 text-center">
          <div className="text-sm font-medium text-[var(--text-secondary)] mb-2">Total Resumes</div>
          <div className="text-3xl font-bold text-[var(--text-primary)]">{progress?.batches?.reduce((sum, b) => sum + (b.total || 0), 0) ?? '-'}</div>
        </Card>
        <Card className="p-6 text-center">
          <div className="text-sm font-medium text-[var(--text-secondary)] mb-2">Processed</div>
          <div className="text-3xl font-bold text-[var(--text-primary)]">{progress?.batches?.reduce((sum, b) => sum + (b.completed || 0), 0) ?? '-'}</div>
        </Card>
        <Card className="p-6 text-center bg-[var(--color-danger-subtle-bg)]">
          <div className="text-sm font-medium text-[var(--color-danger-subtle-text)] mb-2">Failed</div>
          <div className="text-3xl font-bold text-[var(--color-danger-subtle-text)]">{progress?.batches?.reduce((sum, b) => sum + (b.failed || 0), 0) ?? '-'}</div>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2 flex flex-col gap-8">
          <section>
            <h3 className="text-section-heading mb-4 pb-2 border-b border-[var(--border-light)]">Job Description</h3>
            <div className="whitespace-pre-wrap leading-relaxed text-[var(--text-secondary)]">
              {job.description}
            </div>
          </section>
        </div>

        <div className="flex flex-col gap-8">
          <section>
            <h3 className="text-card-title mb-4 pb-2 border-b border-[var(--border-light)]">Required Skills</h3>
            {job.required_skills && job.required_skills.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {job.required_skills.map((skill, index) => (
                  <Badge key={index} variant="success" className="text-sm px-3 py-1">
                    {skill}
                  </Badge>
                ))}
              </div>
            ) : <span className="text-[var(--text-tertiary)] italic">None specified</span>}
          </section>

          <section>
            <h3 className="text-card-title mb-4 pb-2 border-b border-[var(--border-light)]">Preferred Skills</h3>
            {job.preferred_skills && job.preferred_skills.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {job.preferred_skills.map((skill, index) => (
                  <Badge key={index} variant="neutral" className="text-sm px-3 py-1">
                    {skill}
                  </Badge>
                ))}
              </div>
            ) : <span className="text-[var(--text-tertiary)] italic">None specified</span>}
          </section>

          <section>
            <h3 className="text-card-title mb-4 pb-2 border-b border-[var(--border-light)]">Requirements</h3>
            {job.requirements && job.requirements.length > 0 ? (
              <ul className="list-disc pl-5 space-y-2 text-[var(--text-secondary)]">
                {job.requirements.map((req, index) => (
                  <li key={index}>{req}</li>
                ))}
              </ul>
            ) : <span className="text-[var(--text-tertiary)] italic">None specified</span>}
          </section>
        </div>
      </div>
    </div>
  );
};
