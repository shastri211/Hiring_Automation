import { cn } from '../../utils/cn';
import type { ButtonProps } from './Button';

/** Class-name builders shared by components and by plain elements (e.g. a
 * router <Link> styled as a button). Kept out of the component files so they
 * stay component-only (React fast refresh). */

const baseClasses =
  'inline-flex items-center justify-center gap-2 font-medium rounded-md border cursor-pointer transition-base whitespace-nowrap focus-ring disabled:opacity-50 disabled:cursor-not-allowed';

const sizeClasses = {
  md: 'h-9 px-3.5 text-sm',
  sm: 'h-7 px-2.5 text-xs',
};

const variantClasses = {
  primary: 'border-transparent bg-[var(--accent)] text-[var(--accent-fg)] hover:not-disabled:bg-[var(--accent-hover)]',
  secondary:
    'bg-[var(--bg-surface)] border-[color:var(--border-strong)] text-[var(--text-primary)] hover:not-disabled:bg-[var(--bg-hover)]',
  ghost:
    'border-transparent bg-transparent text-[var(--text-secondary)] hover:not-disabled:bg-[var(--bg-hover)] hover:not-disabled:text-[var(--text-primary)]',
  danger:
    'border-transparent bg-[var(--color-danger-600)] text-[var(--bg-surface)] hover:not-disabled:opacity-90',
};

export const buttonClasses = (variant: NonNullable<ButtonProps['variant']> = 'primary', size: NonNullable<ButtonProps['size']> = 'md', className?: string) =>
  cn(baseClasses, sizeClasses[size], variantClasses[variant], className);


/** Shared edge/background/focus treatment for form controls. Edges use
 * --border-input (>= 3:1 against the surface). */
export const controlClasses =
  'w-full rounded-md border border-[var(--border-input)] bg-[var(--bg-surface)] text-[var(--text-primary)] text-sm placeholder:text-[var(--text-tertiary)] focus-ring focus-visible:border-[var(--border-focus)] disabled:cursor-not-allowed disabled:opacity-50 transition-shadow';
