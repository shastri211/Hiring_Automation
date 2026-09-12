import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { formatDistanceToNow } from 'date-fns';
import { Loader2, Calendar, ChevronLeft, ChevronRight } from 'lucide-react';
import { jobsApi } from '../api/jobs';
import { queryKeys } from '../api/queryKeys';
import { useGlobalInterviews } from '../hooks/useGlobalInterviews';
import { Badge, Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '../components/ui';
import { getInterviewStatusBadgeVariant } from '../utils/status';

const PAGE_SIZE = 20;

const STATUS_OPTIONS = ['PENDING', 'SCHEDULED', 'IN_PROGRESS', 'COMPLETED', 'FAILED'];

export const GlobalInterviews = () => {
  const navigate = useNavigate();
  const [status, setStatus] = useState<string | undefined>(undefined);
  const [jobId, setJobId] = useState<number | undefined>(undefined);
  const [page, setPage] = useState(1);

  const { data: jobs } = useQuery({ queryKey: queryKeys.jobs(), queryFn: jobsApi.getJobs });

  const params = { status, job_id: jobId, page, page_size: PAGE_SIZE };
  const { data, isLoading, isError, error } = useGlobalInterviews(params);

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="flex items-center space-x-3 mb-8">
        <div className="w-10 h-10 bg-[var(--color-primary-subtle-bg)] text-[var(--color-primary-subtle-text)] rounded-lg flex items-center justify-center">
          <Calendar className="w-6 h-6" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">All Interviews</h1>
          <p className="text-sm text-[var(--text-secondary)]">Every candidate interview scheduled or completed across all jobs.</p>
        </div>
      </div>

      <div className="flex flex-wrap justify-end gap-3 mb-4">
        <div className="w-48">
          <Select
            value={status || 'all'}
            onValueChange={(value) => { setStatus(value === 'all' ? undefined : value); setPage(1); }}
          >
            <SelectTrigger><SelectValue placeholder="All Statuses" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Statuses</SelectItem>
              {STATUS_OPTIONS.map((s) => (
                <SelectItem key={s} value={s}>{s.replace(/_/g, ' ')}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="w-56">
          <Select
            value={jobId ? String(jobId) : 'all'}
            onValueChange={(value) => { setJobId(value === 'all' ? undefined : Number(value)); setPage(1); }}
          >
            <SelectTrigger><SelectValue placeholder="All Jobs" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Jobs</SelectItem>
              {jobs?.map((job) => (
                <SelectItem key={job.id} value={String(job.id)}>{job.title}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="bg-[var(--bg-surface)] border border-[var(--border-light)] rounded-xl shadow-sm overflow-hidden">
        {isLoading && !data ? (
          <div className="flex justify-center items-center h-64">
            <Loader2 className="w-8 h-8 animate-spin text-[var(--color-primary-500)]" />
          </div>
        ) : isError ? (
          <div className="p-8 text-center text-[var(--color-danger-600)]">
            Failed to load interviews{error instanceof Error ? `: ${error.message}` : '.'}
          </div>
        ) : !data || data.items.length === 0 ? (
          <div className="text-center py-20">
            <Calendar className="w-12 h-12 text-[var(--text-tertiary)] mx-auto mb-4" />
            <h3 className="text-lg font-medium text-[var(--text-primary)] mb-1">No interviews yet</h3>
            <p className="text-[var(--text-secondary)]">Trigger an interview from a candidate's profile to see it appear here.</p>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-[var(--bg-app)] border-b border-[var(--border-light)] text-[var(--text-secondary)]">
                  <tr>
                    <th className="px-6 py-4 font-medium">Candidate</th>
                    <th className="px-6 py-4 font-medium">Job</th>
                    <th className="px-6 py-4 font-medium">Status</th>
                    <th className="px-6 py-4 font-medium">Updated</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border-light)]">
                  {data.items.map((row) => (
                    <tr
                      key={row.id}
                      className="hover:bg-[var(--bg-hover)] transition-colors cursor-pointer"
                      onClick={() => navigate(`/interview/${row.job_id}/${row.resume_id}`)}
                    >
                      <td className="px-6 py-4 font-medium text-[var(--text-primary)]">
                        {row.candidate_name || row.resume_filename || `Resume #${row.resume_id}`}
                      </td>
                      <td className="px-6 py-4 text-[var(--text-secondary)]">{row.job_title}</td>
                      <td className="px-6 py-4">
                        <Badge variant={getInterviewStatusBadgeVariant(row.status)}>{row.status.replace(/_/g, ' ')}</Badge>
                      </td>
                      <td className="px-6 py-4 text-[var(--text-tertiary)] text-xs">
                        {row.updated_at ? formatDistanceToNow(new Date(row.updated_at), { addSuffix: true }) : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="px-6 py-4 border-t border-[var(--border-light)] bg-[var(--bg-app)] flex items-center justify-between text-sm text-[var(--text-secondary)]">
              <span>Showing {(page - 1) * PAGE_SIZE + 1}-{Math.min(page * PAGE_SIZE, data.total)} of {data.total}</span>
              <div className="flex gap-1">
                <button disabled={page === 1} onClick={() => setPage((p) => p - 1)} className="p-1 rounded hover:bg-[var(--bg-hover)] disabled:opacity-50 text-[var(--text-secondary)] focus-ring">
                  <ChevronLeft className="w-5 h-5" />
                </button>
                <button disabled={page * PAGE_SIZE >= data.total} onClick={() => setPage((p) => p + 1)} className="p-1 rounded hover:bg-[var(--bg-hover)] disabled:opacity-50 text-[var(--text-secondary)] focus-ring">
                  <ChevronRight className="w-5 h-5" />
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
};
