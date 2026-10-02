import type { ReactNode } from 'react';
import { cn } from '../../utils/cn';
import { SkeletonCell, type SkeletonColumnKind } from './Skeleton';

/**
 * DataTable — the one dense, enterprise table. Replaces the per-page <table>
 * markup (and its drifting padding/header/hover/selection styles).
 *
 * It owns presentation only: selection state, sorting, filtering and data
 * fetching stay with the page. Responsive behavior is built in — at `md` and
 * above it renders a table; below, each row becomes a stacked card built from
 * the same column definitions, so no page re-implements a mobile layout.
 *
 * Mobile mapping (`Column.mobile`):
 *   'title'   → the card's headline (usually the identity column)
 *   'body'    → full-width content under the title, no label (long text)
 *   'detail'  → a "Label  value" line using the column header (default)
 *   'actions' → a trailing action row
 *   'hidden'  → omitted on mobile
 */
export interface Column<T> {
  id: string;
  header: ReactNode;
  cell: (row: T) => ReactNode;
  align?: 'left' | 'right' | 'center';
  /** Width/min-width utility classes for the <th>, e.g. 'w-40'. */
  className?: string;
  /** Hide this column in the table view below the given breakpoint. */
  hideBelow?: 'md' | 'lg' | 'xl';
  mobile?: 'title' | 'body' | 'detail' | 'actions' | 'hidden';
  /** Placeholder shape while loading. */
  skeleton?: SkeletonColumnKind;
}

type RowId = string | number;

export interface DataTableProps<T> {
  rows: T[];
  columns: Column<T>[];
  getRowId: (row: T) => RowId;
  'aria-label': string;
  onRowClick?: (row: T) => void;
  /** Controlled selection; omit to hide the checkbox column. */
  selection?: { selected: RowId[]; onChange: (ids: RowId[]) => void };
  /** Initial load (no rows yet): shows skeleton rows. */
  isLoading?: boolean;
  skeletonRows?: number;
  /** Rendered instead of the table when not loading and `rows` is empty. */
  empty?: ReactNode;
  /** Accessible name for a row's checkbox, e.g. the candidate's name. */
  rowLabel?: (row: T) => string;
  rowClassName?: (row: T) => string | undefined;
  /** Dim the table while a background refetch is in flight. */
  isRefreshing?: boolean;
  className?: string;
}

const HIDE = {
  md: 'hidden md:table-cell',
  lg: 'hidden lg:table-cell',
  xl: 'hidden xl:table-cell',
};
const ALIGN = { left: 'text-left', right: 'text-right', center: 'text-center' };

