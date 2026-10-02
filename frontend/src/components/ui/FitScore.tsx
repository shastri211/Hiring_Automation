import { cn } from '../../utils/cn';
import { getScoreTier, getScoreTierLabel, type ScoreTier } from '../../utils/scoreTier';

/**
 * FitScore — the one presentation of a candidate's AI fit score, used on every
 * surface that shows it (job candidates, all candidates, shortlisted, drawer,
 * Candidate 360, interview views). The score value and tiers come straight from
 * the backend `score`; this only decides how it looks.
 *
 *   sm — table cell:   "92 ▬▬▬▬▬▬▬▬"   number + thin bar
 *   lg — detail view:  "92 /100" + wide bar + tier label
 *
 * A null score renders an em dash with an empty bar — never a made-up 0. Pass
 * `unscoredLabel` to say why (e.g. "Not scored" for pre-screened-out rows).
 */
const FILL: Record<ScoreTier, string> = {
  high: 'bg-[var(--color-success-500)]',
  medium: 'bg-[var(--color-warning-500)]',
  low: 'bg-[var(--color-neutral-400)]',
};
const TEXT: Record<ScoreTier, string> = {
  high: 'text-[var(--color-success-600)]',
  medium: 'text-[var(--color-warning-600)]',
  low: 'text-[var(--text-secondary)]',
};

export interface FitScoreProps {
  score?: number | null;
  size?: 'sm' | 'lg';
  /** lg only: show the tier wording ("Excellent match") under the bar. */
  showLabel?: boolean;
  unscoredLabel?: string;
  className?: string;
}

export const FitScore = ({ score, size = 'sm', showLabel = true, unscoredLabel, className }: FitScoreProps) => {
  const scored = score != null;
  const tier = getScoreTier(score);
  const value = scored ? Math.round(score) : null;
  const pct = scored ? Math.max(0, Math.min(100, score)) : 0;
  const aria = scored ? `Fit score ${value} out of 100` : unscoredLabel ?? 'Fit score unavailable';

  if (size === 'lg') {
    return (
      <div role="img" aria-label={aria} className={cn('w-full', className)}>
        <div className="flex items-baseline gap-2">
          <span className={cn('tabular text-4xl font-semibold leading-none tracking-tight', scored ? TEXT[tier] : 'text-[var(--text-tertiary)]')}>
            {value ?? '—'}
          </span>
          {scored && <span className="text-sm text-[var(--text-tertiary)]">/ 100</span>}
          {showLabel && (scored || unscoredLabel) && (
            <span className="text-eyebrow ml-auto">{scored ? getScoreTierLabel(score) : unscoredLabel}</span>
          )}
        </div>
        <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-[var(--bg-hover)]">
          <div className={cn('h-full rounded-full', FILL[tier])} style={{ width: `${pct}%` }} />
        </div>
      </div>
    );
  }

  return (
    <div role="img" aria-label={aria} className={cn('inline-flex items-center gap-2.5', className)} title={scored ? getScoreTierLabel(score) ?? undefined : unscoredLabel}>
      <span className={cn('tabular w-7 text-right text-sm font-semibold', scored ? TEXT[tier] : 'text-[var(--text-tertiary)]')}>
        {value ?? '—'}
      </span>
      <span className="h-1.5 w-16 overflow-hidden rounded-full bg-[var(--bg-hover)]">
        <span className={cn('block h-full rounded-full', FILL[tier])} style={{ width: `${pct}%` }} />
      </span>
    </div>
  );
};
