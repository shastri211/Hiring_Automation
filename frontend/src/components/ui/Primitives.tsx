import React, { forwardRef } from 'react';
import { cn } from '../../utils/cn';
import { controlClasses } from './styles';

// -----------------------------------------------------------------------------
// Card — a bordered surface. Flat by design: structure comes from the 1px
// border, not a shadow. Prefer plain sections with rules for long-form content
// (see Candidate 360); reach for Card only for genuinely discrete panels.
// -----------------------------------------------------------------------------
export const Card = forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn('bg-[var(--bg-surface)] border border-[var(--border-light)] rounded-lg overflow-hidden', className)} {...props} />
  )
);
Card.displayName = 'Card';

export const CardHeader = forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn('px-5 py-4 border-b border-[var(--border-light)] flex flex-col gap-1', className)} {...props} />
  )
);
CardHeader.displayName = 'CardHeader';

export const CardTitle = forwardRef<HTMLHeadingElement, React.HTMLAttributes<HTMLHeadingElement>>(
  ({ className, ...props }, ref) => (
    <h3 ref={ref} className={cn('text-card-title', className)} {...props} />
  )
);
CardTitle.displayName = 'CardTitle';

export const CardContent = forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn('p-5', className)} {...props} />
  )
);
CardContent.displayName = 'CardContent';

export const CardFooter = forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn('px-5 py-3 bg-[var(--bg-app)] border-t border-[var(--border-light)] flex items-center', className)} {...props} />
  )
);
CardFooter.displayName = 'CardFooter';

// -----------------------------------------------------------------------------
// Badge — a compact label. Square-ish (not a pill). For a state that reads as a
// status (with a leading dot) use StatusDot instead.
// -----------------------------------------------------------------------------
export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: 'neutral' | 'success' | 'warning' | 'danger' | 'primary';
}
export const Badge = forwardRef<HTMLSpanElement, BadgeProps>(
  ({ className, variant = 'neutral', ...props }, ref) => {
    const variantClasses = {
      neutral: 'bg-[var(--color-neutral-subtle-bg)] text-[var(--color-neutral-subtle-text)]',
      success: 'bg-[var(--color-success-subtle-bg)] text-[var(--color-success-subtle-text)]',
      warning: 'bg-[var(--color-warning-subtle-bg)] text-[var(--color-warning-subtle-text)]',
      danger: 'bg-[var(--color-danger-subtle-bg)] text-[var(--color-danger-subtle-text)]',
      primary: 'bg-[var(--color-primary-subtle-bg)] text-[var(--color-primary-subtle-text)]',
    };
    return (
      <span
        ref={ref}
        className={cn('inline-flex items-center px-2 py-0.5 rounded text-xs font-medium whitespace-nowrap', variantClasses[variant], className)}
        {...props}
      />
    );
  }
);
Badge.displayName = 'Badge';

// -----------------------------------------------------------------------------
// Form elements — control edges use --border-input (>= 3:1 against the surface).
// -----------------------------------------------------------------------------
export const Input = forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input ref={ref} className={cn('flex h-9 px-3 py-2', controlClasses, className)} {...props} />
  )
);
Input.displayName = 'Input';

export const Textarea = forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(
  ({ className, ...props }, ref) => (
    <textarea ref={ref} className={cn('flex min-h-[80px] px-3 py-2', controlClasses, className)} {...props} />
  )
);
Textarea.displayName = 'Textarea';

/** Native <select> with the shared control styling — the right choice for
 * compact toolbar filters (full keyboard/mobile support for free). */
export const NativeSelect = forwardRef<HTMLSelectElement, React.SelectHTMLAttributes<HTMLSelectElement>>(
  ({ className, ...props }, ref) => (
    <select ref={ref} className={cn('h-9 pl-3 pr-8 py-0 cursor-pointer', controlClasses, 'w-auto', className)} {...props} />
  )
);
NativeSelect.displayName = 'NativeSelect';

export const Label = forwardRef<HTMLLabelElement, React.LabelHTMLAttributes<HTMLLabelElement>>(
  ({ className, ...props }, ref) => (
    <label ref={ref} className={cn('text-sm font-medium leading-none text-[var(--text-secondary)] peer-disabled:cursor-not-allowed peer-disabled:opacity-70', className)} {...props} />
  )
);
Label.displayName = 'Label';

// -----------------------------------------------------------------------------
// Utilities
// -----------------------------------------------------------------------------
export const Skeleton = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn('animate-pulse rounded bg-[var(--bg-hover)]', className)} {...props} />
);

export const Spinner = ({ className, size = 24 }: { className?: string, size?: number }) => (
  <svg role="status" aria-label="Loading" className={cn('animate-spin text-[var(--text-tertiary)]', className)} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="12" y1="2" x2="12" y2="6"></line>
    <line x1="12" y1="18" x2="12" y2="22"></line>
    <line x1="4.93" y1="4.93" x2="7.76" y2="7.76"></line>
    <line x1="16.24" y1="16.24" x2="19.07" y2="19.07"></line>
    <line x1="2" y1="12" x2="6" y2="12"></line>
    <line x1="18" y1="12" x2="22" y2="12"></line>
    <line x1="4.93" y1="19.07" x2="7.76" y2="16.24"></line>
    <line x1="16.24" y1="7.76" x2="19.07" y2="4.93"></line>
  </svg>
);

export const EmptyState = ({ icon, title, description, action, className }: { icon?: React.ReactNode, title: string, description?: string, action?: React.ReactNode, className?: string }) => (
  <div className={cn('flex flex-col items-center justify-center py-16 px-4 text-center', className)}>
    {icon && <div className="mb-4 text-[var(--text-tertiary)] border border-[var(--border-light)] bg-[var(--bg-surface)] p-3 rounded-lg">{icon}</div>}
    <h3 className="text-card-title mb-1">{title}</h3>
    {description && <p className="text-body mb-5 max-w-sm">{description}</p>}
    {action && <div>{action}</div>}
  </div>
);
