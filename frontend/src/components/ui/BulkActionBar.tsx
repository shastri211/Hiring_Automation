import type { ButtonHTMLAttributes, ReactNode } from 'react';
import { X } from 'lucide-react';
import { cn } from '../../utils/cn';

/**
 * BulkActionBar — the contextual bottom toolbar shown while rows are selected.
 * Floats over the content (so the table doesn't jump when it appears) and
 * renders nothing when `count` is 0. Put `BulkAction` buttons inside.
 *
 * It sits above page content but below dialogs/drawers (z-30 < z-50).
 */
interface BulkActionBarProps {
  count: number;
  /** Noun for the count, e.g. "candidate" → "3 candidates selected". */
  noun?: string;
  onClear: () => void;
  children: ReactNode;
  className?: string;
}

export const BulkActionBar = ({ count, noun = 'item', onClear, children, className }: BulkActionBarProps) => {
  if (count <= 0) return null;
  return (
    <div
      role="region"
      aria-label="Bulk actions"
      className={cn(
        'bulk-bar-in fixed inset-x-0 bottom-6 z-30 mx-auto flex w-fit max-w-[calc(100vw-1.5rem)] items-center gap-1 overflow-x-auto rounded-lg border border-[var(--border-strong)] bg-[var(--text-primary)] px-2 py-1.5 text-[var(--bg-surface)] shadow-[var(--shadow-lg)]',
        className
      )}
    >
      <span className="tabular whitespace-nowrap px-2 text-sm font-medium" aria-live="polite">
        {count} {noun}{count === 1 ? '' : 's'} selected
      </span>
      <span aria-hidden="true" className="mx-1 h-5 w-px shrink-0 bg-current opacity-25" />
      {children}
      <span aria-hidden="true" className="mx-1 h-5 w-px shrink-0 bg-current opacity-25" />
      <button
        type="button"
        onClick={onClear}
        aria-label="Clear selection"
        className="transition-base focus-ring shrink-0 rounded p-1.5 opacity-75 hover:bg-[var(--bg-surface)]/15 hover:opacity-100"
      >
        <X size={16} />
      </button>
    </div>
  );
};

/** A button on the (inverted) bulk bar. */
export const BulkAction = ({ className, ...props }: ButtonHTMLAttributes<HTMLButtonElement>) => (
  <button
    type="button"
    className={cn(
      'transition-base focus-ring inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded px-2.5 py-1.5 text-sm font-medium hover:bg-[var(--bg-surface)]/15 disabled:pointer-events-none disabled:opacity-50',
      className
    )}
    {...props}
  />
);
