import { useState } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient, keepPreviousData } from '@tanstack/react-query';
import { Loader2, Search, ChevronLeft, ChevronRight, CheckCircle2, XCircle, Clock, Mail } from 'lucide-react';
import { jobsApi } from '../api/jobs';
import { queryKeys } from '../api/queryKeys';
import { useDecisionMutation } from '../hooks/useDecisionMutation';
import type { CandidateDecision } from '../types';
import { CandidateDrawer } from '../components/CandidateDrawer';
import { BulkEmailModal } from '../components/BulkEmailModal';

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

  const { data, isLoading, isError, error } = useQuery({
    queryKey: queryKeys.candidates(jobId, params),
    queryFn: () => jobsApi.getJobResults(jobId, params),
    placeholderData: keepPreviousData,
    staleTime: 0,
  });

  const decisionMutation = useDecisionMutation(jobId);

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
      <div className="flex items-center gap-2 text-sm text-slate-500 mb-6">
        <button onClick={() => navigate('/jobs')} className="hover:text-slate-900 transition-colors">Jobs</button>
        <span>/</span>
        <button onClick={() => navigate(`/jobs/${id}`)} className="hover:text-slate-900 transition-colors">Job #{id}</button>
        <span>/</span>
        <span className="text-slate-900 font-medium">Candidates</span>
      </div>

      <div className="flex justify-between items-end mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900 mb-1">Screening Results</h1>
          <p className="text-slate-500">Review candidates and make shortlisting decisions.</p>
        </div>
      </div>

      {/* Filters or Bulk Actions Toolbar */}
      {selectedIds.length > 0 ? (
        <div className="bg-indigo-50 border border-indigo-200 p-4 rounded-t-xl border-b-0 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <span className="text-indigo-800 font-medium text-sm">{selectedIds.length} candidates selected</span>
            <div className="h-4 w-px bg-indigo-200"></div>
            <button onClick={() => setSelectedIds([])} className="text-sm text-indigo-600 hover:text-indigo-800">Clear</button>
          </div>
          <div className="flex gap-2">
            <button onClick={() => setShowEmailModal(true)} className="px-3 py-1.5 bg-white text-blue-700 border border-blue-200 rounded text-sm hover:bg-blue-50 focus-ring font-medium flex items-center gap-1.5">
              <Mail className="w-4 h-4" /> Email
            </button>
            <div className="w-px bg-indigo-200 mx-1 h-8 self-center"></div>
            <button onClick={() => bulkDecisionMutation.mutate({ resumeIds: selectedIds, decision: 'SHORTLIST' })} disabled={bulkDecisionMutation.isPending} className="px-3 py-1.5 bg-white text-emerald-700 border border-emerald-200 rounded text-sm hover:bg-emerald-50 focus-ring font-medium">Shortlist</button>
            <button onClick={() => bulkDecisionMutation.mutate({ resumeIds: selectedIds, decision: 'REVIEW' })} disabled={bulkDecisionMutation.isPending} className="px-3 py-1.5 bg-white text-amber-700 border border-amber-200 rounded text-sm hover:bg-amber-50 focus-ring font-medium">Review</button>
            <button onClick={() => bulkDecisionMutation.mutate({ resumeIds: selectedIds, decision: 'REJECT' })} disabled={bulkDecisionMutation.isPending} className="px-3 py-1.5 bg-white text-rose-700 border border-rose-200 rounded text-sm hover:bg-rose-50 focus-ring font-medium">Reject</button>
          </div>
        </div>
      ) : (
        <div className="bg-white p-4 border border-slate-200 rounded-t-xl border-b-0 flex flex-wrap gap-4 items-center justify-between">
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
              className="border-slate-300 rounded-md text-sm pl-3 pr-8 py-2 border shadow-sm bg-white focus-ring"
              value={params.decision || ''}
              onChange={(e) => setParams(p => ({ ...p, decision: (e.target.value as CandidateDecision) || undefined, status: undefined, page: 1 }))}
            >
              <option value="">All Decisions</option>
              <option value="SHORTLIST">Shortlisted</option>
              <option value="REVIEW">Needs Review</option>
              <option value="REJECT">Rejected</option>
            </select>

            <select 
              className="border-slate-300 rounded-md text-sm pl-3 pr-8 py-2 border shadow-sm bg-white focus-ring"
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
      <div className="bg-white border border-slate-200 rounded-b-xl overflow-hidden shadow-sm">
        {isLoading && !data ? (
          <div className="flex justify-center items-center h-64">
            <Loader2 className="w-8 h-8 animate-spin text-[var(--color-primary-500)]" />
          </div>
        ) : isError ? (
          <div className="p-8 text-center text-red-600">
            Error loading candidates: {error instanceof Error ? error.message : 'Unknown'}
          </div>
        ) : data?.items.length === 0 ? (
          <div className="p-16 text-center">
            <Search className="w-12 h-12 text-slate-300 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-slate-900 mb-1">No candidates found</h3>
            <p className="text-slate-500">Try adjusting your filters or upload more resumes.</p>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-left">
              <thead className="text-xs text-slate-500 bg-slate-50 uppercase border-b border-slate-200">
                <tr>
                  <th className="px-6 py-4 w-12">
                    <input 
                      type="checkbox" 
                      checked={(data?.items?.length ?? 0) > 0 && selectedIds.length === data?.items?.length}
                      onChange={handleSelectAll}
                      className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-600"
                    />
                  </th>
                  <th className="px-6 py-4 font-medium">Candidate</th>
                  <th className="px-6 py-4 font-medium">Scores</th>
                  <th className="px-6 py-4 font-medium hidden md:table-cell">Evaluation</th>
                  <th className="px-6 py-4 font-medium text-center">Decision</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data?.items?.map((c) => (
                  <tr 
                    key={c.resume_id} 
                    className={`transition-colors cursor-pointer group ${selectedIds.includes(c.resume_id) ? 'bg-indigo-50/50' : 'hover:bg-[var(--color-primary-50)]'}`}
                    onClick={() => setSelectedResumeId(c.resume_id)}
                    tabIndex={0}
                    onKeyDown={(e) => e.key === 'Enter' && setSelectedResumeId(c.resume_id)}
                  >
                    <td className="px-6 py-4" onClick={(e) => e.stopPropagation()}>
                      <input 
                        type="checkbox" 
                        checked={selectedIds.includes(c.resume_id)}
                        onChange={(e) => handleSelect(e, c.resume_id)}
                        className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-600"
                      />
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <div className={`w-10 h-10 rounded-full flex items-center justify-center font-medium ${c.decision === 'PRE_SCREENED_OUT' ? 'bg-rose-100 text-rose-600' : c.status === 'FAILED' ? 'bg-red-100 text-red-600' : c.status === 'PROCESSING' || c.status === 'UPLOADED' ? 'bg-amber-100 text-amber-600' : 'bg-slate-100 text-slate-600'}`}>
                          R{c.resume_id}
                        </div>
                        <div>
                          <div className="font-semibold text-slate-900">{c.display_name || `Resume #${c.resume_id}`}</div>
                          <div className="text-xs text-slate-500 capitalize">{c.status ? c.status.toLowerCase().replace(/_/g, ' ') : 'Unknown'}</div>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex flex-col gap-1.5">
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-slate-400 w-16">Fit Score</span>
                          <span className={`font-semibold ${c.score != null && c.score >= 75 ? 'text-emerald-600' : c.score != null && c.score >= 50 ? 'text-amber-600' : 'text-slate-700'}`}>
                            {c.score != null ? Math.round(c.score) : '—'}
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-slate-400 w-16">Semantic</span>
                          <span className="text-slate-600 font-medium">{c.semantic_score?.toFixed(3) || '—'}</span>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4 hidden md:table-cell max-w-sm">
                      <div className="flex flex-wrap gap-1.5 mb-2">
                        {c.strengths?.slice(0, 2).map((s: string, i: number) => (
                          <span key={i} className="px-2 py-0.5 rounded text-[10px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-100 truncate max-w-[120px]">
                            + {s}
                          </span>
                        ))}
                        {c.gaps?.slice(0, 1).map((g: string, i: number) => (
                          <span key={i} className="px-2 py-0.5 rounded text-[10px] font-medium bg-rose-50 text-rose-700 border border-rose-100 truncate max-w-[120px]">
                            - {g}
                          </span>
                        ))}
                      </div>
                      <p className="text-xs text-slate-500 line-clamp-2 leading-relaxed">
                        {c.decision === 'PRE_SCREENED_OUT' ? (
                          <span className="inline-flex items-center gap-1 text-amber-700 font-medium px-2 py-1 bg-amber-50 border border-amber-100 rounded">
                            Not advanced by semantic pre-screening
                          </span>
                        ) : c.evidence?.[0] ? c.evidence[0] : (
                          <span className="text-slate-400 italic">No evidence provided.</span>
                        )}
                      </p>
                    </td>
                    <td className="px-6 py-4" onClick={(e) => e.stopPropagation()}>
                      <div className="flex justify-end items-center space-x-2">
                        <button 
                          onClick={(e) => { e.stopPropagation(); handleDecision(c.resume_id, 'SHORTLIST'); }}
                          disabled={decisionMutation.isPending}
                          aria-label={`Shortlist resume ${c.resume_id}`}
                          className={`p-1.5 rounded-full transition-colors ${c.decision === 'SHORTLIST' ? 'bg-green-100 text-green-700' : 'hover:bg-gray-100 text-gray-400 hover:text-green-600'}`}
                          title="Shortlist"
                        >
                          <CheckCircle2 className="w-5 h-5" />
                        </button>
                        <button 
                          onClick={(e) => { e.stopPropagation(); handleDecision(c.resume_id, 'REVIEW'); }}
                          disabled={decisionMutation.isPending}
                          aria-label={`Mark resume ${c.resume_id} for review`}
                          className={`p-1.5 rounded-full transition-colors ${c.decision === 'REVIEW' ? 'bg-amber-100 text-amber-700' : 'hover:bg-gray-100 text-gray-400 hover:text-amber-600'}`}
                          title="Review"
                        >
                          <Clock className="w-5 h-5" />
                        </button>
                        <button 
                          onClick={(e) => { e.stopPropagation(); handleDecision(c.resume_id, 'REJECT'); }}
                          disabled={decisionMutation.isPending}
                          aria-label={`Reject resume ${c.resume_id}`}
                          className={`p-1.5 rounded-full transition-colors ${c.decision === 'REJECT' ? 'bg-red-100 text-red-700' : 'hover:bg-gray-100 text-gray-400 hover:text-red-600'}`}
                          title="Reject"
                        >
                          <XCircle className="w-5 h-5" />
                        </button>
                        <button 
                          onClick={(e) => { e.stopPropagation(); handleDecision(c.resume_id, null); }}
                          disabled={decisionMutation.isPending}
                          aria-label={`Clear decision for resume ${c.resume_id}`}
                          className="p-1.5 rounded-full transition-colors hover:bg-gray-100 text-gray-400 hover:text-gray-600 text-xs font-medium"
                          title="Clear Decision"
                        >
                          Clear
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
              <div className="px-6 py-4 border-t border-slate-200 flex items-center justify-between bg-slate-50">
                <span className="text-sm text-slate-500">
                  Showing {(params.page - 1) * 20 + 1}-{Math.min(params.page * 20, data.total)} of {data.total}
                </span>
                <div className="flex gap-1">
                  <button 
                    disabled={params.page === 1} 
                    onClick={() => setParams(p => ({ ...p, page: p.page - 1 }))}
                    className="p-1 rounded hover:bg-slate-200 disabled:opacity-50 text-slate-600 focus-ring"
                  >
                    <ChevronLeft className="w-5 h-5" />
                  </button>
                  <button 
                    disabled={params.page * 20 >= data.total} 
                    onClick={() => setParams(p => ({ ...p, page: p.page + 1 }))}
                    className="p-1 rounded hover:bg-slate-200 disabled:opacity-50 text-slate-600 focus-ring"
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
    variant === 'warning' ? 'bg-amber-600 text-white' :
    variant === 'danger'  ? 'bg-red-600 text-white' :
    'bg-slate-800 text-white';
  return (
    <button 
      onClick={onClick}
      className={`px-4 py-1.5 rounded-full text-sm font-medium transition-colors ${
        active ? activeClass : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
      }`}
    >
      {label}
    </button>
  );
};
