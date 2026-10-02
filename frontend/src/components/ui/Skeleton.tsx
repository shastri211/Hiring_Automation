import { Skeleton } from './Primitives';

/**
 * Content-shaped loading placeholders, replacing bare spinners on page-load
 * states. Spinners stay for short-lived button-pending states — this is
 * specifically about the moment a page's main content is first loading.
 */

/** Mirrors a bordered list card: title row, tags, description lines, footer. */
export const SkeletonCard = () => (
  <div
    className="flex h-full flex-col gap-4 rounded-lg border border-[var(--border-light)] bg-[var(--bg-surface)] p-5"
    aria-hidden="true"
  >
    <div className="flex items-start justify-between gap-2">
      <Skeleton className="h-5 w-2/3" />
      <Skeleton className="h-5 w-5 shrink-0 rounded" />
    </div>
    <div className="flex flex-wrap gap-2">
      <Skeleton className="h-5 w-16" />
      <Skeleton className="h-5 w-20" />
    </div>
    <div className="flex-1 space-y-2">
      <Skeleton className="h-3.5 w-full" />
      <Skeleton className="h-3.5 w-full" />
      <Skeleton className="h-3.5 w-3/4" />
    </div>
  </div>
);

/**
 * Cell skeletons are shaped from column "kinds" so callers describe the real
 * table's shape (`['avatar', 'score', 'text', 'actions']`) instead of every
 * page inventing its own row skeleton.
 */
export type SkeletonColumnKind = 'avatar' | 'score' | 'text' | 'actions' | 'checkbox' | 'badge';

export const SkeletonCell = ({ kind }: { kind: SkeletonColumnKind }) => {
  switch (kind) {
    case 'checkbox':
      return <Skeleton className="h-4 w-4 rounded" />;
    case 'avatar':
      return (
        <div className="flex items-center gap-3">
          <Skeleton className="h-8 w-8 shrink-0 rounded-full" />
          <div className="flex flex-col gap-1.5">
            <Skeleton className="h-4 w-32" />
            <Skeleton className="h-3 w-20" />
          </div>
        </div>
      );
    case 'score':
      return (
        <div className="flex items-center gap-2">
          <Skeleton className="h-5 w-8" />
          <Skeleton className="h-1.5 w-16 rounded-full" />
        </div>
      );
    case 'badge':
      return <Skeleton className="h-5 w-20" />;
    case 'actions':
      return (
        <div className="flex justify-end gap-2">
          <Skeleton className="h-7 w-7" />
          <Skeleton className="h-7 w-7" />
          <Skeleton className="h-7 w-7" />
        </div>
      );
    case 'text':
    default:
      return <Skeleton className="h-4 w-full max-w-[180px]" />;
  }
};

export const SkeletonRow = ({ columns }: { columns: SkeletonColumnKind[] }) => (
  <tr aria-hidden="true">
    {columns.map((kind, i) => (
      <td key={i} className="px-4 py-3">
        <SkeletonCell kind={kind} />
      </td>
    ))}
  </tr>
);
