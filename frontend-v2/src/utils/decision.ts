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
