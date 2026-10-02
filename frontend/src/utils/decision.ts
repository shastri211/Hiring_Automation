export type BadgeVariant = 'neutral' | 'success' | 'warning' | 'danger' | 'primary';
export type CandidateDecision = 'SHORTLIST' | 'REVIEW' | 'REJECT' | 'PRE_SCREENED_OUT';

/**
 * Single source of truth for how a candidate decision maps to a Badge variant.
 * SHORTLIST -> success, REVIEW -> warning, REJECT -> danger,
 * PRE_SCREENED_OUT/null/undefined/anything else -> neutral.
 */
export function getDecisionBadgeVariant(decision?: CandidateDecision | string | null): BadgeVariant {
  switch (decision) {
    case 'SHORTLIST':
      return 'success';
    case 'REVIEW':
      return 'warning';
    case 'REJECT':
      return 'danger';
    case 'PRE_SCREENED_OUT':
    default:
      return 'neutral';
  }
}

/**
 * Parallel lookup for real <button> elements that render a decision's
 * "pressed/active" state and can't be a <Badge> (they need onClick/aria-pressed)
 * — e.g. CandidateComponents.tsx's DecisionControlBar and JobCandidates.tsx's
 * row actions. Keyed by the same BadgeVariant space as getDecisionBadgeVariant
 * so a decision's color can never drift between the label (Badge) and the
 * button (this map) representations.
 *
 * Intentionally just a bg+text pair (no border/layout): the two current
 * consumers render different button shapes (a bordered pill vs. a circular
 * icon button), so border/spacing stays owned by each call site.
 */
export const variantButtonClasses: Record<BadgeVariant, string> = {
  success: 'bg-[var(--color-success-subtle-bg)] text-[var(--color-success-subtle-text)]',
  warning: 'bg-[var(--color-warning-subtle-bg)] text-[var(--color-warning-subtle-text)]',
  danger: 'bg-[var(--color-danger-subtle-bg)] text-[var(--color-danger-subtle-text)]',
  neutral: 'bg-[var(--color-neutral-subtle-bg)] text-[var(--color-neutral-subtle-text)]',
  primary: 'bg-[var(--color-primary-subtle-bg)] text-[var(--color-primary-subtle-text)]',
};

/**
 * What to show as a candidate row's "state": resume-processing problems take
 * precedence over a decision, then the decision itself, then "awaiting".
 * Display-only - it reads fields the API already returns and changes nothing.
 */
export interface CandidateStateInput {
  status?: string | null;
  decision?: CandidateDecision | string | null;
  evaluation_failed?: boolean;
}

export function getCandidateState(c: CandidateStateInput): { label: string; variant: BadgeVariant; live?: boolean } {
  if (c.status === 'FAILED') return { label: 'Processing failed', variant: 'danger' };
  if (c.status === 'PROCESSING' || c.status === 'UPLOADED') return { label: 'Processing', variant: 'primary', live: true };
  if (c.decision === 'PRE_SCREENED_OUT') return { label: 'Pre-screened out', variant: 'neutral' };
  if (c.evaluation_failed) return { label: 'Evaluation failed', variant: 'danger' };
  switch (c.decision) {
    case 'SHORTLIST': return { label: 'Shortlisted', variant: 'success' };
    case 'REVIEW': return { label: 'Review', variant: 'warning' };
    case 'REJECT': return { label: 'Rejected', variant: 'danger' };
    default: return { label: 'Awaiting decision', variant: 'neutral' };
  }
}
