import { useState } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient, keepPreviousData } from '@tanstack/react-query';
import { CheckCircle2, Clock, Eraser, Mail, PackagePlus, Search, XCircle } from 'lucide-react';
import { jobsApi } from '../api/jobs';
import { queryKeys } from '../api/queryKeys';
import { useDecisionMutation, useRetryEvaluation } from '../hooks/useDecisionMutation';
import { useAddToTalentPool } from '../hooks/useTalentPool';
import { emailQueryKeys } from '../hooks/useEmails';
import type { CandidateDecision, ScreeningResultResponse } from '../types';
import { CandidateDrawer } from '../components/CandidateDrawer';
import { BulkEmailModal } from '../components/BulkEmailModal';
import { CandidateIdentity, DecisionStatus, EvaluationSummary } from '../components/candidate/ScreeningCells';
import {
  Breadcrumbs, BulkAction, BulkActionBar, DataTable, EmptyState, ErrorState, FilterBar, FilterBarSpacer, FitScore, IconButton,
  NativeSelect, PageHeader, Pagination, Tabs, type Column,
} from '../components/ui';

const PAGE_SIZE = 20;

type Params = {
  page: number;
  // decision can be a CandidateDecision or a special filter string ('PRE_SCREENED_OUT', 'FAILED')
  decision?: CandidateDecision;
  status?: string;
  sort_by: 'score' | 'created_at';
  min_score?: number;
  max_score?: number;
};

type Segment = 'ALL' | 'SHORTLIST' | 'REVIEW' | 'REJECT' | 'PRE_SCREENED_OUT' | 'FAILED';

const segmentOf = (p: Params): Segment => (p.status === 'FAILED' ? 'FAILED' : ((p.decision as Segment) || 'ALL'));

