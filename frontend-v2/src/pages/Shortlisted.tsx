import { useNavigate } from 'react-router-dom';
import { useShortlistedCandidates } from '../hooks/useShortlistedCandidates';
import { Loader2, Users, FileText, CheckCircle2 } from 'lucide-react';
import { useState } from 'react';
import { CandidateDrawer } from '../components/CandidateDrawer';
import type { GlobalScreeningResultResponse } from '../types';

export const Shortlisted = () => {
  const { candidates, isLoading, isError } = useShortlistedCandidates();
  const navigate = useNavigate();
  const [selectedCandidate, setSelectedCandidate] = useState<{jobId: number, resumeId: number} | null>(null);

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-64 text-slate-400">
        <Loader2 className="w-8 h-8 animate-spin" />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="p-8 text-center text-red-500">
        Failed to load shortlisted candidates.
      </div>
    );
  }

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="flex items-center space-x-3 mb-8">
        <div className="w-10 h-10 bg-green-100 text-green-600 rounded-lg flex items-center justify-center">
          <CheckCircle2 className="w-6 h-6" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Shortlisted Candidates</h1>
          <p className="text-sm text-slate-500">Candidates marked for moving forward across all jobs.</p>
        </div>
      </div>

      {candidates.length === 0 ? (
        <div className="text-center py-20 bg-white rounded-xl border border-slate-200">
          <Users className="w-12 h-12 text-slate-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-slate-800 mb-1">No shortlisted candidates yet</h3>
          <p className="text-slate-500">Review candidate results and mark them as shortlisted to see them here.</p>
        </div>
      ) : (
        <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-600">
              <thead className="bg-slate-50 border-b border-slate-200 text-slate-500">
                <tr>
                  <th className="px-6 py-4 font-medium">Candidate</th>
                  <th className="px-6 py-4 font-medium">Job</th>
                  <th className="px-6 py-4 font-medium">Fit Score</th>
                  <th className="px-6 py-4 font-medium hidden md:table-cell">Key Strengths</th>
                  <th className="px-6 py-4 text-right font-medium">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {candidates.map((candidate: GlobalScreeningResultResponse) => (
                  <tr 
                    key={`${candidate.job_id}-${candidate.resume_id}`}
                    className="hover:bg-slate-50 transition-colors group cursor-pointer"
                    onClick={() => setSelectedCandidate({ jobId: candidate.job_id, resumeId: candidate.resume_id })}
                  >
                    <td className="px-6 py-4">
                      <div className="flex items-center space-x-3">
                        <div className="w-8 h-8 bg-blue-50 text-blue-600 rounded flex items-center justify-center">
                          <FileText className="w-4 h-4" />
                        </div>
                        <div>
                          <div className="font-medium text-slate-800">{candidate.display_name || `Candidate #${candidate.resume_id}`}</div>
                          <div className="text-xs text-slate-400">ID: {candidate.id}</div>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <button 
                        onClick={(e) => {
                          e.stopPropagation();
                          navigate(`/jobs/${candidate.job_id}`);
                        }}
                        className="text-blue-600 hover:underline font-medium"
                      >
                        {candidate.job_title}
                      </button>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center space-x-2">
                        <div className={`w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold shadow-sm border border-slate-100 bg-white ${candidate.score != null && candidate.score >= 75 ? 'text-emerald-600' : candidate.score != null && candidate.score >= 50 ? 'text-amber-600' : 'text-slate-700'}`}>
                          {candidate.score != null ? Math.round(candidate.score) : '—'}
                        </div>
                        <div className="text-xs text-slate-400">
                          Semantic: {candidate.semantic_score != null ? Math.round(candidate.semantic_score) : '—'}
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4 hidden md:table-cell max-w-xs">
                      {candidate.strengths && candidate.strengths.length > 0 ? (
                        <ul className="text-xs list-disc list-inside space-y-1 text-slate-500">
                          {candidate.strengths.slice(0, 2).map((s: string, i: number) => (
                            <li key={i} className="truncate">{s}</li>
                          ))}
                        </ul>
                      ) : (
                        <span className="text-slate-400 italic">No strengths listed</span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-right">
                      <span className="text-sm font-medium text-blue-600 opacity-0 group-hover:opacity-100 transition-opacity">
                        View 360 &rarr;
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="px-6 py-4 border-t border-slate-200 bg-slate-50 flex items-center justify-between text-sm text-slate-500">
            <span>Total Shortlisted: {candidates.length}</span>
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
