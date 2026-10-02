import type { ReactNode } from 'react';
import { Loader2, RefreshCw } from 'lucide-react';
import { FitScore, StatusDot } from '../ui';
import { cn } from '../../utils/cn';
import { getCandidateState, type CandidateStateInput } from '../../utils/decision';
import { getInitials } from '../../utils/initials';
import { formatSemantic } from '../../utils/format';

/**
 * Cell building blocks shared by the three screening tables (a job's
 * candidates, all candidates, shortlisted) so a candidate reads the same
 * everywhere: identity, decision state, and the evaluation summary.
 */

export const CandidateIdentity = ({ name, fallback, sub, muted }: {
  name?: string | null;
  fallback: string;
  sub?: ReactNode;
  /** Dim the avatar (failed / pre-screened-out rows). */
  muted?: boolean;
}) => (
  <div className="flex min-w-0 items-center md:max-w-[13rem] gap-3">
    <span
      aria-hidden="true"
      className={cn(
        'flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-semibold',
        muted ? 'bg-[var(--color-neutral-subtle-bg)] text-[var(--text-tertiary)]' : 'bg-[var(--color-primary-subtle-bg)] text-[var(--color-primary-subtle-text)]'
      )}
    >
      {getInitials(name)}
    </span>
    <div className="min-w-0">
      <p className="truncate text-sm font-medium text-[var(--text-primary)]">{name || fallback}</p>
      {sub && <p className="text-caption truncate">{sub}</p>}
    </div>
  </div>
);

/**
 * The fit-score cell. Semantic match always stays visible: beside the score in
 * its own column on wide screens (see SemanticCell), and as a caption under the
 * score below `xl`, where the extra column would not fit.
 */
export const ScoreCell = ({ score, semantic, unscoredLabel }: { score?: number | null; semantic?: number | null; unscoredLabel?: string }) => (
  <div className="space-y-1">
    <FitScore score={score} unscoredLabel={unscoredLabel} />
    <p className="text-caption tabular hidden md:block xl:hidden">Semantic {formatSemantic(semantic)}</p>
  </div>
);

export const SemanticCell = ({ value }: { value?: number | null }) => (
  <span className="tabular text-sm text-[var(--text-secondary)]">{formatSemantic(value)}</span>
);

export const DecisionStatus = ({ candidate }: { candidate: CandidateStateInput }) => {
  const state = getCandidateState(candidate);
  return <StatusDot variant={state.variant} live={state.live}>{state.label}</StatusDot>;
};

interface EvaluationSummaryProps {
  strengths?: string[] | null;
  gaps?: string[] | null;
  evidence?: string[] | null;
  decision?: string | null;
  evaluationFailed?: boolean;
  /** When provided, a failed evaluation offers a Retry; otherwise it is just labeled. */
  onRetry?: () => void;
  isRetrying?: boolean;
  maxStrengths?: number;
  maxGaps?: number;
}

/** Strengths (+), gaps (−) and the lead evidence line — or the reason there are none. */
export const EvaluationSummary = ({
  strengths, gaps, evidence, decision, evaluationFailed, onRetry, isRetrying, maxStrengths = 2, maxGaps = 1,
}: EvaluationSummaryProps) => {
  if (decision === 'PRE_SCREENED_OUT') {
    return <p className="text-sm text-[var(--color-warning-subtle-text)]">Not advanced by semantic pre-screening — no AI evaluation was run.</p>;
  }
  if (evaluationFailed) {
    return onRetry ? (
      <button
        type="button"
        onClick={(e) => { e.stopPropagation(); onRetry(); }}
        disabled={isRetrying}
        className="transition-base focus-ring inline-flex items-center gap-1.5 rounded-md border border-[var(--color-danger-border)] bg-[var(--color-danger-subtle-bg)] px-2 py-1 text-sm font-medium text-[var(--color-danger-subtle-text)] hover:opacity-80 disabled:opacity-60"
      >
        {isRetrying ? (
          <><Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" /> Retrying evaluation…</>
        ) : (
          <><RefreshCw className="h-3.5 w-3.5" aria-hidden="true" /> Evaluation failed — Retry</>
        )}
      </button>
    ) : (
      <p className="text-sm text-[var(--color-danger-subtle-text)]">Evaluation failed — open the candidate to retry.</p>
    );
  }

  const s = strengths?.slice(0, maxStrengths) ?? [];
  const g = gaps?.slice(0, maxGaps) ?? [];
  const lead = evidence?.[0];
  if (s.length === 0 && g.length === 0 && !lead) {
    return <span className="text-sm italic text-[var(--text-tertiary)]">No evaluation yet.</span>;
  }

  return (
    <div className="space-y-1 text-sm">
      {s.map((text, i) => (
        <p key={`s${i}`} className="flex gap-1.5 text-[var(--text-primary)]">
          <span aria-label="Strength" className="shrink-0 font-semibold text-[var(--color-success-600)]">+</span>
          <span className="line-clamp-1">{text}</span>
        </p>
      ))}
      {g.map((text, i) => (
        <p key={`g${i}`} className="flex gap-1.5 text-[var(--text-primary)]">
          <span aria-label="Gap" className="shrink-0 font-semibold text-[var(--color-danger-600)]">−</span>
          <span className="line-clamp-1">{text}</span>
        </p>
      ))}
      {lead && <p className="text-caption line-clamp-2 leading-relaxed">{lead}</p>}
    </div>
  );
};
