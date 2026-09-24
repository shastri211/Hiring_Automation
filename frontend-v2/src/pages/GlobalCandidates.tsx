import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, keepPreviousData } from '@tanstack/react-query';
import { Loader2, Users, FileText, ChevronLeft, ChevronRight, PackagePlus, Mail } from 'lucide-react';
import { candidatesApi } from '../api/candidates';
import { queryKeys } from '../api/queryKeys';
import { useAddToTalentPool } from '../hooks/useTalentPool';
import { CandidateDrawer } from '../components/CandidateDrawer';
import { BulkEmailModal, type ResumeGroup } from '../components/BulkEmailModal';
import { Badge, Button, Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '../components/ui';
import { getDecisionBadgeVariant } from '../utils/decision';
import type { CandidateDecision, GlobalScreeningResultResponse } from '../types';

const PAGE_SIZE = 20;

const DECISION_OPTIONS: { value: string; label: string }[] = [
  { value: 'all', label: 'All Decisions' },
  { value: 'SHORTLIST', label: 'Shortlisted' },
  { value: 'REVIEW', label: 'Needs Review' },
  { value: 'REJECT', label: 'Rejected' },
  { value: 'PRE_SCREENED_OUT', label: 'Pre-screened Out' },
];

export const GlobalCandidates = () => {
  const navigate = useNavigate();
  const [decision, setDecision] = useState<CandidateDecision | undefined>(undefined);
  const [page, setPage] = useState(1);
  const [selectedCandidate, setSelectedCandidate] = useState<{ jobId: number; resumeId: number } | null>(null);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [showEmailModal, setShowEmailModal] = useState(false);

  const params = { decision, page, page_size: PAGE_SIZE };

  const { data, isLoading, isError, error, refetch } = useQuery({
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
  // design (see Phase 7 plan), so clear it whenever the page changes.
  useEffect(() => {
    setSelectedIds([]);
  }, [page, decision]);

  const handleSelectAll = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.checked && data?.items) {
      setSelectedIds(data.items.map((c) => c.resume_id));
    } else {
      setSelectedIds([]);
    }
  };

  const handleSelect = (e: React.ChangeEvent<HTMLInputElement>, resumeId: number) => {
    if (e.target.checked) {
      setSelectedIds((prev) => [...prev, resumeId]);
    } else {
      setSelectedIds((prev) => prev.filter((id) => id !== resumeId));
    }
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

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="flex items-center space-x-3 mb-8">
        <div className="w-10 h-10 bg-[var(--color-primary-subtle-bg)] text-[var(--color-primary-subtle-text)] rounded-lg flex items-center justify-center">
          <Users className="w-6 h-6" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">All Candidates</h1>
          <p className="text-sm text-[var(--text-secondary)]">Every screened candidate across all jobs, in one place.</p>
        </div>
      </div>

      {selectedIds.length > 0 ? (
        <div className="bg-[var(--color-primary-subtle-bg)] border border-[var(--color-primary-200)] p-4 rounded-t-xl border-b-0 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <span className="text-[var(--color-primary-subtle-text)] font-medium text-sm">{selectedIds.length} candidates selected</span>
            <div className="h-4 w-px bg-[var(--color-primary-200)]"></div>
            <button onClick={() => setSelectedIds([])} className="transition-base text-sm text-[var(--color-primary-600)] hover:text-[var(--color-primary-700)]">Clear</button>
          </div>
          <button
            onClick={() => setShowEmailModal(true)}
            className="transition-base px-3 py-1.5 bg-[var(--bg-surface)] text-[var(--color-primary-subtle-text)] border border-[var(--color-primary-200)] rounded text-sm hover:bg-[var(--color-primary-subtle-bg)] focus-ring font-medium flex items-center gap-1.5"
          >
            <Mail className="w-4 h-4" /> Email
          </button>
        </div>
      ) : (
        <div className="flex justify-end mb-4">
          <div className="w-56">
            <Select
              value={decision || 'all'}
              onValueChange={(value) => {
                setDecision(value === 'all' ? undefined : (value as CandidateDecision));
                setPage(1);
              }}
            >
              <SelectTrigger>
                <SelectValue placeholder="All Decisions" />
              </SelectTrigger>
              <SelectContent>
                {DECISION_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
      )}

      <div className={`bg-[var(--bg-surface)] border border-[var(--border-light)] shadow-sm overflow-hidden ${selectedIds.length > 0 ? 'rounded-b-xl' : 'rounded-xl'}`}>
        {isLoading && !data ? (
          <div className="flex justify-center items-center h-64">
            <Loader2 className="w-8 h-8 animate-spin text-[var(--color-primary-500)]" />
          </div>
        ) : isError ? (
          <div className="p-8 text-center text-[var(--color-danger-600)]">
            <p className="mb-4">Failed to load candidates{error instanceof Error ? `: ${error.message}` : '.'}</p>
            <Button variant="secondary" onClick={() => refetch()}>Retry</Button>
          </div>
        ) : !data || data.items.length === 0 ? (
          <div className="text-center py-20">
            <Users className="w-12 h-12 text-[var(--text-tertiary)] mx-auto mb-4" />
            <h3 className="text-lg font-medium text-[var(--text-primary)] mb-1">No candidates found</h3>
            <p className="text-[var(--text-secondary)]">Try a different decision filter, or come back once more resumes have been screened.</p>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-[var(--bg-app)] border-b border-[var(--border-light)] text-[var(--text-secondary)]">
                  <tr>
                    <th className="px-6 py-4 w-12">
                      <input
                        type="checkbox"
                        checked={data.items.length > 0 && selectedIds.length === data.items.length}
                        onChange={handleSelectAll}
                        className="rounded border-[var(--border-strong)] text-[var(--color-primary-600)] focus:ring-[var(--color-primary-600)]"
                      />
                    </th>
                    <th className="px-6 py-4 font-medium">Candidate</th>
                    <th className="px-6 py-4 font-medium">Job</th>
                    <th className="px-6 py-4 font-medium">Score</th>
                    <th className="px-6 py-4 font-medium">Decision</th>
                    <th className="px-6 py-4 text-right font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border-light)]">
                  {data.items.map((candidate: GlobalScreeningResultResponse) => (
                    <tr
                      key={`${candidate.job_id}-${candidate.resume_id}`}
                      className={`transition-colors cursor-pointer ${selectedIds.includes(candidate.resume_id) ? 'bg-[var(--color-primary-subtle-bg)]' : 'hover:bg-[var(--bg-hover)]'}`}
                      onClick={() => setSelectedCandidate({ jobId: candidate.job_id, resumeId: candidate.resume_id })}
                      tabIndex={0}
                      onKeyDown={(e) => e.key === 'Enter' && setSelectedCandidate({ jobId: candidate.job_id, resumeId: candidate.resume_id })}
                    >
                      <td className="px-6 py-4" onClick={(e) => e.stopPropagation()}>
                        <input
                          type="checkbox"
                          checked={selectedIds.includes(candidate.resume_id)}
                          onChange={(e) => handleSelect(e, candidate.resume_id)}
                          className="rounded border-[var(--border-strong)] text-[var(--color-primary-600)] focus:ring-[var(--color-primary-600)]"
                        />
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex items-center space-x-3">
                          <div className="w-8 h-8 bg-[var(--color-primary-subtle-bg)] text-[var(--color-primary-subtle-text)] rounded flex items-center justify-center">
                            <FileText className="w-4 h-4" />
                          </div>
                          <div>
                            <div className="font-medium text-[var(--text-primary)]">
                              {candidate.display_name || `Candidate #${candidate.resume_id}`}
                            </div>
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <button
                          onClick={(e) => { e.stopPropagation(); navigate(`/jobs/${candidate.job_id}`); }}
                          className="text-[var(--color-primary-600)] hover:underline font-medium"
                        >
                          {candidate.job_title}
                        </button>
                      </td>
                      <td className="px-6 py-4">
                        <span className={`font-semibold ${candidate.score != null && candidate.score >= 75 ? 'text-emerald-600' : candidate.score != null && candidate.score >= 50 ? 'text-amber-600' : 'text-[var(--text-secondary)]'}`}>
                          {candidate.score != null ? Math.round(candidate.score) : '—'}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        <Badge variant={getDecisionBadgeVariant(candidate.decision)}>
                          {candidate.decision ? candidate.decision.replace(/_/g, ' ') : 'Pending'}
                        </Badge>
                      </td>
                      <td className="px-6 py-4 text-right" onClick={(e) => e.stopPropagation()}>
                        <button
                          onClick={() => addToPool.mutate({ resume_id: candidate.resume_id, added_from_job_id: candidate.job_id })}
                          disabled={addToPool.isPending}
                          title="Add to Talent Pool"
                          aria-label={`Add resume ${candidate.resume_id} to Talent Pool`}
                          className="p-1.5 rounded-full text-[var(--text-tertiary)] hover:bg-[var(--bg-hover)] hover:text-[var(--color-primary-600)] transition-colors disabled:opacity-50"
                        >
                          <PackagePlus className="w-5 h-5" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="px-6 py-4 border-t border-[var(--border-light)] bg-[var(--bg-app)] flex items-center justify-between text-sm text-[var(--text-secondary)]">
              <span>
                Showing {(page - 1) * PAGE_SIZE + 1}-{Math.min(page * PAGE_SIZE, data.total)} of {data.total}
              </span>
              <div className="flex gap-1">
                <button
                  disabled={page === 1}
                  onClick={() => setPage((p) => p - 1)}
                  className="p-1 rounded hover:bg-[var(--bg-hover)] disabled:opacity-50 text-[var(--text-secondary)] focus-ring"
                >
                  <ChevronLeft className="w-5 h-5" />
                </button>
                <button
                  disabled={page * PAGE_SIZE >= data.total}
                  onClick={() => setPage((p) => p + 1)}
                  className="p-1 rounded hover:bg-[var(--bg-hover)] disabled:opacity-50 text-[var(--text-secondary)] focus-ring"
                >
                  <ChevronRight className="w-5 h-5" />
                </button>
              </div>
            </div>
          </>
        )}
      </div>

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
