import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from 'recharts';
import { Loader2, BarChart as BarChartIcon } from 'lucide-react';
import { jobsApi } from '../api/jobs';
import { queryKeys } from '../api/queryKeys';
import { useFunnel, useDecisionBreakdown, useThroughput, useJobVolume } from '../hooks/useAnalytics';
import { Card, CardContent, Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '../components/ui';

/**
 * Chart colors are read once from the CSS custom properties in variables.css
 * (getComputedStyle on <html>) so charts follow the active theme's palette at
 * mount time. Fallback hex values mirror the literals in variables.css in
 * case the property read ever comes back empty (e.g. no DOM yet). This is a
 * one-time read, not theme-reactive mid-session — acceptable since a theme
 * toggle already re-renders the whole page tree.
 */
function useChartColors() {
  return useMemo(() => {
    const styles = getComputedStyle(document.documentElement);
    const read = (name: string, fallback: string) => styles.getPropertyValue(name).trim() || fallback;
    return {
      primary: read('--color-primary-500', '#6366f1'),
      success: read('--color-success-500', '#22c55e'),
      warning: read('--color-warning-500', '#f59e0b'),
      danger: read('--color-danger-500', '#ef4444'),
      neutral: read('--color-neutral-400', '#94a3b8'),
    };
  }, []);
}

const ChartSection = ({
  title, isLoading, isError, isEmpty, emptyMessage, children,
}: {
  title: string; isLoading: boolean; isError: boolean; isEmpty: boolean; emptyMessage: string; children: React.ReactNode;
}) => (
  <Card>
    <CardContent className="p-6">
      <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-4">{title}</h3>
      {isLoading ? (
        <div className="flex justify-center py-12"><Loader2 className="w-6 h-6 animate-spin text-[var(--color-primary-500)]" /></div>
      ) : isError ? (
        <p className="text-sm text-[var(--color-danger-600)] py-8 text-center">Failed to load this chart.</p>
      ) : isEmpty ? (
        <p className="text-sm text-[var(--text-tertiary)] italic py-8 text-center">{emptyMessage}</p>
      ) : (
        children
      )}
    </CardContent>
  </Card>
);

export const Analytics = () => {
  const [jobId, setJobId] = useState<number | undefined>(undefined);
  const colors = useChartColors();

  const { data: jobs } = useQuery({ queryKey: queryKeys.jobs(), queryFn: jobsApi.getJobs });

  const funnelQuery = useFunnel(jobId);
  const decisionsQuery = useDecisionBreakdown(jobId);
  const throughputQuery = useThroughput(30, jobId);
  const jobVolumeQuery = useJobVolume();

  const funnelData = useMemo(() => {
    const f = funnelQuery.data;
    if (!f) return [];
    return [
      { stage: 'Uploaded', count: f.uploaded },
      { stage: 'Processed', count: f.processed },
      { stage: 'Screened', count: f.screened },
      { stage: 'Shortlisted', count: f.shortlisted },
      { stage: 'Interviewed', count: f.interviewed },
      { stage: 'Completed', count: f.completed },
    ];
  }, [funnelQuery.data]);

  const decisionData = useMemo(
    () => (decisionsQuery.data?.items || []).map((d) => ({ decision: d.decision || 'Unset', count: d.count })),
    [decisionsQuery.data]
  );

  const throughputData = useMemo(
    () => (throughputQuery.data?.items || []).map((p) => ({ date: p.date, count: p.count })),
    [throughputQuery.data]
  );

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-8 flex-wrap gap-4">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 bg-[var(--color-primary-subtle-bg)] text-[var(--color-primary-subtle-text)] rounded-lg flex items-center justify-center">
            <BarChartIcon className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-[var(--text-primary)]">Analytics</h1>
            <p className="text-sm text-[var(--text-secondary)]">Pipeline health across your hiring funnel.</p>
          </div>
        </div>
        <div className="w-56">
          <Select value={jobId ? String(jobId) : 'all'} onValueChange={(v) => setJobId(v === 'all' ? undefined : Number(v))}>
            <SelectTrigger><SelectValue placeholder="All Jobs" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Jobs</SelectItem>
              {jobs?.map((job) => <SelectItem key={job.id} value={String(job.id)}>{job.title}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <ChartSection
          title="Hiring Funnel"
          isLoading={funnelQuery.isLoading}
          isError={funnelQuery.isError}
          isEmpty={funnelData.every((d) => d.count === 0)}
          emptyMessage="No resumes processed yet for this filter."
        >
          <div style={{ width: '100%', height: 280 }}>
            <ResponsiveContainer>
              <BarChart data={funnelData} layout="vertical" margin={{ left: 24 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-light)" />
                <XAxis type="number" allowDecimals={false} tick={{ fontSize: 12 }} />
                <YAxis type="category" dataKey="stage" width={90} tick={{ fontSize: 12 }} />
                <Tooltip />
                <Bar dataKey="count" fill={colors.primary} radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </ChartSection>

        <ChartSection
          title="Decision Breakdown"
          isLoading={decisionsQuery.isLoading}
          isError={decisionsQuery.isError}
          isEmpty={decisionData.length === 0}
          emptyMessage="No screening decisions recorded yet for this filter."
        >
          <div style={{ width: '100%', height: 280 }}>
            <ResponsiveContainer>
              <BarChart data={decisionData}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-light)" />
                <XAxis dataKey="decision" tick={{ fontSize: 12 }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
                <Tooltip />
                <Bar dataKey="count" fill={colors.success} radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </ChartSection>
      </div>

      <div className="mb-6">
        <ChartSection
          title="Screening Throughput (last 30 days)"
          isLoading={throughputQuery.isLoading}
          isError={throughputQuery.isError}
          isEmpty={throughputData.length === 0}
          emptyMessage="No screening activity in the last 30 days for this filter."
        >
          <div style={{ width: '100%', height: 260 }}>
            <ResponsiveContainer>
              <LineChart data={throughputData}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-light)" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
                <Tooltip />
                <Line type="monotone" dataKey="count" stroke={colors.primary} strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </ChartSection>
      </div>

      <Card>
        <CardContent className="p-6">
          <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-1">Volume by Job</h3>
          <p className="text-xs text-[var(--text-tertiary)] mb-4">Across all jobs — not affected by the job filter above.</p>
          {jobVolumeQuery.isLoading ? (
            <div className="flex justify-center py-8"><Loader2 className="w-6 h-6 animate-spin text-[var(--color-primary-500)]" /></div>
          ) : jobVolumeQuery.isError ? (
            <p className="text-sm text-[var(--color-danger-600)] py-4 text-center">Failed to load job volume.</p>
          ) : !jobVolumeQuery.data || jobVolumeQuery.data.items.length === 0 ? (
            <p className="text-sm text-[var(--text-tertiary)] italic py-4 text-center">No jobs with resumes yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="text-[var(--text-secondary)] border-b border-[var(--border-light)]">
                  <tr><th className="py-2 font-medium">Job</th><th className="py-2 font-medium">Resumes</th></tr>
                </thead>
                <tbody className="divide-y divide-[var(--border-light)]">
                  {jobVolumeQuery.data.items.map((item) => (
                    <tr key={item.job_id}>
                      <td className="py-2 text-[var(--text-primary)]">{item.job_title}</td>
                      <td className="py-2 text-[var(--text-secondary)]">{item.resume_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};
