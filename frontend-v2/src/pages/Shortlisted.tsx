import { useNavigate } from 'react-router-dom';
import { useShortlistedCandidates } from '../hooks/useShortlistedCandidates';
import { useAddToTalentPool } from '../hooks/useTalentPool';
import { Users, FileText, CheckCircle2, PackagePlus } from 'lucide-react';
import { useState } from 'react';
import { CandidateDrawer } from '../components/CandidateDrawer';
import { PageHeader, ScoreRing, SkeletonRow } from '../components/ui';
import type { GlobalScreeningResultResponse } from '../types';

export const Shortlisted = () => {
  const { candidates, isLoading, isError } = useShortlistedCandidates();
  const navigate = useNavigate();
  const [selectedCandidate, setSelectedCandidate] = useState<{jobId: number, resumeId: number} | null>(null);
  const addToPool = useAddToTalentPool();

  if (isError) {
    return (
      <div className="p-8 text-center text-[var(--color-danger-600)]">
        Failed to load shortlisted candidates.
      </div>
    );
  }

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <PageHeader
        className="mb-8"
        eyebrow={
          <div className="w-10 h-10 bg-[var(--color-success-subtle-bg)] text-[var(--color-success-subtle-text)] rounded-lg flex items-center justify-center mb-2">
            <CheckCircle2 className="w-6 h-6" />
          </div>
        }
        title="Shortlisted Candidates"
        subtitle="Candidates marked for moving forward across all jobs."
      />

      {!isLoading && candidates.length === 0 ? (
        <div className="text-center py-20 bg-[var(--bg-surface)] rounded-xl border border-[var(--border-light)]">
          <Users className="w-12 h-12 text-[var(--text-tertiary)] mx-auto mb-4" />
          <h3 className="text-card-title mb-1">No shortlisted candidates yet</h3>
          <p className="text-body">Review candidate results and mark them as shortlisted to see them here.</p>
        </div>
      ) : (
        <div className="bg-[var(--bg-surface)] border border-[var(--border-light)] rounded-xl shadow-[var(--shadow-sm)] overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-[var(--text-secondary)]">
              <thead className="bg-[var(--bg-app)] border-b border-[var(--border-light)] text-[var(--text-secondary)]">
                <tr>
                  <th className="px-6 py-4 font-medium">Candidate</th>
                  <th className="px-6 py-4 font-medium">Job</th>
                  <th className="px-6 py-4 font-medium">Fit Score</th>
                  <th className="px-6 py-4 font-medium hidden md:table-cell">Key Strengths</th>
                  <th className="px-6 py-4 text-right font-medium">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-light)]">
                {isLoading ? (
                  Array.from({ length: 6 }).map((_, i) => (
                    <SkeletonRow key={i} columns={['avatar', 'text', 'score', 'text', 'actions']} />
                  ))
                ) : candidates.map((candidate: GlobalScreeningResultResponse) => (
                  <tr
                    key={`${candidate.job_id}-${candidate.resume_id}`}
                    className="transition-base hover:bg-[var(--bg-app)] group cursor-pointer"
                    onClick={() => setSelectedCandidate({ jobId: candidate.job_id, resumeId: candidate.resume_id })}
                  >
                    <td className="px-6 py-4">
                      <div className="flex items-center space-x-3">
                        <div className="w-8 h-8 bg-[var(--color-primary-subtle-bg)] text-[var(--color-primary-subtle-text)] rounded flex items-center justify-center">
                          <FileText className="w-4 h-4" />
                        </div>
                        <div>
                          <div className="font-medium text-[var(--text-primary)]">{candidate.display_name || `Candidate #${candidate.resume_id}`}</div>
                          <div className="text-xs text-[var(--text-tertiary)]">ID: {candidate.id}</div>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          navigate(`/jobs/${candidate.job_id}`);
                        }}
                        className="transition-base text-[var(--color-primary-600)] hover:text-[var(--color-primary-700)] hover:underline font-medium"
                      >
                        {candidate.job_title}
                      </button>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center space-x-2">
                        <ScoreRing score={candidate.score} size="md" />
                        <div className="text-xs text-[var(--text-tertiary)]">
                          Semantic: {candidate.semantic_score != null ? `${Math.round(candidate.semantic_score * 100)}%` : '—'}
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4 hidden md:table-cell max-w-xs">
                      {candidate.strengths && candidate.strengths.length > 0 ? (
                        <ul className="text-xs list-disc list-inside space-y-1 text-[var(--text-secondary)]">
                          {candidate.strengths.slice(0, 2).map((s: string, i: number) => (
                            <li key={i} className="truncate">{s}</li>
                          ))}
                        </ul>
                      ) : (
                        <span className="text-[var(--text-tertiary)] italic">No strengths listed</span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-right">
                      <div className="flex items-center justify-end gap-3">
                        <button
                          onClick={(e) => { e.stopPropagation(); addToPool.mutate({ resume_id: candidate.resume_id, added_from_job_id: candidate.job_id }); }}
                          disabled={addToPool.isPending}
                          aria-label={`Add resume ${candidate.resume_id} to Talent Pool`}
                          title="Add to Talent Pool"
                          className="transition-base p-1.5 rounded-full text-[var(--text-tertiary)] hover:bg-[var(--bg-hover)] hover:text-[var(--color-primary-600)] disabled:opacity-50"
                        >
                          <PackagePlus className="w-4 h-4" />
                        </button>
                        <span className="transition-base text-sm font-medium text-[var(--color-primary-600)] opacity-0 group-hover:opacity-100">
                          View 360 &rarr;
                        </span>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="px-6 py-4 border-t border-[var(--border-light)] bg-[var(--bg-app)] flex items-center justify-between text-sm text-[var(--text-secondary)]">
            <span>Total Shortlisted: {isLoading ? '—' : candidates.length}</span>
          </div>
        </div>
      )}

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
    </div>
  );
};
