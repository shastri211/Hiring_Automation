
import { CheckCircle2, X, Clock, AlertTriangle, ShieldOff } from 'lucide-react';
import type { CandidateDecision, ScreeningResultResponse, CandidateProfileDetail } from '../../types';

export const ScoreVisualizer = ({ screening }: { screening?: ScreeningResultResponse | null }) => {
  if (!screening) return null;
  const score = screening.score;
  
  if (score === null || score === undefined) return null;
  
  return (
    <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm flex items-center gap-5">
      <div className="relative w-16 h-16 flex items-center justify-center">
        <svg className="absolute inset-0 w-full h-full -rotate-90" viewBox="0 0 100 100" role="img" aria-label={`${Math.round(score)} percent match`}>
          <circle cx="50" cy="50" r="45" fill="none" className="stroke-slate-100" strokeWidth="8" />
          <circle 
            cx="50" cy="50" r="45" fill="none" 
            className={
              score >= 75 ? 'stroke-emerald-500' : 
              score >= 50 ? 'stroke-amber-500' : 'stroke-red-500'
            } 
            strokeWidth="8" 
            strokeDasharray={`${2.827 * score} 282.7`} 
            strokeLinecap="round" 
          />
        </svg>
        <div className="text-center">
          <div className="text-lg font-bold text-slate-900 leading-none">{Math.round(score)}</div>
        </div>
      </div>
      <div>
        <h3 className="font-semibold text-slate-900 mb-1">
          {score >= 75 ? 'Excellent Match' : 
           score >= 50 ? 'Potential Match' : 'Poor Match'}
        </h3>
        <p className="text-xs text-slate-500 leading-relaxed">
          {screening.evidence && screening.evidence.length > 0 
            ? screening.evidence[0] 
            : 'Based on job requirements analysis.'}
        </p>
      </div>
    </div>
  );
};

export const DecisionControlBar = ({ 
  decision, 
  isPending, 
  onDecision 
}: { 
  decision?: CandidateDecision; 
  isPending: boolean; 
  onDecision: (d: CandidateDecision | null) => void;
}) => {
  return (
    <div className="flex flex-wrap items-center gap-3 p-4 bg-slate-50 rounded-lg border border-slate-200">
      <span className="text-sm font-medium text-slate-700">Decision:</span>
      <button 
        type="button"
        onClick={() => onDecision('SHORTLIST')}
        disabled={isPending}
        aria-pressed={decision === 'SHORTLIST'}
        className={`px-4 py-2 rounded-md text-sm font-medium transition-colors border focus-ring ${
          decision === 'SHORTLIST' 
            ? 'bg-green-100 text-green-800 border-green-200' 
            : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-100'
        }`}
      >
        Shortlist
      </button>
      <button 
        type="button"
        onClick={() => onDecision('REVIEW')}
        disabled={isPending}
        aria-pressed={decision === 'REVIEW'}
        className={`px-4 py-2 rounded-md text-sm font-medium transition-colors border focus-ring ${
          decision === 'REVIEW' 
            ? 'bg-amber-100 text-amber-800 border-amber-200' 
            : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-100'
        }`}
      >
        Review
      </button>
      <button 
        type="button"
        onClick={() => onDecision('REJECT')}
        disabled={isPending}
        aria-pressed={decision === 'REJECT'}
        className={`px-4 py-2 rounded-md text-sm font-medium transition-colors border focus-ring ${
          decision === 'REJECT' 
            ? 'bg-red-100 text-red-800 border-red-200' 
            : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-100'
        }`}
      >
        Reject
      </button>
      {decision && (
        <button 
          type="button"
          onClick={() => onDecision(null)}
          disabled={isPending}
          className="ml-auto text-sm text-slate-500 hover:text-slate-700 focus-ring rounded px-2 py-1"
        >
          Clear
        </button>
      )}
    </div>
  );
};

export const ExtractedSkills = ({ profile }: { profile?: CandidateProfileDetail | null }) => {
  const skills = Array.isArray(profile?.skills) ? profile?.skills : [];
  return (
    <div>
      <span className="text-xs text-slate-500 font-medium block mb-1">Extracted Skills</span>
      <div className="flex flex-wrap gap-2">
        {skills.length > 0 
          ? skills.slice(0, 15).map((s: string, i: number) => (
            <span key={i} className="bg-slate-100 text-slate-700 px-2 py-1 rounded text-xs font-medium">
              {s}
            </span>
          ))
          : <span className="text-slate-400 italic">No skills identified</span>
        }
        {skills.length > 15 && (
          <span className="text-xs text-slate-500 py-1">+{skills.length - 15} more</span>
        )}
      </div>
    </div>
  );
};

