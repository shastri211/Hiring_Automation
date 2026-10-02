/**
 * Single threshold source of truth for fit-score color coding and wording,
 * shared by FitScore and anywhere else a score maps to a visual tier.
 * Thresholds are display-only; they never feed screening or decision logic.
 */
export type ScoreTier = 'high' | 'medium' | 'low';

export function getScoreTier(score?: number | null): ScoreTier {
  if (score == null) return 'low';
  if (score >= 75) return 'high';
  if (score >= 50) return 'medium';
  return 'low';
}

/** "Excellent match" / "Potential match" / "Weak match" (or null when unscored). */
export function getScoreTierLabel(score?: number | null): string | null {
  if (score == null) return null;
  const tier = getScoreTier(score);
  return tier === 'high' ? 'Excellent match' : tier === 'medium' ? 'Potential match' : 'Weak match';
}
