// Shared with InterviewWorkspace.tsx, Candidate360.tsx, GlobalInterviews.tsx,
// and InterviewAnalysis.tsx so the recommendation label/color logic can't
// drift between the places it's shown.
export type RatingVariant = 'success' | 'warning' | 'danger' | 'neutral';

export function ratingVariant(rating?: string | null): RatingVariant {
  if (!rating) return 'neutral';
  if (/strong|advance/i.test(rating)) return 'success';
  if (/weak|not a fit/i.test(rating)) return 'danger';
  return 'warning';
}

const RECOMMENDATION_LABELS = ['Advance', 'Hold for Review', 'Likely Not a Fit'];

export function parseRecommendation(
  raw?: string | null
): { label: string; reason: string; variant: RatingVariant } | null {
  if (!raw) return null;
  const matched = RECOMMENDATION_LABELS.find((l) => raw.toLowerCase().startsWith(l.toLowerCase()));
  const label = matched || raw.split(/[-–:]/)[0].trim();
  const reason = matched ? raw.slice(matched.length).replace(/^[\s\-–:]+/, '').trim() : '';
  return { label, reason, variant: ratingVariant(label) };
}