export const ScreeningAnalysis = ({ screening }: { screening?: ScreeningResultResponse | null }) => {
  if (!screening) return null;
  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden mt-6">
      <div className="px-5 py-3 border-b border-slate-100 bg-slate-50/50">
        <h3 className="text-sm font-semibold text-slate-900">AI Evaluation</h3>
      </div>
      <div className="p-5 space-y-5 text-sm">
        <div>
          <div className="flex items-center gap-2 mb-2 text-emerald-700 font-medium">
            <CheckCircle2 className="w-4 h-4" />
            Key Strengths
          </div>
          <ul className="list-disc pl-5 space-y-1 text-slate-600">
            {screening.strengths && screening.strengths.length > 0
              ? screening.strengths.map((s: string, i: number) => <li key={i}>{s}</li>)
              : <li className="text-slate-400 italic">None identified</li>
            }
          </ul>
        </div>
        <div>
          <div className="flex items-center gap-2 mb-2 text-red-700 font-medium">
            <X className="w-4 h-4" />
            Identified Gaps
          </div>
          <ul className="list-disc pl-5 space-y-1 text-slate-600">
            {screening.gaps && screening.gaps.length > 0
              ? screening.gaps.map((g: string, i: number) => <li key={i}>{g}</li>)
              : <li className="text-slate-400 italic">None identified</li>
            }
          </ul>
        </div>
      </div>
    </div>
  );
};

/**
 * CandidateStatusBanner — shown in the drawer when there is no ScreeningResult yet.
 * Covers: PROCESSING/UPLOADED (pending), FAILED, and PRE_SCREENED_OUT.
 * Replaces the blank/empty space that otherwise confuses users.
 */
export const CandidateStatusBanner = ({
  resumeStatus,
  decision,
  errorMessage,
}: {
  resumeStatus?: string | null;
  decision?: string | null;
  errorMessage?: string | null;
}) => {
  // PRE_SCREENED_OUT is stored in decision, not resume status
  if (decision === 'PRE_SCREENED_OUT') {
    return (
      <div className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4">
        <ShieldOff className="w-5 h-5 text-amber-600 mt-0.5 shrink-0" />
        <div>
          <p className="text-sm font-semibold text-amber-900">Pre-screened Out</p>
          <p className="text-xs text-amber-700 mt-0.5">
            This candidate did not meet the semantic similarity threshold for this job and was automatically filtered before LLM evaluation.
            The semantic score is preserved; no AI evaluation was consumed.
          </p>
        </div>
      </div>
    );
  }

  if (resumeStatus === 'FAILED') {
    return (
      <div className="flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 p-4">
        <AlertTriangle className="w-5 h-5 text-red-600 mt-0.5 shrink-0" />
        <div>
          <p className="text-sm font-semibold text-red-900">Processing Failed</p>
          <p className="text-xs text-red-700 mt-0.5">
            {errorMessage || 'An error occurred while processing this resume. It may need to be re-uploaded.'}
          </p>
        </div>
      </div>
    );
  }

  if (resumeStatus === 'PROCESSING' || resumeStatus === 'UPLOADED') {
    return (
      <div className="flex items-start gap-3 rounded-xl border border-blue-200 bg-blue-50 p-4">
        <Clock className="w-5 h-5 text-blue-500 mt-0.5 shrink-0 animate-pulse" />
        <div>
          <p className="text-sm font-semibold text-blue-900">Processing In Progress</p>
          <p className="text-xs text-blue-700 mt-0.5">
            This resume is currently being processed. Screening results will appear here once the pipeline completes.
            Refresh to check for updates.
          </p>
        </div>
      </div>
    );
  }

  // READY but no screening result yet (awaiting screening run)
  if (resumeStatus === 'READY') {
    return (
      <div className="flex items-start gap-3 rounded-xl border border-slate-200 bg-slate-50 p-4">
        <Clock className="w-5 h-5 text-slate-400 mt-0.5 shrink-0" />
        <div>
          <p className="text-sm font-semibold text-slate-700">Awaiting Screening</p>
          <p className="text-xs text-slate-500 mt-0.5">
            This resume has been processed and is queued for AI screening. Results will appear once screening runs.
          </p>
        </div>
      </div>
    );
  }

  return null;
};