export function DataTable<T>({
  rows, columns, getRowId, onRowClick, selection, isLoading, skeletonRows = 8, empty, rowLabel, rowClassName, isRefreshing, className, ...rest
}: DataTableProps<T>) {
  const label = rest['aria-label'];

  if (!isLoading && rows.length === 0 && empty) {
    return <div className={cn('rounded-lg border border-[var(--border-light)] bg-[var(--bg-surface)]', className)}>{empty}</div>;
  }

  const selected = selection?.selected ?? [];
  const allSelected = rows.length > 0 && rows.every((r) => selected.includes(getRowId(r)));
  const someSelected = !allSelected && rows.some((r) => selected.includes(getRowId(r)));
  const toggleAll = () => selection?.onChange(allSelected ? [] : rows.map(getRowId));
  const toggleOne = (id: RowId) =>
    selection?.onChange(selected.includes(id) ? selected.filter((x) => x !== id) : [...selected, id]);

  const handleRowKey = (e: React.KeyboardEvent, row: T) => {
    // Only when the row itself has focus - not when Enter/Space targets a control inside it.
    if (e.target === e.currentTarget && (e.key === 'Enter' || e.key === ' ')) {
      e.preventDefault();
      onRowClick?.(row);
    }
  };

  const checkbox = (id: RowId | null, name: string) => (
    <input
      type="checkbox"
      aria-label={name}
      checked={id === null ? allSelected : selected.includes(id)}
      ref={id === null ? (el) => { if (el) el.indeterminate = someSelected; } : undefined}
      onChange={() => (id === null ? toggleAll() : toggleOne(id))}
      className="h-4 w-4 rounded"
    />
  );

  const titleCols = columns.filter((c) => c.mobile === 'title');
  const bodyCols = columns.filter((c) => c.mobile === 'body');
  const actionCols = columns.filter((c) => c.mobile === 'actions');
  const detailCols = columns.filter((c) => (c.mobile ?? 'detail') === 'detail');

  return (
    <div className={cn('overflow-hidden rounded-lg border border-[var(--border-light)] bg-[var(--bg-surface)]', className)}>
      {/* Table view (md+) */}
      <div className={cn('hidden overflow-x-auto md:block', isRefreshing && 'opacity-70 transition-opacity')}>
        <table className="w-full text-sm" aria-label={label} aria-busy={isLoading || isRefreshing || undefined}>
          <thead>
            <tr className="border-b border-[var(--border-light)] bg-[var(--bg-app)]">
              {selection && <th scope="col" className="w-10 px-4 py-2.5">{checkbox(null, 'Select all rows')}</th>}
              {columns.map((col) => (
                <th
                  key={col.id}
                  scope="col"
                  className={cn('text-eyebrow px-4 py-2.5 font-semibold', ALIGN[col.align ?? 'left'], col.hideBelow && HIDE[col.hideBelow], col.className)}
                >
                  {col.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--border-light)]">
            {isLoading
              ? Array.from({ length: skeletonRows }).map((_, i) => (
                  <tr key={i} aria-hidden="true">
                    {selection && <td className="px-4 py-3"><SkeletonCell kind="checkbox" /></td>}
                    {columns.map((col) => (
                      <td key={col.id} className={cn('px-4 py-3', col.hideBelow && HIDE[col.hideBelow])}>
                        <SkeletonCell kind={col.skeleton ?? 'text'} />
                      </td>
                    ))}
                  </tr>
                ))
              : rows.map((row) => {
                  const id = getRowId(row);
                  const isSelected = selected.includes(id);
                  return (
                    <tr
                      key={id}
                      aria-selected={selection ? isSelected : undefined}
                      tabIndex={onRowClick ? 0 : undefined}
                      onClick={onRowClick ? () => onRowClick(row) : undefined}
                      onKeyDown={onRowClick ? (e) => handleRowKey(e, row) : undefined}
                      className={cn(
                        'group transition-base',
                        onRowClick && 'cursor-pointer focus-visible:bg-[var(--bg-hover)] focus-visible:outline-none',
                        isSelected ? 'bg-[var(--color-primary-subtle-bg)]' : 'hover:bg-[var(--bg-hover)]',
                        rowClassName?.(row)
                      )}
                    >
                      {selection && (
                        <td className="px-4 py-3 align-top" onClick={(e) => e.stopPropagation()}>
                          {checkbox(id, `Select ${rowLabel?.(row) ?? 'row'}`)}
                        </td>
                      )}
                      {columns.map((col) => (
                        <td
                          key={col.id}
                          className={cn('px-4 py-3 align-top', ALIGN[col.align ?? 'left'], col.hideBelow && HIDE[col.hideBelow])}
                          onClick={col.mobile === 'actions' ? (e) => e.stopPropagation() : undefined}
                        >
                          {col.cell(row)}
                        </td>
                      ))}
                    </tr>
                  );
                })}
          </tbody>
        </table>
      </div>

      {/* Card view (< md) */}
      <ul className={cn('divide-y divide-[var(--border-light)] md:hidden', isRefreshing && 'opacity-70')} aria-label={label}>
        {isLoading
          ? Array.from({ length: Math.min(skeletonRows, 5) }).map((_, i) => (
              <li key={i} className="space-y-2 p-4" aria-hidden="true">
                <SkeletonCell kind="avatar" />
                <SkeletonCell kind="score" />
              </li>
            ))
          : rows.map((row) => {
              const id = getRowId(row);
              const isSelected = selected.includes(id);
              return (
                <li
                  key={id}
                  className={cn('flex gap-3 p-4', isSelected && 'bg-[var(--color-primary-subtle-bg)]', rowClassName?.(row))}
                >
                  {selection && <div className="pt-0.5">{checkbox(id, `Select ${rowLabel?.(row) ?? 'row'}`)}</div>}
                  <div className="min-w-0 flex-1 space-y-2.5">
                    <div
                      className={cn('space-y-1', onRowClick && 'cursor-pointer')}
                      role={onRowClick ? 'button' : undefined}
                      tabIndex={onRowClick ? 0 : undefined}
                      onClick={onRowClick ? () => onRowClick(row) : undefined}
                      onKeyDown={onRowClick ? (e) => handleRowKey(e, row) : undefined}
                    >
                      {titleCols.map((col) => <div key={col.id}>{col.cell(row)}</div>)}
                    </div>
                    {bodyCols.map((col) => <div key={col.id}>{col.cell(row)}</div>)}
                    {detailCols.length > 0 && (
                      <dl className="space-y-1.5">
                        {detailCols.map((col) => (
                          <div key={col.id} className="flex items-start justify-between gap-4">
                            <dt className="text-eyebrow shrink-0 pt-0.5">{col.header}</dt>
                            <dd className="min-w-0 text-right text-sm">{col.cell(row)}</dd>
                          </div>
                        ))}
                      </dl>
                    )}
                    {actionCols.length > 0 && (
                      <div className="flex flex-wrap items-center gap-1 border-t border-[var(--border-light)] pt-2.5">
                        {actionCols.map((col) => <div key={col.id}>{col.cell(row)}</div>)}
                      </div>
                    )}
                  </div>
                </li>
              );
            })}
      </ul>
    </div>
  );
}
