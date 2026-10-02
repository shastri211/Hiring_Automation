import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { cn } from '../../utils/cn';
import { Skeleton } from './Primitives';

/**
 * StatTile — one figure with an eyebrow label and an optional hint/footer.
 * Used for dashboard and workspace summary rows. Renders a skeleton while
 * `isLoading`, and a quiet "—" when the value is unavailable (never a made-up
 * 0). With `to`, the whole tile is a link.
 */
interface StatTileProps {
  label: string;
  value?: ReactNode;
  hint?: ReactNode;
  footer?: ReactNode;
  isLoading?: boolean;
  to?: string;
  /** Router state passed along when `to` is followed. */
  linkState?: unknown;
  tone?: 'default' | 'danger';
  className?: string;
}

export const StatTile = ({ label, value, hint, footer, isLoading, to, linkState, tone = 'default', className }: StatTileProps) => {
  const body = (
    <>
      <p className="text-eyebrow">{label}</p>
      <div
        className={cn(
          'tabular mt-2 text-3xl font-semibold leading-none tracking-tight',
          tone === 'danger' ? 'text-[var(--color-danger-600)]' : 'text-[var(--text-primary)]'
        )}
      >
        {isLoading ? <Skeleton className="h-8 w-16" /> : value ?? '—'}
      </div>
      {hint && <p className="text-caption mt-2">{hint}</p>}
      {footer && <div className="mt-3">{footer}</div>}
    </>
  );
  const base = 'block rounded-lg border border-[var(--border-light)] bg-[var(--bg-surface)] p-4';
  return to ? (
    <Link to={to} state={linkState} className={cn(base, 'transition-base focus-ring hover:border-[var(--border-strong)]', className)}>
      {body}
    </Link>
  ) : (
    <div className={cn(base, className)}>{body}</div>
  );
};
