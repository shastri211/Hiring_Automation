import { ChevronLeft, ChevronRight } from 'lucide-react';
import { cn } from '../../utils/cn';

/**
 * Pagination — "Showing 1–20 of 135" plus prev/next. Page-number based; the
 * caller owns `page` (1-indexed). Renders nothing when there are no rows.
 */
interface PaginationProps {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
  className?: string;
}

export const Pagination = ({ page, pageSize, total, onPageChange, className }: PaginationProps) => {
  if (total <= 0) return null;
  const from = (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, total);
  const pageCount = Math.max(1, Math.ceil(total / pageSize));
  const btn =
    'transition-base focus-ring rounded p-1.5 text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)] disabled:pointer-events-none disabled:opacity-40';

  return (
    <nav aria-label="Pagination" className={cn('flex items-center justify-between gap-4 text-sm text-[var(--text-secondary)]', className)}>
      <span className="tabular">
        Showing {from}–{to} of {total}
      </span>
      <div className="flex items-center gap-1">
        <span className="tabular mr-2 hidden sm:inline">Page {page} of {pageCount}</span>
        <button type="button" className={btn} disabled={page <= 1} onClick={() => onPageChange(page - 1)} aria-label="Previous page">
          <ChevronLeft size={16} />
        </button>
        <button type="button" className={btn} disabled={page >= pageCount} onClick={() => onPageChange(page + 1)} aria-label="Next page">
          <ChevronRight size={16} />
        </button>
      </div>
    </nav>
  );
};
