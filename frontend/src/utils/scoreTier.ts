/**
 * Single threshold source of truth for fit-score color coding, shared by
 * ScoreRing and anywhere else a score needs to map to a visual tier.
 */
export type ScoreTier = 'high' | 'medium' | 'low';

export function getScoreTier(score?: number | null): ScoreTier {
  if (score == null) return 'low';
  if (score >= 75) return 'high';
  if (score >= 50) return 'medium';
  return 'low';
}
