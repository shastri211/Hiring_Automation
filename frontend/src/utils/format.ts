/** "45s", "12m", "3.5h", "2.0d" — a compact duration for stage timings. */
export const formatDurationSeconds = (seconds: number): string => {
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const minutes = seconds / 60;
  if (minutes < 60) return `${Math.round(minutes)}m`;
  const hours = minutes / 60;
  if (hours < 24) return `${hours.toFixed(1)}h`;
  return `${(hours / 24).toFixed(1)}d`;
};

/** "Shortlisted", "Pre-screened out" ... for a ScreeningResult.decision value. */
export const decisionLabel = (decision?: string | null): string => {
  switch (decision) {
    case 'SHORTLIST': return 'Shortlisted';
    case 'REVIEW': return 'Review';
    case 'REJECT': return 'Rejected';
    case 'PRE_SCREENED_OUT': return 'Pre-screened out';
    default: return 'Undecided';
  }
};
