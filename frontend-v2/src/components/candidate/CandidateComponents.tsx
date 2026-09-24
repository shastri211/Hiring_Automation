
import { CheckCircle2, X, Clock, AlertTriangle, ShieldOff, RefreshCw, Loader2 } from 'lucide-react';
import type { CandidateDecision, ScreeningResultResponse, CandidateProfileDetail } from '../../types';
import { variantButtonClasses } from '../../utils/decision';
import { ScoreRing } from '../ui/ScoreRing';

export const ScoreVisualizer = ({ screening }: { screening?: ScreeningResultResponse | null }) => {
  if (!screening) return null;
  const score = screening.score;

  if (score === null || score === undefined) return null;

  return (
    <div className="bg-[var(--bg-surface)] p-5 rounded-xl border border-[var(--border-light)] shadow-[var(--shadow-sm)] flex items-center gap-5">
      <ScoreRing score={score} size="lg" />
      <div>
        <h3 className="font-semibold text-[var(--text-primary)] mb-1">
          {score >= 75 ? 'Excellent Match' :
           score >= 50 ? 'Potential Match' : 'Poor Match'}
        </h3>
        <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
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
    <div className="flex flex-wrap items-center gap-3 p-4 bg-[var(--bg-app)] rounded-lg border border-[var(--border-light)]">
      <span className="text-sm font-medium text-[var(--text-secondary)]">Decision:</span>
      <button
        type="button"
        onClick={() => onDecision('SHORTLIST')}
        disabled={isPending}
        aria-pressed={decision === 'SHORTLIST'}
        className={`px-4 py-2 rounded-md text-sm font-medium transition-colors border focus-ring ${
          decision === 'SHORTLIST'
            ? `${variantButtonClasses.success} border-transparent`
            : 'bg-[var(--bg-surface)] text-[var(--text-secondary)] border-[var(--border-light)] hover:bg-[var(--bg-hover)]'
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
            ? `${variantButtonClasses.warning} border-transparent`
            : 'bg-[var(--bg-surface)] text-[var(--text-secondary)] border-[var(--border-light)] hover:bg-[var(--bg-hover)]'
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
            ? `${variantButtonClasses.danger} border-transparent`
            : 'bg-[var(--bg-surface)] text-[var(--text-secondary)] border-[var(--border-light)] hover:bg-[var(--bg-hover)]'
        }`}
      >
        Reject
      </button>
      {decision && (
        <button
          type="button"
          onClick={() => onDecision(null)}
          disabled={isPending}
          className="ml-auto text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] focus-ring rounded px-2 py-1"
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
      <span className="text-xs text-[var(--text-secondary)] font-medium block mb-1">Extracted Skills</span>
      <div className="flex flex-wrap gap-2">
        {skills.length > 0
          ? skills.slice(0, 15).map((s: string, i: number) => (
            <span key={i} className="bg-[var(--bg-hover)] text-[var(--text-secondary)] px-2 py-1 rounded text-xs font-medium">
              {s}
            </span>
          ))
          : <span className="text-[var(--text-tertiary)] italic">No skills identified</span>
        }
        {skills.length > 15 && (
          <span className="text-xs text-[var(--text-secondary)] py-1">+{skills.length - 15} more</span>
        )}
      </div>
    </div>
  );
};

/**
 * EvaluationFailedBanner — shown above the (otherwise empty-looking) score
 * and evaluation panels when every configured LLM provider failed for this
 * one candidate (screener.py's per-candidate fallback path). Without this,
 * ScoreVisualizer renders nothing at all (score is null) and ScreeningAnalysis
 * just shows "None identified" for both strengths and gaps, indistinguishable
 * from a real (if uninformative) outcome.
 */
export const EvaluationFailedBanner = ({ onRetry, isPending }: { onRetry: () => void; isPending: boolean }) => (
  <div className="flex items-start justify-between gap-3 rounded-xl border border-[var(--color-danger-border)] bg-[var(--color-danger-subtle-bg)] p-4">
    <div className="flex items-start gap-3">
      <AlertTriangle className="w-5 h-5 text-[var(--color-danger-600)] mt-0.5 shrink-0" />
      <div>
        <p className="text-sm font-semibold text-[var(--color-danger-subtle-text)]">AI Evaluation Failed</p>
        <p className="text-xs text-[var(--color-danger-subtle-text)] mt-0.5">
          Every configured LLM provider failed for this candidate - usually a transient outage, not a resume problem. Retry once it's cleared.
        </p>
      </div>
    </div>
    <button
      type="button"
      onClick={onRetry}
      disabled={isPending}
      className="shrink-0 flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium bg-[var(--bg-surface)] border border-[var(--color-danger-border)] text-[var(--color-danger-subtle-text)] hover:bg-[var(--color-danger-subtle-bg)] disabled:opacity-60 transition-colors focus-ring"
    >
      {isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
      Retry
    </button>
  </div>
);

export const ScreeningAnalysis = ({ screening }: { screening?: ScreeningResultResponse | null }) => {
  if (!screening) return null;
  return (
    <div className="bg-[var(--bg-surface)] rounded-xl border border-[var(--border-light)] shadow-sm overflow-hidden mt-6">
      <div className="px-5 py-3 border-b border-[var(--border-light)] bg-[var(--bg-app)]">
        <h3 className="text-sm font-semibold text-[var(--text-primary)]">AI Evaluation</h3>
      </div>
      <div className="p-5 space-y-5 text-sm">
        <div>
          <div className="flex items-center gap-2 mb-2 text-[var(--color-success-subtle-text)] font-medium">
            <CheckCircle2 className="w-4 h-4" />
            Key Strengths
          </div>
          <ul className="list-disc pl-5 space-y-1 text-[var(--text-secondary)]">
            {screening.strengths && screening.strengths.length > 0
              ? screening.strengths.map((s: string, i: number) => <li key={i}>{s}</li>)
              : <li className="text-[var(--text-tertiary)] italic">None identified</li>
            }
          </ul>
        </div>
        <div>
          <div className="flex items-center gap-2 mb-2 text-[var(--color-danger-subtle-text)] font-medium">
            <X className="w-4 h-4" />
            Identified Gaps
          </div>
          <ul className="list-disc pl-5 space-y-1 text-[var(--text-secondary)]">
            {screening.gaps && screening.gaps.length > 0
              ? screening.gaps.map((g: string, i: number) => <li key={i}>{g}</li>)
              : <li className="text-[var(--text-tertiary)] italic">None identified</li>
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
      <div className="flex items-start gap-3 rounded-xl border border-[var(--color-warning-border)] bg-[var(--color-warning-subtle-bg)] p-4">
        <ShieldOff className="w-5 h-5 text-[var(--color-warning-600)] mt-0.5 shrink-0" />
        <div>
          <p className="text-sm font-semibold text-[var(--color-warning-subtle-text)]">Pre-screened Out</p>
          <p className="text-xs text-[var(--color-warning-subtle-text)] mt-0.5">
            This candidate did not meet the semantic similarity threshold for this job and was automatically filtered before LLM evaluation.
            The semantic score is preserved; no AI evaluation was consumed.
          </p>
        </div>
      </div>
    );
  }

  if (resumeStatus === 'FAILED') {
    return (
      <div className="flex items-start gap-3 rounded-xl border border-[var(--color-danger-border)] bg-[var(--color-danger-subtle-bg)] p-4">
        <AlertTriangle className="w-5 h-5 text-[var(--color-danger-600)] mt-0.5 shrink-0" />
        <div>
          <p className="text-sm font-semibold text-[var(--color-danger-subtle-text)]">Processing Failed</p>
          <p className="text-xs text-[var(--color-danger-subtle-text)] mt-0.5">
            {errorMessage || 'An error occurred while processing this resume. It may need to be re-uploaded.'}
          </p>
        </div>
      </div>
    );
  }

  if (resumeStatus === 'PROCESSING' || resumeStatus === 'UPLOADED') {
    return (
      <div className="flex items-start gap-3 rounded-xl border border-[var(--color-info-border)] bg-[var(--color-info-subtle-bg)] p-4">
        <Clock className="w-5 h-5 text-[var(--color-info-icon)] mt-0.5 shrink-0 animate-pulse" />
        <div>
          <p className="text-sm font-semibold text-[var(--color-info-subtle-text)]">Processing In Progress</p>
          <p className="text-xs text-[var(--color-info-subtle-text)] mt-0.5">
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
      <div className="flex items-start gap-3 rounded-xl border border-[var(--border-light)] bg-[var(--bg-app)] p-4">
        <Clock className="w-5 h-5 text-[var(--text-tertiary)] mt-0.5 shrink-0" />
        <div>
          <p className="text-sm font-semibold text-[var(--text-secondary)]">Awaiting Screening</p>
          <p className="text-xs text-[var(--text-secondary)] mt-0.5">
            This resume has been processed and is queued for AI screening. Results will appear once screening runs.
          </p>
        </div>
      </div>
    );
  }

  return null;
};

