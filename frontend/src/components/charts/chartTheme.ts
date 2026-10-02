/**
 * Recharts styling driven by the design tokens. Every value is a CSS variable
 * reference, so charts re-theme the moment data-theme changes - no read-once
 * snapshot of computed colors (the old approach went stale on a theme toggle).
 */
export const chart = {
  primary: 'var(--color-primary-600)',
  success: 'var(--color-success-500)',
  warning: 'var(--color-warning-500)',
  danger: 'var(--color-danger-500)',
  neutral: 'var(--color-neutral-400)',
  grid: 'var(--border-light)',
  axis: { fontSize: 12, fill: 'var(--text-secondary)' },
  axisSmall: { fontSize: 11, fill: 'var(--text-secondary)' },
  axisLine: { stroke: 'var(--border-strong)' },
  tooltip: {
    contentStyle: {
      background: 'var(--bg-surface)',
      border: '1px solid var(--border-strong)',
      borderRadius: 6,
      boxShadow: 'var(--shadow-md)',
      fontSize: 12,
      color: 'var(--text-primary)',
    },
    labelStyle: { color: 'var(--text-secondary)', fontWeight: 600 },
    itemStyle: { color: 'var(--text-primary)' },
    cursor: { fill: 'var(--bg-hover)' },
  },
} as const;
