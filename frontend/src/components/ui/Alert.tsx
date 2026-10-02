import type { HTMLAttributes, ReactNode } from 'react';
import { AlertTriangle, CheckCircle2, Info, XCircle } from 'lucide-react';
import { cn } from '../../utils/cn';

/**
 * Alert — the one inline banner. Replaces the hand-rolled red/amber boxes that
 * were copy-pasted across the auth pages and detail views (with hardcoded
 * light-mode colors). All colors come from the semantic subtle/border tokens,
 * so it is correct in dark mode.
 */
type AlertVariant = 'info' | 'success' | 'warning' | 'danger';

const STYLES: Record<AlertVariant, { box: string; icon: string; Icon: typeof Info }> = {
  info: {
    box: 'border-[var(--color-info-border)] bg-[var(--color-info-subtle-bg)] text-[var(--color-info-subtle-text)]',
    icon: 'text-[var(--color-info-icon)]',
    Icon: Info,
  },
  success: {
    box: 'border-[var(--color-success-border)] bg-[var(--color-success-subtle-bg)] text-[var(--color-success-subtle-text)]',
    icon: 'text-[var(--color-success-600)]',
    Icon: CheckCircle2,
  },
  warning: {
    box: 'border-[var(--color-warning-border)] bg-[var(--color-warning-subtle-bg)] text-[var(--color-warning-subtle-text)]',
    icon: 'text-[var(--color-warning-600)]',
    Icon: AlertTriangle,
  },
  danger: {
    box: 'border-[var(--color-danger-border)] bg-[var(--color-danger-subtle-bg)] text-[var(--color-danger-subtle-text)]',
    icon: 'text-[var(--color-danger-600)]',
    Icon: XCircle,
  },
};

export interface AlertProps extends Omit<HTMLAttributes<HTMLDivElement>, 'title'> {
  variant?: AlertVariant;
  title?: ReactNode;
  /** Right-aligned control (e.g. a Retry button). */
  action?: ReactNode;
  /** Override the default icon, or pass `null` for none. */
  icon?: ReactNode | null;
}

export const Alert = ({ variant = 'info', title, action, icon, className, children, ...props }: AlertProps) => {
  const { box, icon: iconClass, Icon } = STYLES[variant];
  return (
    <div
      role={variant === 'danger' ? 'alert' : 'status'}
      className={cn('flex items-start gap-3 rounded-md border px-3.5 py-3 text-sm', box, className)}
      {...props}
    >
      {icon !== null && (
        <span className={cn('mt-0.5 shrink-0', iconClass)} aria-hidden="true">
          {icon ?? <Icon size={16} />}
        </span>
      )}
      <div className="min-w-0 flex-1">
        {title && <p className="font-semibold">{title}</p>}
        {children && <div className={cn('leading-5', title && 'mt-0.5')}>{children}</div>}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
};
