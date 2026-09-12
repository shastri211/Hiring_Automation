import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import { Loader2, MessageSquare, ChevronLeft, ChevronRight } from 'lucide-react';
import { jobsApi } from '../api/jobs';
import { queryKeys } from '../api/queryKeys';
import { useInterviewAnalysisSummary, useInterviewAnalysisList } from '../hooks/useInterviewAnalysis';
import { Card, CardContent, Badge, Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '../components/ui';

const PAGE_SIZE = 20;

function formatDuration(seconds?: number | null): string {
  if (seconds == null) return '—';
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}

export const InterviewAnalysis = () => {
  const [jobId, setJobId] = useState<number | undefined>(undefined);
  const [page, setPage] = useState(1);

  const { data: jobs } = useQuery({ queryKey: queryKeys.jobs(), queryFn: jobsApi.getJobs });

  const summaryQuery = useInterviewAnalysisSummary(jobId);
  const listQuery = useInterviewAnalysisList({ job_id: jobId, page, page_size: PAGE_SIZE });

  const dispositionData = useMemo(() => {
    const breakdown = summaryQuery.data?.disposition_breakdown || {};
    return Object.entries(breakdown).map(([disposition, count]) => ({ disposition, count }));
  }, [summaryQuery.data]);

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-8 flex-wrap gap-4">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 bg-[var(--color-primary-subtle-bg)] text-[var(--color-primary-subtle-text)] rounded-lg flex items-center justify-center">
            <MessageSquare className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-[var(--text-primary)]">Interview Analysis</h1>
            <p className="text-sm text-[var(--text-secondary)]">Outcomes and dispositions from completed candidate interviews.</p>
          </div>
        </div>
        <div className="w-56">
          <Select value={jobId ? String(jobId) : 'all'} onValueChange={(v) => { setJobId(v === 'all' ? undefined : Number(v)); setPage(1); }}>
            <SelectTrigger><SelectValue placeholder="All Jobs" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Jobs</SelectItem>
              {jobs?.map((job) => <SelectItem key={job.id} value={String(job.id)}>{job.title}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
      </div>

      {summaryQuery.isLoading ? (
        <div className="flex justify-center py-12"><Loader2 className="w-8 h-8 animate-spin text-[var(--color-primary-500)]" /></div>
      ) : summaryQuery.isError ? (
        <div className="p-6 text-center text-[var(--color-danger-600)] bg-[var(--bg-surface)] border border-[var(--border-light)] rounded-xl mb-8">
          Failed to load interview analysis summary.
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
            <Card><CardContent className="p-5">
              <div className="text-sm text-[var(--text-secondary)] mb-1">Completion Rate</div>
              <div className="text-2xl font-bold text-[var(--text-primary)]">{Math.round((summaryQuery.data?.completion_rate ?? 0) * 100)}%</div>
            </CardContent></Card>
            <Card><CardContent className="p-5">
              <div className="text-sm text-[var(--text-secondary)] mb-1">Avg Call Duration</div>
              <div className="text-2xl font-bold text-[var(--text-primary)]">{formatDuration(summaryQuery.data?.avg_call_duration_seconds)}</div>
            </CardContent></Card>
            <Card><CardContent className="p-5">
              <div className="text-sm text-[var(--text-secondary)] mb-1">Total Interviews</div>
              <div className="text-2xl font-bold text-[var(--text-primary)]">{summaryQuery.data?.total_interviews ?? 0}</div>
              <div className="text-xs text-[var(--text-tertiary)] mt-1">{summaryQuery.data?.completed_interviews ?? 0} completed</div>
            </CardContent></Card>
          </div>

          <Card className="mb-8">
            <CardContent className="p-6">
              <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-4">Disposition Breakdown</h3>
              {dispositionData.length === 0 ? (
                <p className="text-sm text-[var(--text-tertiary)] italic py-8 text-center">
                  No completed interviews with recorded dispositions yet.
                </p>
              ) : (
                <div style={{ width: '100%', height: 260 }}>
                  <ResponsiveContainer>
                    <BarChart data={dispositionData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--border-light)" />
                      <XAxis dataKey="disposition" tick={{ fontSize: 12 }} />
                      <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
                      <Tooltip />
                      <Bar dataKey="count" fill="#6366f1" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}

      <div className="bg-[var(--bg-surface)] border border-[var(--border-light)] rounded-xl shadow-sm overflow-hidden">
        {listQuery.isLoading && !listQuery.data ? (
          <div className="flex justify-center items-center h-64">
            <Loader2 className="w-8 h-8 animate-spin text-[var(--color-primary-500)]" />
          </div>
        ) : listQuery.isError ? (
          <div className="p-8 text-center text-[var(--color-danger-600)]">Failed to load interview analysis records.</div>
        ) : !listQuery.data || listQuery.data.items.length === 0 ? (
          <div className="text-center py-20">
            <MessageSquare className="w-12 h-12 text-[var(--text-tertiary)] mx-auto mb-4" />
            <h3 className="text-lg font-medium text-[var(--text-primary)] mb-1">No interview records yet</h3>
            <p className="text-[var(--text-secondary)]">Completed interviews with evaluation data will appear here.</p>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-[var(--bg-app)] border-b border-[var(--border-light)] text-[var(--text-secondary)]">
                  <tr>
                    <th className="px-6 py-4 font-medium">Candidate</th>
                    <th className="px-6 py-4 font-medium">Job</th>
                    <th className="px-6 py-4 font-medium">Disposition</th>
                    <th className="px-6 py-4 font-medium">Duration</th>
                    <th className="px-6 py-4 font-medium">Date</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border-light)]">
                  {listQuery.data.items.map((item) => (
                    <tr key={item.id} className="hover:bg-[var(--bg-hover)] transition-colors">
                      <td className="px-6 py-4 font-medium text-[var(--text-primary)]">{item.candidate_name || `Resume #${item.resume_id}`}</td>
                      <td className="px-6 py-4 text-[var(--text-secondary)]">{item.job_title}</td>
                      <td className="px-6 py-4"><Badge variant="neutral">{item.call_disposition || 'unspecified'}</Badge></td>
                      <td className="px-6 py-4 text-[var(--text-secondary)]">{formatDuration(item.cost_info?.call_duration_seconds)}</td>
                      <td className="px-6 py-4 text-xs text-[var(--text-tertiary)]">
                        {item.created_at ? new Date(item.created_at).toLocaleDateString() : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="px-6 py-4 border-t border-[var(--border-light)] bg-[var(--bg-app)] flex items-center justify-between text-sm text-[var(--text-secondary)]">
              <span>Showing {(page - 1) * PAGE_SIZE + 1}-{Math.min(page * PAGE_SIZE, listQuery.data.total)} of {listQuery.data.total}</span>
              <div className="flex gap-1">
                <button disabled={page === 1} onClick={() => setPage((p) => p - 1)} className="p-1 rounded hover:bg-[var(--bg-hover)] disabled:opacity-50 text-[var(--text-secondary)] focus-ring">
                  <ChevronLeft className="w-5 h-5" />
                </button>
                <button disabled={page * PAGE_SIZE >= listQuery.data.total} onClick={() => setPage((p) => p + 1)} className="p-1 rounded hover:bg-[var(--bg-hover)] disabled:opacity-50 text-[var(--text-secondary)] focus-ring">
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
