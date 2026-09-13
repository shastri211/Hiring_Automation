import { cn } from '../../utils/cn';
import { getScoreTier, type ScoreTier } from '../../utils/scoreTier';

/**
 * ScoreRing — single source of truth for the circular fit-score badge.
 *
 * Previously reimplemented slightly differently in Shortlisted.tsx (a plain
 * colored-text div, no ring), JobCandidates.tsx (plain colored text, no ring
 * at all) and Candidate360.tsx's ScoreVisualizer (a real SVG ring, red below
 * 50). This component reconciles all three into one visual language with one
 * threshold source of truth (see utils/scoreTier.ts): >=75 "high" (success),
 * >=50 "medium" (warning), else "low" (neutral — a below-threshold score
 * isn't a failure state, just lower, so it reads as quiet/neutral rather
 * than alarming red).
 */
const TIER_STROKE: Record<ScoreTier, string> = {
  high: 'var(--color-success-500)',
  medium: 'var(--color-warning-500)',
  low: 'var(--color-neutral-300)',
};

const TIER_TEXT_CLASS: Record<ScoreTier, string> = {
  high: 'text-[var(--color-success-600)]',
  medium: 'text-[var(--color-warning-600)]',
  low: 'text-[var(--text-secondary)]',
};

const SIZE_CONFIG = {
  sm: { box: 32, stroke: 4, fontClass: 'text-[10px]' },
  md: { box: 40, stroke: 5, fontClass: 'text-xs' },
  lg: { box: 64, stroke: 7, fontClass: 'text-lg' },
} as const;

export type ScoreRingSize = keyof typeof SIZE_CONFIG;

export interface ScoreRingProps {
  score?: number | null;
  size?: ScoreRingSize;
  className?: string;
}

export const ScoreRing = ({ score, size = 'md', className }: ScoreRingProps) => {
  const { box, stroke, fontClass } = SIZE_CONFIG[size];
  const radius = (box - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const tier = getScoreTier(score);
  const clamped = score != null ? Math.max(0, Math.min(100, score)) : 0;
  const dash = (clamped / 100) * circumference;

  return (
    <div
      className={cn('relative inline-flex shrink-0 items-center justify-center', className)}
      style={{ width: box, height: box }}
    >
      <svg
        className="absolute inset-0 -rotate-90"
        width={box}
        height={box}
        viewBox={`0 0 ${box} ${box}`}
        role="img"
        aria-label={score != null ? `Fit score ${Math.round(score)} out of 100` : 'Fit score unavailable'}
      >
        <circle cx={box / 2} cy={box / 2} r={radius} fill="none" stroke="var(--border-light)" strokeWidth={stroke} />
        {score != null && (
          <circle
            cx={box / 2}
            cy={box / 2}
            r={radius}
            fill="none"
            stroke={TIER_STROKE[tier]}
            strokeWidth={stroke}
            strokeDasharray={`${dash} ${circumference}`}
            strokeLinecap="round"
            style={{ transition: `stroke-dasharray var(--transition-base)` }}
          />
        )}
      </svg>
      <span className={cn('font-bold leading-none', fontClass, TIER_TEXT_CLASS[tier])}>
        {score != null ? Math.round(score) : '—'}
      </span>
    </div>
  );
};
