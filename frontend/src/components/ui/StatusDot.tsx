import type { HTMLAttributes, ReactNode } from 'react';
import { cn } from '../../utils/cn';
import type { BadgeVariant } from '../../utils/decision';

/**
 * StatusDot — a status read as "● Label": a small colored dot plus plain text.
 * The editorial replacement for filled pill badges in tables and headers. Use
 * `Badge` for categorical labels (department, skill) that aren't a state.
 *
 * Color is never the only signal: the text always names the state.
 */
const DOT: Record<BadgeVariant, string> = {
  neutral: 'bg-[var(--color-neutral-400)]',
  success: 'bg-[var(--color-success-500)]',
  warning: 'bg-[var(--color-warning-500)]',
  danger: 'bg-[var(--color-danger-500)]',
  primary: 'bg-[var(--color-primary-500)]',
};

export interface StatusDotProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
  children: ReactNode;
  /** Pulse the dot — for in-flight states (processing, running). */
  live?: boolean;
}

export const StatusDot = ({ variant = 'neutral', live, className, children, ...props }: StatusDotProps) => (
  <span className={cn('inline-flex items-center gap-1.5 text-sm text-[var(--text-primary)] whitespace-nowrap', className)} {...props}>
    <span aria-hidden="true" className={cn('h-1.5 w-1.5 shrink-0 rounded-full', DOT[variant], live && 'animate-pulse')} />
    {children}
  </span>
);
