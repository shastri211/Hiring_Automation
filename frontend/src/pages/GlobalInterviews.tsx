import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { formatDistanceToNow } from 'date-fns';
import { Calendar } from 'lucide-react';
import { jobsApi } from '../api/jobs';
import { queryKeys } from '../api/queryKeys';
import { useGlobalInterviews } from '../hooks/useGlobalInterviews';
import {
  Badge, DataTable, EmptyState, ErrorState, FilterBar, FilterBarSpacer, NativeSelect, PageHeader, Pagination, StatusDot,
  type Column,
} from '../components/ui';
import { CandidateIdentity } from '../components/candidate/ScreeningCells';
import { getInterviewStatusBadgeVariant, interviewStatusLabel } from '../utils/status';
import { parseRecommendation } from '../utils/interviewEvaluation';
import { getErrorMessage } from '../utils/errors';
import type { GlobalInterviewResponse } from '../types';

const PAGE_SIZE = 20;

const STATUS_OPTIONS = [
  'PENDING', 'SCHEDULED', 'IN_PROGRESS', 'COMPLETED', 'FAILED',
  'RESCHEDULE_PENDING', 'NO_SHOW', 'DECLINED',
];

export const GlobalInterviews = () => {
  const navigate = useNavigate();
  const [status, setStatus] = useState<string | undefined>(undefined);
  const [jobId, setJobId] = useState<number | undefined>(undefined);
  const [page, setPage] = useState(1);

  const { data: jobs } = useQuery({ queryKey: queryKeys.jobs(), queryFn: jobsApi.getJobs });

  const params = { status, job_id: jobId, page, page_size: PAGE_SIZE };
  const { data, isLoading, isFetching, isError, error, refetch } = useGlobalInterviews(params);

  const filtered = !!(status || jobId);

  const columns: Column<GlobalInterviewResponse>[] = [
    {
      id: 'candidate',
      header: 'Candidate',
      mobile: 'title',
      skeleton: 'avatar',
      className: 'w-64',
      cell: (r) => <CandidateIdentity name={r.candidate_name} fallback={r.resume_filename || `Resume #${r.resume_id}`} />,
    },
    { id: 'job', header: 'Job', cell: (r) => <span className="text-sm text-[var(--text-secondary)]">{r.job_title}</span> },
    {
      id: 'status',
      header: 'Status',
      className: 'w-44',
      skeleton: 'badge',
      cell: (r) => (
        <StatusDot variant={getInterviewStatusBadgeVariant(r.status)} live={r.status === 'IN_PROGRESS'}>
          {interviewStatusLabel(r.status)}
        </StatusDot>
      ),
    },
    {
      id: 'recommendation',
      header: 'Recommendation',
      className: 'w-44',
      cell: (r) => {
        const rec = parseRecommendation(r.evaluation?.interview_recommendation);
        return rec ? (
          <Badge variant={rec.variant} title={rec.reason || undefined}>{rec.label}</Badge>
        ) : (
          <span className="text-sm text-[var(--text-tertiary)]">—</span>
        );
      },
    },
    {
      id: 'updated',
      header: 'Updated',
      className: 'w-36',
      cell: (r) => (
        <span className="text-caption whitespace-nowrap">{r.updated_at ? formatDistanceToNow(new Date(r.updated_at), { addSuffix: true }) : '—'}</span>
      ),
    },
  ];

  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader
        className="mb-6"
        title="All interviews"
        subtitle="Every candidate interview scheduled or completed across all jobs."
      />

      <FilterBar className="mb-4">
        <NativeSelect
          aria-label="Filter by status"
          value={status ?? ''}
          onChange={(e) => { setStatus(e.target.value || undefined); setPage(1); }}
        >
          <option value="">All statuses</option>
          {STATUS_OPTIONS.map((s) => <option key={s} value={s}>{interviewStatusLabel(s)}</option>)}
        </NativeSelect>
        <NativeSelect
          aria-label="Filter by job"
          value={jobId ?? ''}
          onChange={(e) => { setJobId(e.target.value ? Number(e.target.value) : undefined); setPage(1); }}
          className="max-w-[16rem]"
        >
          <option value="">All jobs</option>
          {jobs?.map((job) => <option key={job.id} value={job.id}>{job.title}</option>)}
        </NativeSelect>
        <FilterBarSpacer />
        {data && <span className="text-caption tabular" aria-live="polite">{data.total} interview{data.total === 1 ? '' : 's'}</span>}
      </FilterBar>

      {isError ? (
        <div className="rounded-lg border border-[var(--border-light)] bg-[var(--bg-surface)]">
          <ErrorState title="Failed to load interviews" message={getErrorMessage(error)} onRetry={() => refetch()} />
        </div>
      ) : (
        <>
          <DataTable
            aria-label="Interviews"
            rows={data?.items ?? []}
            columns={columns}
            getRowId={(r) => r.id}
            isLoading={isLoading && !data}
            isRefreshing={isFetching && !!data}
            onRowClick={(r) => navigate(`/interview/${r.job_id}/${r.resume_id}`)}
            empty={
              <EmptyState
                icon={<Calendar size={20} />}
                title={filtered ? 'No interviews match these filters' : 'No interviews yet'}
                description={filtered ? 'Try a different status or job.' : "Trigger an interview from a candidate's profile to see it appear here."}
              />
            }
          />
          {data && data.total > 0 && <Pagination className="mt-4" page={page} pageSize={PAGE_SIZE} total={data.total} onPageChange={setPage} />}
        </>
      )}
    </div>
  );
};
