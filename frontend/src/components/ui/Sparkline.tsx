import { useId } from 'react';
import { cn } from '../../utils/cn';

/**
 * Sparkline — a tiny, axis-free trend line for dashboard tiles. Pure SVG (no
 * chart library), themed through currentColor. Not for reading exact values:
 * pair it with a figure and an accessible `label`.
 */
export const Sparkline = ({
  values,
  label,
  className,
}: {
  values: number[];
  label: string;
  className?: string;
}) => {
  const id = useId();
  if (values.length < 2) return null;
  const w = 200;
  const h = 40;
  const pad = 2;
  const max = Math.max(...values, 1);
  const step = (w - pad * 2) / (values.length - 1);
  const pts = values.map((v, i) => [pad + i * step, h - pad - (v / max) * (h - pad * 2)] as const);
  const line = pts.map(([x, y], i) => `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`).join(' ');
  const area = `${line} L${pts[pts.length - 1][0].toFixed(1)},${h} L${pts[0][0].toFixed(1)},${h} Z`;

  return (
    <svg
      role="img"
      aria-label={label}
      viewBox={`0 0 ${w} ${h}`}
      preserveAspectRatio="none"
      className={cn('h-10 w-full text-[var(--color-primary-600)]', className)}
    >
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="currentColor" stopOpacity="0.16" />
          <stop offset="100%" stopColor="currentColor" stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#${id})`} />
      <path d={line} fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
    </svg>
  );
};
