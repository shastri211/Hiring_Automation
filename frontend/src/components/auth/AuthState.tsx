import type { ReactNode } from 'react';
import { cn } from '../../utils/cn';

/**
 * AuthState — the centered "something happened" block on public pages
 * (account confirmed, link invalid, application received, interview ended).
 * One treatment instead of a hand-rolled icon + heading + paragraph per page;
 * the icon sits in a bordered square tinted by tone, never a bare colored glyph.
 */
type Tone = 'success' | 'danger' | 'neutral';

const TONE: Record<Tone, string> = {
  success: 'border-[var(--color-success-border)] bg-[var(--color-success-subtle-bg)] text-[var(--color-success-600)]',
  danger: 'border-[var(--color-danger-border)] bg-[var(--color-danger-subtle-bg)] text-[var(--color-danger-600)]',
  neutral: 'border-[var(--border-light)] bg-[var(--bg-app)] text-[var(--text-tertiary)]',
};

export const AuthState = ({
  tone = 'neutral', icon, title, children, action, className,
}: {
  tone?: Tone;
  icon: ReactNode;
  title: ReactNode;
  children?: ReactNode;
  action?: ReactNode;
  className?: string;
}) => (
  <div className={cn('flex flex-col items-center gap-3 py-2 text-center', className)}>
    <span aria-hidden="true" className={cn('rounded-lg border p-3', TONE[tone])}>{icon}</span>
    <h1 className="text-section-heading">{title}</h1>
    {children && <div className="text-body max-w-sm">{children}</div>}
    {action && <div className="mt-1">{action}</div>}
  </div>
);
