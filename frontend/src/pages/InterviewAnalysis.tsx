import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import { MessageSquare } from 'lucide-react';
import { jobsApi } from '../api/jobs';
import { queryKeys } from '../api/queryKeys';
import { useInterviewAnalysisSummary, useInterviewAnalysisList } from '../hooks/useInterviewAnalysis';
import {
  Badge, Card, DataTable, EmptyState, ErrorState, FilterBar, FilterBarSpacer, NativeSelect, PageHeader, PanelBody, PanelHeader,
  Pagination, StatTile, type Column,
} from '../components/ui';
import { CandidateIdentity } from '../components/candidate/ScreeningCells';
import { chart } from '../components/charts/chartTheme';
import { parseRecommendation } from '../utils/interviewEvaluation';
import { getErrorMessage } from '../utils/errors';
import type { InterviewAnalysisItem } from '../types';

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

  const summary = summaryQuery.data;

  const columns: Column<InterviewAnalysisItem>[] = [
    {
      id: 'candidate',
      header: 'Candidate',
      mobile: 'title',
      skeleton: 'avatar',
      className: 'w-64',
      cell: (i) => <CandidateIdentity name={i.candidate_name} fallback={`Resume #${i.resume_id}`} />,
    },
    { id: 'job', header: 'Job', cell: (i) => <span className="text-sm text-[var(--text-secondary)]">{i.job_title}</span> },
    { id: 'disposition', header: 'Disposition', skeleton: 'badge', cell: (i) => <Badge>{i.call_disposition || 'unspecified'}</Badge> },
    {
      id: 'recommendation',
      header: 'Recommendation',
      cell: (i) => {
        const rec = parseRecommendation(i.interview_recommendation);
        return rec ? <Badge variant={rec.variant} title={rec.reason || undefined}>{rec.label}</Badge> : <span className="text-sm text-[var(--text-tertiary)]">—</span>;
      },
    },
    {
      id: 'duration',
      header: 'Duration',
      align: 'right',
      className: 'w-28',
      cell: (i) => <span className="tabular text-sm text-[var(--text-secondary)]">{formatDuration(i.cost_info?.call_duration_seconds)}</span>,
    },
    {
      id: 'date',
      header: 'Date',
      className: 'w-32',
      cell: (i) => <span className="text-caption whitespace-nowrap">{i.created_at ? new Date(i.created_at).toLocaleDateString() : '—'}</span>,
    },
  ];

  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader className="mb-6" title="Interview analysis" subtitle="Outcomes and dispositions from completed candidate interviews." />

      <FilterBar className="mb-6">
        <NativeSelect
          aria-label="Filter by job"
          value={jobId ?? ''}
          onChange={(e) => { setJobId(e.target.value ? Number(e.target.value) : undefined); setPage(1); }}
          className="max-w-[18rem]"
        >
          <option value="">All jobs</option>
          {jobs?.map((job) => <option key={job.id} value={job.id}>{job.title}</option>)}
        </NativeSelect>
        <FilterBarSpacer />
      </FilterBar>

      {summaryQuery.isError ? (
        <div className="mb-6 rounded-lg border border-[var(--border-light)] bg-[var(--bg-surface)]">
          <ErrorState title="Failed to load the interview summary" message={getErrorMessage(summaryQuery.error)} onRetry={() => summaryQuery.refetch()} />
        </div>
      ) : (
        <>
          <section aria-label="Interview summary" className="mb-6 grid grid-cols-1 gap-4 md:grid-cols-3">
            <StatTile
              label="Completion rate"
              isLoading={summaryQuery.isLoading}
              value={summary ? `${Math.round((summary.completion_rate ?? 0) * 100)}%` : undefined}
            />
            <StatTile label="Avg call duration" isLoading={summaryQuery.isLoading} value={summary ? formatDuration(summary.avg_call_duration_seconds) : undefined} />
            <StatTile
              label="Total interviews"
              isLoading={summaryQuery.isLoading}
              value={summary?.total_interviews ?? 0}
              hint={`${summary?.completed_interviews ?? 0} completed`}
            />
          </section>

          <Card className="mb-6">
            <PanelHeader title="Disposition breakdown" />
            <PanelBody
              isLoading={summaryQuery.isLoading}
              isError={false}
              onRetry={() => summaryQuery.refetch()}
              isEmpty={dispositionData.length === 0}
              empty={<p className="text-body px-5 py-10 text-center">No completed interviews with recorded dispositions yet.</p>}
              rows={4}
            >
              <div className="p-5" role="img" aria-label={`Dispositions: ${dispositionData.map((d) => `${d.disposition} ${d.count}`).join(', ')}`}>
                <div style={{ width: '100%', height: 240 }}>
                  <ResponsiveContainer>
                    <BarChart data={dispositionData}>
                      <CartesianGrid strokeDasharray="3 3" stroke={chart.grid} vertical={false} />
                      <XAxis dataKey="disposition" tick={chart.axis} axisLine={chart.axisLine} tickLine={false} />
                      <YAxis allowDecimals={false} tick={chart.axis} axisLine={false} tickLine={false} />
                      <Tooltip {...chart.tooltip} />
                      <Bar dataKey="count" fill={chart.primary} radius={[3, 3, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </PanelBody>
          </Card>
        </>
      )}

      {listQuery.isError ? (
        <div className="rounded-lg border border-[var(--border-light)] bg-[var(--bg-surface)]">
          <ErrorState title="Failed to load interview records" message={getErrorMessage(listQuery.error)} onRetry={() => listQuery.refetch()} />
        </div>
      ) : (
        <>
          <DataTable
            aria-label="Interview records"
            rows={listQuery.data?.items ?? []}
            columns={columns}
            getRowId={(i) => i.id}
            isLoading={listQuery.isLoading && !listQuery.data}
            isRefreshing={listQuery.isFetching && !!listQuery.data}
            empty={
              <EmptyState
                icon={<MessageSquare size={20} />}
                title="No interview records yet"
                description="Completed interviews with evaluation data will appear here."
              />
            }
          />
          {listQuery.data && listQuery.data.total > 0 && (
            <Pagination className="mt-4" page={page} pageSize={PAGE_SIZE} total={listQuery.data.total} onPageChange={setPage} />
          )}
        </>
      )}
    </div>
  );
};
