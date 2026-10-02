import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ExternalLink, Mail, PackagePlus, Star } from 'lucide-react';
import { useShortlistedCandidates } from '../hooks/useShortlistedCandidates';
import { useAddToTalentPool } from '../hooks/useTalentPool';
import { CandidateDrawer } from '../components/CandidateDrawer';
import { BulkEmailModal, type ResumeGroup } from '../components/BulkEmailModal';
import { CandidateIdentity, EvaluationSummary, ScoreCell, SemanticCell } from '../components/candidate/ScreeningCells';
import {
  BulkAction, BulkActionBar, DataTable, EmptyState, ErrorState, IconButton, PageHeader, Pagination, type Column,
} from '../components/ui';
import type { GlobalScreeningResultResponse } from '../types';

export const Shortlisted = () => {
  const [page, setPage] = useState(1);
  const { candidates, total, pageSize, isLoading, isError, refetch } = useShortlistedCandidates(page);
  const navigate = useNavigate();
  const [selectedCandidate, setSelectedCandidate] = useState<{ jobId: number; resumeId: number } | null>(null);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [showEmailModal, setShowEmailModal] = useState(false);
  const addToPool = useAddToTalentPool();

  // Selected rows can span multiple jobs - group by job_id since the
  // bulk-send endpoint is job-scoped. Only the current page's rows are
  // resolvable, so selection is cleared whenever the page changes.
  const resumeGroups: ResumeGroup[] = Object.values(
    candidates
      .filter((c: GlobalScreeningResultResponse) => selectedIds.includes(c.resume_id))
      .reduce((acc: Record<number, ResumeGroup>, c: GlobalScreeningResultResponse) => {
        const key = c.job_id;
        if (!acc[key]) acc[key] = { jobId: c.job_id, jobTitle: c.job_title, resumeIds: [] };
        acc[key].resumeIds.push(c.resume_id);
        return acc;
      }, {})
  );

  const goToPage = (next: number) => {
    setPage(next);
    setSelectedIds([]);
  };

  const columns: Column<GlobalScreeningResultResponse>[] = [
    {
      id: 'candidate',
      header: 'Candidate',
      mobile: 'title',
      skeleton: 'avatar',
      className: 'w-48',
      cell: (c) => (
        <CandidateIdentity
          name={c.display_name}
          fallback={`Candidate #${c.resume_id}`}
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
    { id: 'score', header: 'Fit score', skeleton: 'score', className: 'w-36', cell: (c) => <ScoreCell score={c.score} semantic={c.semantic_score} /> },
    {
      id: 'semantic',
      header: 'Semantic',
      align: 'right',
      hideBelow: 'xl',
      className: 'w-24',
      cell: (c) => <SemanticCell value={c.semantic_score} />,
    },
    {
      id: 'strengths',
      header: 'Key strengths',
      hideBelow: 'md',
      mobile: 'hidden',
      className: 'min-w-[16rem]',
      cell: (c) => <EvaluationSummary strengths={c.strengths} maxStrengths={2} maxGaps={0} />,
    },
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
            onClick={() => navigate(`/jobs/${c.job_id}/candidates/${c.resume_id}`, { state: { from: 'shortlisted' } })}
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

  return (
    <div className="mx-auto max-w-7xl">
      <PageHeader
        className="mb-6"
        title="Shortlisted candidates"
        subtitle="Candidates marked for moving forward across all jobs."
      />

      {isError ? (
        <div className="rounded-lg border border-[var(--border-light)] bg-[var(--bg-surface)]">
          <ErrorState title="Failed to load shortlisted candidates" onRetry={() => refetch()} />
        </div>
      ) : (
        <>
          <DataTable
            aria-label="Shortlisted candidates"
            rows={candidates}
            columns={columns}
            getRowId={(c) => c.resume_id}
            rowLabel={(c) => c.display_name || `resume ${c.resume_id}`}
            isLoading={isLoading}
            onRowClick={(c) => setSelectedCandidate({ jobId: c.job_id, resumeId: c.resume_id })}
            selection={{ selected: selectedIds, onChange: (ids) => setSelectedIds(ids as number[]) }}
            empty={
              <EmptyState
                icon={<Star size={20} />}
                title="No shortlisted candidates yet"
                description="Review candidate results and mark them as shortlisted to see them here."
              />
            }
          />
          <Pagination className="mt-4" page={page} pageSize={pageSize} total={total} onPageChange={goToPage} />
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
            navigate(`/jobs/${selectedCandidate.jobId}/candidates/${selectedCandidate.resumeId}`, { state: { from: 'shortlisted' } });
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
