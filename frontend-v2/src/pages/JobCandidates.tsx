import { useState } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient, keepPreviousData } from '@tanstack/react-query';
import { Search, ChevronLeft, ChevronRight, CheckCircle2, XCircle, Clock, Mail, PackagePlus } from 'lucide-react';
import { jobsApi } from '../api/jobs';
import { queryKeys } from '../api/queryKeys';
import { useDecisionMutation } from '../hooks/useDecisionMutation';
import { useAddToTalentPool } from '../hooks/useTalentPool';
import type { CandidateDecision } from '../types';
import { CandidateDrawer } from '../components/CandidateDrawer';
import { BulkEmailModal } from '../components/BulkEmailModal';
import { variantButtonClasses } from '../utils/decision';
import { getInitials } from '../utils/initials';
import { Button, PageHeader, ScoreRing, SkeletonRow } from '../components/ui';

export const JobCandidates = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const jobId = parseInt(id || '0', 10);

  const location = useLocation();
  // decision can be a CandidateDecision or a special filter string ('PRE_SCREENED_OUT', 'FAILED')
  const [params, setParams] = useState<{
    page: number;
    decision?: CandidateDecision;
    status?: string;
    sort_by: 'score' | 'created_at';
    min_score?: number;
    max_score?: number;
  }>(location.state?.params || { page: 1, sort_by: 'score' });

  const [selectedResumeId, setSelectedResumeId] = useState<number | null>(null);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [showEmailModal, setShowEmailModal] = useState(false);

  const queryClient = useQueryClient();

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: queryKeys.candidates(jobId, params),
    queryFn: () => jobsApi.getJobResults(jobId, params),
    placeholderData: keepPreviousData,
    staleTime: 0,
  });

  const { data: jobMeta } = useQuery({
    queryKey: ['job', jobId],
    queryFn: () => jobsApi.getJob(jobId),
    enabled: jobId > 0,
  });

  const decisionMutation = useDecisionMutation(jobId);
  const addToPool = useAddToTalentPool();

  const handleDecision = (resumeId: number, decision: CandidateDecision | null) => {
    decisionMutation.mutate({ resumeId, decision });
  };

  const bulkDecisionMutation = useMutation({
    mutationFn: ({ resumeIds, decision }: { resumeIds: number[], decision: CandidateDecision }) =>
      jobsApi.bulkUpdateDecision(jobId, resumeIds, decision),
    onSuccess: () => {
      // Invalidate all paginated/filtered variants for this job, not just the current one
      queryClient.invalidateQueries({ queryKey: queryKeys.candidates(jobId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.candidateDetail(jobId, 0).slice(0, 2) });
      setSelectedIds([]);
    }
  });

  const handleSelectAll = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.checked && data?.items) {
      setSelectedIds(data.items.map((c: any) => c.resume_id));
    } else {
      setSelectedIds([]);
    }
  };

  const handleSelect = (e: React.ChangeEvent<HTMLInputElement>, resumeId: number) => {
    if (e.target.checked) {
      setSelectedIds(prev => [...prev, resumeId]);
    } else {
      setSelectedIds(prev => prev.filter(id => id !== resumeId));
    }
  };

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="flex items-center gap-2 text-sm text-[var(--text-secondary)] mb-6">
        <button onClick={() => navigate('/jobs')} className="transition-base hover:text-[var(--text-primary)]">Jobs</button>
        <span>/</span>
        <button onClick={() => navigate(`/jobs/${id}`)} className="transition-base hover:text-[var(--text-primary)]">{jobMeta?.title || 'Job'}</button>
        <span>/</span>
        <span className="text-[var(--text-primary)] font-medium">Candidates</span>
      </div>

      <PageHeader
        className="mb-6"
        title="Screening Results"
        subtitle="Review candidates and make shortlisting decisions."
      />

      {/* Filters or Bulk Actions Toolbar */}
      {selectedIds.length > 0 ? (
        <div className="bg-[var(--color-primary-subtle-bg)] border border-[var(--color-primary-200)] p-4 rounded-t-xl border-b-0 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <span className="text-[var(--color-primary-subtle-text)] font-medium text-sm">{selectedIds.length} candidates selected</span>
            <div className="h-4 w-px bg-[var(--color-primary-200)]"></div>
            <button onClick={() => setSelectedIds([])} className="transition-base text-sm text-[var(--color-primary-600)] hover:text-[var(--color-primary-700)]">Clear</button>
          </div>
          <div className="flex gap-2">
            <button onClick={() => setShowEmailModal(true)} className="transition-base px-3 py-1.5 bg-[var(--bg-surface)] text-[var(--color-primary-subtle-text)] border border-[var(--color-primary-200)] rounded text-sm hover:bg-[var(--color-primary-subtle-bg)] focus-ring font-medium flex items-center gap-1.5">
              <Mail className="w-4 h-4" /> Email
            </button>
            <div className="w-px bg-[var(--color-primary-200)] mx-1 h-8 self-center"></div>
            <button onClick={() => bulkDecisionMutation.mutate({ resumeIds: selectedIds, decision: 'SHORTLIST' })} disabled={bulkDecisionMutation.isPending} className="transition-base px-3 py-1.5 bg-[var(--bg-surface)] text-[var(--color-success-subtle-text)] border border-[var(--border-light)] rounded text-sm hover:bg-[var(--color-success-subtle-bg)] focus-ring font-medium">Shortlist</button>
            <button onClick={() => bulkDecisionMutation.mutate({ resumeIds: selectedIds, decision: 'REVIEW' })} disabled={bulkDecisionMutation.isPending} className="transition-base px-3 py-1.5 bg-[var(--bg-surface)] text-[var(--color-warning-subtle-text)] border border-[var(--border-light)] rounded text-sm hover:bg-[var(--color-warning-subtle-bg)] focus-ring font-medium">Review</button>
            <button onClick={() => bulkDecisionMutation.mutate({ resumeIds: selectedIds, decision: 'REJECT' })} disabled={bulkDecisionMutation.isPending} className="transition-base px-3 py-1.5 bg-[var(--bg-surface)] text-[var(--color-danger-subtle-text)] border border-[var(--border-light)] rounded text-sm hover:bg-[var(--color-danger-subtle-bg)] focus-ring font-medium">Reject</button>
          </div>
        </div>
      ) : (
        <div className="bg-[var(--bg-surface)] p-4 border border-[var(--border-light)] rounded-t-xl border-b-0 flex flex-wrap gap-4 items-center justify-between">
          <div className="flex flex-wrap gap-2">
            <FilterChip
              active={!params.decision && !params.status}
              label="All"
              onClick={() => setParams(p => ({ ...p, decision: undefined, status: undefined, page: 1 }))}
            />
            <FilterChip
              active={params.decision === 'SHORTLIST'}
              label="Shortlisted"
              onClick={() => setParams(p => ({ ...p, decision: 'SHORTLIST', status: undefined, page: 1 }))}
            />
            <FilterChip
              active={params.decision === 'REVIEW'}
              label="Review"
              onClick={() => setParams(p => ({ ...p, decision: 'REVIEW', status: undefined, page: 1 }))}
            />
            <FilterChip
              active={params.decision === 'REJECT'}
              label="Rejected"
              onClick={() => setParams(p => ({ ...p, decision: 'REJECT', status: undefined, page: 1 }))}
            />
            <FilterChip
              active={params.decision === 'PRE_SCREENED_OUT'}
              label="Pre-screened Out"
              variant="warning"
              onClick={() => setParams(p => ({ ...p, decision: 'PRE_SCREENED_OUT', status: undefined, page: 1 }))}
            />
            <FilterChip
              active={params.status === 'FAILED'}
              label="Failed"
              variant="danger"
              onClick={() => setParams(p => ({ ...p, decision: undefined, status: 'FAILED', page: 1 }))}
            />
          </div>

          <div className="flex items-center gap-4">
            <select
              className="border-[var(--border-strong)] rounded-md text-sm pl-3 pr-8 py-2 border shadow-[var(--shadow-sm)] bg-[var(--bg-surface)] text-[var(--text-primary)] focus-ring"
              value={params.decision || ''}
              onChange={(e) => setParams(p => ({ ...p, decision: (e.target.value as CandidateDecision) || undefined, status: undefined, page: 1 }))}
            >
              <option value="">All Decisions</option>
              <option value="SHORTLIST">Shortlisted</option>
              <option value="REVIEW">Needs Review</option>
              <option value="REJECT">Rejected</option>
            </select>

            <select
              className="border-[var(--border-strong)] rounded-md text-sm pl-3 pr-8 py-2 border shadow-[var(--shadow-sm)] bg-[var(--bg-surface)] text-[var(--text-primary)] focus-ring"
              value={params.sort_by}
              onChange={(e) => setParams(p => ({ ...p, sort_by: e.target.value as any, page: 1 }))}
            >
              <option value="score">Sort: Score</option>
              <option value="created_at">Sort: Latest</option>
            </select>
          </div>
        </div>
      )}

      {/* Table Area */}
      <div className="bg-[var(--bg-surface)] border border-[var(--border-light)] rounded-b-xl overflow-hidden shadow-[var(--shadow-sm)]">
        {isError ? (
          <div className="p-8 text-center text-[var(--color-danger-600)]">
            <p className="mb-4">Error loading candidates: {error instanceof Error ? error.message : 'Unknown'}</p>
            <Button variant="secondary" onClick={() => refetch()}>Retry</Button>
          </div>
        ) : !isLoading && data?.items.length === 0 ? (
          <div className="p-16 text-center">
            <Search className="w-12 h-12 text-[var(--text-tertiary)] mx-auto mb-4" />
            <h3 className="text-card-title mb-1">No candidates found</h3>
            <p className="text-body">Try adjusting your filters or upload more resumes.</p>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-left">
              <thead className="text-xs text-[var(--text-secondary)] bg-[var(--bg-app)] uppercase border-b border-[var(--border-light)]">
                <tr>
                  <th className="px-6 py-4 w-12">
                    <input
                      type="checkbox"
                      checked={(data?.items?.length ?? 0) > 0 && selectedIds.length === data?.items?.length}
                      onChange={handleSelectAll}
                      className="rounded border-[var(--border-strong)] text-[var(--color-primary-600)] focus:ring-[var(--color-primary-600)]"
                    />
                  </th>
                  <th className="px-6 py-4 font-medium">Candidate</th>
                  <th className="px-6 py-4 font-medium">Scores</th>
                  <th className="px-6 py-4 font-medium hidden md:table-cell">Evaluation</th>
                  <th className="px-6 py-4 font-medium text-center">Decision</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-light)]">
                {isLoading && !data ? (
                  Array.from({ length: 8 }).map((_, i) => (
                    <SkeletonRow key={i} columns={['checkbox', 'avatar', 'score', 'text', 'actions']} />
                  ))
                ) : data?.items?.map((c) => (
                  <tr
                    key={c.resume_id}
                    className={`transition-base cursor-pointer group ${selectedIds.includes(c.resume_id) ? 'bg-[var(--color-primary-subtle-bg)]' : 'hover:bg-[var(--color-primary-50)]'}`}
                    onClick={() => setSelectedResumeId(c.resume_id)}
                    tabIndex={0}
                    onKeyDown={(e) => e.key === 'Enter' && setSelectedResumeId(c.resume_id)}
                  >
                    <td className="px-6 py-4" onClick={(e) => e.stopPropagation()}>
                      <input
                        type="checkbox"
                        checked={selectedIds.includes(c.resume_id)}
                        onChange={(e) => handleSelect(e, c.resume_id)}
                        className="rounded border-[var(--border-strong)] text-[var(--color-primary-600)] focus:ring-[var(--color-primary-600)]"
                      />
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <div className={`w-10 h-10 rounded-full flex items-center justify-center font-medium ${c.decision === 'PRE_SCREENED_OUT' ? 'bg-[var(--color-danger-subtle-bg)] text-[var(--color-danger-subtle-text)]' : c.status === 'FAILED' ? 'bg-[var(--color-danger-subtle-bg)] text-[var(--color-danger-subtle-text)]' : c.status === 'PROCESSING' || c.status === 'UPLOADED' ? 'bg-[var(--color-warning-subtle-bg)] text-[var(--color-warning-subtle-text)]' : 'bg-[var(--bg-hover)] text-[var(--text-secondary)]'}`}>
                          {getInitials(c.display_name)}
                        </div>
                        <div>
                          <div className="font-semibold text-[var(--text-primary)]">{c.display_name || `Resume #${c.resume_id}`}</div>
                          <div className="text-xs text-[var(--text-tertiary)] capitalize">{c.status ? c.status.toLowerCase().replace(/_/g, ' ') : 'Unknown'}</div>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <ScoreRing score={c.score} size="sm" />
                        <div className="text-xs text-[var(--text-tertiary)]">
                          Semantic: {c.semantic_score?.toFixed(3) || '—'}
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4 hidden md:table-cell max-w-sm">
                      <div className="flex flex-wrap gap-1.5 mb-2">
                        {c.strengths?.slice(0, 2).map((s: string, i: number) => (
                          <span key={i} className="px-2 py-0.5 rounded text-[10px] font-medium bg-[var(--color-success-subtle-bg)] text-[var(--color-success-subtle-text)] border border-[var(--border-light)] truncate max-w-[120px]">
                            + {s}
                          </span>
                        ))}
                        {c.gaps?.slice(0, 1).map((g: string, i: number) => (
                          <span key={i} className="px-2 py-0.5 rounded text-[10px] font-medium bg-[var(--color-danger-subtle-bg)] text-[var(--color-danger-subtle-text)] border border-[var(--border-light)] truncate max-w-[120px]">
                            - {g}
                          </span>
                        ))}
                      </div>
                      <p className="text-xs text-[var(--text-secondary)] line-clamp-2 leading-relaxed">
                        {c.decision === 'PRE_SCREENED_OUT' ? (
                          <span className="inline-flex items-center gap-1 text-[var(--color-warning-subtle-text)] font-medium px-2 py-1 bg-[var(--color-warning-subtle-bg)] border border-[var(--border-light)] rounded">
                            Not advanced by semantic pre-screening
                          </span>
                        ) : c.evidence?.[0] ? c.evidence[0] : (
                          <span className="text-[var(--text-tertiary)] italic">No evidence provided.</span>
                        )}
                      </p>
                    </td>
                    <td className="px-6 py-4" onClick={(e) => e.stopPropagation()}>
                      <div className="flex justify-end items-center space-x-2">
                        <button
                          onClick={(e) => { e.stopPropagation(); handleDecision(c.resume_id, 'SHORTLIST'); }}
                          disabled={decisionMutation.isPending}
                          aria-label={`Shortlist resume ${c.resume_id}`}
                          className={`transition-base p-1.5 rounded-full ${c.decision === 'SHORTLIST' ? variantButtonClasses.success : 'hover:bg-[var(--bg-hover)] text-[var(--text-tertiary)] hover:text-[var(--color-success-600)]'}`}
                          title="Shortlist"
                        >
                          <CheckCircle2 className="w-5 h-5" />
                        </button>
                        <button
                          onClick={(e) => { e.stopPropagation(); handleDecision(c.resume_id, 'REVIEW'); }}
                          disabled={decisionMutation.isPending}
                          aria-label={`Mark resume ${c.resume_id} for review`}
                          className={`transition-base p-1.5 rounded-full ${c.decision === 'REVIEW' ? variantButtonClasses.warning : 'hover:bg-[var(--bg-hover)] text-[var(--text-tertiary)] hover:text-[var(--color-warning-600)]'}`}
                          title="Review"
                        >
                          <Clock className="w-5 h-5" />
                        </button>
                        <button
                          onClick={(e) => { e.stopPropagation(); handleDecision(c.resume_id, 'REJECT'); }}
                          disabled={decisionMutation.isPending}
                          aria-label={`Reject resume ${c.resume_id}`}
                          className={`transition-base p-1.5 rounded-full ${c.decision === 'REJECT' ? variantButtonClasses.danger : 'hover:bg-[var(--bg-hover)] text-[var(--text-tertiary)] hover:text-[var(--color-danger-600)]'}`}
                          title="Reject"
                        >
                          <XCircle className="w-5 h-5" />
                        </button>
                        <button
                          onClick={(e) => { e.stopPropagation(); handleDecision(c.resume_id, null); }}
                          disabled={decisionMutation.isPending}
                          aria-label={`Clear decision for resume ${c.resume_id}`}
                          className="transition-base p-1.5 rounded-full hover:bg-[var(--bg-hover)] text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] text-xs font-medium"
                          title="Clear Decision"
                        >
                          Clear
                        </button>
                        <button
                          onClick={(e) => { e.stopPropagation(); addToPool.mutate({ resume_id: c.resume_id, added_from_job_id: jobId }); }}
                          disabled={addToPool.isPending}
                          aria-label={`Add resume ${c.resume_id} to Talent Pool`}
                          className="transition-base p-1.5 rounded-full hover:bg-[var(--bg-hover)] text-[var(--text-tertiary)] hover:text-[var(--color-primary-600)]"
                          title="Add to Talent Pool"
                        >
                          <PackagePlus className="w-5 h-5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>

            {/* Pagination */}
            {data && data.total > 0 && (
              <div className="px-6 py-4 border-t border-[var(--border-light)] flex items-center justify-between bg-[var(--bg-app)]">
                <span className="text-sm text-[var(--text-secondary)]">
                  Showing {(params.page - 1) * 20 + 1}-{Math.min(params.page * 20, data.total)} of {data.total}
                </span>
                <div className="flex gap-1">
                  <button
                    disabled={params.page === 1}
                    onClick={() => setParams(p => ({ ...p, page: p.page - 1 }))}
                    className="transition-base p-1 rounded hover:bg-[var(--bg-hover)] disabled:opacity-50 text-[var(--text-secondary)] focus-ring"
                  >
                    <ChevronLeft className="w-5 h-5" />
                  </button>
                  <button
                    disabled={params.page * 20 >= data.total}
                    onClick={() => setParams(p => ({ ...p, page: p.page + 1 }))}
                    className="transition-base p-1 rounded hover:bg-[var(--bg-hover)] disabled:opacity-50 text-[var(--text-secondary)] focus-ring"
                  >
                    <ChevronRight className="w-5 h-5" />
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>

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
          jobId={jobId}
          selectedResumeIds={selectedIds}
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

const FilterChip = ({ active, label, onClick, variant = 'default' }: { active: boolean, label: string, onClick: () => void, variant?: 'default' | 'warning' | 'danger' }) => {
  const activeClass =
    variant === 'warning' ? 'bg-[var(--color-warning-600)] text-white' :
    variant === 'danger'  ? 'bg-[var(--color-danger-600)] text-white' :
    'bg-[var(--text-primary)] text-[var(--bg-surface)]';
  return (
    <button
      onClick={onClick}
      className={`transition-base px-4 py-1.5 rounded-full text-sm font-medium ${
        active ? activeClass : 'bg-[var(--bg-hover)] text-[var(--text-secondary)] hover:bg-[var(--border-light)]'
      }`}
    >
      {label}
    </button>
  );
};