export const JobCandidates = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const jobId = parseInt(id || '0', 10);
  const location = useLocation();

  const [params, setParams] = useState<Params>(location.state?.params || { page: 1, sort_by: 'score' });
  const [selectedResumeId, setSelectedResumeId] = useState<number | null>(null);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [showEmailModal, setShowEmailModal] = useState(false);

  const queryClient = useQueryClient();

  const { data, isLoading, isFetching, isError, error, refetch } = useQuery({
    queryKey: queryKeys.candidates(jobId, params),
    queryFn: () => jobsApi.getJobResults(jobId, params),
    placeholderData: keepPreviousData,
    staleTime: 0,
  });

  const { data: jobMeta } = useQuery({
    queryKey: queryKeys.job(jobId),
    queryFn: () => jobsApi.getJob(jobId),
    enabled: jobId > 0,
  });

  const decisionMutation = useDecisionMutation(jobId);
  const retryEvaluation = useRetryEvaluation(jobId);
  const addToPool = useAddToTalentPool();

  const handleDecision = (resumeId: number, decision: CandidateDecision | null) => {
    decisionMutation.mutate({ resumeId, decision });
  };

  const bulkDecisionMutation = useMutation({
    mutationFn: ({ resumeIds, decision }: { resumeIds: number[]; decision: CandidateDecision }) =>
      jobsApi.bulkUpdateDecision(jobId, resumeIds, decision),
    onSuccess: (_, { resumeIds }) => {
      // Invalidate all paginated/filtered variants for this job, not just the current one
      queryClient.invalidateQueries({ queryKey: queryKeys.candidates(jobId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.candidateDetail(jobId, 0).slice(0, 2) });
      // Mirrors useDecisionMutation's single-decision invalidation - a bulk
      // SHORTLIST must also refresh the global Shortlisted page.
      queryClient.invalidateQueries({ queryKey: queryKeys.shortlisted() });
      // Bulk SHORTLIST can auto-mint interview links and auto-send emails
      // (see useDecisionMutation's single-decision counterpart) - each
      // resume's OutreachHistory reads its own query key, so it needs its
      // own invalidation too.
      resumeIds.forEach((resumeId) => {
        queryClient.invalidateQueries({ queryKey: emailQueryKeys.candidateHistory(resumeId) });
      });
      setSelectedIds([]);
    },
  });

  const setSegment = (segment: Segment) => {
    setParams((p) => ({
      ...p,
      page: 1,
      decision: segment === 'ALL' || segment === 'FAILED' ? undefined : (segment as CandidateDecision),
      status: segment === 'FAILED' ? 'FAILED' : undefined,
    }));
  };

  const isFiltered = segmentOf(params) !== 'ALL' || params.min_score != null;
  const bulkBusy = bulkDecisionMutation.isPending;

  const columns: Column<ScreeningResultResponse>[] = [
    {
      id: 'candidate',
      header: 'Candidate',
      mobile: 'title',
      skeleton: 'avatar',
      className: 'w-48',
      cell: (c) => (
        <CandidateIdentity
          name={c.display_name}
          fallback={`Resume #${c.resume_id}`}
          muted={c.status === 'FAILED' || c.decision === 'PRE_SCREENED_OUT'}
          sub={c.applications_count && c.applications_count > 1 ? `Applied to ${c.applications_count} jobs` : undefined}
        />
      ),
    },
    {
      id: 'score',
      header: 'Fit score',
      skeleton: 'score',
      className: 'w-36',
      cell: (c) => (
        <FitScore score={c.score} unscoredLabel={c.decision === 'PRE_SCREENED_OUT' ? 'Not scored — pre-screened out' : undefined} />
      ),
    },
    {
      id: 'semantic',
      header: 'Semantic',
      align: 'right',
      hideBelow: 'xl',
      className: 'w-24',
      cell: (c) => (
        <span className="tabular text-sm text-[var(--text-secondary)]">{c.semantic_score != null ? c.semantic_score.toFixed(3) : '—'}</span>
      ),
    },
    {
      id: 'evaluation',
      header: 'Strengths, gaps & evidence',
      mobile: 'body',
      className: 'min-w-[15rem]',
      skeleton: 'text',
      cell: (c) => (
        <EvaluationSummary
          strengths={c.strengths}
          gaps={c.gaps}
          evidence={c.evidence}
          decision={c.decision}
          evaluationFailed={c.evaluation_failed}
          onRetry={() => retryEvaluation.mutate(c.resume_id)}
          isRetrying={retryEvaluation.isPending && retryEvaluation.variables === c.resume_id}
        />
      ),
    },
    {
      id: 'decision',
      header: 'Decision',
      skeleton: 'badge',
      cell: (c) => <DecisionStatus candidate={c} />,
    },
    {
      id: 'actions',
      header: <span className="sr-only">Actions</span>,
      align: 'right',
      mobile: 'actions',
      className: 'w-44',
      skeleton: 'actions',
      cell: (c) => (
        <div className="flex items-center justify-end gap-0.5">
          <IconButton
            label="Shortlist"
            tone="success"
            active={c.decision === 'SHORTLIST'}
            icon={<CheckCircle2 size={16} />}
            disabled={decisionMutation.isPending}
            onClick={() => handleDecision(c.resume_id, 'SHORTLIST')}
          />
          <IconButton
            label="Mark for review"
            tone="warning"
            active={c.decision === 'REVIEW'}
            icon={<Clock size={16} />}
            disabled={decisionMutation.isPending}
            onClick={() => handleDecision(c.resume_id, 'REVIEW')}
          />
          <IconButton
            label="Reject"
            tone="danger"
            active={c.decision === 'REJECT'}
            icon={<XCircle size={16} />}
            disabled={decisionMutation.isPending}
            onClick={() => handleDecision(c.resume_id, 'REJECT')}
          />
          <IconButton
            label="Clear decision"
            icon={<Eraser size={15} />}
            disabled={decisionMutation.isPending || !c.decision}
            onClick={() => handleDecision(c.resume_id, null)}
          />
          <span aria-hidden="true" className="mx-1 h-4 w-px bg-[var(--border-light)]" />
          <IconButton
            label="Add to Talent Pool"
            tone="primary"
            icon={<PackagePlus size={16} />}
            disabled={addToPool.isPending}
            onClick={() => addToPool.mutate({ resume_id: c.resume_id, added_from_job_id: jobId })}
          />
        </div>
      ),
    },
  ];

  return (
    <div className="mx-auto max-w-7xl">
      <Breadcrumbs
        className="mb-4"
        items={[{ label: 'Jobs', to: '/jobs' }, { label: jobMeta?.title || 'Job', to: `/jobs/${id}` }, { label: 'Candidates' }]}
      />

      <PageHeader className="mb-6" title="Screening results" subtitle="Review candidates and make shortlisting decisions." />

      <Tabs<Segment>
        aria-label="Filter by decision"
        value={segmentOf(params)}
        onChange={setSegment}
        tabs={[
          { value: 'ALL', label: 'All' },
          { value: 'SHORTLIST', label: 'Shortlisted' },
          { value: 'REVIEW', label: 'Review' },
          { value: 'REJECT', label: 'Rejected' },
          { value: 'PRE_SCREENED_OUT', label: 'Pre-screened out', tone: 'warning' },
          { value: 'FAILED', label: 'Failed', tone: 'danger' },
        ]}
      />

      <FilterBar className="my-4">
        <NativeSelect
          aria-label="Minimum fit score"
          value={params.min_score ?? ''}
          onChange={(e) => setParams((p) => ({ ...p, min_score: e.target.value ? Number(e.target.value) : undefined, page: 1 }))}
        >
          <option value="">Any fit score</option>
          <option value="50">Score 50+</option>
          <option value="75">Score 75+</option>
        </NativeSelect>
        <NativeSelect
          aria-label="Sort order"
          value={params.sort_by}
          onChange={(e) => setParams((p) => ({ ...p, sort_by: e.target.value as Params['sort_by'], page: 1 }))}
        >
          <option value="score">Sort: Fit score</option>
          <option value="created_at">Sort: Latest</option>
        </NativeSelect>
        <FilterBarSpacer />
        {data && (
          <span className="text-caption tabular" aria-live="polite">
            {data.total} candidate{data.total === 1 ? '' : 's'}
          </span>
        )}
      </FilterBar>

      {isError ? (
        <div className="rounded-lg border border-[var(--border-light)] bg-[var(--bg-surface)]">
          <ErrorState
            title="Couldn't load candidates"
            message={error instanceof Error ? error.message : undefined}
            onRetry={() => refetch()}
          />
        </div>
      ) : (
        <>
          <DataTable
            aria-label="Screening results"
            rows={data?.items ?? []}
            columns={columns}
            getRowId={(c) => c.resume_id}
            rowLabel={(c) => c.display_name || `resume ${c.resume_id}`}
            isLoading={isLoading && !data}
            isRefreshing={isFetching && !!data}
            onRowClick={(c) => setSelectedResumeId(c.resume_id)}
            selection={{ selected: selectedIds, onChange: (ids) => setSelectedIds(ids as number[]) }}
            empty={
              <EmptyState
                icon={<Search size={20} />}
                title={isFiltered ? 'No candidates match these filters' : 'No candidates yet'}
                description={isFiltered ? 'Try a different segment or clear the score filter.' : 'Upload resumes to this job to see screening results here.'}
              />
            }
          />
          {data && data.total > 0 && (
            <Pagination
              className="mt-4"
              page={params.page}
              pageSize={PAGE_SIZE}
              total={data.total}
              onPageChange={(page) => setParams((p) => ({ ...p, page }))}
            />
          )}
        </>
      )}

      <BulkActionBar count={selectedIds.length} noun="candidate" onClear={() => setSelectedIds([])}>
        <BulkAction onClick={() => setShowEmailModal(true)}>
          <Mail size={15} aria-hidden="true" /> Email
        </BulkAction>
        <BulkAction onClick={() => bulkDecisionMutation.mutate({ resumeIds: selectedIds, decision: 'SHORTLIST' })} disabled={bulkBusy}>
          <CheckCircle2 size={15} aria-hidden="true" /> Shortlist
        </BulkAction>
        <BulkAction onClick={() => bulkDecisionMutation.mutate({ resumeIds: selectedIds, decision: 'REVIEW' })} disabled={bulkBusy}>
          <Clock size={15} aria-hidden="true" /> Review
        </BulkAction>
        <BulkAction onClick={() => bulkDecisionMutation.mutate({ resumeIds: selectedIds, decision: 'REJECT' })} disabled={bulkBusy}>
          <XCircle size={15} aria-hidden="true" /> Reject
        </BulkAction>
      </BulkActionBar>

      <CandidateDrawer
        jobId={jobId}
        resumeId={selectedResumeId}
        isOpen={selectedResumeId !== null}
        onClose={() => setSelectedResumeId(null)}
        onView360={() => {
          navigate(`/jobs/${jobId}/candidates/${selectedResumeId}`, { state: { from: 'candidates', params } });
        }}
      />

      {showEmailModal && (
        <BulkEmailModal
          resumeGroups={[{ jobId, resumeIds: selectedIds, jobTitle: jobMeta?.title }]}
          onClose={() => setShowEmailModal(false)}
          onSuccess={() => {
            setShowEmailModal(false);
            setSelectedIds([]);
          }}
        />
      )}
    </div>
  );
};
