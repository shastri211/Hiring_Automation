import { useQuery } from '@tanstack/react-query';
import { api } from '../api';
import { Card, EmptyState, PageHeader, Skeleton } from '../components/ui';
import { ArrowRight, Briefcase, Plus, Loader2 } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Button } from '../components/ui';
import type { Job } from '../types';

export const Dashboard = () => {
  const { data: jobs, isLoading, error } = useQuery({
    queryKey: ['jobs'],
    queryFn: api.jobs.getJobs,
  });

  return (
    <div className="max-w-6xl mx-auto">
      <PageHeader
        title="Overview"
        subtitle="Welcome to RecruitPro"
        className="mb-8"
        actions={
          <Link to="/jobs/new">
            <Button variant="primary">
              <Plus size={16} className="mr-2" />
              New Job
            </Button>
          </Link>
        }
      />

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
        <Card className="p-6">
          <div className="flex items-center gap-3 mb-2 text-[var(--text-secondary)]">
            <Briefcase size={20} />
            <span className="text-sm font-medium">Total Jobs</span>
          </div>
          <div className="text-3xl font-bold text-[var(--text-primary)]">
            {isLoading ? <Loader2 className="animate-spin" size={24} /> : jobs?.length || 0}
          </div>
        </Card>

        <Card className="flex items-center justify-between gap-4 p-6">
          <div>
            <p className="text-sm font-medium text-[var(--text-secondary)]">Ready to screen?</p>
            <p className="mt-1 text-sm text-[var(--text-secondary)]">Create a role, then upload resumes to begin reviewing candidates.</p>
          </div>
          <Link to="/jobs/new" className="focus-ring transition-base shrink-0 rounded-md text-[var(--color-primary-600)] hover:text-[var(--color-primary-700)]" aria-label="Create a new job">
            <ArrowRight size={20} aria-hidden="true" />
          </Link>
        </Card>
      </div>

      <div>
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-section-heading">Recent Jobs</h3>
          <Link to="/jobs" className="focus-ring transition-base text-[var(--color-primary-600)] text-sm font-medium hover:text-[var(--color-primary-700)] rounded">View All &rarr;</Link>
        </div>

        {isLoading ? (
          <div className="flex flex-col gap-3" aria-hidden="true">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-[76px] w-full rounded-xl" />
            ))}
          </div>
        ) : error ? (
          <div className="p-8 text-center text-[var(--color-danger-600)] bg-[var(--color-danger-subtle-bg)] rounded-xl">
            Failed to load jobs. Please try again.
          </div>
        ) : jobs?.length === 0 ? (
          <EmptyState
            icon={<Briefcase size={48} />}
            title="No jobs found"
            description="Get started by creating your first job posting."
            action={<Link to="/jobs/new"><Button variant="primary">Create Job</Button></Link>}
          />
        ) : (
          <div className="flex flex-col gap-3">
            {jobs?.slice(0, 5).map((job: Job) => (
              <Link
                to={`/jobs/${job.id}`}
                key={job.id}
                className="transition-base focus-ring group block rounded-xl border border-[var(--border-light)] bg-[var(--bg-surface)] p-5 hover:border-[var(--border-focus)] hover:shadow-[var(--shadow-sm)]"
              >
                <div className="flex justify-between items-start">
                  <div>
                    <h4 className="text-card-title transition-base mb-1 group-hover:text-[var(--color-primary-700)]">{job.title}</h4>
                    <div className="flex gap-4 text-body">
                      {job.department && <span>{job.department}</span>}
                      {job.location && <span>&bull; {job.location}</span>}
                    </div>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
