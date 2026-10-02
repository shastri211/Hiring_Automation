import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from 'react';
import { cn } from '../../utils/cn';

/**
 * IconButton — a square, icon-only action (row actions, toolbars). `label` is
 * required: it becomes both the accessible name and the native tooltip, so an
 * icon button can never ship unlabeled. `active` renders the pressed/selected
 * state in the tone's color (e.g. the currently chosen decision).
 */
type Tone = 'default' | 'success' | 'warning' | 'danger' | 'primary';

const HOVER: Record<Tone, string> = {
  default: 'hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]',
  success: 'hover:bg-[var(--color-success-subtle-bg)] hover:text-[var(--color-success-subtle-text)]',
  warning: 'hover:bg-[var(--color-warning-subtle-bg)] hover:text-[var(--color-warning-subtle-text)]',
  danger: 'hover:bg-[var(--color-danger-subtle-bg)] hover:text-[var(--color-danger-subtle-text)]',
  primary: 'hover:bg-[var(--color-primary-subtle-bg)] hover:text-[var(--color-primary-subtle-text)]',
};
const ACTIVE: Record<Tone, string> = {
  default: 'bg-[var(--bg-hover)] text-[var(--text-primary)]',
  success: 'bg-[var(--color-success-subtle-bg)] text-[var(--color-success-subtle-text)]',
  warning: 'bg-[var(--color-warning-subtle-bg)] text-[var(--color-warning-subtle-text)]',
  danger: 'bg-[var(--color-danger-subtle-bg)] text-[var(--color-danger-subtle-text)]',
  primary: 'bg-[var(--color-primary-subtle-bg)] text-[var(--color-primary-subtle-text)]',
};

interface IconButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'children' | 'title'> {
  label: string;
  icon: ReactNode;
  tone?: Tone;
  active?: boolean;
}

export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(
  ({ label, icon, tone = 'default', active, className, type = 'button', ...props }, ref) => (
    <button
      ref={ref}
      type={type}
      aria-label={label}
      title={label}
      aria-pressed={active === undefined ? undefined : active}
      className={cn(
        'transition-base focus-ring inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md disabled:pointer-events-none disabled:opacity-40',
        active ? ACTIVE[tone] : cn('text-[var(--text-tertiary)]', HOVER[tone]),
        className
      )}
      {...props}
    >
      {icon}
    </button>
  )
);
IconButton.displayName = 'IconButton';
