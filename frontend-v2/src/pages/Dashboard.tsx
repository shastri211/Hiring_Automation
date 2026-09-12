import { useQuery } from '@tanstack/react-query';
import { api } from '../api';
import { EmptyState } from '../components/ui';
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
      <div className="flex justify-between items-center mb-8">
        <div>
          <h2 className="text-2xl font-semibold text-slate-900">Overview</h2>
          <p className="text-slate-500 mt-1">Welcome to RecruitPro</p>
        </div>
        <Link to="/jobs/new">
          <Button variant="primary">
            <Plus size={16} className="mr-2" />
            New Job
          </Button>
        </Link>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
          <div className="flex items-center gap-3 mb-2 text-slate-500">
            <Briefcase size={20} />
            <span className="text-sm font-medium">Total Jobs</span>
          </div>
          <div className="text-3xl font-bold text-slate-900">
            {isLoading ? <Loader2 className="animate-spin" size={24} /> : jobs?.length || 0}
          </div>
        </div>
        
        <div className="flex items-center justify-between gap-4 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <div>
            <p className="text-sm font-medium text-slate-500">Ready to screen?</p>
            <p className="mt-1 text-sm text-slate-700">Create a role, then upload resumes to begin reviewing candidates.</p>
          </div>
          <Link to="/jobs/new" className="focus-ring shrink-0 rounded-md text-[var(--color-primary-600)] hover:text-[var(--color-primary-700)]" aria-label="Create a new job">
            <ArrowRight size={20} aria-hidden="true" />
          </Link>
        </div>
      </div>

      <div>
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-xl font-semibold text-slate-900 tracking-tight">Recent Jobs</h3>
          <Link to="/jobs" className="text-[var(--color-primary-600)] text-sm font-medium hover:text-[var(--color-primary-700)] focus-ring rounded">View All &rarr;</Link>
        </div>

        {isLoading ? (
          <div className="flex justify-center py-12 text-slate-400">
            <Loader2 className="animate-spin" size={32} />
          </div>
        ) : error ? (
          <div className="p-8 text-center text-red-600 bg-red-50 rounded-xl">
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
                className="block p-5 bg-white border border-slate-200 rounded-xl hover:border-[var(--border-focus)] hover:shadow-sm focus-ring transition-all group"
              >
                <div className="flex justify-between items-start">
                  <div>
                    <h4 className="text-lg font-semibold text-slate-900 mb-1 group-hover:text-[var(--color-primary-700)] transition-colors">{job.title}</h4>
                    <div className="flex gap-4 text-sm text-slate-500">
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
