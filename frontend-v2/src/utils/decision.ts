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
  success: 'bg-green-100 text-green-700',
  warning: 'bg-amber-100 text-amber-700',
  danger: 'bg-red-100 text-red-700',
  neutral: 'bg-slate-100 text-slate-700',
  primary: 'bg-indigo-100 text-indigo-700',
};
