import type { ReactNode } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import { cn } from '../../utils/cn';
import { Button } from './Button';
import { Spinner } from './Primitives';

/** Centered spinner for a section whose content has no better-shaped skeleton. */
export const LoadingState = ({ label = 'Loading…', className }: { label?: string; className?: string }) => (
  <div className={cn('flex flex-col items-center justify-center gap-3 py-16 text-[var(--text-tertiary)]', className)}>
    <Spinner size={24} />
    <p className="text-caption">{label}</p>
  </div>
);

/**
 * ErrorState — a failed fetch. Always offers a retry when one is available, and
 * surfaces the real error message rather than a generic one.
 */
export const ErrorState = ({
  title = 'Something went wrong',
  message,
  onRetry,
  action,
  className,
}: {
  title?: string;
  message?: ReactNode;
  onRetry?: () => void;
  action?: ReactNode;
  className?: string;
}) => (
  <div role="alert" className={cn('flex flex-col items-center justify-center px-4 py-16 text-center', className)}>
    <div className="mb-4 rounded-lg border border-[var(--color-danger-border)] bg-[var(--color-danger-subtle-bg)] p-3 text-[var(--color-danger-600)]">
      <AlertTriangle size={20} aria-hidden="true" />
    </div>
    <h3 className="text-card-title mb-1">{title}</h3>
    {message && <p className="text-body mb-5 max-w-sm">{message}</p>}
    <div className="flex items-center gap-2">
      {onRetry && (
        <Button variant="secondary" onClick={onRetry}>
          <RefreshCw size={14} aria-hidden="true" /> Retry
        </Button>
      )}
      {action}
    </div>
  </div>
);
