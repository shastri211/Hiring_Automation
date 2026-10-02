import type { ReactNode } from 'react';
import { CardHeader, CardTitle } from './Primitives';
import { ErrorState } from './States';
import { Skeleton } from './Primitives';

/** Header row for a bordered dashboard/analytics panel: title left, optional action right. */
export const PanelHeader = ({ title, action }: { title: string; action?: ReactNode }) => (
  <CardHeader className="flex-row items-center justify-between gap-3 py-3">
    <CardTitle className="text-sm">{title}</CardTitle>
    {action}
  </CardHeader>
);

/**
 * The loading / error / empty / content switch every panel needs, so no panel
 * can forget one of the four states.
 */
export const PanelBody = ({
  isLoading, isError, onRetry, isEmpty, empty, rows = 3, children,
}: {
  isLoading: boolean;
  isError: boolean;
  onRetry: () => void;
  isEmpty: boolean;
  empty: ReactNode;
  rows?: number;
  children: ReactNode;
}) => {
  if (isLoading) {
    return (
      <div className="space-y-3 p-5" aria-hidden="true">
        {Array.from({ length: rows }).map((_, i) => <Skeleton key={i} className="h-5 w-full" />)}
      </div>
    );
  }
  if (isError) return <ErrorState className="py-10" title="Couldn't load this" onRetry={onRetry} />;
  if (isEmpty) return <>{empty}</>;
  return <>{children}</>;
};
