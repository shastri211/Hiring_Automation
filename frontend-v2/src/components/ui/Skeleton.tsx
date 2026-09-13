import { Skeleton } from './Primitives';

/**
 * Content-shaped loading placeholders, replacing bare spinners on page-load
 * states (JobsList, JobCandidates, Shortlisted). Spinners stay for
 * short-lived button-pending states elsewhere — this is specifically about
 * the moment a page's main content is first loading.
 */

/** Mirrors a JobCard: checkbox+title row, badge row, description lines, footer. */
export const SkeletonCard = () => (
  <div
    className="flex h-full flex-col gap-4 rounded-xl border border-[var(--border-light)] bg-[var(--bg-surface)] p-6"
    style={{ boxShadow: 'var(--shadow-sm)' }}
    aria-hidden="true"
  >
    <div className="flex items-start justify-between gap-2">
      <Skeleton className="h-5 w-2/3" />
      <Skeleton className="h-5 w-5 shrink-0 rounded" />
    </div>
    <div className="flex flex-wrap gap-2">
      <Skeleton className="h-5 w-16 rounded-full" />
      <Skeleton className="h-5 w-20 rounded-full" />
    </div>
    <div className="flex-1 space-y-2">
      <Skeleton className="h-3.5 w-full" />
      <Skeleton className="h-3.5 w-full" />
      <Skeleton className="h-3.5 w-3/4" />
    </div>
    <div className="flex items-center justify-between gap-2 border-t border-[var(--border-light)] pt-4">
      <Skeleton className="h-6 w-16 rounded" />
      <Skeleton className="h-8 w-28 rounded-md" />
    </div>
  </div>
);

/**
 * A single table row shaped from column "kinds" so callers can describe the
 * real table's shape (`['avatar', 'score', 'text', 'actions']`) instead of
 * every page inventing its own row skeleton.
 */
export type SkeletonColumnKind = 'avatar' | 'score' | 'text' | 'actions' | 'checkbox';

const SkeletonCell = ({ kind }: { kind: SkeletonColumnKind }) => {
  switch (kind) {
    case 'checkbox':
      return <Skeleton className="h-4 w-4 rounded" />;
    case 'avatar':
      return (
        <div className="flex items-center gap-3">
          <Skeleton className="h-10 w-10 shrink-0 rounded-full" />
          <div className="flex flex-col gap-1.5">
            <Skeleton className="h-4 w-32" />
            <Skeleton className="h-3 w-20" />
          </div>
        </div>
      );
    case 'score':
      return (
        <div className="flex items-center gap-2">
          <Skeleton className="h-10 w-10 shrink-0 rounded-full" />
          <Skeleton className="h-3 w-14" />
        </div>
      );
    case 'actions':
      return (
        <div className="flex justify-end gap-2">
          <Skeleton className="h-7 w-7 rounded-full" />
          <Skeleton className="h-7 w-7 rounded-full" />
          <Skeleton className="h-7 w-7 rounded-full" />
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
      <td key={i} className="px-6 py-4">
        <SkeletonCell kind={kind} />
      </td>
    ))}
  </tr>
);
