import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, keepPreviousData } from '@tanstack/react-query';
import { ExternalLink, Mail, PackagePlus, Users } from 'lucide-react';
import { candidatesApi } from '../api/candidates';
import { queryKeys } from '../api/queryKeys';
import { useAddToTalentPool } from '../hooks/useTalentPool';
import { CandidateDrawer } from '../components/CandidateDrawer';
import { BulkEmailModal, type ResumeGroup } from '../components/BulkEmailModal';
import { CandidateIdentity, DecisionStatus, EvaluationSummary, ScoreCell, SemanticCell } from '../components/candidate/ScreeningCells';
import {
  BulkAction, BulkActionBar, DataTable, EmptyState, ErrorState, FilterBar, FilterBarSpacer, IconButton, PageHeader,
  Pagination, Tabs, type Column,
} from '../components/ui';
import { getErrorMessage } from '../utils/errors';
import type { CandidateDecision, GlobalScreeningResultResponse } from '../types';

const PAGE_SIZE = 20;

type Segment = 'ALL' | 'SHORTLIST' | 'REVIEW' | 'REJECT' | 'PRE_SCREENED_OUT';

export const GlobalCandidates = () => {
  const navigate = useNavigate();
  const [decision, setDecision] = useState<CandidateDecision | undefined>(undefined);
  const [page, setPage] = useState(1);
  const [selectedCandidate, setSelectedCandidate] = useState<{ jobId: number; resumeId: number } | null>(null);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [showEmailModal, setShowEmailModal] = useState(false);

  const params = { decision, page, page_size: PAGE_SIZE };

  const { data, isLoading, isFetching, isError, error, refetch } = useQuery({
    queryKey: queryKeys.globalCandidates(params),
    queryFn: () => candidatesApi.getGlobalCandidates(params),
    placeholderData: keepPreviousData,
  });

  const addToPool = useAddToTalentPool();

  // resumeGroups (below) is derived by filtering the CURRENT page's
  // data.items against selectedIds - a selection made on a previous page
  // would otherwise silently vanish from the send (while the toolbar still
  // shows a stale "N selected" count) once the page/filter changes and
  // data.items no longer contains those rows. Selection is page-scoped by
  // design, so every page/filter change clears it.
  const goToPage = (nextPage: number) => {
    setPage(nextPage);
    setSelectedIds([]);
  };

  // Selected rows span multiple jobs here (unlike JobCandidates) - group by
  // job_id since the bulk-send endpoint is job-scoped.
  const resumeGroups: ResumeGroup[] = data?.items
    ? Object.values(
        data.items
          .filter((c) => selectedIds.includes(c.resume_id))
          .reduce((acc, c) => {
            const key = c.job_id;
            if (!acc[key]) acc[key] = { jobId: c.job_id, jobTitle: c.job_title, resumeIds: [] };
            acc[key].resumeIds.push(c.resume_id);
            return acc;
          }, {} as Record<number, ResumeGroup>)
      )
    : [];

  const columns: Column<GlobalScreeningResultResponse>[] = [
    {
      id: 'candidate',
      header: 'Candidate',
      mobile: 'title',
      skeleton: 'avatar',
      className: 'w-44',
      cell: (c) => (
        <CandidateIdentity
          name={c.display_name}
          fallback={`Candidate #${c.resume_id}`}
          muted={c.status === 'FAILED' || c.decision === 'PRE_SCREENED_OUT'}
          sub={c.applications_count && c.applications_count > 1 ? `Applied to ${c.applications_count} jobs` : undefined}
        />
      ),
    },
    {
      id: 'job',
      header: 'Job',
      className: 'min-w-[10rem]',
      cell: (c) => (
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); navigate(`/jobs/${c.job_id}`); }}
          className="transition-base focus-ring rounded text-left text-sm text-[var(--color-primary-600)] hover:text-[var(--color-primary-700)] hover:underline"
        >
          {c.job_title}
        </button>
      ),
    },
    {
      id: 'score',
      header: 'Fit score',
      skeleton: 'score',
      className: 'w-32',
      cell: (c) => <ScoreCell score={c.score} semantic={c.semantic_score} unscoredLabel={c.decision === 'PRE_SCREENED_OUT' ? 'Not scored — pre-screened out' : undefined} />,
    },
    {
      id: 'semantic',
      header: 'Semantic',
      align: 'right',
      hideBelow: 'xl',
      className: 'w-24',
      cell: (c) => <SemanticCell value={c.semantic_score} />,
    },
    {
      id: 'evaluation',
      header: 'Strengths & gaps',
      hideBelow: 'xl',
      mobile: 'hidden',
      className: 'min-w-[12rem]',
      cell: (c) => (
        <div className="max-w-[11rem]">
          <EvaluationSummary
            strengths={c.strengths}
            gaps={c.gaps}
            evidence={null}
            decision={c.decision}
            evaluationFailed={c.evaluation_failed}
          />
        </div>
      ),
    },
    { id: 'decision', header: 'Decision', skeleton: 'badge', cell: (c) => <DecisionStatus candidate={c} /> },
    {
      id: 'actions',
      header: <span className="sr-only">Actions</span>,
      align: 'right',
      mobile: 'actions',
      className: 'w-24',
      skeleton: 'actions',
      cell: (c) => (
        <div className="flex items-center justify-end gap-0.5">
          <IconButton
            label="Open full profile"
            icon={<ExternalLink size={15} />}
            onClick={() => navigate(`/jobs/${c.job_id}/candidates/${c.resume_id}`, { state: { from: 'candidates' } })}
          />
          <IconButton
            label="Add to Talent Pool"
            tone="primary"
            icon={<PackagePlus size={16} />}
            disabled={addToPool.isPending}
            onClick={() => addToPool.mutate({ resume_id: c.resume_id, added_from_job_id: c.job_id })}
          />
        </div>
      ),
    },
  ];

  const segment: Segment = (decision as Segment) || 'ALL';

  return (
    <div className="mx-auto max-w-7xl">
      <PageHeader className="mb-6" title="All candidates" subtitle="Every screened candidate across all jobs, in one place." />

      <Tabs<Segment>
        aria-label="Filter by decision"
        value={segment}
        onChange={(value) => {
          setDecision(value === 'ALL' ? undefined : (value as CandidateDecision));
          goToPage(1);
        }}
        tabs={[
          { value: 'ALL', label: 'All' },
          { value: 'SHORTLIST', label: 'Shortlisted' },
          { value: 'REVIEW', label: 'Needs review' },
          { value: 'REJECT', label: 'Rejected' },
          { value: 'PRE_SCREENED_OUT', label: 'Pre-screened out', tone: 'warning' },
        ]}
      />

      <FilterBar className="my-4">
        <FilterBarSpacer />
        {data && (
          <span className="text-caption tabular" aria-live="polite">
            {data.total} candidate{data.total === 1 ? '' : 's'}
          </span>
        )}
      </FilterBar>

      {isError ? (
        <div className="rounded-lg border border-[var(--border-light)] bg-[var(--bg-surface)]">
          <ErrorState title="Failed to load candidates" message={getErrorMessage(error)} onRetry={() => refetch()} />
        </div>
      ) : (
        <>
          <DataTable
            aria-label="All candidates"
            rows={data?.items ?? []}
            columns={columns}
            getRowId={(c) => c.resume_id}
            rowLabel={(c) => c.display_name || `resume ${c.resume_id}`}
            isLoading={isLoading && !data}
            isRefreshing={isFetching && !!data}
            onRowClick={(c) => setSelectedCandidate({ jobId: c.job_id, resumeId: c.resume_id })}
            selection={{ selected: selectedIds, onChange: (ids) => setSelectedIds(ids as number[]) }}
            empty={
              <EmptyState
                icon={<Users size={20} />}
                title="No candidates found"
                description="Try a different decision filter, or come back once more resumes have been screened."
              />
            }
          />
          {data && data.total > 0 && (
            <Pagination className="mt-4" page={page} pageSize={PAGE_SIZE} total={data.total} onPageChange={goToPage} />
          )}
        </>
      )}

      <BulkActionBar count={selectedIds.length} noun="candidate" onClear={() => setSelectedIds([])}>
        <BulkAction onClick={() => setShowEmailModal(true)}>
          <Mail size={15} aria-hidden="true" /> Email
        </BulkAction>
      </BulkActionBar>

      {selectedCandidate && (
        <CandidateDrawer
          jobId={selectedCandidate.jobId}
          resumeId={selectedCandidate.resumeId}
          isOpen={true}
          onClose={() => setSelectedCandidate(null)}
          onView360={() => {
            navigate(`/jobs/${selectedCandidate.jobId}/candidates/${selectedCandidate.resumeId}`, { state: { from: 'candidates' } });
          }}
        />
      )}

      {showEmailModal && (
        <BulkEmailModal
          resumeGroups={resumeGroups}
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
